# Thebenpaul Graph Layer

The graph layer adds a Neo4j product knowledge graph to the Thebenpaul lakehouse architecture. It is derived from curated data-layer/product-layer product exports and uses product numbers as the root classifier.

The layer is intentionally small: it does not replace the lakehouse, product-layer UI, or data-layer ingestion. It creates a relationship-oriented read model for product lineage, document evidence, certifications, DPP identity fields, and agent-facing traversal.

## Architecture

```text
data-layer AI ingest
        |
        v
data-layer export/products.json
        |
        v
product-layer curated product JSON
        |
        v
graph-layer sync API -> Neo4j
        |
        v
Product root graph, evidence graph, identity graph, agent graph context
```

## Runtime Principles

- `Product.product_number` is the graph root classifier.
- Identity precedence is `article_number`, then `sku`, then `product_number`, then `id`.
- Neo4j is a derived graph store, not the source of truth.
- Data-layer and product-layer remain the governed lakehouse/product-data modules.
- Sync endpoints are the only write path in this first version.
- Graph data keeps lineage and source evidence links from the curated product export.

## Services

| Service | Port | Purpose |
| --- | ---: | --- |
| `graph-layer` | `8096` | REST API for graph sync and graph reads |
| `neo4j` | `7474`, `7687` | Neo4j browser and Bolt database |

## Quick Start

Run the graph layer with Neo4j:

```bash
cd graph-layer
docker compose up --build
```

Open Neo4j Browser:

```text
http://localhost:7474
```

Default local credentials:

```text
user: neo4j
password: thebenpaul
```

Health check:

```bash
curl http://localhost:8096/health
```

Sync the mounted product-layer export:

```bash
curl -X POST http://localhost:8096/api/graph/sync/from-file \
  -H "Content-Type: application/json" \
  -d '{"path":"/product-layer-data/products.json"}'
```

Sync directly from the data-layer export endpoint:

```bash
curl -X POST http://localhost:8096/api/graph/sync/from-url \
  -H "Content-Type: application/json" \
  -d '{"url":"http://host.docker.internal:8000/api/v1/export/products.json"}'
```

## API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service and Neo4j connectivity |
| `GET` | `/api/graph/schema` | Graph labels, relationships, and root classifier |
| `GET` | `/api/graph/products` | List product root nodes |
| `GET` | `/api/graph/products/{product_number}` | Read a product neighborhood |
| `POST` | `/api/graph/sync` | Sync product export JSON posted in the request body |
| `POST` | `/api/graph/sync/from-file` | Sync product export JSON from a file path |
| `POST` | `/api/graph/sync/from-url` | Sync product export JSON from a URL |

## Graph Model

Root node:

```text
(:Product {product_number})
```

Supported derived nodes:

```text
(:ProductFamily)
(:GTIN)
(:Batch)
(:ProductInstance)
(:ProductAttribute)
(:Certification)
(:SourceDocument)
(:MetadataField)
```

Primary relationships:

```text
(:Product)-[:BELONGS_TO_FAMILY]->(:ProductFamily)
(:Product)-[:HAS_GTIN]->(:GTIN)
(:GTIN)-[:HAS_BATCH]->(:Batch)
(:Product)-[:HAS_INSTANCE]->(:ProductInstance)
(:Product)-[:HAS_ATTRIBUTE]->(:ProductAttribute)
(:Product)-[:HAS_CERTIFICATION]->(:Certification)
(:Product)-[:SUPPORTED_BY]->(:SourceDocument)
(:Product)-[:HAS_METADATA]->(:MetadataField)
```

## Configuration

Runtime configuration lives in `config/runtime.json`.

Important environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8096` | API port |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt URI |
| `NEO4J_USERNAME` | `neo4j` | Neo4j user |
| `NEO4J_PASSWORD` | `thebenpaul` | Neo4j password |
| `NEO4J_DATABASE` | `neo4j` | Neo4j database |
| `THEBEN_PRODUCT_EXPORT_PATH` | `graph-layer/data/sample_products.json` | Default file sync source |
| `THEBEN_GRAPH_CONFIG` | `graph-layer/config/runtime.json` | Runtime config path |

## Validation

Run the unit test suite:

```bash
cd graph-layer
python3 -B -m unittest discover -s tests -v
```

Or use the validation script:

```bash
cd graph-layer
sh scripts/validate.sh
```

The unit tests validate product-number root classification, data-layer export parsing, DPP identity graph mapping, schema metadata, and sample data loading.

## Operations

Useful Cypher checks in Neo4j Browser:

```cypher
MATCH (p:Product) RETURN p.product_number, p.name, p.family ORDER BY p.product_number;
```

```cypher
MATCH (p:Product {product_number: "LUXA-200-360"})-[r]-(n)
RETURN p, r, n;
```

This graph layer is a derived read model. If data looks wrong, fix the source product data in the data-layer/product-layer flow and run the sync again.
