from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from benchcad3d2d.contracts import ContractError, read_json
from benchcad3d2d.evaluator import evaluate
from benchcad3d2d.linear import solve
from benchcad3d2d.dependencies import analyze_dependencies
from tools.run_framework_demo import legacy_example, symmetry_example

ROOT = Path(__file__).resolve().parents[1]


def workspace_temp():
    base = ROOT/".outputs/test_tmp"
    base.mkdir(parents=True,exist_ok=True)
    directory = tempfile.TemporaryDirectory(dir=base)
    # Cleanup is recursive: verify the absolute target stays in this checkout.
    if not Path(directory.name).resolve().is_relative_to(ROOT.resolve()):
        raise RuntimeError("Test temporary path escapes checkout")
    return directory


class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.rules = read_json(ROOT/"config/rules.v0.2.json")
        self.gt, self.prediction = legacy_example()

    def evaluate(self, prediction=None):
        return evaluate(self.gt, self.prediction if prediction is None else prediction, self.rules)

    def test_original_example_proof_and_scope(self):
        report = self.evaluate()
        self.assertTrue(report["complete_within_relation_scope"])
        self.assertFalse(report["whole_drawing_complete"])
        self.assertIsNone(report["score"])
        self.assertEqual(report["dimensions"]["variables"]["hole_1.center.x"]["proof"], ["d_right", "d_width"])

    def test_missing_dimension_not_filled_from_features_or_gt(self):
        self.prediction["dimensions"] = [d for d in self.prediction["dimensions"] if d["id"] != "d_right"]
        report = self.evaluate()
        self.assertEqual(report["dimensions"]["variables"]["hole_1.center.x"]["status"], "missing")
        self.assertFalse(report["complete_within_relation_scope"])

    def test_equivalent_chain(self):
        self.prediction["dimensions"][1] = {"id":"direct","view_id":"top","type":"signed_distance","axis":"x","from":"left.x","to":"hole_1.center.x","value":20}
        self.assertTrue(self.evaluate()["complete_within_relation_scope"])

    def test_conflicting_component_does_not_poison_independent_axis(self):
        self.prediction["dimensions"].append({"id":"conflict","view_id":"top","type":"signed_distance","axis":"x","from":"left.x","to":"hole_1.center.x","value":21})
        report = self.evaluate()
        self.assertEqual(report["dimensions"]["variables"]["hole_1.center.x"]["status"], "inconsistent")
        self.assertEqual(report["dimensions"]["variables"]["hole_1.center.y"]["status"], "determined")
        self.assertTrue(report["dimensions"]["conflicts"])

    def test_uniquely_determined_but_wrong(self):
        self.prediction["dimensions"][1]["value"] = 31
        report = self.evaluate()
        self.assertEqual(report["dimensions"]["variables"]["hole_1.center.x"]["status"], "wrong")

    def test_structure_is_separate_from_numeric_rank(self):
        self.prediction["structure"] = []
        report = self.evaluate()
        self.assertEqual(len(report["dimensions"]["correct"]), 5)
        self.assertFalse(report["complete_within_relation_scope"])

    def test_matrix_dependency_lists_entire_position_chain(self):
        self.prediction["dimensions"].append({"id":"direct","view_id":"top","type":"signed_distance","axis":"x","from":"left.x","to":"hole_1.center.x","value":20})
        report = self.evaluate()
        self.assertEqual(report["dependency_diagnostics"]["dependency_count"], 1)
        involved = set(report["dependency_diagnostics"]["participating_annotation_ids"])
        self.assertEqual(involved, {"d_right", "direct", "d_width"})

    def test_symmetry_and_direct_offsets_both_determine_pair(self):
        gt, prediction = symmetry_example()
        report = evaluate(gt, prediction, self.rules)
        self.assertTrue(report["complete_within_relation_scope"])
        self.assertEqual(report["dimensions"]["rank"], 2)
        prediction["dimensions"] = prediction["dimensions"][:1]
        report = evaluate(gt, prediction, self.rules)
        self.assertFalse(report["complete_within_relation_scope"])
        self.assertEqual(report["dimensions"]["rank"], 1)

    def test_partial_redundancy_preserves_unanchored_relative_information(self):
        gt, prediction = symmetry_example()
        prediction["dimensions"] = prediction["dimensions"][:1]
        duplicate = copy.deepcopy(prediction["dimensions"][0]); duplicate["id"] = "duplicate_spacing"
        prediction["dimensions"].append(duplicate)
        report = evaluate(gt, prediction, self.rules)
        self.assertEqual(report["dependency_diagnostics"]["dependency_count"], 1)
        self.assertEqual(len(report["dependency_diagnostics"]["participating_annotation_ids"]), 2)
        self.assertFalse(report["complete_within_relation_scope"])

    def test_conflict_does_not_hide_missing_degree_of_freedom(self):
        gt, prediction = symmetry_example()
        prediction["dimensions"] = prediction["dimensions"][:1]
        duplicate = copy.deepcopy(prediction["dimensions"][0]); duplicate["id"] = "conflict"
        duplicate["value"] += 1; prediction["dimensions"].append(duplicate)
        report = evaluate(gt, prediction, self.rules)
        self.assertTrue(report["drawn_nominal_diagnostics"]["conflicts"])
        self.assertEqual(set(report["underdetermined_required_variables"]), set(gt["required_variables"]))

    def test_partial_rank_can_determine_individual_parameter(self):
        report = solve({"x":{},"y":{},"z":{}},{},[
            {"annotation_id":"a","terms":{"x":1},"value":10},
            {"annotation_id":"b","terms":{"y":1,"z":1},"value":20}])
        self.assertEqual(report["variables"]["x"]["value"], 10)
        self.assertEqual(report["variables"]["y"]["status"], "missing")

    def test_dependency_count_and_participants_do_not_require_added_annotation(self):
        rows = [{"annotation_id":"a","terms":{"width":1},"value":50},
                {"annotation_id":"b","terms":{"width":1,"hole":-1},"value":30},
                {"annotation_id":"c","terms":{"hole":1},"value":20}]
        before = analyze_dependencies({"width":{},"hole":{}},{},rows)
        after = analyze_dependencies({"width":{},"hole":{}},{},list(reversed(rows)))
        self.assertEqual(before,after)
        self.assertEqual(before["dependency_count"],1)
        self.assertEqual(before["participating_annotation_ids"],["a","b","c"])
        renamed = [{**r,"annotation_id":{"a":"z","b":"y","c":"x"}[r["annotation_id"]]} for r in rows]
        report = analyze_dependencies({"width":{},"hole":{}},{},renamed)
        self.assertEqual(report["dependency_count"],1)
        self.assertEqual(report["participating_annotation_ids"],["x","y","z"])
        for proof in report["certificates"]:
            self.assertLess(proof["coefficient_residual"],1e-10)
            self.assertLess(abs(proof["weighted_value_residual_mm"]),1e-10)
        rows[-1]["value"] = 21
        conflict = analyze_dependencies({"width":{},"hole":{}},{},rows)
        self.assertEqual(conflict["certificates"][0]["kind"],"conflict")

    def test_redundancy_does_not_recount_downstream_paths(self):
        rows = [{"annotation_id":"a","terms":{"x":1},"value":20},
                {"annotation_id":"b","terms":{"x":1},"value":20},
                {"annotation_id":"c","terms":{"y":1,"x":-1},"value":5},
                {"annotation_id":"d","terms":{"z":1,"y":-1},"value":6}]
        report = analyze_dependencies({"x":{},"y":{},"z":{}},{},rows)
        self.assertEqual(report["dependency_count"],1)
        self.assertEqual(report["participating_annotation_ids"],["a","b"])

    def test_matrix_handles_zero_constraint_system(self):
        report = analyze_dependencies({"x":{}},{},[])
        self.assertEqual(report["coefficient_rank"],0)
        self.assertEqual(report["dependency_count"],0)

    def test_unanchored_inconsistent_component(self):
        rows = [{"annotation_id":"a","terms":{"x":1,"y":-1},"value":10},
                {"annotation_id":"b","terms":{"x":1,"y":-1},"value":11}]
        report = solve({"x":{},"y":{}},{},rows)
        self.assertEqual(report["variables"]["x"]["status"], "inconsistent")

    def test_radius_conversion(self):
        self.prediction["dimensions"][-1]["type"] = "radius"
        self.prediction["dimensions"][-1]["value"] = 5
        self.assertTrue(self.evaluate()["complete_within_relation_scope"])

    def test_unknown_constraint_is_visible_and_blocks_completion(self):
        self.prediction["dimensions"].append({"id":"angle","view_id":"top","type":"angle","value":90})
        report = self.evaluate()
        self.assertFalse(report["complete_within_relation_scope"])
        self.assertEqual(report["unsupported"][0]["id"], "angle")

    def test_mixed_axis_is_rejected(self):
        self.prediction["dimensions"][1]["axis"] = "y"
        self.assertTrue(self.evaluate()["rejected_annotations"])

    def test_nan_and_duplicate_keys_are_rejected(self):
        with workspace_temp() as folder:
            path = Path(folder)/"test.json"
            for content in ['{"x":NaN}', '{"x":1,"x":2}']:
                path.write_text(content)
                with self.assertRaises(ContractError):read_json(path)

    def test_gt_anchors_cannot_prefill_target(self):
        self.gt["geometry"]["anchors"]["hole_1.center.x"] = 20
        with self.assertRaises(ContractError):self.evaluate()

    def test_identity_and_duplicate_ids(self):
        self.prediction["case_id"] = "wrong"
        with self.assertRaises(ContractError):self.evaluate()
        self.prediction["case_id"] = self.gt["case_id"]
        self.prediction["dimensions"].append(copy.deepcopy(self.prediction["dimensions"][0]))
        with self.assertRaises(ContractError):self.evaluate()

    def test_feature_ids_are_matched_by_geometry(self):
        self.prediction["features"][0]["id"] = "my_hole"
        self.prediction["structure"][0]["entity"] = "my_hole"
        report = self.evaluate()
        self.assertTrue(report["complete_within_relation_scope"])
        self.assertEqual(report["features"]["matched"]["hole_1"], "my_hole")

    def test_extra_features_reduce_feature_score(self):
        self.prediction["features"].append({**self.prediction["features"][0],"id":"extra"})
        self.assertLess(self.evaluate()["features"]["score"], 1)

    def test_rule_edit_changes_report_fingerprint(self):
        before = self.evaluate()
        self.rules["tolerances"]["value_absolute_mm"] = 0.2
        self.assertNotEqual(before["rules_sha256"], self.evaluate()["rules_sha256"])

    def test_determinism(self):
        self.assertEqual(self.evaluate(), self.evaluate())


class ControlledDxfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import ezdxf
        except ImportError:
            raise unittest.SkipTest("CAD tests require ezdxf")
        from tools.build_controlled_demo import make_gt, draw
        cls.temp = workspace_temp()
        cls.base = Path(cls.temp.name)
        cls.gt = make_gt("0"*64)
        cls.rules = read_json(ROOT/"config/rules.v0.2.json")
        cls.draw = staticmethod(draw)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_variant(self, name):
        folder = self.base/name
        prediction = self.draw(self.gt, folder, name)
        return evaluate(self.gt, prediction, self.rules, folder/"drawing.dxf", "controlled-dxf")

    def test_trusted_extension_reuses_drawing_scoring_and_failure_gates(self):
        from benchcad3d2d.evidence import collect_dxf
        # Test routing with real DXF evidence; this does not implement PDF recognition.
        for variant in ("good", "conflicting_dimension", "overlapping_labels"):
            with self.subTest(variant=variant):
                folder = self.base/("adapter_"+variant)
                prediction = self.draw(self.gt, folder, variant)
                original = evaluate(self.gt, prediction, self.rules, folder/"drawing.dxf", "controlled-dxf")
                extended = evaluate(self.gt, prediction, self.rules, folder/"drawing.dxf",
                                    "test-dxf", evidence_adapter=collect_dxf)
                for key in ("status", "score", "components", "whole_drawing_complete",
                            "dependency_diagnostics", "drawing_evidence_verified"):
                    self.assertEqual(original[key], extended[key], key)

    def test_good_and_equivalent_actual_drawings(self):
        for name in ["good", "equivalent_direct"]:
            with self.subTest(name=name):
                report = self.run_variant(name)
                self.assertTrue(report["whole_drawing_complete"], report)
                self.assertEqual(len(report["dimensions"]["correct"]), 15)
                self.assertEqual(report["score"], 100)

    def test_missing_cutting_line_deducts_and_blocks(self):
        report = self.run_variant("missing_cutting_line")
        self.assertFalse(report["whole_drawing_complete"])
        self.assertEqual(report["views"][1]["marking_penalty_points"], 10)
        self.assertLess(report["score"], 100)

    def test_actual_dimension_defect_combinations(self):
        baseline = self.run_variant("good")
        for name, redundant, conflict, missing in [
            ("redundant_dimension", True, False, False),
            ("conflicting_dimension", False, True, False),
            ("missing_dimension", False, False, True),
            ("conflict_and_missing", False, True, True),
            ("redundant_and_missing", True, False, True),
        ]:
            with self.subTest(name=name):
                report = self.run_variant(name)
                self.assertEqual(report["dependency_diagnostics"]["dependency_count"], int(redundant or conflict))
                self.assertEqual(bool(report["drawn_nominal_diagnostics"]["conflicts"]), conflict)
                self.assertEqual("plate.thickness" in report["underdetermined_required_variables"], missing)
                self.assertEqual(report["whole_drawing_complete"], not (conflict or missing))
                self.assertLess(report["score"], baseline["score"])
                if conflict:
                    proof = report["drawn_nominal_diagnostics"]["conflicts"][0]["annotation_ids"]
                    self.assertEqual(set(proof), {"a_g04", "a_g04_extra"})
                    self.assertEqual(report["dimensions"]["variables"]["H1.center.x"]["status"], "inconsistent")
                    self.assertTrue(report["rejected_annotations"])
                if conflict or missing:self.assertEqual(report["components"]["efficiency"], 0)

    def test_hole_to_edges_is_equivalent_or_redundant_or_conflicting(self):
        good = self.run_variant("equivalent_edge_offsets")
        self.assertEqual(good["score"],100)
        self.assertTrue(good["whole_drawing_complete"])
        redundant = self.run_variant("redundant_edge_offsets")
        self.assertTrue(redundant["whole_drawing_complete"])
        self.assertEqual(redundant["dependency_diagnostics"]["dependency_count"],2)
        conflict = self.run_variant("conflicting_edge_offsets")
        self.assertFalse(conflict["whole_drawing_complete"])
        self.assertGreater(conflict["drawn_nominal_diagnostics"]["augmented_rank"], conflict["drawn_nominal_diagnostics"]["rank"])

    def test_label_occlusion_is_separate_from_dimension_completeness(self):
        for variant, issue in [("overlapping_labels","text_text_collision"),("label_on_outline","text_line_collision")]:
            with self.subTest(variant=variant):
                report = self.run_variant(variant)
                self.assertEqual(len(report["dimensions"]["correct"]),15)
                self.assertFalse(report["whole_drawing_complete"])
                self.assertLess(report["components"]["views"],1)
                self.assertIn(issue,report["views"][1]["issues"])

    def test_diameters_are_grouped_in_section_without_overlap(self):
        folder = self.base/"grouped_diameters"
        prediction = self.draw(self.gt,folder,"good")
        for ref in ["g05","g06"]:
            annotation = next(a for a in prediction["dimensions"] if a["binding_ref"] == ref)
            self.assertEqual(annotation["view_id"],"section")
        report = evaluate(self.gt,prediction,self.rules,folder/"drawing.dxf","controlled-dxf")
        self.assertTrue(all(v["readability_complete"] for v in report["views"]))

    def test_json_only_claims_do_not_supply_dimensions_or_structures(self):
        report = self.run_variant("json_only_dimension")
        self.assertFalse(report["whole_drawing_complete"])
        self.assertTrue(report["rejected_annotations"])
        self.assertEqual(report["dimensions"]["variables"]["H1.center.x"]["status"], "missing")
        self.assertFalse(report["drawn_nominal_diagnostics"]["conflicts"])
        self.assertEqual(report["annotation_evidence"]["claim_count"], 11)
        self.assertEqual(report["annotation_evidence"]["verified_count"], 10)
        self.assertEqual(report["annotation_evidence"]["verified_claim_fraction"], 10/11)
        report = self.run_variant("json_only_note")
        self.assertFalse(report["whole_drawing_complete"])
        self.assertEqual(sum(s["expressed"] for s in report["structure"]), 0)
        self.assertTrue(report["rejected_annotations"])

    def test_hidden_note_cannot_supply_structure(self):
        import ezdxf
        folder = self.base/"hidden_note";prediction = self.draw(self.gt,folder,"good")
        doc = ezdxf.readfile(folder/"drawing.dxf")
        doc.entitydb[prediction["structure"][0]["drawing_ref"]].dxf.invisible = 1
        doc.saveas(folder/"drawing.dxf")
        report = evaluate(self.gt,prediction,self.rules,folder/"drawing.dxf","controlled-dxf")
        self.assertFalse(report["whole_drawing_complete"])
        self.assertEqual(sum(s["expressed"] for s in report["structure"]), 0)

    def test_marker_components_and_plane_spoof(self):
        for name in ["wrong_cutting_line", "missing_arrows", "missing_labels", "wrong_title", "spoofed_plane"]:
            with self.subTest(name=name):self.assertFalse(self.run_variant(name)["whole_drawing_complete"])

    def test_dimension_anchor_spoof_and_missing_dimension(self):
        self.assertTrue(self.run_variant("wrong_anchor")["rejected_annotations"])
        report = self.run_variant("missing_spacing")
        self.assertEqual(report["dimensions"]["variables"]["H1.center.x"]["status"], "missing")

    def test_declared_section_without_geometry(self):
        self.assertFalse(self.run_variant("fake_section")["views"][1]["geometry_ok"])

    def test_redundant_actual_view_lowers_efficiency(self):
        report = self.run_variant("redundant_view")
        self.assertTrue(report["whole_drawing_complete"])
        self.assertLess(report["components"]["efficiency"], 1)

    def test_json_claim_cannot_use_uninserted_view(self):
        import ezdxf
        folder = self.base/"uninserted"
        prediction = self.draw(self.gt, folder, "good")
        doc = ezdxf.readfile(folder/"drawing.dxf")
        for insert in list(doc.modelspace().query('INSERT[name=="VIEW_TOP"]')):doc.modelspace().delete_entity(insert)
        doc.saveas(folder/"drawing.dxf")
        report = evaluate(self.gt, prediction, self.rules, folder/"drawing.dxf", "controlled-dxf")
        self.assertFalse(report["whole_drawing_complete"])
        self.assertTrue(report["rejected_annotations"])

    def test_rotated_view_is_explicitly_unsupported(self):
        import ezdxf
        folder = self.base/"rotated";prediction = self.draw(self.gt, folder, "good")
        doc = ezdxf.readfile(folder/"drawing.dxf")
        doc.modelspace().query("INSERT").first.dxf.rotation = 90;doc.saveas(folder/"drawing.dxf")
        with self.assertRaisesRegex(ContractError,"Rotated/scaled"):
            evaluate(self.gt,prediction,self.rules,folder/"drawing.dxf","controlled-dxf")

    def test_undeclared_actual_dimension_cannot_be_hidden(self):
        import ezdxf
        folder = self.base/"undeclared";prediction = self.draw(self.gt,folder,"good")
        doc = ezdxf.readfile(folder/"drawing.dxf")
        doc.blocks["VIEW_TOP"].add_linear_dim(base=(0,52),p1=(-28,0),p2=(28,0),angle=0).render()
        doc.saveas(folder/"drawing.dxf")
        report = evaluate(self.gt,prediction,self.rules,folder/"drawing.dxf","controlled-dxf")
        self.assertFalse(report["whole_drawing_complete"])
        self.assertTrue(any(item["type"] == "unverified_drawn_dimension" for item in report["unsupported"]))

    def test_false_display_text_does_not_pass_geometry_only_measurement(self):
        import ezdxf
        folder = self.base/"override";prediction = self.draw(self.gt,folder,"good")
        handle = prediction["dimensions"][0]["drawing_ref"]
        doc = ezdxf.readfile(folder/"drawing.dxf");doc.entitydb[handle].dxf.text = "999"
        doc.saveas(folder/"drawing.dxf")
        report = evaluate(self.gt,prediction,self.rules,folder/"drawing.dxf","controlled-dxf")
        self.assertFalse(report["whole_drawing_complete"])
        self.assertTrue(any("False dimension text" in item["reason"] for item in report["rejected_annotations"]))

    def test_unsupported_half_section_does_not_become_ordinary_view(self):
        folder = self.base/"half_section";prediction = self.draw(self.gt,folder,"good")
        prediction["views"][1]["type"] = "half_section"
        report = evaluate(self.gt,prediction,self.rules,folder/"drawing.dxf","controlled-dxf")
        self.assertFalse(report["whole_drawing_complete"])
        self.assertTrue(any(item["type"] == "unsupported_view_type" for item in report["unsupported"]))

    def test_rendered_label_style_visibility_must_agree(self):
        import ezdxf
        for variant in ["rendered_label", "dimlfac", "invisible"]:
            with self.subTest(variant=variant):
                folder = self.base/variant;prediction = self.draw(self.gt,folder,"good")
                doc = ezdxf.readfile(folder/"drawing.dxf")
                dimension = doc.entitydb[prediction["dimensions"][0]["drawing_ref"]]
                if variant == "rendered_label":
                    label = doc.blocks[dimension.dxf.geometry].query("MTEXT").first
                    label.text = "999"
                elif variant == "dimlfac":
                    override = dimension.override();override.update({"dimlfac":2});override.commit()
                else:
                    dimension.dxf.invisible = 1
                doc.saveas(folder/"drawing.dxf")
                report = evaluate(self.gt,prediction,self.rules,folder/"drawing.dxf","controlled-dxf")
                self.assertFalse(report["whole_drawing_complete"])
                self.assertTrue(report["rejected_annotations"])


if __name__ == "__main__":unittest.main()
