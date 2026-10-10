from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .contracts import ContractError, read_json
from .adapters import ADAPTERS
from .evaluator import evaluate
from .projection import ProjectionUnsupported, geometry_catalog, verify_views


def main(argv=None):
    parser = argparse.ArgumentParser(description="BenchCAD 3D2D development verifier")
    parser.add_argument("command", choices=["verify", "verify-views", "inspect-step"])
    parser.add_argument("--gt", type=Path)
    parser.add_argument("--input-step", type=Path)
    parser.add_argument("--view-tolerance", type=float, default=0.1)
    parser.add_argument("--prediction", type=Path)
    parser.add_argument("--rules", type=Path, default=Path(__file__).resolve().parents[1]/"config/rules.v0.2.json")
    parser.add_argument("--mode", choices=sorted(ADAPTERS), default="relations-only")
    parser.add_argument("--drawing", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect-step":
            if args.input_step is None:
                raise ContractError("inspect-step requires --input-step")
            report = geometry_catalog(args.input_step)
            code = 0
        elif args.command == "verify-views":
            if args.input_step is None or args.drawing is None:
                raise ContractError("verify-views requires --input-step and --drawing")
            if args.prediction is None:
                raise ContractError("verify-views requires --prediction")
            report = verify_views(args.input_step, args.drawing, read_json(args.prediction), args.view_tolerance)
        else:
            if args.gt is None or args.prediction is None:
                raise ContractError("verify requires --gt and --prediction")
            report = evaluate(read_json(args.gt), read_json(args.prediction), read_json(args.rules), args.drawing, args.mode)
        if args.command != "inspect-step":
            code = 3 if report["status"] == "unsupported" else (0 if report["status"] in ("pass", "relations_complete", "views_verified") else 1)
    except ProjectionUnsupported as exc:
        report = {"schema_version": "benchcad-3d2d-view-report/0.1", "status": "unsupported",
                  "score": None, "whole_drawing_complete": False, "error": str(exc)}
        code = 3
    except (ContractError, ValueError, KeyError, TypeError, OSError, AttributeError) as exc:
        report = {"schema_version": "benchcad-3d2d-report/0.2", "status": "invalid_input", "error": str(exc)}
        code = 2
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(text.encode("utf-8"))
        print(json.dumps({k: report[k] for k in ("status", "case_id", "score", "whole_drawing_complete") if k in report}))
        print(args.out.resolve())
    else:
        print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
