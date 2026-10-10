from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

from benchcad3d2d.contracts import ContractError, read_json
from benchcad3d2d.evaluator import evaluate
from benchcad3d2d.evidence import collect_relations
from tools.run_framework_demo import legacy_example
from test_framework import ROOT, workspace_temp


class PdfInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.gt, self.prediction = legacy_example()
        self.rules = read_json(ROOT / "config/rules.v0.2.json")

    def test_reserved_pdf_does_not_accept_correct_json_as_drawn_evidence(self):
        with workspace_temp() as folder:
            # Path fixture only; no PDF contents are parsed by the reserved adapter.
            drawing = Path(folder) / "drawing.PDF"
            drawing.write_bytes(b"reserved interface test")
            report = evaluate(self.gt, self.prediction, self.rules, drawing, "pdf")
        self.assertEqual(report["status"], "unsupported")
        self.assertIsNone(report["score"])
        self.assertFalse(report["whole_drawing_complete"])
        self.assertFalse(report["complete_within_relation_scope"])
        self.assertFalse(report["drawing_evidence_checked"])
        self.assertFalse(report["drawing_evidence_verified"])
        self.assertEqual(report["annotation_evidence"]["verified_count"], 0)
        self.assertEqual(report["dimensions"]["correct"], [])
        self.assertEqual(report["unsupported"][0]["type"], "adapter_not_implemented")

    def test_pdf_invalid_paths_are_input_errors(self):
        with workspace_temp() as folder:
            wrong = Path(folder) / "drawing.dxf"
            wrong.write_bytes(b"")
            for drawing in (None, Path(folder) / "absent.pdf", wrong):
                with self.subTest(drawing=drawing), self.assertRaises(ContractError):
                    evaluate(self.gt, self.prediction, self.rules, drawing, "pdf")

    def test_cli_reports_unavailable_adapter_separately(self):
        with workspace_temp() as folder:
            base = Path(folder)
            for name, document in (("gt", self.gt), ("prediction", self.prediction)):
                (base / f"{name}.json").write_text(json.dumps(document), encoding="utf-8")
            (base / "drawing.pdf").write_bytes(b"reserved interface test")
            result = subprocess.run([
                sys.executable, "-m", "benchcad3d2d", "verify",
                "--gt", str(base / "gt.json"), "--prediction", str(base / "prediction.json"),
                "--drawing", str(base / "drawing.pdf"), "--mode", "pdf",
                "--out", str(base / "report.json"),
            ], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertEqual(read_json(base / "report.json")["status"], "unsupported")

    def test_trusted_extension_cannot_pass_without_drawing_checks(self):
        calls = []

        def unverified_collector(gt, prediction, drawing, rules):
            calls.append((drawing, rules))
            return collect_relations(gt, prediction)

        with workspace_temp() as folder:
            drawing = Path(folder) / "drawing.pdf"
            drawing.write_bytes(b"interface test")
            report = evaluate(self.gt, self.prediction, self.rules, drawing, "pdf",
                              evidence_adapter=unverified_collector)
        self.assertEqual(calls, [(drawing, self.rules)])
        self.assertFalse(report["whole_drawing_complete"])
        self.assertFalse(report["drawing_evidence_verified"])
        self.assertEqual(report["status"], "fail")


if __name__ == "__main__":
    unittest.main()
