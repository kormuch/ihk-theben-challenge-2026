import json
import unittest
from pathlib import Path

from app.app import assess_product, config_payload, enabled_agent_ids, standards_records


class AgentsLayerConfigTests(unittest.TestCase):
    def test_goal_portfolio_counts_are_within_bounds(self):
        config = config_payload()
        catalog = config["rule_catalog"]
        self.assertGreaterEqual(len(catalog["compliance_agents"]), 1)
        self.assertLessEqual(len(catalog["compliance_agents"]), 10)
        self.assertGreaterEqual(len(catalog["expert_agents"]), 1)
        self.assertLessEqual(len(catalog["expert_agents"]), 10)
        self.assertIn("compliance-sustainability", enabled_agent_ids(config))
        self.assertIn("expert-dpp-readiness", enabled_agent_ids(config))

    def test_standards_validity_records_are_machine_readable(self):
        records = standards_records(config_payload()["standards_validity"])
        identifiers = {record["identifier"] for record in records}
        self.assertIn("ESPR-DPP-BASE", identifiers)
        self.assertIn("EMC-2014-30-EU", identifiers)
        for record in records:
            self.assertIn("status", record)
            self.assertIn("valid_from", record)
            self.assertIn("evidence_required", record)

    def test_all_minimum_config_files_exist(self):
        config_dir = Path(__file__).resolve().parents[1] / "config"
        required = [
            "ai_agents.md",
            "standards_validity.md",
            "compliance_sustainability_skill.md",
            "compliance_emc_skill.md",
            "compliance_cybersecurity_skill.md",
            "compliance_wireless_skill.md",
            "compliance_privacy_skill.md",
            "expert_dpp_readiness.md",
            "expert_sustainability.md",
            "expert_emc_design.md",
            "expert_cybersecurity_quality.md",
            "expert_governance.md",
            "expert_cad_mechanical.md",
            "expert_pricing_sales_market.md",
            "expert_aftermarket_service.md",
            "rule_catalog.json",
            "evidence_model.json",
            "access_control.json",
            "runtime.json",
        ]
        missing = [name for name in required if not (config_dir / name).exists()]
        self.assertEqual(missing, [])


class AgentsLayerAssessmentTests(unittest.TestCase):
    def test_assessment_is_advisory_traceable_and_non_mutating(self):
        payload = {
            "target_market": "EU",
            "date_placing_on_market": "2026-07-06",
            "product": {
                "id": "THB-TEST-001",
                "family": "KNX Actuator",
                "lifecycle_state": "draft",
                "attributes": {
                    "gtin": "04003468000001",
                    "batch_lot_number": "LOT-001",
                    "serial_number": "SN-001",
                    "nominal_voltage": "230V",
                    "recyclable_share_pct": 82,
                    "co2_kg": 1.4,
                    "connectivity": "knx",
                    "wireless_protocol": "none",
                    "telemetry": "none",
                    "ip_rating": "IP20"
                },
                "metadata": {
                    "owner": "Product Data Domain",
                    "domain": "product",
                    "source_system": "product-layer",
                    "lineage": "data-layer -> product-layer",
                    "classification": "internal",
                    "certification_status": "draft"
                }
            },
            "evidence": [
                {"type": "product_master_record", "reference": "product-layer/THB-TEST-001", "confidence": "verified"},
                {"type": "lineage_record", "reference": "lineage/THB-TEST-001", "confidence": "high"},
                {"type": "environmental_declaration", "reference": "evidence/env-001", "confidence": "medium"},
                {"type": "emc_test_report", "reference": "evidence/emc-001", "confidence": "medium"},
                {"type": "cad_reference", "reference": "cad/THB-TEST-001", "confidence": "medium"},
                {"type": "service_instruction", "reference": "service/THB-TEST-001", "confidence": "medium"},
                {"type": "sales_claim_evidence", "reference": "sales/THB-TEST-001", "confidence": "medium"}
            ]
        }
        result = assess_product(payload, role="reviewer")
        self.assertTrue(result["advisory_only"])
        self.assertTrue(result["human_signoff_required"])
        self.assertEqual(result["workflow_feedback"]["product_layer_write_policy"].split(";")[0], "advisory output only")
        self.assertGreater(len(result["findings"]), 0)
        for finding in result["findings"]:
            traceability = finding["traceability"]
            self.assertEqual(traceability["product_id"], "THB-TEST-001")
            self.assertIn("agent_version", traceability)
            self.assertEqual(traceability["human_review_state"], "pending")

    def test_viewer_cannot_run_assessment(self):
        with self.assertRaises(PermissionError):
            assess_product({"product": {"id": "P1"}}, role="viewer")

    def test_requested_agent_ids_limit_assessment_scope(self):
        payload = {
            "agent_ids": ["expert-dpp-readiness"],
            "product": {
                "id": "THB-TEST-002",
                "family": "KNX Actuator",
                "attributes": {},
                "metadata": {},
            },
            "evidence": [],
        }
        result = assess_product(payload, role="reviewer")
        self.assertEqual(result["product_context"]["requested_agent_ids"], ["expert-dpp-readiness"])
        self.assertGreater(len(result["findings"]), 0)
        self.assertEqual({finding["agent_id"] for finding in result["findings"]}, {"expert-dpp-readiness"})


if __name__ == "__main__":
    unittest.main()
