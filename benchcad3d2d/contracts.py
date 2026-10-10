"""Runtime checks for the deliberately small v0.1 contract."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def number(value, where):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value), f"{where}: expected finite number")
    return float(value)


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda s: (_ for _ in ()).throw(ContractError(f"Invalid number: {s}")))


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def validate_rules(rules):
    require(rules.get("schema_version") == "benchcad-3d2d-rules/0.2", "Unknown rule version")
    require(rules.get("units") == "mm", "v0.1 supports mm only")
    require(set(rules["weights"]) == {"features", "dimensions", "views", "efficiency"}, "Invalid weights")
    require(all(number(v, "weight") >= 0 for v in rules["weights"].values()), "Negative weight")
    require(abs(sum(rules["weights"].values()) - 1) < 1e-9, "Weights must sum to one")
    for key in ("value_absolute_mm", "value_relative", "equation_consistency_mm", "drawing_coordinates_mm", "direction_degrees"):
        require(number(rules["tolerances"][key], key) > 0, "Tolerances must be positive")
    mark = rules["section_marking"]
    require(number(mark["budget_points"], "budget") > 0, "Invalid marking budget")
    for key, value in mark.items():
        require(number(value, key) >= 0, "Negative marking penalty")
    require(0 <= number(rules["view_geometry_fraction"], "view_geometry_fraction") <= 1, "Invalid view split")
    require(0 < number(rules["matrix_rank_rcond"], "matrix_rank_rcond") < 1, "Invalid matrix rank threshold")
    require(number(rules["readability"]["budget_points"], "readability budget") > 0, "Invalid readability budget")
    require(number(rules["readability"]["collision_points"], "collision penalty") > 0, "Invalid collision penalty")
    require(number(rules["readability"]["clearance_mm"], "readability clearance") >= 0, "Invalid clearance")
    require(rules.get("unsupported_blocks_completion") is True, "Unsupported items cannot pass")
    require(rules.get("efficiency_requires_complete") is True, "Efficiency requires completeness")
    for key in ("variables", "annotations"):
        value = rules["limits"][key]
        require(isinstance(value, int) and 0 < value <= 10000, "Invalid resource limit")


def validate(gt, prediction, rules):
    validate_rules(rules)
    for document, fields, label in (
        (gt, ("schema_version", "case_id", "units", "geometry", "variables", "required_variables", "entities", "structure"), "GT"),
        (prediction, ("schema_version", "case_id", "units", "features", "views", "dimensions", "structure"), "prediction"),
    ):
        require(isinstance(document, dict) and all(field in document for field in fields), f"{label}: missing required fields")
    require(gt.get("schema_version") == "benchcad-3d2d-gt/0.1", "Unknown GT version")
    require(prediction.get("schema_version") == "benchcad-3d2d-prediction/0.1", "Unknown prediction version")
    require(gt["case_id"] == prediction["case_id"], "Case ID mismatch")
    require(gt.get("units") == prediction.get("units") == rules["units"], "Unit mismatch")
    variables = gt["variables"]
    anchors = gt["geometry"].get("anchors", {})
    require(isinstance(variables, dict) and variables, "Empty variable table")
    require(not set(anchors) & set(variables), "Datum anchors cannot prefill target variables")
    require(len(variables) <= rules["limits"]["variables"], "Too many variables")
    for name, definition in variables.items():
        require(isinstance(name, str) and name, "Invalid variable ID")
        number(definition["value"], name)
    for name, value in anchors.items():
        number(value, name)
    required = gt["required_variables"]
    require(isinstance(required, list) and required and len(set(required)) == len(required), "Invalid required_variables")
    require(set(required) <= set(variables), "Unknown required variable")
    views = prediction.get("views", [])
    require(isinstance(views, list), "views must be an array")
    view_ids = [v["id"] for v in views]
    require(len(set(view_ids)) == len(view_ids), "Duplicate view ID")
    annotations = prediction.get("dimensions", []) + prediction.get("structure", [])
    require(len(annotations) <= rules["limits"]["annotations"], "Too many annotations")
    ids = [a["id"] for a in annotations]
    require(all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids), "Invalid/duplicate annotation ID")
    for annotation in annotations:
        require(annotation.get("view_id") in view_ids, "Annotation references unknown view")
    feature_ids = [f["id"] for f in prediction.get("features", [])]
    require(all(isinstance(i, str) and i for i in feature_ids) and len(feature_ids) == len(set(feature_ids)), "Invalid/duplicate feature ID")
    entity_ids = [e["id"] for e in gt["entities"]]
    require(len(entity_ids) == len(set(entity_ids)), "Duplicate GT entity ID")
    require(all(s["entity"] in entity_ids for s in gt["structure"]), "Structure references unknown GT entity")
