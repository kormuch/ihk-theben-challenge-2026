import unittest
from pathlib import Path
from unittest.mock import patch

from app.app import (
    LegacyClient,
    article_path,
    build_cve_export,
    build_cyclonedx,
    build_openvex,
    build_vex,
    collect_report_data,
    create_security_export,
    create_report,
    collect_security_export_data,
    list_security_artifacts,
    normalize_product,
    select_demo_products,
)


class ThebenLayerTests(unittest.TestCase):
    def test_normalize_product_uses_article_number(self):
        product = normalize_product({"articleNumber": "VC-2025-001", "name": "Vacuum Cleaner Pro"})
        self.assertEqual(product["article_number"], "VC-2025-001")
        self.assertEqual(product["name"], "Vacuum Cleaner Pro")

    def test_select_demo_products_prefers_vacuum_and_coffee(self):
        selected = select_demo_products([
            {"articleNumber": "X", "name": "Other", "category": "Misc"},
            {"articleNumber": "VC", "name": "Vacuum Cleaner Pro", "category": "Household"},
            {"articleNumber": "CM", "name": "Coffee Machine Deluxe", "category": "Household"},
        ])
        self.assertEqual([p["article_number"] for p in selected], ["VC", "CM"])

    def test_fixture_report_contains_sbom_and_vex(self):
        report = collect_report_data(LegacyClient("http://example.invalid", use_fixture=True))
        self.assertEqual(len(report["products"]), 2)
        self.assertGreater(len(report["products"][0]["sbom"]["components"]), 0)
        self.assertIn("vulnerabilities", report["products"][0]["vex"])

    def test_build_vex_has_csaf_vex_category(self):
        product = {"article_number": "A-1", "name": "Demo"}
        sbom = build_cyclonedx(product, {"bom": []}, {"components": []})
        vex = build_vex(product, sbom, [{"cve": "CVE-2026-0001", "status": "not_affected"}])
        self.assertEqual(vex["document"]["category"], "csaf_vex")
        self.assertEqual(vex["vulnerabilities"][0]["cve"], "CVE-2026-0001")

    def test_cve_export_uses_requested_template_shape(self):
        product = {"article_number": "VC-2025-001", "name": "Vacuum Cleaner Pro"}
        sbom = build_cyclonedx(
            product,
            {"bom": []},
            {"components": [{"name": "FreeRTOS", "version": "10.4.3", "purl": "pkg:generic/freertos@10.4.3"}]},
        )
        cve = build_cve_export(
            product,
            sbom,
            [{"cve": "CVE-2023-12345", "description": "Network stack flaw.", "severity": "HIGH", "component": "FreeRTOS"}],
        )
        self.assertEqual(cve["schema"], "thebenpaul-cve-export-v1")
        self.assertEqual(cve["cves"][0]["cveId"], "CVE-2023-12345")
        self.assertEqual(cve["cves"][0]["severity"], "HIGH")
        self.assertIn("https://nvd.nist.gov/vuln/detail/CVE-2023-12345", cve["cves"][0]["references"])
        self.assertEqual(cve["cves"][0]["affected_components"][0]["name"], "FreeRTOS")

    def test_openvex_export_uses_requested_template_shape(self):
        product = {"article_number": "VC-2025-001", "name": "Vacuum Cleaner Pro"}
        sbom = build_cyclonedx(product, {"bom": []}, {"components": []})
        openvex = build_openvex(
            product,
            sbom,
            [{"cve": "CVE-2023-12345", "status": "not_affected", "justification": "vulnerable_code_not_in_execute_path"}],
        )
        self.assertEqual(openvex["@context"], "https://openvex.dev/ns/v0.2.0")
        self.assertEqual(openvex["author"], "Theben Security Team")
        self.assertEqual(openvex["statements"][0]["vulnerability"]["name"], "CVE-2023-12345")
        self.assertEqual(openvex["statements"][0]["status"], "not_affected")

    def test_create_report_with_fixtures_writes_pdf(self):
        result = create_report(use_fixture=True)
        pdf_path = Path(result["artifacts"]["pdf_path"])
        self.assertTrue(pdf_path.exists())
        self.assertGreater(pdf_path.stat().st_size, 1200)

    def test_create_report_tries_live_then_falls_back_when_unreachable(self):
        report = collect_report_data(LegacyClient("http://example.invalid", use_fixture=True))
        with patch("app.app.collect_report_data", side_effect=[OSError("connection refused"), report]), patch(
            "app.app.save_report_artifacts",
            return_value={"report_id": "fallback-report"},
        ):
            result = create_report(use_fixture=None)
        self.assertTrue(result["report"]["fixture_fallback"])
        self.assertIn("connection refused", result["report"]["legacy_error"])

    def test_create_report_use_fixture_false_still_allows_configured_fallback(self):
        report = collect_report_data(LegacyClient("http://example.invalid", use_fixture=True))
        with patch("app.app.collect_report_data", side_effect=[OSError("connection refused"), report]), patch(
            "app.app.save_report_artifacts",
            return_value={"report_id": "fallback-report"},
        ):
            result = create_report(use_fixture=False)
        self.assertTrue(result["report"]["fixture_fallback"])

    def test_create_report_force_live_only_disables_fixture_fallback(self):
        with patch("app.app.collect_report_data", side_effect=OSError("connection refused")):
            with self.assertRaises(OSError):
                create_report(use_fixture=False, force_live_only=True)

    def test_security_artifact_listing_exposes_sbom_and_vex_urls(self):
        create_report(use_fixture=True)
        create_security_export(
            selected_product={"sku": "VC-2025-001", "name": "Vacuum Cleaner Pro"},
            artifact_type="both",
            use_fixture=True,
        )
        listing = list_security_artifacts()
        self.assertTrue(listing["sbom_artifacts"])
        self.assertTrue(listing["cve_artifacts"])
        self.assertTrue(listing["vex_artifacts"])
        self.assertTrue(listing["openvex_artifacts"])
        self.assertTrue(listing["sbom_artifacts"][0]["url"].startswith("/api/theben/sbom/"))
        self.assertTrue(listing["cve_artifacts"][0]["url"].startswith("/api/theben/cve/"))
        self.assertTrue(listing["vex_artifacts"][0]["url"].startswith("/api/theben/vex/"))
        self.assertTrue(listing["sbom_artifacts"][0]["filename"].endswith(".json"))

    def test_security_export_handles_selected_product_missing_from_fixture_bom(self):
        export = collect_security_export_data(
            LegacyClient("http://example.invalid", use_fixture=True),
            {"sku": "LUXA 200-360", "name": "LUXA 200-360", "family": "Motion Detector"},
            "vex",
        )
        product = export["products"][0]
        self.assertEqual(product["product"]["article_number"], "LUXA 200-360")
        self.assertEqual(product["vulnerability_count"], 0)
        self.assertTrue(product["evidence_warnings"])
        self.assertEqual(product["sbom"]["components"], [])
        self.assertEqual(product["openvex"]["statements"], [])

    def test_real_api_query_parameter_is_lowercase_articlenumber(self):
        self.assertEqual(
            article_path("/products/bom", "7654126"),
            "/products/bom?articlenumber=7654126",
        )
        client = LegacyClient("http://example.invalid", use_fixture=True)
        payload = client.get_json("/products/bom?articlenumber=VC-2025-001")
        self.assertEqual(payload["articleNumber"], "VC-2025-001")


if __name__ == "__main__":
    unittest.main()
