"""Read native features/dimensions and export a comparison STEP, without saving the source.

Requires a licensed local SOLIDWORKS installation and pywin32. This records raw
display dimensions, not an automatic normalized feature-tree interpretation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def extract(source, out):
    import pythoncom
    import win32com.client
    from win32com.client import VARIANT
    def read(obj, name, *args):
        member = getattr(obj, name)
        return member(*args) if callable(member) and not hasattr(member, "_oleobj_") else member
    source = Path(source).resolve(); out = Path(out).resolve()
    if source.suffix.lower() != ".sldprt" or not source.is_file():
        raise ValueError("Expected an existing SLDPRT source")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    out.mkdir(parents=True, exist_ok=True)
    pythoncom.CoInitialize()
    sw = win32com.client.Dispatch("SldWorks.Application")
    errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    doc = sw.OpenDoc6(str(source), 1, 3, "", errors, warnings)  # silent + read-only
    if doc is None:
        raise RuntimeError(f"OpenDoc6 failed: {errors.value}, {warnings.value}")
    try:
        result = {"source_filename": source.name, "source_sha256": before,
                  "solidworks_revision": read(sw, "RevisionNumber"), "units": "SI meters (SystemValue)",
                  "open_errors": errors.value, "open_warnings": warnings.value, "features": []}
        feature = read(doc, "FirstFeature")
        while feature is not None:
            row = {"name": read(feature, "Name"), "type": read(feature, "GetTypeName2"), "dimensions": []}
            try:
                dimension = read(feature, "GetFirstDisplayDimension")
                while dimension is not None:
                    param = read(dimension, "GetDimension2", 0)
                    row["dimensions"].append({"name": read(param, "FullName"), "system_value": read(param, "SystemValue")})
                    dimension = read(feature, "GetNextDisplayDimension", dimension)
            except Exception as exc:
                row["dimension_error"] = str(exc)
            result["features"].append(row)
            feature = read(feature, "GetNextFeature")
        export = out / "native_export.step"
        ok = doc.Extension.SaveAs(str(export), 0, 1, VARIANT(pythoncom.VT_DISPATCH, None), errors, warnings)
        result["export"] = {"saved": bool(ok), "errors": errors.value, "warnings": warnings.value}
        if not ok or errors.value:
            raise RuntimeError(f"STEP export failed: {result['export']}")
        result["export"]["sha256"] = hashlib.sha256(export.read_bytes()).hexdigest()
        if hashlib.sha256(source.read_bytes()).hexdigest() != before:
            raise RuntimeError("Native source changed during read-only extraction")
        (out / "native_features.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result
    finally:
        sw.CloseDoc(read(doc, "GetTitle"))
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = extract(args.source, args.out)
    print(json.dumps({"features": len(result["features"]), "open_warnings": result["open_warnings"], "export": result["export"]}))
