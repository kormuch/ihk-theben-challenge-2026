import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request
from urllib.error import HTTPError

from app.app import (
    Handler,
    INDEX_PATH,
    ProductStore,
    agents_layer_contract,
    avatar_layer_contract,
    build_agents_layer_assessment_payload,
    build_avatar_layer_assessment_payload,
    apply_access_controls,
    catalog_data_products,
    current_user,
    data_product_surface,
    data_layer_contract,
    dpp_public_html,
    dpp_public_base_url,
    dpp_record,
    dpp_versions,
    generate_products,
    lineage_model,
    passport_svg,
    parse_import_payload,
    prepare_data_layer_products,
    product_identity,
    products_csv,
    record_avatar_user_action,
    row_allowed,
    run_avatar_layer_assessment,
    run_agents_layer_assessment,
    run_theben_layer_sbom_extract,
    run_theben_layer_security_export,
    sync_from_data_layer,
    theben_layer_contract,
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

    def test_store_auto_reloads_when_shared_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "products.json"
            store = ProductStore(path)
            first_count = len(store.products)
            replacement = {
                "schema_version": "1.0.0",
                "generated_at": "2026-07-03T00:00:00Z",
                "products": [
                    {
                        "id": "external-1",
                        "sku": "EXT-1",
                        "name": "External Product",
                        "family": "External",
                        "attributes": {
                            "gtin": "04003468000999",
                            "batch_lot_number": "LOT-EXT",
                            "serial_number": "SN-EXT",
                        },
                        "metadata": {
                            "owner": "Data Layer",
                            "domain": "product",
                            "classification": "internal",
                            "certification_status": "needs_review",
                        },
                        "certifications": [],
                    }
                ],
            }
            time.sleep(0.01)
            path.write_text(json.dumps(replacement), encoding="utf-8")

            products = store.list_products({"limit": ["10"]}, {"role": "viewer"})

        self.assertEqual(first_count, 1000)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["sku"], "EXT-1")

    def test_dpp_update_versions_metadata_attributes_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            product = store.get_raw_product("thb-tim-0001")
            product["metadata"]["dpp_version"] = "1.2.3"
            store.upsert_product(product)

            updated = store.update_dpp_record(
                "thb-tim-0001",
                {
                    "attributes": {"recycled_content_share_pct": 42},
                    "metadata": {"manufacturer_name": "Thebenpaul Test GmbH"},
                    "change_rationale": "Updated recycled content after supplier evidence.",
                },
                {"role": "editor", "actor": "test-editor@example.local"},
            )
            store.record_audit(
                action="dpp_record_update",
                product_id="thb-tim-0001",
                role="editor",
                actor="test-editor@example.local",
                view="authority",
                channel="api",
                details={
                    "dpp_version": updated["metadata"]["dpp_version"],
                    "change_rationale": updated["metadata"]["change_rationale"],
                },
            )

            record = dpp_record(updated, "authority", "dpp.local", store.audit_for_product("thb-tim-0001"))
        self.assertEqual(record["record_version"], "1.2.4")
        self.assertEqual(record["lifecycle"]["version_history"][-1]["change_rationale"], "Updated recycled content after supplier evidence.")
        self.assertEqual(updated["attributes"]["recycled_content_share_pct"], 42)
        self.assertEqual(updated["metadata"]["manufacturer_name"], "Thebenpaul Test GmbH")
        self.assertEqual(record["audit"]["events"][-1]["action"], "dpp_record_update")
        self.assertEqual(record["audit"]["events"][-1]["details"]["dpp_version"], "1.2.4")
        self.assertEqual(record["audit"]["events"][-1]["actor"], "test-editor@example.local")

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
        self.assertEqual(consumer["data_matrix"]["encoded_content"], "https://dpp.thebenpaul.local/dpp/thb-tim-0001")
        self.assertIn("(01)", consumer["data_matrix"]["structured_identifier"])

    def test_dpp_public_base_url_is_configured_stable_https(self):
        product = generate_products(1)[0]
        first = dpp_record(product, "consumer", "caller-a.local")
        second = dpp_record(product, "consumer", "http://caller-b.local")
        self.assertEqual(dpp_public_base_url("caller-a.local"), "https://dpp.thebenpaul.local")
        self.assertEqual(first["public_url"], second["public_url"])
        self.assertTrue(first["public_url"].startswith("https://"))

    def test_public_dpp_html_is_no_login_consumer_view(self):
        product = generate_products(1)[0]
        html = dpp_public_html(product, "dpp.local")
        self.assertIn("Digital Product Passport", html)
        self.assertIn("Free public access, no login required", html)
        self.assertIn('application/ld+json', html)
        self.assertIn(product["attributes"]["gtin"], html)
        self.assertNotIn("Authority-only compliance data", html)

    def test_public_dpp_json_ld_is_machine_parseable(self):
        product = generate_products(1)[0]
        html = dpp_public_html(product, "dpp.local")
        script = html.split('<script type="application/ld+json">', 1)[1].split("</script>", 1)[0]
        payload = json.loads(script)
        self.assertEqual(payload["@type"], "Product")
        self.assertEqual(payload["gtin"], product["attributes"]["gtin"])

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

    def test_role_headers_are_ignored_by_default_without_trust_switch(self):
        with patch.dict(os.environ, {"THEBEN_DEFAULT_ROLE": "viewer"}, clear=False):
            os.environ.pop("THEBEN_ROLE_TOKEN", None)
            os.environ.pop("THEBEN_TRUST_ROLE_HEADERS", None)
            user = current_user({"X-Role": "admin"})
        self.assertEqual(user["role"], "viewer")

    def test_role_headers_can_be_enabled_for_local_trusted_runtime(self):
        with patch.dict(os.environ, {"THEBEN_DEFAULT_ROLE": "viewer", "THEBEN_TRUST_ROLE_HEADERS": "true"}, clear=False):
            os.environ.pop("THEBEN_ROLE_TOKEN", None)
            user = current_user({"X-Role": "editor"})
        self.assertEqual(user["role"], "editor")

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

    def test_agents_layer_contract_exposes_lakehouse_proxy_calls(self):
        contract = agents_layer_contract("127.0.0.1:8080")
        self.assertEqual(contract["source_layer"], "curated")
        self.assertEqual(contract["target_layer"], "advisory_agents")
        self.assertTrue(contract["human_review_required"])
        self.assertEqual(contract["interfaces"]["product_layer_proxy"]["agent_catalog"], "/api/agents-layer/agents")
        self.assertEqual(contract["avatar_layer"]["target_layer"], "avatar_interaction_layer")
        calls = {call["name"]: call["curl"] for call in contract["rest_api_calls"]}
        self.assertIn("/api/agents-layer/assessments", calls["Run advisory assessment for one product through product-layer"])
        self.assertIn("agent_ids", calls["Run advisory assessment for one product through product-layer"])

    def test_avatar_layer_contract_exposes_lakehouse_proxy_calls(self):
        contract = avatar_layer_contract("127.0.0.1:8080")
        self.assertEqual(contract["source_layer"], "product_ui_runtime")
        self.assertEqual(contract["target_layer"], "avatar_interaction_layer")
        self.assertTrue(contract["human_review_required"])
        self.assertEqual(
            contract["interfaces"]["product_layer_proxy"]["selected_product_avatar_assessment"],
            "/api/avatar-layer/assessments",
        )
        calls = {call["name"]: call["curl"] for call in contract["rest_api_calls"]}
        self.assertIn("/api/avatar-layer/assessments", calls["Run avatar assessment through product-layer"])
        self.assertIn("/api/avatar/assess", calls["Run avatar assessment directly against avatar-layer"])

    def test_theben_layer_contract_exposes_sbom_extract_calls(self):
        contract = theben_layer_contract("127.0.0.1:8080")
        self.assertEqual(contract["source_layer"], "curated_product_context")
        self.assertEqual(contract["target_layer"], "theben_corporate_reporting_layer")
        self.assertEqual(contract["interfaces"]["product_layer_proxy"]["sbom_extract"], "/api/theben-layer/sbom-extract")
        calls = {call["name"]: call["curl"] for call in contract["rest_api_calls"]}
        self.assertIn("/api/theben-layer/sbom-extract", calls["Extract SBOM through product-layer"])
        self.assertIn("/api/theben/sbom", calls["List extracted CycloneDX SBOM artifacts"])
        self.assertIn("/api/theben-layer/security-export", calls["Generate CVE export for selected product"])
        self.assertIn('"artifact_type":"vex"', calls["Generate OpenVEX export for selected product"])

    def test_agents_layer_assessment_payload_carries_product_and_evidence_context(self):
        product = generate_products(1)[0]
        payload = build_agents_layer_assessment_payload(
            product,
            {"agent_ids": ["expert-dpp-readiness"], "target_market": "EU"},
        )
        self.assertEqual(payload["product"]["id"], product["id"])
        self.assertEqual(payload["product"]["attributes"]["gtin"], product["attributes"]["gtin"])
        self.assertEqual(payload["agent_ids"], ["expert-dpp-readiness"])
        evidence_types = {item["type"] for item in payload["evidence"]}
        self.assertIn("product_master_record", evidence_types)
        self.assertIn("lineage_record", evidence_types)

    def test_avatar_layer_assessment_payload_wraps_advisory_context(self):
        product = generate_products(1)[0]
        payload = build_avatar_layer_assessment_payload(
            product,
            {
                "agent_ids": ["compliance-cybersecurity"],
                "assessment": {"readiness": {"status": "review_required", "score": 71}},
                "reduced_motion": True,
            },
            {"role": "viewer", "region": "EU", "purpose": "analytics"},
        )
        self.assertEqual(payload["product_id"], product["id"])
        self.assertEqual(payload["assessment_mode"], "cybersecurity")
        self.assertEqual(payload["product_context"]["lakehouse_layer"], "curated")
        self.assertEqual(payload["product_context"]["lifecycle_state"], product["lifecycle_status"])
        self.assertEqual(payload["source_contract"], "product-layer-avatar-assessment-v1")
        self.assertTrue(payload["reduced_motion"])

    def test_avatar_layer_assessment_proxy_adds_contract_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            product = store.get_raw_product("thb-tim-0001")
            expected = {
                "product_id": product["id"],
                "spoken_summary": "Avatar summary.",
                "display_summary": "Avatar summary.",
                "assessment_status": "review_required",
                "severity": "medium",
                "session": {"session_id": "av-test"},
            }
            with patch("app.app.fetch_json_url", return_value=expected) as fetch:
                result = run_avatar_layer_assessment(
                    store,
                    {"product_id": product["id"], "agent_ids": ["expert-dpp-readiness"], "assessment": {"findings": []}},
                    {"role": "viewer", "region": "EU", "purpose": "analytics"},
                )
        self.assertEqual(result["integration"]["source"], "product-layer-avatar-layer-proxy")
        self.assertEqual(result["integration"]["contract"], "product-layer-avatar-assessment-v1")
        payload = fetch.call_args.kwargs["payload"]
        headers = fetch.call_args.kwargs["headers"]
        self.assertEqual(payload["product_id"], product["id"])
        self.assertEqual(payload["assessment_mode"], "dpp")
        self.assertEqual(headers["X-Role"], "viewer")
        self.assertEqual(headers["X-Delegated-Role"], "viewer")
        self.assertEqual(payload["request_context"]["caller_role"], "viewer")

    def test_agents_layer_proxy_uses_service_role_and_delegated_caller_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            product = store.get_raw_product("thb-tim-0001")
            expected = {
                "assessment_id": "assessment-test",
                "product_context": {"product_id": product["id"]},
                "readiness": {"status": "review_required", "score": 71},
                "findings": [],
            }
            with patch("app.app.fetch_json_url", return_value=expected) as fetch:
                result = run_agents_layer_assessment(
                    store,
                    {"product_id": product["id"], "agent_ids": ["expert-dpp-readiness"]},
                    {"role": "viewer", "region": "EU", "purpose": "analytics"},
                )
        self.assertEqual(result["integration"]["source"], "product-layer-agents-layer-proxy")
        payload = fetch.call_args.kwargs["payload"]
        headers = fetch.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Role"], "reviewer")
        self.assertEqual(headers["X-Delegated-Role"], "viewer")
        self.assertEqual(payload["request_context"]["caller_role"], "viewer")
        self.assertEqual(payload["request_context"]["proxy_authorization_model"], "product-layer service role with delegated caller context")

    def test_theben_layer_sbom_extract_proxy_returns_report_and_artifact_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            product = store.get_raw_product("thb-tim-0001")
            extraction = {
                "status": "ok",
                "artifacts": {"report_id": "theben-report-test"},
                "report": {"discovery": [{"method": "GET", "path": "/products/sbom", "status": 200}]},
            }
            artifacts = {
                "sbom_artifacts": [{"filename": "7654126.cyclonedx.json", "url": "/api/theben/sbom/7654126.cyclonedx.json"}],
                "vex_artifacts": [{"filename": "7654126.vex.json", "url": "/api/theben/vex/7654126.vex.json"}],
            }
            with patch("app.app.fetch_json_url", side_effect=[extraction, artifacts]) as fetch:
                result = run_theben_layer_sbom_extract(
                    store,
                    {"product_id": product["id"]},
                    {"role": "viewer", "region": "EU", "purpose": "analytics"},
                )
        self.assertEqual(result["integration"]["contract"], "product-layer-theben-sbom-extract-v1")
        self.assertEqual(result["report"]["preview_url"], "http://127.0.0.1:8098/api/theben/reports/theben-report-test/preview")
        self.assertTrue(result["sbom_artifacts"][0]["url"].startswith("http://127.0.0.1:8098/api/theben/sbom/"))
        payload = fetch.call_args_list[0].kwargs["payload"]
        self.assertEqual(payload["selected_product"]["id"], product["id"])
        self.assertNotIn("use_fixtures", payload)
        self.assertEqual(payload["request_context"]["proxy_authorization_model"], "product-layer selected product context with theben-layer extraction ownership")

    def test_theben_layer_security_export_proxy_returns_cve_and_openvex_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            product = store.get_raw_product("thb-tim-0001")
            export = {
                "status": "ok",
                "artifacts": {"export_id": "theben-security-export-test"},
                "export": {"export_id": "theben-security-export-test", "discovery": []},
            }
            artifacts = {
                "sbom_artifacts": [{"filename": "7654126.cyclonedx.json", "url": "/api/theben/sbom/7654126.cyclonedx.json"}],
                "cve_artifacts": [{"filename": "7654126.cve.json", "url": "/api/theben/cve/7654126.cve.json"}],
                "vex_artifacts": [{"filename": "7654126.openvex.json", "url": "/api/theben/vex/7654126.openvex.json"}],
                "openvex_artifacts": [{"filename": "7654126.openvex.json", "url": "/api/theben/vex/7654126.openvex.json"}],
            }
            with patch("app.app.fetch_json_url", side_effect=[export, artifacts]) as fetch:
                result = run_theben_layer_security_export(
                    store,
                    {"product_id": product["id"], "artifact_type": "vex"},
                    {"role": "viewer", "region": "EU", "purpose": "analytics"},
                )
        self.assertEqual(result["integration"]["source"], "product-layer-theben-layer-security-export-proxy")
        self.assertEqual(result["artifact_type"], "vex")
        self.assertTrue(result["cve_artifacts"][0]["url"].startswith("http://127.0.0.1:8098/api/theben/cve/"))
        self.assertTrue(result["openvex_artifacts"][0]["url"].startswith("http://127.0.0.1:8098/api/theben/vex/"))
        payload = fetch.call_args_list[0].kwargs["payload"]
        self.assertEqual(payload["artifact_type"], "vex")
        self.assertEqual(payload["selected_product"]["id"], product["id"])
        self.assertNotIn("use_fixtures", payload)
        self.assertIn("attributes", payload["selected_product"])

    def test_avatar_ui_action_is_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            event = record_avatar_user_action(
                store,
                {
                    "action": "speak",
                    "product_id": "thb-tim-0001",
                    "session_id": "avatar-session-test",
                    "transcript_id": "transcript-test",
                    "assessment_mode": "dpp",
                },
                {"role": "viewer", "actor": "viewer@example.local"},
            )
        self.assertEqual(event["action"], "avatar_ui_speak")
        self.assertEqual(event["details"]["session_id"], "avatar-session-test")

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

    def test_public_scan_ignores_row_filter_but_dpp_json_stays_role_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            product = store.get_raw_product("thb-tim-0001")
            product["metadata"]["region"] = "DE"
            store.upsert_product(product)
            handler = Handler.__new__(Handler)
            handler.server = type("FakeServer", (), {"store": store})()
            handler.headers = {"Host": "dpp.local"}
            sent = {}
            handler.send_json = lambda payload, status=200: sent.update({"payload": payload, "status": status})
            handler.send_error_json = lambda status, message: sent.update({"error": message, "status": int(status)})

            Handler.resolve_dpp_scan(
                handler,
                {"code": ["https://dpp.thebenpaul.local/dpp/thb-tim-0001"]},
                {"role": "viewer", "region": "EU"},
            )

            self.assertEqual(sent["payload"]["record"]["identifiers"]["internal_product_id"], "thb-tim-0001")
            self.assertFalse(row_allowed(product, {"role": "viewer", "region": "EU"}))
            self.assertIsNone(store.get_product("thb-tim-0001", {"role": "viewer", "region": "EU"}))

    def test_product_reads_and_exports_are_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            handler = Handler.__new__(Handler)
            handler.server = type("FakeServer", (), {"store": store})()
            handler.headers = {"Host": "dpp.local"}
            handler.path = "/api/products/thb-tim-0001"
            sent = {}
            handler.send_json = lambda payload, status=200: sent.update({"payload": payload, "status": status})
            handler.send_error_json = lambda status, message: sent.update({"error": message, "status": int(status)})
            handler.send_json_or_404 = lambda payload, message: sent.update({"payload": payload, "message": message})

            Handler.do_GET(handler)

            handler.path = "/api/export/products.csv"
            handler.send_bytes = lambda payload, content_type, filename=None, status=200: sent.update(
                {"bytes": payload, "content_type": content_type, "filename": filename, "status": status}
            )

            Handler.do_GET(handler)

            actions = [event["action"] for event in store.audit_events]
        self.assertIn("product_read", actions)
        self.assertIn("products_csv_export", actions)

    def test_dpp_update_endpoint_and_security_cache_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProductStore(Path(tmp) / "products.json")
            handler = Handler.__new__(Handler)
            handler.server = type("FakeServer", (), {"store": store})()
            handler.headers = {"Host": "dpp.local"}
            handler.read_json = lambda: {
                "attributes": {"repairability_score": "8/10"},
                "dpp_version": "2.0.0",
                "change_rationale": "Released updated repairability score.",
            }
            sent = {}
            handler.send_json = lambda payload, status=200: sent.update({"payload": payload, "status": status})
            handler.send_error_json = lambda status, message: sent.update({"error": message, "status": int(status)})
            handler.send_json_or_404 = lambda payload, message: sent.update({"payload": payload, "message": message})

            Handler.update_dpp(
                handler,
                "/api/dpp/thb-tim-0001",
                {"role": "editor", "region": "EU", "actor": "editor@example.local"},
            )

            updated = sent["payload"]
            self.assertEqual(updated["record_version"], "2.0.0")
            self.assertEqual(updated["lifecycle"]["version_history"][-1]["change_rationale"], "Released updated repairability score.")
            self.assertEqual(updated["audit"]["events"][-1]["action"], "dpp_record_update")
            self.assertEqual(updated["audit"]["events"][-1]["actor"], "editor@example.local")

            api_headers = {}
            api_handler = Handler.__new__(Handler)
            api_handler.path = "/api/dpp/thb-tim-0001"
            api_handler.send_header = lambda key, value: api_headers.update({key: value})
            Handler.common_headers(api_handler, "application/json; charset=utf-8")

            html_headers = {}
            html_handler = Handler.__new__(Handler)
            html_handler.path = "/dpp/thb-tim-0001"
            html_handler.send_header = lambda key, value: html_headers.update({key: value})
            Handler.common_headers(html_handler, "text/html; charset=utf-8")

            self.assertEqual(api_headers["Cache-Control"], "no-store")
            self.assertEqual(api_headers["X-Content-Type-Options"], "nosniff")
            self.assertNotIn("Access-Control-Allow-Origin", api_headers)
            self.assertIn("public, max-age=60", html_headers["Cache-Control"])
            self.assertIn("frame-ancestors 'none'", html_headers["Content-Security-Policy"])


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
        if os.environ.get("TEST_ALLOW_HEADER_ROLES") != "true":
            self.skipTest("set TEST_ALLOW_HEADER_ROLES=true when the target runtime trusts X-Role headers")
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
