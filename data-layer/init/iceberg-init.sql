CREATE SCHEMA IF NOT EXISTS iceberg.products;

CREATE TABLE IF NOT EXISTS iceberg.products.product_master (
    article_number VARCHAR,
    product_name   VARCHAR,
    family         VARCHAR,
    nominal_voltage VARCHAR,
    ip_rating      VARCHAR,
    certifications VARCHAR,
    attributes     VARCHAR,
    source_system  VARCHAR,
    lineage        VARCHAR,
    owner          VARCHAR,
    classification VARCHAR,
    created_at     TIMESTAMP(6) WITH TIME ZONE,
    updated_at     TIMESTAMP(6) WITH TIME ZONE,
    ingested_at    TIMESTAMP(6) WITH TIME ZONE
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['family']
);

CREATE TABLE IF NOT EXISTS iceberg.products.document_lineage (
    document_id    VARCHAR,
    product_article_number VARCHAR,
    original_filename VARCHAR,
    doc_type       VARCHAR,
    source_uri     VARCHAR,
    classification_confidence INTEGER,
    ingested_by    VARCHAR,
    ingested_at    TIMESTAMP(6) WITH TIME ZONE
)
WITH (
    format = 'PARQUET'
);
