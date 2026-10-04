"""Verify source-package integrity; does not validate CAD geometry or model scores."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {".step": "step", ".stp": "step", ".sldprt": "sldprt"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_path(base: Path, relative: str) -> Path:
    require(isinstance(relative, str) and bool(relative), "Empty or invalid path")
    require("\\" not in relative and ":" not in relative, f"Nonportable path: {relative}")
    rel = Path(relative)
    require(not rel.is_absolute() and ".." not in rel.parts, f"Unsafe path: {relative}")
    result = (base / rel).resolve()
    require(result.is_relative_to(base.resolve()), f"Path escapes case: {relative}")
    return result


def main() -> None:
    registry = read_json(ROOT / "registry.json")
    require(registry["schema_version"] == "benchcad-3d2d-registry/1", "Unknown registry schema")
    case_ids: set[str] = set()
    total_files = 0
    total_bytes = 0
    for entry in registry["cases"]:
        cid = entry["case_id"]
        require(re.fullmatch(r"case_\d{3}", cid) is not None, f"Invalid case ID: {cid}")
        require(cid not in case_ids, f"Duplicate case: {cid}")
        case_ids.add(cid)
        require(entry["path"] == f"cases/{cid}", f"Registry path mismatch: {cid}")
        case_dir = safe_path(ROOT, entry["path"])
        case = read_json(case_dir / "case.json")
        require(case["schema_version"] == "benchcad-3d2d-source/1", f"Unknown schema: {cid}")
        for field in ("case_id", "source_case_number", "pilot_group", "status"):
            require(case[field] == entry[field], f"Registry mismatch: {cid}.{field}")
        require(case["source_case_number"] == int(cid[-3:]), f"Source number mismatch: {cid}")
        require(case["status"] == "source_collected", f"Unsupported source lifecycle state: {cid}")
        require(case["pairing_verified"] is False and case["gt_extracted"] is False,
                f"Readiness claims require a versioned validation contract: {cid}")
        require(case["input_step"] is None and case["gt_source"] is None,
                f"Selected pairs require a versioned validation contract: {cid}")
        require(entry["file_count"] == len(case["files"]), f"File count mismatch: {cid}")

        listed: set[Path] = set()
        kinds: set[str] = set()
        for asset in case["files"]:
            path = safe_path(case_dir, asset["path"])
            require(path.is_relative_to(case_dir / "sources"), f"Asset outside sources: {path}")
            require(path not in listed, f"Duplicate asset path: {path}")
            listed.add(path)
            require(path.is_file(), f"Missing asset: {path}")
            require(path.suffix.lower() in EXTENSIONS, f"Unsupported source file: {path}")
            require(asset["kind"] == EXTENSIONS[path.suffix.lower()], f"Wrong asset kind: {path}")
            require(re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]) is not None,
                    f"Invalid SHA-256: {path}")
            require(asset["source_url"].startswith("https://drive.google.com/"),
                    f"Missing source URL: {path}")
            require(bool(asset["drive_id"]) and bool(asset["original_path"]),
                    f"Missing provenance: {path}")
            content = path.read_bytes()
            require(len(content) == asset["bytes"], f"Size mismatch: {path}")
            require(hashlib.sha256(content).hexdigest() == asset["sha256"], f"Hash mismatch: {path}")
            kinds.add(asset["kind"])
            total_files += 1
            total_bytes += len(content)
        require(kinds == {"step", "sldprt"}, f"Missing source type: {cid}")
        actual = {p.resolve() for p in (case_dir / "sources").rglob("*") if p.is_file()}
        require(actual == listed, f"Unlisted or missing source assets: {cid}")
        all_files = {p.resolve() for p in case_dir.rglob("*") if p.is_file()}
        require(all_files == listed | {(case_dir / "case.json").resolve()},
                f"Unexpected files in case: {cid}")

    directories = {p.name for p in (ROOT / "cases").iterdir() if p.is_dir()}
    require(case_ids == directories, "Registry does not match case directories")
    require(bool(case_ids), "Empty source registry")
    print(f"PASS: {len(case_ids)} cases, {total_files} CAD files, {total_bytes:,} bytes")
    print("Source integrity only; CAD pairing, feature GT, and model scoring are not checked.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
