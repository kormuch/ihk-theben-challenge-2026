import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.app import append_audit_events, avatar_assess, config_payload, role_from_request


class AvatarLayerConfigTests(unittest.TestCase):
    def test_required_config_files_exist_and_are_loaded(self):
        root = Path(__file__).resolve().parents[1]
        required = [
            "runtime.json",
            "avatar_profiles.json",
            "speech_policies.json",
            "assessment_modes.json",
        ]
        missing = [name for name in required if not (root / "config" / name).exists()]
        self.assertEqual(missing, [])
        config = config_payload()
        self.assertEqual(config["runtime"]["service"]["name"], "thebenpaul-avatar-layer")
        self.assertIn("theben-assess", config["avatar_profiles"]["profiles"])
        self.assertIn("viewer", config["speech_policies"]["roles"])
        self.assertIn("dpp", config["assessment_modes"]["modes"])

    def test_static_shell_files_exist(self):
        root = Path(__file__).resolve().parents[1]
        for name in ["index.html", "app.js", "styles.css"]:
            self.assertTrue((root / "static" / name).exists(), name)


class AvatarAssessmentContractTests(unittest.TestCase):
    def payload(self):
        return {
            "role": "viewer",
            "assessment_mode": "cybersecurity",
            "product_id": "THB-SEC-001",
            "agent_ids": ["compliance-cybersecurity"],
            "assessment": {
                "readiness": {"status": "review_required", "score": 71},
                "findings": [
                    {
                        "agent_id": "compliance-cybersecurity",
                        "agent_version": "0.1.0",
                        "rule_id": "RULE-CYBER-SBOM-001",
                        "rule_version": "2026.1",
                        "standard_refs": ["CRA", "IEC 62443"],
                        "assumptions": ["SBOM status is based on supplied evidence."],
                        "severity": "high",
                        "status": "needs_review",
                        "human_review_state": "required",
                        "missing_evidence": ["signed SBOM"],
                        "recommended_action": "Complete cybersecurity human review.",
                        "traceability": {
                            "evidence_refs": [
                                {
                                    "type": "sbom",
                                    "reference": "agents-layer/sbom/THB-SEC-001",
                                    "classification": "internal",
                                    "confidence": "medium",
                                    "text": "SBOM component inventory available."
                                }
                            ]
                        },
                        "restricted_evidence_refs": [
                            {
                                "type": "vulnerability_details",
                                "reference": "security/CVE-internal-001",
                                "classification": "restricted",
                                "text": "CVE exploit proof details must never be spoken to viewer roles."
                            }
                        ]
                    }
                ]
            }
        }

    def test_avatar_assessment_returns_required_contract_fields(self):
        result = avatar_assess(self.payload())
        for key in [
            "spoken_summary",
            "display_summary",
            "assessment_status",
            "severity",
            "confidence",
            "evidence_refs",
            "restricted_refs_hidden",
            "missing_evidence",
            "human_review_required",
            "next_actions",
            "agent_versions",
            "transcript",
            "session",
        ]:
            self.assertIn(key, result)
        self.assertTrue(result["advisory_only"])
        self.assertTrue(result["human_review_required"])
        self.assertEqual(result["product_id"], "THB-SEC-001")
        self.assertEqual(result["severity"], "high")
        self.assertEqual(result["agent_versions"]["compliance-cybersecurity"], "0.1.0")
        self.assertIn("signed SBOM", result["missing_evidence"])
        self.assertGreaterEqual(len(result["transcript"]["entries"]), 2)

    def test_viewer_evidence_filter_hides_restricted_text_from_speech(self):
        result = avatar_assess(self.payload())
        refs = result["evidence_refs"]
        restricted = [ref for ref in refs if ref.get("restricted")]
        self.assertEqual(result["restricted_refs_hidden"], 1)
        self.assertEqual(len(restricted), 1)
        self.assertTrue(restricted[0]["redacted"])
        serialized = json.dumps(result)
        self.assertNotIn("CVE exploit proof details", result["spoken_summary"])
        self.assertNotIn("CVE exploit proof details", restricted[0].get("text", ""))
        self.assertNotIn("must never be spoken", result["display_summary"])
        self.assertIn("SBOM component inventory", serialized)

    def test_steward_can_see_restricted_reference_text_but_speech_stays_guarded(self):
        payload = self.payload()
        payload["role"] = "steward"
        with patch.dict(os.environ, {"THEBEN_AVATAR_TRUST_BODY_ROLE": "true"}, clear=False):
            result = avatar_assess(payload)
        restricted = [ref for ref in result["evidence_refs"] if ref.get("restricted")]
        self.assertEqual(result["restricted_refs_hidden"], 0)
        self.assertEqual(len(restricted), 1)
        self.assertIn("CVE exploit proof details", restricted[0]["text"])
        self.assertNotIn("CVE exploit proof details", result["spoken_summary"])

    def test_direct_role_spoofing_defaults_to_viewer_without_trust_switch(self):
        with patch.dict(os.environ, {"THEBEN_AVATAR_DEFAULT_ROLE": "viewer"}, clear=False):
            os.environ.pop("THEBEN_AVATAR_TRUST_ROLE_HEADERS", None)
            os.environ.pop("THEBEN_AVATAR_TRUST_BODY_ROLE", None)
            os.environ.pop("THEBEN_AVATAR_ROLE_TOKEN", None)
            role = role_from_request({"role": "admin"}, {"X-Role": "admin"})
        self.assertEqual(role, "viewer")

    def test_rule_traceability_and_audit_events_are_preserved(self):
        result = avatar_assess(self.payload())
        self.assertEqual(result["rule_traceability"][0]["rule_id"], "RULE-CYBER-SBOM-001")
        self.assertEqual(result["rule_traceability"][0]["rule_version"], "2026.1")
        self.assertIn("CRA", result["rule_traceability"][0]["standard_refs"])
        self.assertEqual(result["rule_traceability"][0]["human_review_state"], "required")
        events = {event["event"] for event in result["audit_events"]}
        self.assertIn("avatar_assessment_requested", events)
        self.assertIn("spoken_summary_generated", events)
        self.assertIn("transcript_generated", events)

    def test_audit_events_can_be_persisted_for_direct_avatar_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "avatar_audit.jsonl"
            with patch("app.app.DATA_DIR", Path(tmp)), patch("app.app.AUDIT_FILE", audit_path):
                append_audit_events([{"event": "avatar_assessment_requested", "product_id": "P1"}])
            lines = audit_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("avatar_assessment_requested", lines[0])

    def test_product_id_only_request_returns_missing_context_contract(self):
        result = avatar_assess({"product_id": "THB-ONLY-001", "agent_ids": ["expert-dpp-readiness"]})
        self.assertEqual(result["product_id"], "THB-ONLY-001")
        self.assertEqual(result["assessment_status"], "missing_context")
        self.assertEqual(result["agent_versions"]["expert-dpp-readiness"], "unknown")
        self.assertEqual(result["evidence_refs"], [])
        self.assertTrue(result["human_review_required"])

if __name__ == "__main__":
    unittest.main()
