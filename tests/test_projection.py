from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

from benchcad3d2d.contracts import ContractError, read_json
from benchcad3d2d.projection import Frame, compare_curves, geometry_catalog, validate_submission, verify_views
from tools.build_projection_demo import make_fixture, specs, view_spec
from test_framework import ROOT, workspace_temp


CAD_AVAILABLE = all(importlib.util.find_spec(name) for name in ("cadquery","ezdxf","numpy"))


def declaration():
    views=specs()
    for view in views:
        view["geometry"]["visible"]=[["A","B"]]
        if view["type"]=="full_section":
            view["geometry"].update(cut_edges=[["A","C"]],hatches=[["A","D"]])
            view["section"]["markers"]={"traces":[["E"]],"labels":[["F"],["10"]],"title":["11"],
                                        "arrows":[{"drawing_ref":["12"],"tip_vertex":0},{"drawing_ref":["13"],"tip_vertex":0}]}
    return {"schema_version":"benchcad-3d2d-prediction/0.2","case_id":"contract",
            "units":"mm","input_sha256":"0"*64,"drawing_sha256":"0"*64,
            "views":views,"features":[],"dimensions":[],"structure":[],"auxiliary":[]}


class ProjectionContractTests(unittest.TestCase):
    def test_self_reported_score_is_not_a_submission_field(self):
        prediction=declaration();prediction["score"]=100
        with self.assertRaisesRegex(ContractError,"unknown fields"):validate_submission(prediction)

    def test_general_frames_do_not_depend_on_view_names(self):
        prediction=declaration()
        validate_submission(prediction)
        view=prediction["views"][3]
        frame=Frame.read(view)
        for point in ((0,0),(18.5,-29.25),(-100,100)):
            self.assertLess(math.dist(point,frame.from_sheet(frame.to_sheet(point))),1e-10)
        self.assertLess(math.dist(frame.project([10,20,30]),(0,0)),1e-10)

    def test_invalid_frames_and_false_section_direction_are_rejected(self):
        for field,value in (("right",[2,0,0]),("up",[1,0,0]),("normal",[0,0,-1])):
            with self.subTest(field=field):
                prediction=declaration();prediction["views"][0]["projection"][field]=value
                with self.assertRaises(ContractError):validate_submission(prediction)
        prediction=declaration();prediction["views"][-1]["section"]["retained_side"]="positive"
        with self.assertRaises(ContractError):validate_submission(prediction)

    def test_extra_lines_fail_bidirectional_geometry_check(self):
        outline=[[(0,0),(10,0)]]
        result=compare_curves(outline,outline+[[(20,0),(30,0)]],0.1)
        self.assertFalse(result["ok"])
        self.assertAlmostEqual(result["expected_to_drawing_mm"],0)
        self.assertAlmostEqual(result["drawing_to_expected_mm"],20)

    def test_private_bindings_cannot_enter_general_submission(self):
        prediction=declaration()
        prediction["dimensions"]=[{"id":"d","type":"length","view_id":"top","drawing_ref":["21"],
                                   "value":20,"binding_ref":"private_gt_key","attachments":[{}]}]
        with self.assertRaisesRegex(ContractError,"private GT"):validate_submission(prediction)


@unittest.skipUnless(CAD_AVAILABLE,"General view tests need CadQuery/OCP and ezdxf")
class GeneralDrawingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=workspace_temp();cls.folder=Path(cls.temp.name)
        cls.prediction=make_fixture(cls.folder)
        cls.baseline=verify_views(cls.folder/"model.step",cls.folder/"drawing.dxf",cls.prediction)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_arbitrary_layout_rotation_scale_and_oblique_section(self):
        self.assertEqual(self.baseline["status"],"views_verified",self.baseline)
        self.assertEqual(len(self.baseline["views"]),5)
        self.assertIsNone(self.baseline["score"])
        self.assertFalse(self.baseline["whole_drawing_complete"])
        self.assertEqual(self.baseline["verified_annotation_ids"],[])

    def test_drawn_defects_cannot_be_fixed_by_json_claims(self):
        expectations={"wrong_direction":"visible_geometry_mismatch",
                      "wrong_cut_plane":"cut_edges_geometry_mismatch",
                      "missing_geometry":"visible_geometry_mismatch",
                      "extra_geometry":"visible_geometry_mismatch",
                      "reversed_arrows":"Section arrows disagree",
                      "missing_trace":"DXF entity path does not exist",
                      "wrong_hatch":"hatches_geometry_mismatch",
                      "json_only_section":"DXF entity path does not exist"}
        for variant,issue in expectations.items():
            with self.subTest(variant=variant):
                folder=self.folder/variant
                prediction=make_fixture(folder,variant)
                report=verify_views(folder/"model.step",folder/"drawing.dxf",prediction)
                self.assertEqual(report["status"],"fail",report)
                self.assertIn(issue," ".join(i for v in report["views"] for i in v["issues"]))
                self.assertIsNone(report["score"])

    def test_hash_mismatch_is_an_input_error(self):
        prediction=copy.deepcopy(self.prediction);prediction["drawing_sha256"]="0"*64
        with self.assertRaisesRegex(ContractError,"hash mismatch"):
            verify_views(self.folder/"model.step",self.folder/"drawing.dxf",prediction)

    def test_unclassified_actual_line_cannot_disappear_from_json(self):
        import ezdxf
        doc=ezdxf.readfile(self.folder/"drawing.dxf")
        entity=doc.modelspace().add_line((1000,0),(1100,0))
        drawing=self.folder/"unclassified.dxf";doc.saveas(drawing)
        prediction=copy.deepcopy(self.prediction)
        prediction["drawing_sha256"]=hashlib.sha256(drawing.read_bytes()).hexdigest()
        report=verify_views(self.folder/"model.step",drawing,prediction)
        self.assertEqual(report["status"],"fail")
        self.assertIn([entity.dxf.handle],report["unclassified_entities"])

    def test_feature_json_is_not_converted_to_a_drawing_score(self):
        prediction=copy.deepcopy(self.prediction)
        ref=geometry_catalog(self.folder/"model.step")["faces"][0]
        prediction["features"]=[{"id":"claimed_feature","type":"unverified_type",
                                  "geometry_refs":[{"kind":"face","fingerprint":ref["fingerprint"]}]}]
        report=verify_views(self.folder/"model.step",self.folder/"drawing.dxf",prediction)
        self.assertEqual(report["status"],"views_verified")
        self.assertEqual(report["unverified_feature_ids"],["claimed_feature"])
        self.assertIsNone(report["score"])
        self.assertFalse(report["whole_drawing_complete"])

    def test_public_geometry_catalog_is_repeatable_and_contains_no_gt(self):
        a=geometry_catalog(self.folder/"model.step");b=geometry_catalog(self.folder/"model.step")
        self.assertEqual(a,b)
        self.assertEqual(len(a["faces"]),14)
        self.assertNotIn("features",a)
        self.assertNotIn("required_variables",a)

    def test_cli_keeps_views_verified_distinct_from_drawing_pass(self):
        report_path=self.folder/"cli-report.json"
        result=subprocess.run([sys.executable,"-m","benchcad3d2d","verify-views",
                               "--input-step",str(self.folder/"model.step"),"--drawing",str(self.folder/"drawing.dxf"),
                               "--prediction",str(self.folder/"prediction.json"),"--out",str(report_path)],
                              cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=read_json(report_path)
        self.assertEqual(report["status"],"views_verified")
        self.assertIsNone(report["score"])
        self.assertFalse(report["whole_drawing_complete"])

    def test_independent_analytic_circle_matches_kernel_projection(self):
        # This DXF is constructed analytically, not by the projection generator.
        import cadquery as cq
        import ezdxf
        folder=self.folder/"analytic";folder.mkdir()
        step=folder/"model.step"
        cq.exporters.export(cq.Workplane("XY").circle(6).extrude(4),str(step))
        doc=ezdxf.new();doc.header["$INSUNITS"]=4
        view=view_spec("free_name",[1,0,0],[0,1,0],[0,0,1],[13,-42],78,0.4)
        circle=doc.modelspace().add_circle((13,-42),2.4)
        view["geometry"]["visible"]=[[circle.dxf.handle]]
        drawing=folder/"drawing.dxf";doc.saveas(drawing)
        prediction={"schema_version":"benchcad-3d2d-prediction/0.2","case_id":"analytic_cylinder","units":"mm",
                    "input_sha256":hashlib.sha256(step.read_bytes()).hexdigest(),
                    "drawing_sha256":hashlib.sha256(drawing.read_bytes()).hexdigest(),
                    "views":[view],"features":[],"dimensions":[],"structure":[],"auxiliary":[]}
        report=verify_views(step,drawing,prediction)
        self.assertEqual(report["status"],"views_verified",report)


if __name__=="__main__":unittest.main()
