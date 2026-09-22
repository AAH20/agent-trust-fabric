import copy
import json
import unittest
from pathlib import Path

from agent_trust_fabric.core import run_case, verify
from agent_trust_fabric.report import render_html


CASE = json.loads((Path(__file__).parents[1] / "fixtures" / "refund-agent.json").read_text())


class TrustFabricTests(unittest.TestCase):
    def test_demo_decisions_and_roundtrip(self):
        result = run_case(CASE)
        self.assertEqual([r["decision"] for r in result["receipts"]], ["allow", "deny", "deny", "deny"])
        self.assertIn("AUTHORITY_EXPIRED", result["receipts"][1]["reasons"])
        self.assertIn("RESOURCE_OUT_OF_SCOPE", result["receipts"][2]["reasons"])
        self.assertIn("APPROVAL_REPLAY", result["receipts"][3]["reasons"])
        self.assertEqual(verify(result, CASE), [])

    def test_receipt_tamper_is_detected(self):
        result = run_case(CASE)
        result["receipts"][0]["decision"] = "deny"
        self.assertTrue(any("digest mismatch" in error for error in verify(result, CASE)))

    def test_case_tamper_is_detected(self):
        result = run_case(CASE)
        altered = copy.deepcopy(CASE)
        altered["events"][0]["amount"] = 80
        self.assertTrue(any("input mismatch" in error for error in verify(result, altered)))

    def test_approval_cannot_cross_run(self):
        altered = copy.deepcopy(CASE)
        altered["events"][0]["approval"]["run_id"] = "run-8"
        result = run_case(altered)
        self.assertIn("APPROVAL_SCOPE_MISMATCH", result["receipts"][0]["reasons"])

    def test_approval_cannot_change_amount(self):
        altered = copy.deepcopy(CASE)
        altered["events"][0]["amount"] = 80
        result = run_case(altered)
        self.assertIn("APPROVAL_AMOUNT_MISMATCH", result["receipts"][0]["reasons"])

    def test_missing_authority_denies_or_rejects(self):
        altered = copy.deepcopy(CASE)
        del altered["events"][0]["authority"]["actions"]
        with self.assertRaises(ValueError):
            run_case(altered)

    def test_resource_traversal_rejected(self):
        altered = copy.deepcopy(CASE)
        altered["events"][0]["resource"] = "customers/acme/../other/orders/42"
        with self.assertRaises(ValueError):
            run_case(altered)

    def test_prefix_boundary_required(self):
        altered = copy.deepcopy(CASE)
        altered["events"][0]["authority"]["resource_prefix"] = "customers/acme"
        with self.assertRaises(ValueError):
            run_case(altered)

    def test_unbounded_amount_denied(self):
        altered = copy.deepcopy(CASE)
        del altered["events"][0]["authority"]["max_amount"]
        self.assertIn("AMOUNT_OUT_OF_SCOPE", run_case(altered)["receipts"][0]["reasons"])

    def test_html_escapes_untrusted_case_name(self):
        altered = copy.deepcopy(CASE)
        altered["case_id"] = "<script>alert(1)</script>"
        html = render_html(run_case(altered))
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
