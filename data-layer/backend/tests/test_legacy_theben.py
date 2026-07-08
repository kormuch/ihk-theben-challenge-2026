import importlib.util
import asyncio
import unittest

import httpx

if importlib.util.find_spec("sqlalchemy") is None:
    legacy_theben = None
else:
    from app.api import legacy_theben


@unittest.skipIf(legacy_theben is None, "sqlalchemy is not installed in the lightweight local test environment")
class LegacyThebenTests(unittest.TestCase):
    def test_article_number_accepts_lowercase_articlenumber(self):
        self.assertEqual(legacy_theben._article_number({"articlenumber": "7654126"}), "7654126")

    def test_decode_bom_response_accepts_json_wrapper(self):
        response = httpx.Response(
            200,
            json={"articlenumber": "7654126", "bom": "<bom id=\"BOM-CM-001\"/>"},
        )
        payload = legacy_theben._decode_bom_response(response, "7654126")
        self.assertEqual(payload["articlenumber"], "7654126")
        self.assertIn("BOM-CM-001", payload["bom"])

    def test_decode_bom_response_accepts_raw_xml(self):
        response = httpx.Response(200, text="<bom id=\"BOM-CM-001\"/>")
        payload = legacy_theben._decode_bom_response(response, "7654126")
        self.assertEqual(payload["articlenumber"], "7654126")
        self.assertEqual(payload["bom"], "<bom id=\"BOM-CM-001\"/>")

    def test_parse_bom_xml_extracts_items(self):
        summary = legacy_theben.parse_bom_xml(
            """
            <bom id="BOM-X" version="1">
              <product><name>Demo Product</name><type>Demo</type></product>
              <items>
                <item line="1" partNumber="P-1" quantity="2" unit="pcs">
                  <description>Part 1</description>
                  <category>Electronics</category>
                  <manufacturerName>Supplier A</manufacturerName>
                </item>
              </items>
            </bom>
            """
        )
        self.assertEqual(summary["bom_id"], "BOM-X")
        self.assertEqual(summary["product_name"], "Demo Product")
        self.assertEqual(summary["items"][0]["part_number"], "P-1")
        self.assertEqual(summary["suppliers"], ["Supplier A"])

    def test_legacy_http_client_ignores_proxy_environment(self):
        client = legacy_theben.legacy_http_client()
        try:
            self.assertFalse(client._trust_env)
        finally:
            asyncio.run(client.aclose())


if __name__ == "__main__":
    unittest.main()
