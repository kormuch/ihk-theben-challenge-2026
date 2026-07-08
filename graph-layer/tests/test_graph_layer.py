import json
import unittest
from pathlib import Path

from app.app import build_product_graph, flatten_products, graph_schema, load_products_file, product_number


class GraphLayerTests(unittest.TestCase):
    def test_product_number_uses_sku_as_root_classifier(self):
        self.assertEqual(product_number({"sku": "LUXA-200-360"}), "LUXA-200-360")

    def test_build_product_graph_links_identity_nodes(self):
        product = {
            "sku": "LUXA-200-360",
            "name": "LUXA 200-360",
            "family": "Motion Detector",
            "attributes": {
                "gtin": "4010337061234",
                "batch_lot_number": "BATCH-1",
                "serial_number": "SN-1",
                "ip_rating": "IP55",
            },
            "certifications": ["CE"],
            "documents": [{"name": "datasheet.pdf", "type": "datasheet", "source_uri": "doc://datasheet"}],
            "metadata": {"owner": "Product Data Domain", "classification": "internal"},
        }
        document = build_product_graph(product)
        labels = {node.label for node in document.nodes}
        relationship_types = {rel.rel_type for rel in document.relationships}

        self.assertEqual(document.product_number, "LUXA-200-360")
        self.assertIn("Product", labels)
        self.assertIn("GTIN", labels)
        self.assertIn("Batch", labels)
        self.assertIn("ProductInstance", labels)
        self.assertIn("HAS_GTIN", relationship_types)
        self.assertIn("HAS_BATCH", relationship_types)
        self.assertIn("HAS_INSTANCE", relationship_types)
        self.assertIn("SUPPORTED_BY", relationship_types)

    def test_flatten_products_accepts_data_layer_export_shape(self):
        payload = {"schema_version": "0.1.0", "products": [{"sku": "A"}, {"sku": "B"}]}
        self.assertEqual([p["sku"] for p in flatten_products(payload)], ["A", "B"])

    def test_sample_products_load(self):
        path = Path(__file__).resolve().parents[1] / "data" / "sample_products.json"
        products = load_products_file(path)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["sku"], "LUXA-200-360")

    def test_schema_declares_product_number_root(self):
        schema = graph_schema()
        self.assertEqual(schema["root_classifier"], "product_number")
        self.assertIn("Product", schema["node_labels"])


if __name__ == "__main__":
    unittest.main()
