from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .contracts import ContractError, read_json
from .adapters import ADAPTERS
from .evaluator import evaluate


def main(argv=None):
    parser = argparse.ArgumentParser(description="BenchCAD 3D2D development verifier")
    parser.add_argument("command", choices=["verify"])
    parser.add_argument("--gt", type=Path, required=True)
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--rules", type=Path, default=Path(__file__).resolve().parents[1]/"config/rules.v0.2.json")
    parser.add_argument("--mode", choices=sorted(ADAPTERS), default="relations-only")
    parser.add_argument("--drawing", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = evaluate(read_json(args.gt), read_json(args.prediction), read_json(args.rules), args.drawing, args.mode)
        code = 3 if report["status"] == "unsupported" else (0 if report["status"] in ("pass", "relations_complete") else 1)
    except (ContractError, ValueError, KeyError, TypeError, OSError, AttributeError) as exc:
        report = {"schema_version": "benchcad-3d2d-report/0.2", "status": "invalid_input", "error": str(exc)}
        code = 2
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("status", "case_id", "score", "whole_drawing_complete") if k in report}))
        print(args.out.resolve())
    else:
        print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
