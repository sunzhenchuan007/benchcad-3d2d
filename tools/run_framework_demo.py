"""Run the repository's existing relation example and a linear symmetry example."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchcad3d2d.contracts import read_json
from benchcad3d2d.evaluator import evaluate


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def legacy_example():
    gt = read_json(ROOT/"examples/dimension_chain/gt.json")
    prediction = read_json(ROOT/"examples/dimension_chain/prediction.json")
    gt["schema_version"] = "benchcad-3d2d-gt/0.1"
    prediction["schema_version"] = "benchcad-3d2d-prediction/0.1"
    gt["entities"][0]["score"] = False  # Original example tests only the hole feature.
    return gt, prediction


def symmetry_example():
    gt = {
        "schema_version": "benchcad-3d2d-gt/0.1", "case_id": "synthetic_symmetric_positions",
        "synthetic": True, "units": "mm", "scope": "Two X coordinates only; not a CAD drawing",
        "geometry": {"anchors": {"origin.x": 0}},
        "variables": {"left_hole.x": {"axis": "x", "value": -28}, "right_hole.x": {"axis": "x", "value": 28}},
        "required_variables": ["left_hole.x", "right_hole.x"], "entities": [], "structure": []
    }
    prediction = {
        "schema_version": "benchcad-3d2d-prediction/0.1", "case_id": gt["case_id"], "units": "mm",
        "features": [], "views": [{"id": "top", "type": "orthographic"}], "structure": [],
        "dimensions": [
            {"id": "spacing", "view_id": "top", "type": "signed_distance", "axis": "x", "from": "left_hole.x", "to": "right_hole.x", "value": 56},
            {"id": "symmetry", "view_id": "top", "type": "linear", "terms": {"left_hole.x": 1, "right_hole.x": 1}, "value": 0}
        ]
    }
    return gt, prediction


def run(out):
    rules = read_json(ROOT/"config/rules.v0.2.json")
    gt, baseline = legacy_example()
    scenarios = {"baseline": copy.deepcopy(baseline)}
    missing = copy.deepcopy(baseline)
    missing["dimensions"] = [d for d in missing["dimensions"] if d["id"] != "d_right"]
    scenarios["missing_position"] = missing
    direct = copy.deepcopy(baseline)
    direct["dimensions"][1] = {"id": "direct_x", "view_id": "top", "type": "signed_distance", "axis": "x", "from": "left.x", "to": "hole_1.center.x", "value": 20}
    scenarios["equivalent_direct"] = direct
    contradiction = copy.deepcopy(baseline)
    contradiction["dimensions"].append({**direct["dimensions"][1], "value": 21})
    scenarios["contradiction"] = contradiction
    redundant = copy.deepcopy(baseline)
    redundant["dimensions"].append(direct["dimensions"][1])
    scenarios["redundant"] = redundant
    missing_structure = copy.deepcopy(baseline); missing_structure["structure"] = []
    scenarios["missing_termination"] = missing_structure
    nonlinear = copy.deepcopy(baseline)
    nonlinear["dimensions"].append({"id": "angle", "view_id": "top", "type": "angle", "value": 90})
    scenarios["unsupported_angle"] = nonlinear
    summary = {}
    for name, prediction in scenarios.items():
        report = evaluate(gt, prediction, rules)
        write(out/"dimension_chain"/name/"gt.json", gt)
        write(out/"dimension_chain"/name/"prediction.json", prediction)
        write(out/"dimension_chain"/name/"report.json", report)
        summary["dimension_chain/"+name] = {"status": report["status"], "drawing_verified": report["drawing_evidence_verified"],
            "missing_or_wrong": {k: v["status"] for k, v in report["dimensions"]["variables"].items() if v["status"] != "determined"},
            "dependencies": report["efficiency"]["dependency_count"],
            "dependency_participants": report["efficiency"]["participating_annotation_ids"]}
    gt, baseline = symmetry_example()
    variants = {"spacing_plus_symmetry": baseline}
    direct = copy.deepcopy(baseline)
    direct["dimensions"] = [
        {"id": "left", "view_id": "top", "type": "signed_distance", "axis": "x", "from": "origin.x", "to": "left_hole.x", "value": -28},
        {"id": "right", "view_id": "top", "type": "signed_distance", "axis": "x", "from": "origin.x", "to": "right_hole.x", "value": 28}
    ]
    variants["two_direct_offsets"] = direct
    missing = copy.deepcopy(baseline); missing["dimensions"] = missing["dimensions"][:1]
    variants["spacing_only_unanchored"] = missing
    for name, prediction in variants.items():
        report = evaluate(gt, prediction, rules)
        write(out/"symmetry"/name/"gt.json", gt); write(out/"symmetry"/name/"prediction.json", prediction)
        write(out/"symmetry"/name/"report.json", report)
        summary["symmetry/"+name] = {"status": report["status"], "rank": report["dimensions"]["rank"],
                                  "complete": report["complete_within_relation_scope"]}
    write(out/"summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path, default=ROOT/".outputs/framework")
    args = parser.parse_args()
    print(json.dumps(run(args.out), ensure_ascii=False, indent=2))
