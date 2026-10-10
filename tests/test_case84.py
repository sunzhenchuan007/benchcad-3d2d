from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import shutil
import unittest

from benchcad3d2d.contracts import read_json
from benchcad3d2d.evaluator import evaluate
from tools.build_case84 import CASE, draw, native_parameters, load_construction, geometry_validation
from tools.verify_sources import verify_selected_case
from test_framework import ROOT, workspace_temp


class SelectedCaseContractTests(unittest.TestCase):
    def test_hashed_text_artifacts_have_portable_lf_bytes(self):
        metadata=read_json(CASE/"case.json")
        for artifact in metadata["artifacts"]:
            if Path(artifact["path"]).suffix in (".json",".py",".md"):
                with self.subTest(path=artifact["path"]):
                    self.assertNotIn(b"\r\n",(CASE/artifact["path"]).read_bytes())

    def test_selected_case_evidence_links_and_six_native_dimensions(self):
        metadata=read_json(CASE/"case.json")
        self.assertEqual(len(verify_selected_case(CASE,metadata)),8)
        gt=read_json(CASE/"gt/gt.json")
        native=native_parameters(read_json(CASE/"gt/native_features.json"))
        self.assertEqual({k:v["value"] for k,v in gt["variables"].items()},native)
        self.assertEqual(set(gt["required_variables"]),set(native))
        self.assertFalse(gt["synthetic"])

    def test_resigned_input_manifest_cannot_replace_original_source(self):
        with workspace_temp() as folder:
            copied=Path(folder)/"case";shutil.copytree(CASE,copied,ignore=shutil.ignore_patterns("__pycache__"))
            metadata=read_json(copied/"case.json")
            path=copied/"input/model.step";path.write_bytes(b"different STEP")
            artifact=next(a for a in metadata["artifacts"] if a["path"]=="input/model.step")
            artifact.update(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError,"Input is not an original source STEP"):
                verify_selected_case(copied,metadata)

    def test_resigned_gt_manifest_cannot_change_validated_answer(self):
        with workspace_temp() as folder:
            copied=Path(folder)/"case";shutil.copytree(CASE,copied,ignore=shutil.ignore_patterns("__pycache__"))
            metadata=read_json(copied/"case.json");path=copied/"gt/gt.json"
            gt=read_json(path);gt["variables"]["base.width_x"]["value"]+=1
            path.write_text(json.dumps(gt),encoding="utf-8")
            artifact=next(a for a in metadata["artifacts"] if a["path"]=="gt/gt.json")
            artifact.update(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError,"Validation artifact mismatch"):
                verify_selected_case(copied,metadata)


class Case84DrawingTests(unittest.TestCase):
    def test_real_case_equivalence_conflict_missing_and_evidence_gates(self):
        try:
            import ezdxf
        except ImportError:
            self.skipTest("Controlled drawing checks require ezdxf")
        gt=read_json(CASE/"gt/gt.json");rules=read_json(ROOT/"config/rules.v0.2.json")
        expected={"good":(True,0),"equivalent_total_height":(True,0),"redundant_dimension":(True,1),
                  "conflicting_dimension":(False,1),"missing_dimension":(False,0),"conflict_and_missing":(False,1),
                  "redundant_and_missing":(False,1),"json_only_dimension":(False,0),"missing_structure_note":(False,0),
                  "missing_view":(False,0),"wrong_profile":(False,0),"overlapping_labels":(False,0)}
        with workspace_temp() as folder:
            for variant,(complete,dependencies) in expected.items():
                with self.subTest(variant=variant):
                    path=Path(folder)/variant;prediction=draw(gt,path,variant)
                    result=evaluate(gt,prediction,rules,path/"drawing.dxf","controlled-dxf")
                    self.assertEqual(result["whole_drawing_complete"],complete)
                    self.assertEqual(result["dependency_diagnostics"]["dependency_count"],dependencies)
                    if variant in ("good","equivalent_total_height"):
                        self.assertEqual(result["score"],100)
                    if variant in ("missing_dimension","conflict_and_missing","redundant_and_missing","json_only_dimension"):
                        self.assertIn("neck.width_z",result["underdetermined_required_variables"])
                    if variant in ("conflicting_dimension","conflict_and_missing"):
                        self.assertGreater(result["drawn_nominal_diagnostics"]["augmented_rank"],
                                           result["drawn_nominal_diagnostics"]["rank"])
                    if variant=="missing_structure_note":
                        self.assertFalse(any(s["expressed"] for s in result["structure"]))


class Case84GeometryTests(unittest.TestCase):
    def test_native_derived_reconstruction_and_wrong_parameter(self):
        try:
            import cadquery as cq
        except ImportError:
            self.skipTest("Geometry checks require CadQuery")
        p=native_parameters(read_json(CASE/"gt/native_features.json"))
        source=cq.importers.importStep(str(CASE/"input/model.step")).val()
        native=cq.importers.importStep(str(CASE/"gt/native_export.step")).val()
        constructor=load_construction()
        result=geometry_validation(p,source,native,constructor.build(p))
        self.assertEqual(result["analytic_volume_mm3"],495000)
        altered=copy.deepcopy(p);altered["neck.width_z"]+=1
        with self.assertRaisesRegex(ValueError,"Native, CQ and input solids differ"):
            geometry_validation(altered,source,native,constructor.build(altered))


if __name__ == "__main__":
    unittest.main()
