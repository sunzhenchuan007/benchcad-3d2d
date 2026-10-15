#!/usr/bin/env python3
"""Derive an unscored drawing manifest from trusted normalized CAD JSONL.

No CAD vendor adapter, DXF geometry verification, or GT matching is provided.
See docs/OPERATION_LOG_DERIVATION.md for the trust boundary and wire contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator, Protocol


LOG_SCHEMA = "benchcad-cad-events/1"
MANIFEST_SCHEMA = "benchcad-derived-drawing/1"


class LogError(ValueError):
    """Invalid, unsupported, or over-budget input; never a scoring result."""


@dataclass(frozen=True)
class Limits:
    max_line_bytes: int = 8 * 1024 * 1024
    max_total_bytes: int = 1024 * 1024 * 1024
    max_events: int = 2_000_000
    max_views: int = 10_000

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in vars(self).values()):
            raise LogError("all limits must be positive integers")


class EventAdapter(Protocol):
    """Extension point: vendor records -> normalized events, incrementally.

    Adapters must emit the same contract as NormalizedJSONLAdapter. They must
    obtain successful results and final snapshots from the trusted CAD backend,
    not reconstruct geometry from chat text or intended tool calls.
    """

    def events(self, stream: BinaryIO, limits: Limits) -> Iterable[dict]: ...


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LogError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class NormalizedJSONLAdapter:
    """Reference adapter only; raw CAD/chat transcripts are not supported."""

    def __init__(self):
        self.sha256 = None

    def events(self, stream: BinaryIO, limits: Limits) -> Iterator[dict]:
        total = 0
        count = 0
        digest = hashlib.sha256()
        self.sha256 = None
        while True:
            # Bounded readline avoids loading an unbounded line into RAM.
            raw = stream.readline(limits.max_line_bytes + 1)
            if not raw:
                break
            total += len(raw)
            count += 1
            if len(raw) > limits.max_line_bytes:
                raise LogError(f"line {count}: line byte limit exceeded")
            if total > limits.max_total_bytes or count > limits.max_events:
                raise LogError(f"line {count}: total log budget exceeded")
            digest.update(raw)
            try:
                event = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                                   parse_constant=lambda _: (_ for _ in ()).throw(
                                       LogError("non-finite JSON number")))
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise LogError(f"line {count}: invalid JSON: {exc}") from exc
            if not isinstance(event, dict):
                raise LogError(f"line {count}: event must be an object")
            yield event
        self.sha256 = digest.hexdigest()


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise LogError(f"{name} must be a nonempty string <= 512 characters")
    return value


def _sha(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(
            ch not in "0123456789abcdef" for ch in value):
        raise LogError(f"{name} must be a lowercase SHA-256")
    return value


def _integer(value, name):
    if type(value) is not int or value < 0:
        raise LogError(f"{name} must be a nonnegative integer")
    return value


def _vector(value, name, unit=False):
    if not isinstance(value, list) or len(value) != 3:
        raise LogError(f"{name} must contain three finite numbers")
    try:
        valid = all(type(v) in (int, float) and math.isfinite(v) for v in value)
    except OverflowError:
        valid = False
    if not valid:
        raise LogError(f"{name} must contain three finite numbers")
    if unit and abs(math.hypot(*value) - 1) > 1e-6:
        raise LogError(f"{name} must be a unit vector")
    return list(value)


def _handles(value, name):
    if not isinstance(value, list):
        raise LogError(f"{name} must be a list")
    result = []
    for item in value:
        if not isinstance(item, str) or not item or len(item) > 32 or any(
                c not in "0123456789abcdefABCDEF" for c in item):
            raise LogError(f"{name} contains an invalid DXF handle")
        result.append(item.upper())
    return sorted(set(result))


def _view(value):
    if not isinstance(value, dict):
        raise LogError("view must be an object")
    result = {"id": _text(value.get("id"), "view.id")}
    kind = value.get("kind")
    if kind not in ("projection", "section"):
        raise LogError("unsupported view kind")
    result["kind"] = kind
    if kind == "section":
        section = value.get("section")
        if not isinstance(section, dict) or section.get("type") != "full":
            raise LogError("v1 supports planar full sections only; adapter extension needed")
        plane = section.get("plane")
        if not isinstance(plane, dict):
            raise LogError("section.plane must be an object")
        result["section"] = {"type": "full", "plane": {
            "point_mm": _vector(plane.get("point_mm"), "plane.point_mm"),
            "normal": _vector(plane.get("normal"), "plane.normal", unit=True)}}
    elif "section" in value:
        raise LogError("projection views cannot contain section definitions")
    evidence = value.get("dxf_evidence", {})
    if not isinstance(evidence, dict):
        raise LogError("dxf_evidence must be an object")
    result["dxf_evidence"] = {
        key: _handles(evidence.get(key, []), key)
        for key in ("view_handles", "cutting_line_handles", "label_handles")}
    return result


def derive(events: Iterable[dict], *, run_id: str, case_id: str,
           input_sha256: str, dxf_sha256: str, limits: Limits = Limits()) -> dict:
    """Reduce bounded normalized events; the selected export freezes its state.

    Caller-supplied identities must come from the orchestrator. A log claiming
    to be trusted does not authenticate itself. No GT is read by this function.
    """
    _text(run_id, "run_id")
    _text(case_id, "case_id")
    _sha(input_sha256, "input_sha256")
    _sha(dxf_sha256, "dxf_sha256")
    previous_seq = -1
    count = 0
    started = False
    finalized = False
    revision = -1
    snapshot_revision = None
    views = {}
    exported = None
    for event in events:
        count += 1
        if count > limits.max_events:
            raise LogError("event count limit exceeded")
        if not isinstance(event, dict) or event.get("run_id") != run_id:
            raise LogError("event object/run_id mismatch")
        seq = _integer(event.get("seq"), "seq")
        if seq <= previous_seq:
            raise LogError("seq must strictly increase")
        previous_seq = seq
        if type(event.get("success")) is not bool:
            raise LogError("success must be a boolean")
        kind = event.get("kind")
        if kind not in {"run_started", "telemetry", "view_upsert", "view_delete",
                        "drawing_snapshot", "dxf_export", "submission_finalized"}:
            raise LogError(f"unsupported event kind: {kind!r}")
        if not started:
            if kind != "run_started" or not event["success"]:
                raise LogError("first event must be successful run_started")
            if (event.get("schema_version") != LOG_SCHEMA
                    or event.get("case_id") != case_id
                    or event.get("input_sha256") != input_sha256
                    or event.get("units") != "mm"
                    or event.get("frame") != "input_step"):
                raise LogError("run metadata/schema/frame mismatch")
            started = True
            continue
        if kind == "run_started":
            raise LogError("multiple run_started events")
        if kind == "telemetry":
            continue
        if finalized:
            raise LogError("non-telemetry event after submission_finalized")
        if not event["success"]:
            continue  # Failed commands never alter the drawing state.
        if kind in ("view_upsert", "view_delete", "drawing_snapshot"):
            new_revision = _integer(event.get("document_revision"), "document_revision")
            if new_revision < revision or (kind != "drawing_snapshot" and new_revision == revision):
                raise LogError("document revision must advance for mutations")
            old_revision = revision
            previous_views = views
            revision = new_revision
            snapshot_revision = None
            if kind == "view_upsert":
                view = _view(event.get("view"))
                views[view["id"]] = view
            elif kind == "view_delete":
                identifier = _text(event.get("view_id"), "view_id")
                if identifier not in views:
                    raise LogError("delete references unknown view")
                del views[identifier]
            else:
                records = event.get("views")
                if not isinstance(records, list) or len(records) > limits.max_views:
                    raise LogError("invalid snapshot/views limit exceeded")
                views = {}
                for record in records:
                    view = _view(record)
                    if view["id"] in views:
                        raise LogError("duplicate view id in snapshot")
                    views[view["id"]] = view
                if old_revision == revision and views != previous_views:
                    raise LogError("snapshot changes state without advancing document revision")
                snapshot_revision = revision
            if len(views) > limits.max_views:
                raise LogError("active view limit exceeded")
        elif kind == "dxf_export":
            export_id = _text(event.get("export_id"), "export_id")
            export_revision = _integer(event.get("document_revision"), "document_revision")
            if export_revision != revision:
                raise LogError("export revision does not match current document")
            export_hash = _sha(event.get("dxf_sha256"), "export.dxf_sha256")
            exported = {"export_id": export_id, "document_revision": revision,
                        "dxf_sha256": export_hash, "export_seq": seq,
                        "snapshot_bound": snapshot_revision == revision,
                        "views": list(views.values())}
        elif kind == "submission_finalized":
            if exported is None or event.get("export_id") != exported["export_id"]:
                raise LogError("submission must select the latest successful export")
            if exported["dxf_sha256"] != dxf_sha256:
                raise LogError("submitted DXF hash differs from selected export")
            finalized = True
    if not started or not finalized or exported is None:
        raise LogError("missing run start, selected export, or submission finalization")
    issues = []
    if not exported["snapshot_bound"]:
        issues.append("missing_final_snapshot")
    if not exported["views"]:
        issues.append("no_views_recorded")
    for view in exported["views"]:
        required = ["view_handles"]
        if view["kind"] == "section":
            required += ["cutting_line_handles", "label_handles"]
        if any(not view["dxf_evidence"][key] for key in required):
            issues.append(f"missing_dxf_references:{view['id']}")
    return {
        "schema_version": MANIFEST_SCHEMA,
        "status": "incomplete" if issues else "derived",
        "run_id": run_id, "case_id": case_id, "input_sha256": input_sha256,
        "units": "mm", "frame": "input_step",
        "source": {key: exported[key] for key in (
            "export_id", "document_revision", "dxf_sha256", "export_seq", "snapshot_bound")},
        "views": sorted(exported["views"], key=lambda view: view["id"]),
        "issues": issues,
        "evidence_status": "not_checked",
        "scoring_status": "not_scored",
        "events_processed": count,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--dxf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--input-sha256", required=True)
    for name, default in vars(Limits()).items():
        parser.add_argument("--" + name.replace("_", "-"), type=int, default=default)
    args = parser.parse_args(argv)
    try:
        if args.output.resolve() in {args.log.resolve(), args.dxf.resolve()}:
            raise LogError("output must differ from log and DXF")
        if args.output.exists():
            raise LogError("output already exists; use a fresh evaluator artifact path")
        limits = Limits(**{name: getattr(args, name) for name in vars(Limits())})
        adapter = NormalizedJSONLAdapter()
        with args.log.open("rb") as stream:
            result = derive(adapter.events(stream, limits),
                            run_id=args.run_id, case_id=args.case_id,
                            input_sha256=args.input_sha256,
                            dxf_sha256=sha256_file(args.dxf), limits=limits)
        result["source"]["operation_log_sha256"] = adapter.sha256
        # Never overwrite another run's artifact, even if the path races.
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        print(f"{result['status']}: {len(result['views'])} views; evidence not checked; not scored")
        return 0 if result["status"] == "derived" else 2
    except (LogError, OSError) as exc:
        print(f"derivation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
