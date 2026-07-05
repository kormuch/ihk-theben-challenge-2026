"""
Write product data to Apache Iceberg tables via Trino.

Non-blocking: if Trino is unreachable, logs a warning and returns.
PostgreSQL remains the primary datastore — Iceberg is the lakehouse mirror.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import trino

log = logging.getLogger("paul.iceberg")


def _get_connection():
    return trino.dbapi.connect(
        host=os.getenv("TRINO_HOST", "trino"),
        port=int(os.getenv("TRINO_PORT", "8080")),
        user="paul-backend",
        catalog=os.getenv("TRINO_CATALOG", "iceberg"),
        schema=os.getenv("TRINO_SCHEMA", "products"),
    )


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


def _esc(value) -> str:
    """Escape a value for Trino SQL. Strings get single-quoted with '' escaping."""
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value).replace("'", "''")
    return f"'{s}'"


def write_product_to_iceberg(
    article_number: str,
    product_name: str,
    family: str,
    attributes: dict,
    certifications: list[str],
    owner: str = "Product Data Domain",
    source_system: str = "paul-data-layer",
) -> bool:
    """Insert or update a product in the Iceberg product_master table.
    Returns True on success, False on failure (non-blocking)."""
    try:
        conn = _get_connection()
        cur = conn.cursor()

        # Delete existing row for this article_number (Iceberg supports row-level deletes)
        cur.execute(f"DELETE FROM product_master WHERE article_number = {_esc(article_number)}")

        now = _now_ts()
        attrs_json = json.dumps(attributes, default=str)
        certs_str = ", ".join(certifications) if certifications else ""

        cur.execute(f"""INSERT INTO product_master (
                article_number, product_name, family,
                nominal_voltage, ip_rating, certifications,
                attributes, source_system, lineage, owner,
                classification, created_at, updated_at, ingested_at
            ) VALUES (
                {_esc(article_number)}, {_esc(product_name)}, {_esc(family)},
                {_esc(attributes.get('nominal_voltage', ''))},
                {_esc(attributes.get('ip_rating', ''))},
                {_esc(certs_str)},
                {_esc(attrs_json)},
                {_esc(source_system)},
                {_esc('paul-ai-ingest -> data-layer-postgres -> iceberg-product_master')},
                {_esc(owner)},
                {_esc('internal')},
                TIMESTAMP {_esc(now)},
                TIMESTAMP {_esc(now)},
                TIMESTAMP {_esc(now)}
            )""")
        log.info("ICEBERG OK: wrote product %s to product_master", article_number)
        return True
    except Exception as exc:
        log.warning("ICEBERG SKIP: could not write product %s — %s", article_number, exc)
        return False


def write_document_lineage(
    document_id: str,
    product_article_number: str,
    original_filename: str,
    doc_type: str,
    source_uri: str,
    classification_confidence: int = 0,
    ingested_by: str = "paul-ai-pipeline",
) -> bool:
    """Record document lineage in Iceberg. Returns True on success."""
    try:
        conn = _get_connection()
        cur = conn.cursor()

        now = _now_ts()
        cur.execute(f"""INSERT INTO document_lineage (
                document_id, product_article_number, original_filename,
                doc_type, source_uri, classification_confidence,
                ingested_by, ingested_at
            ) VALUES (
                {_esc(document_id)},
                {_esc(product_article_number)},
                {_esc(original_filename)},
                {_esc(doc_type)},
                {_esc(source_uri)},
                {classification_confidence},
                {_esc(ingested_by)},
                TIMESTAMP {_esc(now)}
            )""")
        log.info("ICEBERG OK: wrote lineage for document %s -> %s", original_filename, product_article_number)
        return True
    except Exception as exc:
        log.warning("ICEBERG SKIP: could not write lineage for %s — %s", original_filename, exc)
        return False


def query_product_master(article_number: Optional[str] = None) -> list[dict]:
    """Query Iceberg product_master. For demo/health-check purposes."""
    try:
        conn = _get_connection()
        cur = conn.cursor()
        if article_number:
            cur.execute(f"SELECT * FROM product_master WHERE article_number = {_esc(article_number)}")
        else:
            cur.execute("SELECT * FROM product_master ORDER BY updated_at DESC LIMIT 100")
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as exc:
        log.warning("ICEBERG QUERY FAILED: %s", exc)
        return []
