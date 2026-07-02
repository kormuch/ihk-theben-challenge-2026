import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib import request
from urllib.error import HTTPError

from app.app import (
    Handler,
    INDEX_PATH,
    ProductStore,
    apply_access_controls,
    generate_products,
    passport_svg,
    parse_import_payload,
    products_csv,
    row_allowed,
    validate_product,
)


class ProductLayerTests(unittest.TestCase):
    def test_seed_generation_has_expected_shape(self):
        products = generate_products(20)
        self.assertEqual(len(products), 20)
        self.assertIn("attributes", products[0])
        self.assertIn("metadata", products[0])
        self.assertIn("gtin", products[0]["attributes"])

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
        self.assertIn("metadata.domain", fields)

    def test_csv_import_payload(self):
        raw = b"sku,name,family,attributes.gtin,metadata.classification,certifications\nT-1,Demo,Energy Meter,123,internal,CE|RoHS\n"
        products = parse_import_payload(raw, "text/csv")
        self.assertEqual(products[0]["sku"], "T-1")
        self.assertEqual(products[0]["attributes"]["gtin"], 123)
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

    def test_csv_export_contains_governance_fields(self):
        product = generate_products(1)[0]
        csv_text = products_csv([product]).decode("utf-8")
        self.assertIn("metadata.certification_status", csv_text)
        self.assertIn(product["sku"], csv_text)


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


if __name__ == "__main__":
    unittest.main()
