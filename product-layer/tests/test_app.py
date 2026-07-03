import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request
from urllib.error import HTTPError

from app.app import (
    Handler,
    INDEX_PATH,
    ProductStore,
    apply_access_controls,
    catalog_data_products,
    current_user,
    data_product_surface,
    data_layer_contract,
    dpp_public_html,
    dpp_record,
    dpp_versions,
    generate_products,
    lineage_model,
    passport_svg,
    parse_import_payload,
    prepare_data_layer_products,
    product_identity,
    products_csv,
    row_allowed,
    sync_from_data_layer,
    validate_product,
)


class ProductLayerTests(unittest.TestCase):
    def test_seed_generation_has_expected_shape(self):
        products = generate_products(20)
        self.assertEqual(len(products), 20)
        self.assertIn("attributes", products[0])
        self.assertIn("metadata", products[0])
        self.assertIn("gtin", products[0]["attributes"])
        self.assertIn("batch_lot_number", products[0]["attributes"])
        self.assertIn("serial_number", products[0]["attributes"])

    def test_validation_catches_missing_metadata_and_attributes(self):
        product = {
            "family": "Time Switch",
            "attributes": {"gtin": "1"},
            "metadata": {"owner": "x"},
        }
        result = validate_product(product)
        self.assertEqual(result["status"], "needs_review")
        fields = {issue["field"] for issue in result["issues"]}
        self.assertIn("attributes.nominal_voltage", fields)
        self.assertIn("attributes.batch_lot_number", fields)
        self.assertIn("attributes.serial_number", fields)
        self.assertIn("metadata.domain", fields)

    def test_csv_import_payload(self):
        raw = b"sku,name,family,attributes.gtin,attributes.batch_lot_number,attributes.serial_number,metadata.classification,certifications\nT-1,Demo,Energy Meter,04003468000123,LOT-1,SN-1,internal,CE|RoHS\n"
        products = parse_import_payload(raw, "text/csv")
        self.assertEqual(products[0]["sku"], "T-1")
        self.assertEqual(products[0]["attributes"]["gtin"], "04003468000123")
        self.assertEqual(products[0]["attributes"]["batch_lot_number"], "LOT-1")
        self.assertEqual(products[0]["attributes"]["serial_number"], "SN-1")
        self.assertEqual(products[0]["certifications"], ["CE", "RoHS"])

    def test_store_upsert_and_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            product = store.upsert_product({"sku": "T-2", "name": "Demo", "family": "Time Switch"})
            patched = store.patch_attributes(product["id"], {"gtin": "999"})
            self.assertEqual(patched["attributes"]["gtin"], "999")

    def test_svg_export_contains_product_identity(self):
        product = generate_products(1)[0]
        svg = passport_svg(product)
        self.assertIn("<svg", svg)
        self.assertIn(product["sku"], svg)
        self.assertIn(product["attributes"]["gtin"], svg)

    def test_product_identity_builds_gs1_data_matrix_payload(self):
        product = generate_products(1)[0]
        identity = product_identity(product)
        self.assertEqual(identity["gtin"], product["attributes"]["gtin"])
        self.assertEqual(identity["gtin_14"], product["attributes"]["gtin"])
        self.assertIn("(01)", identity["data_matrix"]["payload"])
        self.assertIn("(10)", identity["data_matrix"]["payload"])
        self.assertIn("(21)", identity["data_matrix"]["payload"])
        self.assertEqual(
            identity["globally_unique_instance_id"],
            f"{product['attributes']['gtin']}:{product['attributes']['serial_number']}",
        )

    def test_dpp_record_filters_fields_by_role_view(self):
        product = generate_products(1)[0]
        consumer = dpp_record(product, "consumer", "dpp.local")
        b2b = dpp_record(product, "b2b", "dpp.local")
        authority = dpp_record(product, "authority", "dpp.local")

        consumer_ids = {field["id"] for field in consumer["fields"]}
        b2b_ids = {field["id"] for field in b2b["fields"]}
        authority_ids = {field["id"] for field in authority["fields"]}

        self.assertIn("main_materials", consumer_ids)
        self.assertIn("recycled_content_share_pct", consumer_ids)
        self.assertNotIn("source_system", consumer_ids)
        self.assertIn("source_system", b2b_ids)
        self.assertIn("quality_status", authority_ids)
        self.assertEqual(consumer["data_matrix"]["encoded_content"], "http://dpp.local/dpp/thb-tim-0001")
        self.assertIn("(01)", consumer["data_matrix"]["structured_identifier"])

    def test_public_dpp_html_is_no_login_consumer_view(self):
        product = generate_products(1)[0]
        html = dpp_public_html(product, "dpp.local")
        self.assertIn("Digital Product Passport", html)
        self.assertIn("Free public access, no login required", html)
        self.assertIn('application/ld+json', html)
        self.assertIn(product["attributes"]["gtin"], html)
        self.assertNotIn("Authority-only compliance data", html)

    def test_dpp_versions_expose_lifecycle_metadata(self):
        product = generate_products(1)[0]
        versions = dpp_versions(product)
        self.assertEqual(versions["current_version"], "0.1.0")
        self.assertEqual(versions["versions"][0]["status"], "active")

    def test_static_path_traversal_falls_back_to_index(self):
        translated = Handler.translate_path(object(), "/../app/app.py")
        self.assertEqual(Path(translated), INDEX_PATH)

    def test_region_row_level_security(self):
        product = generate_products(1)[0]
        product["metadata"]["region"] = "DE"
        self.assertFalse(row_allowed(product, {"role": "viewer", "region": "EU"}))
        self.assertTrue(row_allowed(product, {"role": "steward", "region": "EU"}))

    def test_confidential_masking(self):
        product = generate_products(11)[0]
        product["metadata"]["classification"] = "confidential"
        masked = apply_access_controls(product, {"role": "viewer", "region": product["metadata"]["region"]})
        self.assertEqual(masked["attributes"]["commercial_price_eur"], "***masked***")
        unmasked = apply_access_controls(product, {"role": "steward", "region": product["metadata"]["region"]})
        self.assertNotEqual(unmasked["attributes"]["commercial_price_eur"], "***masked***")

    def test_role_headers_can_be_token_gated(self):
        with patch.dict(os.environ, {"THEBEN_DEFAULT_ROLE": "viewer", "THEBEN_ROLE_TOKEN": "secret"}, clear=False):
            spoofed = current_user({"X-Role": "admin"})
            authorized = current_user({"X-Role": "admin", "X-Role-Token": "secret"})
        self.assertEqual(spoofed["role"], "viewer")
        self.assertEqual(authorized["role"], "admin")

    def test_csv_export_contains_governance_fields(self):
        product = generate_products(1)[0]
        csv_text = products_csv([product]).decode("utf-8")
        self.assertIn("metadata.certification_status", csv_text)
        self.assertIn("identity.data_matrix.payload", csv_text)
        self.assertIn(product["attributes"]["serial_number"], csv_text)
        self.assertIn(product["sku"], csv_text)

    def test_data_layer_contract_is_active_and_configurable(self):
        previous = os.environ.get("THEBEN_DATA_LAYER_EXPORT_URL")
        previous_enabled = os.environ.get("THEBEN_DATA_LAYER_SYNC_ENABLED")
        os.environ["THEBEN_DATA_LAYER_EXPORT_URL"] = "http://127.0.0.1:8000/api/v1/export/products.json"
        os.environ["THEBEN_DATA_LAYER_SYNC_ENABLED"] = "true"
        try:
            contract = data_layer_contract()
        finally:
            if previous is None:
                os.environ.pop("THEBEN_DATA_LAYER_EXPORT_URL", None)
            else:
                os.environ["THEBEN_DATA_LAYER_EXPORT_URL"] = previous
            if previous_enabled is None:
                os.environ.pop("THEBEN_DATA_LAYER_SYNC_ENABLED", None)
            else:
                os.environ["THEBEN_DATA_LAYER_SYNC_ENABLED"] = previous_enabled
        self.assertEqual(contract["status"], "active_adapter")
        self.assertTrue(contract["sync_enabled"])
        self.assertEqual(contract["source_layer"], "standardized")
        self.assertEqual(contract["target_layer"], "curated")
        self.assertEqual(contract["sync_permission"], "product:import")
        self.assertEqual(contract["export_url"], "http://127.0.0.1:8000/api/v1/export/products.json")

    def test_prepare_data_layer_products_adds_lakehouse_lineage(self):
        payload = {
            "schema_version": "1.0.0",
            "generated_at": "2026-07-03T09:00:00+00:00",
            "products": [
                {
                    "sku": "DL-1",
                    "name": "Data Layer Product",
                    "family": "Time Switch",
                    "attributes": {
                        "gtin": "04003468000001",
                        "batch_lot_number": "LOT-1",
                        "serial_number": "SN-1",
                        "nominal_voltage": "230V",
                        "ip_rating": "IP20",
                    },
                    "metadata": {"owner": "Product Data Domain", "domain": "product"},
                }
            ],
        }
        products = prepare_data_layer_products(payload, "http://data-layer/api/v1/export/products.json")
        metadata = products[0]["metadata"]
        self.assertEqual(products[0]["sku"], "DL-1")
        self.assertEqual(metadata["lakehouse_layer"], "curated")
        self.assertEqual(metadata["upstream_export_url"], "http://data-layer/api/v1/export/products.json")
        self.assertEqual(metadata["target_table"], "curated_product.product_master_dpp")
        self.assertIn("contract_version", metadata)

    def test_catalog_and_lineage_expose_lakehouse_modules(self):
        catalog = catalog_data_products()
        product = catalog["data_products"][0]
        self.assertEqual(product["module"], "product")
        self.assertEqual(product["interfaces"]["target_lakehouse"]["format"], "Apache Iceberg")
        self.assertIn("owner", product["mandatory_metadata"])

        lineage = lineage_model()
        layer_names = [layer["name"] for layer in lineage["layers"]]
        self.assertEqual(layer_names, ["raw", "standardized", "curated", "consumption"])
        self.assertIn("central lakehouse", lineage["architecture"])

    def test_data_product_surface_exposes_access_and_sync_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            surface = data_product_surface(store, {"role": "viewer", "region": "EU", "purpose": "analytics"})
        self.assertEqual(surface["domain_module"]["domain"], "product")
        self.assertEqual(surface["interfaces"]["sync"], "/api/sync/data-layer")
        self.assertFalse(surface["effective_access"]["can_import"])
        self.assertIn("lineage", surface["mandatory_metadata"])

    def test_data_layer_sync_imports_export_contract_and_records_lineage(self):
        payload = {
            "schema_version": "1.0.0",
            "generated_at": "2026-07-03T10:00:00+00:00",
            "products": [
                {
                    "sku": "DL-100",
                    "name": "Data Layer Product",
                    "family": "Energy Meter",
                    "attributes": {
                        "gtin": "4003468990001",
                        "batch_lot_number": "LOT-2026-001",
                        "serial_number": "SN-DL-100",
                        "nominal_voltage": "230V",
                        "ip_rating": "IP20",
                        "co2_kg": 1.2,
                        "recyclable_share_pct": 80,
                        "measurement_accuracy": "class B",
                        "phases": 3,
                    },
                    "certifications": ["CE", "RoHS"],
                    "metadata": {
                        "owner": "Product Data Domain",
                        "domain": "product",
                        "source_system": "paul-data-layer",
                        "lineage": "paul-ai-ingest -> data-layer-postgres -> product-layer-json-store",
                        "refresh_frequency": "on export",
                        "sla": "local MVP, no production SLA",
                        "classification": "internal",
                        "certification_status": "certified",
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            store.products = []
            store.save()
            with patch("app.app.fetch_data_layer_export", return_value=payload) as fetch:
                result = sync_from_data_layer(
                    store,
                    {
                        "enabled": True,
                        "source_url": "http://backend:8000/api/v1/export/products.json",
                        "timeout_seconds": 2,
                        "contract": "product-layer-products-json-v1",
                        "allowed_hosts": ["backend"],
                    },
                )
            product = store.get_product("dl-100", {"role": "steward", "region": "EU"})

        self.assertEqual(result["imported"], 1)
        fetch.assert_called_once_with("http://backend:8000/api/v1/export/products.json", 2.0)
        self.assertEqual(product["sku"], "DL-100")
        self.assertEqual(store.sync_state["source"]["schema_version"], "1.0.0")
        self.assertEqual(store.sync_state["source"]["lakehouse_layer"], "curated")

    def test_data_layer_sync_rejects_unapproved_hosts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            with self.assertRaises(ValueError):
                sync_from_data_layer(
                    store,
                    {
                        "enabled": True,
                        "source_url": "http://metadata.service.local/latest",
                        "timeout_seconds": 2,
                        "allowed_hosts": ["backend"],
                    },
                )

    def test_data_layer_sync_disabled_without_explicit_enable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            with self.assertRaises(ValueError):
                sync_from_data_layer(store, {"enabled": False, "source_url": "http://127.0.0.1/unused"})


@unittest.skipUnless(os.environ.get("TEST_BASE_URL"), "set TEST_BASE_URL to run live HTTP tests")
class LiveHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = os.environ["TEST_BASE_URL"].rstrip("/")
        cls.timeout = float(os.environ.get("TEST_HTTP_TIMEOUT", "5"))

    def get_json(self, path, headers=None):
        req = request.Request(self.base + path, headers=headers or {})
        with request.urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_openapi_and_products_endpoints(self):
        spec = self.get_json("/api/openapi.json")
        self.assertEqual(spec["openapi"], "3.0.3")
        products = self.get_json("/api/products?limit=5")
        self.assertEqual(len(products["products"]), 5)

    def test_write_requires_role(self):
        body = json.dumps({"sku": "T-3", "name": "Demo"}).encode("utf-8")
        req = request.Request(
            self.base + "/api/products",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as ctx:
            request.urlopen(req, timeout=self.timeout)
        self.assertEqual(ctx.exception.code, 403)

    def test_editor_can_create_product(self):
        body = json.dumps({"sku": "T-4", "name": "Demo"}).encode("utf-8")
        req = request.Request(
            self.base + "/api/products",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "X-Role": "editor"},
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.status, 201)
        self.assertEqual(payload["product"]["sku"], "T-4")

    def test_dpp_endpoints_are_live(self):
        record = self.get_json("/api/dpp/thb-tim-0001")
        self.assertEqual(record["record_type"], "eu_digital_product_passport")
        self.assertIn("quality", record)
        self.assertIn("data_carrier", record)

        req = request.Request(self.base + "/dpp/thb-tim-0001")
        with request.urlopen(req, timeout=self.timeout) as response:
            html = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertIn("Digital Product Passport", html)
        self.assertIn("Free public access, no login required", html)


if __name__ == "__main__":
    unittest.main()
