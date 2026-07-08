#!/usr/bin/env python3
"""Neo4j-backed graph API for the Thebenpaul lakehouse product graph."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover - exercised in minimal local envs.
    GraphDatabase = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("graph-layer")


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = Path(os.environ.get("THEBEN_GRAPH_DATA_DIR", str(ROOT / "data")))
DEFAULT_PRODUCTS_PATH = Path(
    os.environ.get("THEBEN_PRODUCT_EXPORT_PATH", str(DATA_DIR / "sample_products.json"))
)

JSON = "application/json; charset=utf-8"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "unknown"


def product_number(product: dict[str, Any]) -> str:
    """Return the canonical graph root classifier for a product."""
    for key in ("article_number", "sku", "product_number", "id"):
        value = product.get(key)
        if value:
            return str(value).strip()
    raise ValueError("product is missing article_number/sku/product_number")


@dataclass(frozen=True)
class GraphNode:
    label: str
    key: str
    properties: dict[str, Any]


@dataclass(frozen=True)
class GraphRelationship:
    start_label: str
    start_key: str
    rel_type: str
    end_label: str
    end_key: str
    properties: dict[str, Any]


@dataclass(frozen=True)
class GraphDocument:
    product_number: str
    nodes: list[GraphNode]
    relationships: list[GraphRelationship]


def load_runtime_config() -> dict[str, Any]:
    path = Path(os.environ.get("THEBEN_GRAPH_CONFIG", str(CONFIG_DIR / "runtime.json")))
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def flatten_products(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        products = payload
    else:
        products = payload.get("products", [])
    return [p for p in products if isinstance(p, dict)]


def build_product_graph(product: dict[str, Any]) -> GraphDocument:
    number = product_number(product)
    now = utc_now()
    nodes = [
        GraphNode(
            label="Product",
            key=number,
            properties={
                "product_number": number,
                "sku": str(product.get("sku") or number),
                "name": product.get("name") or number,
                "family": product.get("family") or "Unassigned",
                "lifecycle_status": product.get("lifecycle_status") or "unknown",
                "updated_at": product.get("updated_at") or now,
                "root_classifier": "product_number",
            },
        )
    ]
    relationships: list[GraphRelationship] = []

    family = product.get("family")
    if family:
        family_key = slug(family)
        nodes.append(GraphNode("ProductFamily", family_key, {"family_id": family_key, "name": family}))
        relationships.append(
            GraphRelationship("Product", number, "BELONGS_TO_FAMILY", "ProductFamily", family_key, {})
        )

    for cert in product.get("certifications") or []:
        cert_key = slug(cert)
        nodes.append(GraphNode("Certification", cert_key, {"certification_id": cert_key, "name": str(cert)}))
        relationships.append(
            GraphRelationship("Product", number, "HAS_CERTIFICATION", "Certification", cert_key, {})
        )

    for index, document in enumerate(product.get("documents") or []):
        if not isinstance(document, dict):
            continue
        doc_key = str(document.get("source_uri") or document.get("name") or f"{number}-document-{index}")
        nodes.append(
            GraphNode(
                "SourceDocument",
                doc_key,
                {
                    "document_id": doc_key,
                    "name": document.get("name") or doc_key,
                    "type": document.get("type") or "unknown",
                    "source_uri": document.get("source_uri") or doc_key,
                },
            )
        )
        relationships.append(
            GraphRelationship("Product", number, "SUPPORTED_BY", "SourceDocument", doc_key, {"rank": index})
        )

    metadata = product.get("metadata") or {}
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if value in (None, ""):
                continue
            meta_key = f"{number}:metadata:{key}"
            nodes.append(
                GraphNode(
                    "MetadataField",
                    meta_key,
                    {"field_id": meta_key, "name": key, "value": str(value), "scope": "product"},
                )
            )
            relationships.append(
                GraphRelationship("Product", number, "HAS_METADATA", "MetadataField", meta_key, {})
            )

    attributes = product.get("attributes") or {}
    if isinstance(attributes, dict):
        for key, value in attributes.items():
            if value in (None, ""):
                continue
            attr_key = f"{number}:attribute:{key}"
            nodes.append(
                GraphNode(
                    "ProductAttribute",
                    attr_key,
                    {
                        "attribute_id": attr_key,
                        "name": key,
                        "value": json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value),
                    },
                )
            )
            relationships.append(
                GraphRelationship("Product", number, "HAS_ATTRIBUTE", "ProductAttribute", attr_key, {})
            )

        gtin = attributes.get("gtin")
        batch = attributes.get("batch_lot_number") or attributes.get("batch_number") or attributes.get("lot_number")
        serial = attributes.get("serial_number")
        if gtin:
            gtin_key = str(gtin)
            nodes.append(GraphNode("GTIN", gtin_key, {"gtin": gtin_key}))
            relationships.append(GraphRelationship("Product", number, "HAS_GTIN", "GTIN", gtin_key, {}))
        if batch and gtin:
            batch_key = f"{gtin}:{batch}"
            nodes.append(GraphNode("Batch", batch_key, {"batch_id": batch_key, "batch_lot_number": str(batch)}))
            relationships.append(GraphRelationship("GTIN", str(gtin), "HAS_BATCH", "Batch", batch_key, {}))
            relationships.append(GraphRelationship("Product", number, "HAS_BATCH", "Batch", batch_key, {}))
        if serial and gtin:
            instance_key = f"{gtin}:{serial}"
            nodes.append(
                GraphNode(
                    "ProductInstance",
                    instance_key,
                    {"instance_id": instance_key, "gtin": str(gtin), "serial_number": str(serial)},
                )
            )
            relationships.append(
                GraphRelationship("Product", number, "HAS_INSTANCE", "ProductInstance", instance_key, {})
            )
            relationships.append(GraphRelationship("GTIN", str(gtin), "IDENTIFIES", "ProductInstance", instance_key, {}))
            if batch:
                relationships.append(
                    GraphRelationship("Batch", f"{gtin}:{batch}", "CONTAINS_INSTANCE", "ProductInstance", instance_key, {})
                )

    return GraphDocument(product_number=number, nodes=dedupe_nodes(nodes), relationships=dedupe_relationships(relationships))


def dedupe_nodes(nodes: list[GraphNode]) -> list[GraphNode]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []
    for node in nodes:
        identity = (node.label, node.key)
        if identity not in merged:
            merged[identity] = {}
            order.append(identity)
        merged[identity].update({k: v for k, v in node.properties.items() if v is not None})
    return [GraphNode(label, key, merged[(label, key)]) for label, key in order]


def dedupe_relationships(relationships: list[GraphRelationship]) -> list[GraphRelationship]:
    seen: set[tuple[str, str, str, str, str]] = set()
    result: list[GraphRelationship] = []
    for rel in relationships:
        identity = (rel.start_label, rel.start_key, rel.rel_type, rel.end_label, rel.end_key)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(rel)
    return result


class Neo4jRepository:
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j") -> None:
        if GraphDatabase is None:
            raise RuntimeError("neo4j Python driver is not installed")
        self.database = database
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self) -> None:
        self.driver.close()

    def ping(self) -> bool:
        self.driver.verify_connectivity()
        return True

    def setup_constraints(self) -> None:
        statements = [
            "CREATE CONSTRAINT product_number IF NOT EXISTS FOR (n:Product) REQUIRE n.product_number IS UNIQUE",
            "CREATE CONSTRAINT family_id IF NOT EXISTS FOR (n:ProductFamily) REQUIRE n.family_id IS UNIQUE",
            "CREATE CONSTRAINT certification_id IF NOT EXISTS FOR (n:Certification) REQUIRE n.certification_id IS UNIQUE",
            "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:SourceDocument) REQUIRE n.document_id IS UNIQUE",
            "CREATE CONSTRAINT attribute_id IF NOT EXISTS FOR (n:ProductAttribute) REQUIRE n.attribute_id IS UNIQUE",
            "CREATE CONSTRAINT metadata_field_id IF NOT EXISTS FOR (n:MetadataField) REQUIRE n.field_id IS UNIQUE",
            "CREATE CONSTRAINT gtin IF NOT EXISTS FOR (n:GTIN) REQUIRE n.gtin IS UNIQUE",
            "CREATE CONSTRAINT batch_id IF NOT EXISTS FOR (n:Batch) REQUIRE n.batch_id IS UNIQUE",
            "CREATE CONSTRAINT instance_id IF NOT EXISTS FOR (n:ProductInstance) REQUIRE n.instance_id IS UNIQUE",
        ]
        with self.driver.session(database=self.database) as session:
            for statement in statements:
                session.run(statement)

    def upsert_document(self, document: GraphDocument) -> None:
        with self.driver.session(database=self.database) as session:
            for node in document.nodes:
                session.run(node_merge_cypher(node.label), key=node.key, props=node.properties)
            for rel in document.relationships:
                session.run(
                    relationship_merge_cypher(rel),
                    start_key=rel.start_key,
                    end_key=rel.end_key,
                    props=rel.properties,
                )

    def upsert_products(self, products: list[dict[str, Any]]) -> dict[str, Any]:
        self.setup_constraints()
        synced = []
        for product in products:
            document = build_product_graph(product)
            self.upsert_document(document)
            synced.append(document.product_number)
        return {"status": "ok", "synced": len(synced), "product_numbers": synced}

    def list_products(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (p:Product)
                RETURN p.product_number AS product_number, p.sku AS sku, p.name AS name,
                       p.family AS family, p.lifecycle_status AS lifecycle_status
                ORDER BY p.product_number
                LIMIT $limit
                """,
                limit=limit,
            )
            return [dict(record) for record in result]

    def product_neighborhood(self, number: str, limit: int = 200) -> dict[str, Any]:
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (p:Product {product_number: $number})
                OPTIONAL MATCH path=(p)-[r]-(n)
                RETURN p AS product, collect({type: type(r), node: n})[0..$limit] AS neighborhood
                """,
                number=number,
                limit=limit,
            )
            record = result.single()
            if not record:
                return {"product_number": number, "nodes": [], "relationships": []}
            nodes = [{"labels": list(item["node"].labels), "properties": dict(item["node"])} for item in record["neighborhood"] if item["node"]]
            return {
                "product_number": number,
                "product": dict(record["product"]),
                "neighbors": nodes,
            }


def node_merge_cypher(label: str) -> str:
    identity_property = {
        "Product": "product_number",
        "ProductFamily": "family_id",
        "Certification": "certification_id",
        "SourceDocument": "document_id",
        "ProductAttribute": "attribute_id",
        "MetadataField": "field_id",
        "GTIN": "gtin",
        "Batch": "batch_id",
        "ProductInstance": "instance_id",
    }[label]
    return f"MERGE (n:{label} {{{identity_property}: $key}}) SET n += $props"


def relationship_merge_cypher(rel: GraphRelationship) -> str:
    start_identity = node_identity_property(rel.start_label)
    end_identity = node_identity_property(rel.end_label)
    return (
        f"MATCH (a:{rel.start_label} {{{start_identity}: $start_key}}) "
        f"MATCH (b:{rel.end_label} {{{end_identity}: $end_key}}) "
        f"MERGE (a)-[r:{rel.rel_type}]->(b) SET r += $props"
    )


def node_identity_property(label: str) -> str:
    return {
        "Product": "product_number",
        "ProductFamily": "family_id",
        "Certification": "certification_id",
        "SourceDocument": "document_id",
        "ProductAttribute": "attribute_id",
        "MetadataField": "field_id",
        "GTIN": "gtin",
        "Batch": "batch_id",
        "ProductInstance": "instance_id",
    }[label]


class GraphLayerHandler(BaseHTTPRequestHandler):
    repository: Neo4jRepository | None = None
    config: dict[str, Any] = {}

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s - %s", self.client_address[0], format % args)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/health":
                self.send_json({"status": "ok", "service": "graph-layer", "neo4j": self.neo4j_status()})
            elif path == "/api/graph/schema":
                self.send_json(graph_schema())
            elif path == "/api/graph/products":
                self.require_repository()
                self.send_json({"products": self.repository.list_products()})
            elif path.startswith("/api/graph/products/"):
                self.require_repository()
                number = unquote(path.rsplit("/", 1)[-1])
                self.send_json(self.repository.product_neighborhood(number))
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            logger.exception("GET failed: %s", exc)
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/api/graph/sync":
                self.require_repository()
                payload = self.read_json()
                products = flatten_products(payload)
                self.send_json(self.repository.upsert_products(products), HTTPStatus.CREATED)
            elif path == "/api/graph/sync/from-file":
                self.require_repository()
                payload = self.read_json(optional=True)
                source = Path(payload.get("path") or str(DEFAULT_PRODUCTS_PATH))
                self.send_json(sync_from_file(self.repository, source), HTTPStatus.CREATED)
            elif path == "/api/graph/sync/from-url":
                self.require_repository()
                payload = self.read_json()
                source_url = payload.get("url") or self.config.get("data_layer_export_url")
                if not source_url:
                    raise ValueError("url is required")
                self.send_json(sync_from_url(self.repository, source_url), HTTPStatus.CREATED)
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            logger.exception("POST failed: %s", exc)
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def read_json(self, optional: bool = False) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {} if optional else {}
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8"))

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", JSON)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def require_repository(self) -> None:
        if self.repository is None:
            raise RuntimeError("Neo4j repository is not configured")

    def neo4j_status(self) -> str:
        if self.repository is None:
            return "not_configured"
        try:
            self.repository.ping()
            return "connected"
        except Exception as exc:
            return f"unavailable: {exc}"


def graph_schema() -> dict[str, Any]:
    return {
        "root_classifier": "product_number",
        "root_node": "Product",
        "node_labels": [
            "Product",
            "ProductFamily",
            "GTIN",
            "Batch",
            "ProductInstance",
            "ProductAttribute",
            "Certification",
            "SourceDocument",
            "MetadataField",
        ],
        "relationship_types": [
            "BELONGS_TO_FAMILY",
            "HAS_GTIN",
            "HAS_BATCH",
            "HAS_INSTANCE",
            "HAS_ATTRIBUTE",
            "HAS_CERTIFICATION",
            "SUPPORTED_BY",
            "HAS_METADATA",
            "IDENTIFIES",
            "CONTAINS_INSTANCE",
        ],
    }


def load_products_file(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return flatten_products(payload)


def sync_from_file(repository: Neo4jRepository, path: Path) -> dict[str, Any]:
    products = load_products_file(path)
    result = repository.upsert_products(products)
    result["source"] = str(path)
    return result


def sync_from_url(repository: Neo4jRepository, source_url: str) -> dict[str, Any]:
    request = Request(source_url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=float(os.environ.get("THEBEN_GRAPH_HTTP_TIMEOUT", "10"))) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"{source_url} returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"{source_url} is not reachable: {exc.reason}") from exc
    products = flatten_products(payload)
    result = repository.upsert_products(products)
    result["source"] = source_url
    return result


def make_repository(config: dict[str, Any]) -> Neo4jRepository | None:
    enabled = os.environ.get("THEBEN_GRAPH_NEO4J_ENABLED", str(config.get("neo4j_enabled", True))).lower()
    if enabled in {"0", "false", "no"}:
        return None
    uri = os.environ.get("NEO4J_URI", config.get("neo4j_uri", "bolt://localhost:7687"))
    username = os.environ.get("NEO4J_USERNAME", config.get("neo4j_username", "neo4j"))
    password = os.environ.get("NEO4J_PASSWORD", config.get("neo4j_password", "thebenpaul"))
    database = os.environ.get("NEO4J_DATABASE", config.get("neo4j_database", "neo4j"))
    return Neo4jRepository(uri=uri, username=username, password=password, database=database)


def wait_for_repository(repository: Neo4jRepository | None, attempts: int = 30) -> None:
    if repository is None:
        return
    for attempt in range(1, attempts + 1):
        try:
            repository.ping()
            return
        except Exception as exc:
            if attempt == attempts:
                raise
            logger.info("Neo4j not ready yet (%s/%s): %s", attempt, attempts, exc)
            time.sleep(2)


def run_server(host: str, port: int) -> None:
    config = load_runtime_config()
    repository = make_repository(config)
    wait_for_repository(repository)
    GraphLayerHandler.repository = repository
    GraphLayerHandler.config = config
    server = ThreadingHTTPServer((host, port), GraphLayerHandler)
    logger.info("graph-layer listening on http://%s:%s", host, port)
    try:
        server.serve_forever()
    finally:
        if repository:
            repository.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Thebenpaul graph layer API")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8096")))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
