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
    require(registry["schema_version"] in ("benchcad-3d2d-registry/1", "benchcad-3d2d-registry/2"), "Unknown registry schema")
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
        require(case["schema_version"] in ("benchcad-3d2d-source/1", "benchcad-3d2d-source/2"), f"Unknown schema: {cid}")
        for field in ("case_id", "source_case_number", "pilot_group", "status"):
            require(case[field] == entry[field], f"Registry mismatch: {cid}.{field}")
        require(case["source_case_number"] == int(cid[-3:]), f"Source number mismatch: {cid}")
        if case["schema_version"] == "benchcad-3d2d-source/1":
            require(case["status"] == "source_collected", f"Unsupported source lifecycle state: {cid}")
            require(case["pairing_verified"] is False and case["gt_extracted"] is False,
                    f"Readiness claims require a versioned validation contract: {cid}")
            require(case["input_step"] is None and case["gt_source"] is None,
                    f"Selected pairs require a versioned validation contract: {cid}")
        else:
            require(registry["schema_version"] == "benchcad-3d2d-registry/2", "Selected cases require registry/2")
            require(case["status"] == "development_ready", f"Unknown selected-case lifecycle state: {cid}")
            require(case["pairing_verified"] is True and case["gt_extracted"] is True, "Incomplete selected case")
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
        artifacts = verify_selected_case(case_dir, case) if case["schema_version"] == "benchcad-3d2d-source/2" else set()
        all_files = {p.resolve() for p in case_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        require(all_files == listed | artifacts | {(case_dir / "case.json").resolve()},
                f"Unexpected files in case: {cid}")

    directories = {p.name for p in (ROOT / "cases").iterdir() if p.is_dir()}
    require(case_ids == directories, "Registry does not match case directories")
    require(bool(case_ids), "Empty source registry")
    print(f"PASS: {len(case_ids)} cases, {total_files} CAD files, {total_bytes:,} bytes")
    print("Source integrity only; CAD pairing, feature GT, and model scoring are not checked.")


def verify_selected_case(case_dir, case):
    """Verify immutable readiness evidence links; CAD comparison is a separate job."""
    paths = set()
    allowed = {"input/model.step", "gt/gt.json", "gt/reconstruction.py", "gt/native_features.json",
               "gt/native_export.step", "gt/validation.json", "README.md", "preview.png"}
    require({a["path"] for a in case["artifacts"]} == allowed, "Selected artifact set is incomplete or unsupported")
    for artifact in case["artifacts"]:
        path = safe_path(case_dir, artifact["path"])
        require(path not in paths, f"Duplicate selected artifact: {path}")
        require(path.is_file(), f"Missing selected artifact: {path}")
        data = path.read_bytes()
        require(len(data) == artifact["bytes"], f"Selected artifact size mismatch: {path}")
        require(hashlib.sha256(data).hexdigest() == artifact["sha256"], f"Selected artifact hash mismatch: {path}")
        paths.add(path)
    require(case["input_step"] == "input/model.step" and case["gt_file"] == "gt/gt.json"
            and case["validation_file"] == "gt/validation.json", "Invalid selected-case paths")
    native_source = next((a for a in case["files"] if a["path"] == case["gt_source"]), None)
    require(native_source is not None and native_source["kind"] == "sldprt", "Invalid selected native source")
    input_hash = hashlib.sha256((case_dir / case["input_step"]).read_bytes()).hexdigest()
    require(any(a["kind"] == "step" and a["sha256"] == input_hash for a in case["files"]), "Input is not an original source STEP")
    gt = read_json(case_dir / case["gt_file"])
    validation = read_json(case_dir / case["validation_file"])
    require(gt["case_id"] == case["case_id"] == validation["case_id"], "Selected-case ID mismatch")
    require(gt["geometry"]["input_sha256"] == input_hash == validation["input_sha256"], "GT/input evidence mismatch")
    for key, relative in (("gt_sha256", "gt/gt.json"), ("native_features_sha256", "gt/native_features.json"),
                          ("native_export_sha256", "gt/native_export.step"), ("reconstruction_sha256", "gt/reconstruction.py")):
        require(validation[key] == hashlib.sha256((case_dir/relative).read_bytes()).hexdigest(), f"Validation artifact mismatch: {relative}")
    require(validation["native_source_sha256"] == native_source["sha256"], "Wrong native validation source")
    require(validation["valid"] is True and validation["calibrated"] is False, "Invalid development validation state")
    require(validation["review_status"] == "geometric and developer review; expert calibration pending", "Unsupported review status")
    return paths


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
