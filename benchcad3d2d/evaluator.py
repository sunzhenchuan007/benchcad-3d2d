"""Configurable scoring; relations-only results never claim drawing completion."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .contracts import digest, validate
from .adapters import AdapterUnavailable, EvidenceAdapter, get_adapter
from .linear import check_values, solve
from .dependencies import analyze_dependencies


def equivalent(expected, observed, tolerance):
    if isinstance(expected, bool):
        return expected is observed
    if isinstance(expected, (int, float)):
        return isinstance(observed, (int, float)) and not isinstance(observed, bool) and abs(expected-observed) <= tolerance
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(k in observed and equivalent(v, observed[k], tolerance) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(observed, list) and len(expected) == len(observed) and all(equivalent(a, b, tolerance) for a, b in zip(expected, observed))
    return expected == observed


def feature_match(gt, prediction, tolerance):
    expected = [e for e in gt.get("entities", []) if e.get("score", True)]
    observed = prediction.get("features", [])
    fields = ("type", "center", "axis", "diameter", "depth", "parameters")
    candidates = {i: [j for j, feature in enumerate(observed)
                       if all(k in feature and equivalent(entity[k], feature[k], tolerance)
                              for k in fields if k in entity)] for i, entity in enumerate(expected)}
    # Augmenting paths give maximum one-to-one matching, independent of claimed IDs.
    owners = {}
    def assign(i, visited):
        for j in candidates[i]:
            if j in visited:
                continue
            visited.add(j)
            if j not in owners or assign(owners[j], visited):
                owners[j] = i
                return True
        return False
    for i in range(len(expected)):
        assign(i, set())
    pairs = {expected[i]["id"]: observed[j]["id"] for j, i in owners.items()}
    matched = len(pairs)
    score = 2*matched/(len(expected)+len(observed)) if expected or observed else 1.0
    return {"score": score, "matched": pairs,
            "missing": [e["id"] for e in expected if e["id"] not in pairs],
            "extra": [f["id"] for f in observed if f["id"] not in pairs.values()]}


def evaluate(gt, prediction, rules, drawing=None, mode="relations-only", *,
             evidence_adapter: EvidenceAdapter | None = None):
    validate(gt, prediction, rules)
    collector = get_adapter(mode) if evidence_adapter is None else evidence_adapter
    drawing_mode = mode != "relations-only"
    adapter_available = True
    try:
        evidence = collector(gt, prediction, Path(drawing) if drawing is not None else None, rules)
    except AdapterUnavailable as exc:
        adapter_available = False
        evidence = {"equations": [], "structures": [], "rejected": [],
                    "unsupported": [{"type": "adapter_not_implemented", "adapter": mode, "reason": str(exc)}],
                    "views": [], "drawing_verified": False, "view_count": 0}
    tolerance = rules["tolerances"]
    anchors = gt["geometry"].get("anchors", {})
    equations = evidence["equations"]
    def resolve(rows):
        return check_values(solve(gt["variables"], anchors, rows, tolerance["equation_consistency_mm"]), gt, tolerance)
    solution = resolve(equations)
    nominal_solution = resolve(evidence.get("nominal_equations", equations))
    dependency_diagnostics = analyze_dependencies(gt["variables"], anchors,
                                                 evidence.get("nominal_equations", equations),
                                                 tolerance["equation_consistency_mm"],
                                                 rules["matrix_rank_rcond"])
    # Determine information availability separately from consistency. A conflict
    # must not hide a simultaneously unconstrained degree of freedom.
    underdetermined = [n for n in gt["required_variables"]
                      if nominal_solution["variables"][n]["underdetermined"]]
    states = solution["variables"]
    for name, nominal in nominal_solution["variables"].items():
        if nominal["status"] == "inconsistent":
            states[name] = {"status": "inconsistent", "proof": []}
    required = gt["required_variables"]
    continuous_correct = [name for name in required if states[name]["status"] == "determined"]
    features = feature_match(gt, prediction, tolerance["value_absolute_mm"])
    structure_results = []
    for requirement in gt.get("structure", []):
        # Controlled tool evidence has canonical geometry-bound entity IDs; JSON-only
        # observations use prediction IDs and must be mapped by feature matching.
        target = (features["matched"].get(requirement["entity"]) if mode == "relations-only" else requirement["entity"])
        valid = any(a.get("entity") == target and a.get("type") == requirement["type"]
                    and a.get("value") == requirement["value"] for a in evidence["structures"])
        structure_results.append({**requirement, "expressed": valid})
    structure_correct = sum(s["expressed"] for s in structure_results)
    dimensions_score = (len(continuous_correct)+structure_correct)/(len(required)+len(structure_results))
    constraints_valid = (not solution["conflicts"] and not solution["global_conflicts"]
                         and not nominal_solution["conflicts"] and not nominal_solution["global_conflicts"])
    all_values_correct = all(item["status"] not in ("wrong", "inconsistent") for item in states.values())
    if dependency_diagnostics["coefficient_rank"] != nominal_solution["rank"]:
        evidence["unsupported"].append({"type":"numerical_and_exact_rank_disagree"})
    relations_complete = (len(continuous_correct) == len(required) and structure_correct == len(structure_results)
                          and constraints_valid and all_values_correct and not evidence["unsupported"] and not evidence["rejected"])
    views = evidence["views"]
    views_complete = bool(views) and all(v["geometry_ok"] and v["marking_complete"]
                                       and v.get("readability_complete", True) for v in views)
    view_parts = []
    for view in views:
        if view["type"] != "full_section":
            part = float(view["geometry_ok"])
        else:
            geometry_fraction = rules["view_geometry_fraction"]
            marking = 1 - view["marking_penalty_points"]/rules["section_marking"]["budget_points"]
            part = geometry_fraction*float(view["geometry_ok"]) + (1-geometry_fraction)*marking
        view_parts.append(part*view.get("readability_score", 1))
    # Average all required view checks. Separate hard gates stop averages masking omissions.
    views_score = sum(view_parts)/len(view_parts) if view_parts else 0
    complete = (drawing_mode and adapter_available and relations_complete and features["score"] == 1
                and views_complete and evidence["drawing_verified"])
    row_count = dependency_diagnostics["constraint_row_count"]
    annotation_efficiency = dependency_diagnostics["coefficient_rank"]/row_count if row_count else 0
    preferred = gt.get("reference_view_count", 1)
    view_efficiency = min(1, preferred/max(1, evidence["view_count"]))
    efficiency = annotation_efficiency*view_efficiency if complete else 0
    components = {"features": features["score"], "dimensions": dimensions_score,
                  "views": views_score, "efficiency": efficiency}
    score = round(100*sum(rules["weights"][k]*v for k, v in components.items()), 4) if drawing_mode and adapter_available else None
    claims = len(prediction["dimensions"])+len(prediction["structure"])
    backed = len(evidence.get("verified_annotation_ids", []))
    return {
        "schema_version": "benchcad-3d2d-report/0.2", "case_id": gt["case_id"],
        "rule_set_id": rules["rule_set_id"], "rules_sha256": digest(rules), "calibrated": rules["calibrated"],
        "gt_sha256": digest(gt), "prediction_sha256": digest(prediction), "mode": mode,
        "verifier_revision": "development-v0.2",
        "drawing_sha256": hashlib.sha256(Path(drawing).read_bytes()).hexdigest() if drawing_mode and adapter_available else None,
        "status": ("unsupported" if not adapter_available else
                   "pass" if complete else ("relations_complete" if mode == "relations-only" and relations_complete else "fail")),
        "complete_within_relation_scope": relations_complete,
        "whole_drawing_complete": complete, "drawing_evidence_checked": evidence["drawing_verified"],
        "drawing_evidence_verified": evidence["drawing_verified"] and not evidence["rejected"] and not evidence["unsupported"] and views_complete,
        "score": score, "components": components, "features": features,
        "dimensions": {"required": required, "correct": continuous_correct, **solution},
        "drawn_nominal_diagnostics": nominal_solution,
        "dependency_diagnostics": dependency_diagnostics,
        "underdetermined_required_variables": underdetermined,
        "annotation_evidence": {"claim_count": claims, "verified_count": backed,
                                "verified_annotation_ids": evidence.get("verified_annotation_ids", []),
                                "verified_claim_fraction": backed/claims if claims and drawing_mode and adapter_available else None},
        "structure": structure_results, "views": views, "rejected_annotations": evidence["rejected"],
        "unsupported": evidence["unsupported"],
        "efficiency": {"score": efficiency, "dependency_count": dependency_diagnostics["dependency_count"],
                       "participating_annotation_ids": dependency_diagnostics["participating_annotation_ids"],
                       "annotation_efficiency": annotation_efficiency,
                       "view_count": evidence["view_count"], "reference_view_count": preferred,
                       "basis": "rank(A) / scalar constraint rows; whole-matrix dependency count, without annotation chronology or deletion"},
        "limitations": ["Linear millimeter constraints only; angles and nonlinear branches unsupported.",
                        "Relations-only mode provides no drawing or model-task completion claim.",
                        "controlled-dxf is a template/binding adapter, not arbitrary CAD drawing interpretation.",
                        "Built-in PDF evidence recognition is an unimplemented fallback interface.",
                        "Native SLDPRT extraction, SLDDRW parsing, GD&T and expert-taste calibration are pending."]
    }
