"""Recompute native-input/CQ geometry comparisons and the stored GT; no SOLIDWORKS needed."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchcad3d2d.contracts import read_json, validate
from tools.build_case84 import CASE, build, draw


def verify(out):
    gt, validation=build(out,publish_metadata=False)
    if gt != read_json(CASE/"gt/gt.json"):
        raise ValueError("Stored GT differs from audited native-derived GT")
    prediction=read_json(out/"submissions/good/prediction.json")
    validate(gt,prediction,read_json(ROOT/"config/rules.v0.2.json"))
    print("PASS: Case 84 native/input/CQ geometry, stored GT and 12 controlled-DXF variants")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=ROOT/".outputs/case_084_recheck")
    verify(parser.parse_args().out)
