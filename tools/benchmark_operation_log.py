#!/usr/bin/env python3
"""Synthetic streaming benchmark; not CAD or DXF validation.

Run from the repository: python tools/benchmark_operation_log.py
Generation is excluded; timings include tracemalloc overhead and log hashing.
The peak measures Python allocations only, not total process/container memory.
"""

import argparse
import json
import platform
import tempfile
import time
import tracemalloc
from pathlib import Path

from operation_log_manifest import LOG_SCHEMA, Limits, NormalizedJSONLAdapter, derive


def measure(count):
    def event(seq, kind, **fields):
        return dict(run_id="synthetic", seq=seq, kind=kind, success=True, **fields)

    def view(identifier):
        return dict(id=identifier, kind="section",
                    section=dict(type="full", plane=dict(point_mm=[0, 0, 30], normal=[0, 0, 1])),
                    dxf_evidence=dict(view_handles=["A1"], cutting_line_handles=["B1"],
                                      label_handles=["C1"]))

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic.jsonl"
        views = {}
        revision = 0
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            def write(record):
                stream.write(json.dumps(record) + "\n")
            write(event(0, "run_started", schema_version=LOG_SCHEMA, case_id="synthetic",
                        input_sha256="a" * 64, units="mm", frame="input_step"))
            for seq in range(1, count + 1):
                if seq % 100 == 0:
                    revision += 1
                    identifier = f"view-{(seq // 100) % 10}"
                    record = view(identifier)
                    record["section"]["plane"]["point_mm"][2] = seq % 200
                    views[identifier] = record
                    write(event(seq, "view_upsert", document_revision=revision, view=record))
                else:
                    write(event(seq, "telemetry", message="synthetic CAD timing"))
            write(event(count + 1, "drawing_snapshot", document_revision=revision,
                        views=list(views.values())))
            write(event(count + 2, "dxf_export", document_revision=revision,
                        export_id="export-1", dxf_sha256="b" * 64))
            write(event(count + 3, "submission_finalized", export_id="export-1"))
        tracemalloc.start()
        started = time.perf_counter()
        adapter = NormalizedJSONLAdapter()
        with path.open("rb") as stream:
            result = derive(adapter.events(stream, Limits()), run_id="synthetic",
                            case_id="synthetic", input_sha256="a" * 64, dxf_sha256="b" * 64)
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return dict(events=result["events_processed"], bytes=path.stat().st_size,
                    seconds=round(elapsed, 3), python_peak_mib=round(peak / 1024**2, 3),
                    final_views=len(result["views"]), status=result["status"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", nargs="+", type=int, default=[10_000, 100_000, 500_000])
    args = parser.parse_args()
    if any(n < 1000 or n + 4 > Limits().max_events for n in args.events):
        parser.error("event counts must be between 1000 and max_events - 4")
    print(json.dumps(dict(python=platform.python_version(), platform=platform.platform(),
                          results=[measure(count) for count in args.events]), indent=2))


if __name__ == "__main__":
    main()
