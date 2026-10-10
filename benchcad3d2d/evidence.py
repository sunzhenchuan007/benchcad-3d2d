"""Evidence boundary: JSON-only diagnostics or a narrowly controlled vector DXF.

The controlled adapter requires actual INSERTed views and exact geometric bindings.
It is not a generic DXF/SLDDRW symbol recognizer. Unsupported transforms fail closed.
"""
from __future__ import annotations

import math

from .contracts import ContractError, number, require
from .readability import inspect_labels


SCALARS = {"diameter", "radius", "depth", "length"}


def relation_equations(gt, annotation):
    kind = annotation["type"]
    known = set(gt["variables"]) | set(gt["geometry"].get("anchors", {}))
    if kind == "signed_distance":
        start, end = annotation["from"], annotation["to"]
        require(start != end, "Identical distance endpoints")
        require(annotation.get("axis") in ("x", "y", "z"), "Missing distance axis")
        for name in (start, end):
            axis = gt["variables"].get(name, {}).get("axis", name.rsplit(".", 1)[-1])
            require(axis == annotation["axis"], "Distance mixes axes")
        terms = {start: -1, end: 1}; value = number(annotation["value"], "distance")
    elif kind in SCALARS:
        name = annotation["parameter"]
        expected_kind = gt["variables"].get(name, {}).get("type")
        require(expected_kind == kind or (kind == "radius" and expected_kind == "diameter"), "Scalar type mismatch")
        terms = {name: 1}; value = number(annotation["value"], kind)
        require(value > 0, "Scalar dimensions must be positive")
        if kind == "radius" and expected_kind == "diameter":
            value *= 2
    elif kind == "linear":
        require(isinstance(annotation["terms"], dict) and annotation["terms"], "Empty linear equation")
        terms = {k: number(v, "coefficient") for k, v in annotation["terms"].items()}
        require(any(terms.values()), "Zero linear equation")
        value = number(annotation["value"], "linear value")
    else:
        return None
    require(set(terms) <= known, "Unknown equation variable")
    return [{"terms": terms, "value": value, "annotation_id": annotation["id"]}]


def collect_relations(gt, prediction):
    equations = []; unsupported = []; rejected = []
    for annotation in prediction.get("dimensions", []):
        try:
            result = relation_equations(gt, annotation)
            if result is None:
                unsupported.append({"id": annotation["id"], "type": annotation["type"]})
            else:
                equations.extend(result)
        except (ContractError, KeyError, TypeError, ValueError) as exc:
            rejected.append({"id": annotation["id"], "reason": str(exc)})
    return {"equations": equations, "structures": prediction.get("structure", []),
            "rejected": rejected, "unsupported": unsupported, "views": [],
            "drawing_verified": False, "view_count": len(prediction.get("views", []))}


def near_points(a, b, tol):
    return len(a) == len(b) and all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def segment_matches(entity, endpoints, tol):
    if entity.dxftype() != "LINE":
        return False
    a = list(entity.dxf.start)[:2]; b = list(entity.dxf.end)[:2]
    return ((near_points(a, endpoints[0], tol) and near_points(b, endpoints[1], tol))
            or (near_points(b, endpoints[0], tol) and near_points(a, endpoints[1], tol)))


def collect_dxf(gt, prediction, drawing, rules):
    try:
        import ezdxf
    except ImportError as exc:
        raise ContractError("controlled-dxf requires ezdxf; use an existing CAD environment") from exc
    require(drawing is not None, "controlled-dxf requires --drawing")
    doc = ezdxf.readfile(str(drawing))
    require(doc.header.get("$INSUNITS") == 4, "DXF units must explicitly be millimeters")
    tol = rules["tolerances"]["drawing_coordinates_mm"]
    blocks = {}; unsupported = []; rejected = []; view_reports = []
    for insert in doc.modelspace().query("INSERT"):
        if not insert.dxf.name.startswith("VIEW_"):
            unsupported.append({"type": "unclassified_modelspace_insert", "name": insert.dxf.name})
            continue
        require(insert.dxf.name not in blocks, "Duplicate inserted view")
        require(abs(insert.dxf.rotation) < 1e-9 and all(abs(insert.dxf.get(k, 1)-1) < 1e-9
                for k in ("xscale", "yscale", "zscale")), "Rotated/scaled view INSERT unsupported in controlled-dxf/0.1")
        blocks[insert.dxf.name] = doc.blocks[insert.dxf.name]
    if any(e.dxftype() != "INSERT" for e in doc.modelspace()):
        unsupported.append({"type": "unclassified_modelspace_entities"})
    declared = {v.get("drawing_block") for v in prediction.get("views", [])}
    declarations_ok = declared == set(blocks) and len(declared) == len(prediction.get("views", []))
    entities = {e.dxf.handle: (name, e) for name, block in blocks.items() for e in block}
    prediction_views = {v["id"]: v for v in prediction.get("views", [])}
    equations = []; nominal_equations = []; structures = []; used_handles = set(); verified_ids = []
    bindings = gt.get("annotation_bindings", {})
    for annotation in prediction.get("dimensions", []) + prediction.get("structure", []):
        try:
            binding = bindings.get(annotation.get("binding_ref"))
            if binding is None:
                unsupported.append({"id": annotation["id"], "type": "unregistered_binding"})
                continue
            handle = annotation.get("drawing_ref")
            require(handle in entities, "Annotation has no entity in an inserted view")
            require(handle not in used_handles, "Drawing entity reused for multiple annotation claims")
            block_name, entity = entities[handle]
            view = prediction_views[annotation["view_id"]]
            require(block_name == view["drawing_block"] == binding["drawing_block"], "Wrong annotation view")
            require(annotation["type"] == binding["type"], "Annotation/binding type mismatch")
            if entity.dxftype() == "DIMENSION" and binding["type"] in SCALARS | {"signed_distance"}:
                require((entity.dxf.dimtype & 7) == 0, "Controlled adapter expects linear DIMENSION entities")
                points = [list(entity.dxf.defpoint2)[:2], list(entity.dxf.defpoint3)[:2]]
                expected = binding["anchors"]
                require((near_points(points[0], expected[0], tol) and near_points(points[1], expected[1], tol))
                        or (near_points(points[0], expected[1], tol) and near_points(points[1], expected[0], tol)), "Wrong dimension anchors")
                axis = binding.get("axis", "x")
                expected_angle = 0 if axis == "x" else 90
                require(abs((entity.dxf.angle - expected_angle + 90) % 180 - 90) <= 0.01, "Wrong dimension measurement direction")
                measured = float(entity.get_measurement())
                require(math.isfinite(measured), "Nonfinite DXF measurement")
                require(abs(entity.override().get("dimlfac",1)-1) < 1e-9, "Dimension scale factor unsupported")
                require(not entity.dxf.get("invisible",0) and not doc.layers.get(entity.dxf.layer).is_off()
                        and not doc.layers.get(entity.dxf.layer).is_frozen(), "Dimension is hidden")
                text = str(entity.dxf.get("text", "<>"))
                # Check the actual anonymous graphics block as well as DIMENSION
                # metadata: an independently edited displayed label must not pass.
                rendered = [e for e in doc.blocks[entity.dxf.geometry] if e.dxftype() in ("TEXT","MTEXT")]
                require(len(rendered) == 1, "Rendered dimension label missing or unsupported")
                label_entity = rendered[0]
                require(not label_entity.dxf.get("invisible",0) and not doc.layers.get(label_entity.dxf.layer).is_off(), "Rendered label is hidden")
                label = label_entity.plain_text().strip()
                if binding["type"] == "diameter":
                    require(label.startswith(("Ø","⌀")), "Rendered diameter symbol missing")
                    label = label[1:]
                nominal = number(float(label), "Rendered nominal dimension")
                require(nominal > 0, "Rendered dimension must be positive")
                # The visible, geometry-bound number is diagnostic evidence even
                # when it disagrees with measurement or the submitted JSON. It must
                # never become accepted completeness evidence after rejection.
                sign = 1
                if binding["type"] == "signed_distance":
                    idx = 0 if axis == "x" else 1
                    sign = 1 if expected[1][idx] >= expected[0][idx] else -1
                nominal_equations.append({"terms": binding["terms"], "value": sign*nominal,
                                          "annotation_id": annotation["id"]})
                if binding["type"] == "diameter":
                    require(text.lower().startswith("%%c"), "Diameter symbol missing")
                    require(abs(number(float(text[3:]), "diameter text")-abs(measured)) <= tol, "False diameter text")
                elif text not in ("", "<>"):
                    require(abs(float(text)-abs(measured)) <= tol, "False dimension text override")
                require(abs(nominal-abs(measured)) <= tol, "Rendered label and measurement disagree")
                observed = abs(measured)
                if binding["type"] == "signed_distance":
                    idx = 0 if axis == "x" else 1
                    observed *= 1 if expected[1][idx] >= expected[0][idx] else -1
                require(abs(number(annotation["value"], "declared dimension")-observed) <= tol, "JSON and drawn measurement disagree")
                equations.append({"terms": binding["terms"], "value": observed,
                                  "annotation_id": annotation["id"]})
            elif entity.dxftype() == "TEXT" and binding["type"] in ("symmetry", "alignment", "termination", "structure_note"):
                require(not entity.dxf.get("invisible",0) and not doc.layers.get(entity.dxf.layer).is_off()
                        and not doc.layers.get(entity.dxf.layer).is_frozen(), "Annotation text is hidden")
                require(entity.dxf.text == binding["text"], "Symbol/text does not match controlled vocabulary")
                require(near_points(list(entity.dxf.insert)[:2], binding["position"], tol), "Text attached at wrong location")
                block = blocks[block_name]
                for segment in binding.get("required_centerlines", []):
                    require(any(e.dxf.layer == "CENTER" and segment_matches(e, segment, tol) for e in block), "Associated centerline missing")
                if binding["type"] in ("termination", "structure_note"):
                    require(annotation.get("value") == binding["value"], "Termination declaration mismatch")
                    structures.extend({**condition, "id": annotation["id"]} for condition in binding["structures"])
                    equations.extend({**equation, "annotation_id": annotation["id"]}
                                     for equation in binding.get("equations", []))
                else:
                    equations.extend({**equation, "annotation_id": annotation["id"]}
                                     for equation in binding["equations"])
                nominal_equations.extend({**equation, "annotation_id": annotation["id"]}
                                         for equation in binding.get("equations", []))
            else:
                raise ContractError("Wrong drawing entity type")
            used_handles.add(handle)
            verified_ids.append(annotation["id"])
        except (ContractError, KeyError, TypeError, ValueError, AttributeError) as exc:
            rejected.append({"id": annotation["id"], "reason": str(exc)})

    mark_rules = rules["section_marking"]
    required_blocks = {v["drawing_block"] for v in gt.get("view_requirements", [])}
    for view in prediction.get("views", []):
        if view.get("type") not in ("orthographic", "full_section"):
            unsupported.append({"type": "unsupported_view_type", "id": view["id"]})
        elif view["type"] == "full_section" and view.get("drawing_block") not in required_blocks:
            unsupported.append({"type": "unregistered_section_view", "id": view["id"]})
    for requirement in gt.get("view_requirements", []):
        require(requirement["type"] in ("orthographic", "full_section"), "View requirement type unsupported in controlled-dxf/0.1")
        name = requirement["drawing_block"]
        block = blocks.get(name)
        report = {"drawing_block": name, "type": requirement["type"], "geometry_ok": False,
                  "marking_penalty_points": 0, "marking_complete": True, "issues": []}
        if block is None:
            report["issues"].append("missing_view")
            view_reports.append(report)
            continue
        geometry_ok = True
        for segment in requirement.get("segments", []):
            geometry_ok &= any(e.dxf.layer == segment["layer"] and segment_matches(e, segment["points"], tol) for e in block)
        for circle in requirement.get("circles", []):
            geometry_ok &= any(e.dxftype() == "CIRCLE" and near_points(list(e.dxf.center)[:2], circle["center"], tol)
                               and abs(e.dxf.radius-circle["radius"]) <= tol for e in block)
        if requirement["type"] == "full_section":
            hatch = [e for e in block if e.dxftype() == "LINE" and e.dxf.layer == "HATCH_SECTION"]
            geometry_ok &= len(hatch) >= 6 and any(e.dxf.start.x < 0 for e in hatch) and any(e.dxf.start.x > 0 for e in hatch)
            declaration = next((v for v in prediction["views"] if v.get("drawing_block") == name), {})
            plane = declaration.get("cut_plane", {})
            expected = requirement["cut_plane"]
            normal = plane.get("normal", [])
            point = plane.get("point_mm", [])
            # v0.1 explicitly supports this demo's Y-normal plane only.
            require(expected["normal"] == [0, 1, 0], "Section plane orientation unsupported")
            normal_length = math.sqrt(sum(number(v,"plane normal")**2 for v in normal))
            parallel = (len(normal) == 3 and normal_length > 1e-12 and
                        abs(normal[1])/normal_length >= math.cos(math.radians(rules["tolerances"]["direction_degrees"])))
            geometry_ok &= (len(point) == 3 and abs(point[1]-expected["point_mm"][1]) <= tol and parallel)
            parent = blocks.get(requirement["parent_block"])
            trace = [e for e in parent or [] if e.dxftype() == "LINE" and e.dxf.layer == "CUTTING_PLANE"]
            if not trace:
                report["marking_penalty_points"] = mark_rules["missing_trace_points"]
                report["issues"].append("missing_cutting_trace")
            else:
                trace_ok = any(segment_matches(e, requirement["cutting_trace"], tol) for e in trace)
                if not trace_ok:
                    report["marking_penalty_points"] += mark_rules["wrong_trace_points"]
                    report["issues"].append("wrong_cutting_trace")
                for key, layer, penalty, issue in (
                    ("arrow_segments", "CUT_ARROW", "arrows_points", "missing_or_wrong_arrows"),
                ):
                    ok = all(any(e.dxf.layer == layer and segment_matches(e, segment, tol) for e in parent) for segment in requirement[key])
                    solids = [e for e in parent if e.dxftype() == "SOLID" and e.dxf.layer == layer]
                    for vertices in requirement["arrow_heads"]:
                        ok &= any(all(any(near_points(list(e.dxf.get(f"vtx{i}"))[:2], vertex, tol)
                                          for i in range(4)) for vertex in vertices) for e in solids)
                    if not ok:
                        report["marking_penalty_points"] += mark_rules[penalty]
                        report["issues"].append(issue)
                for key, target, penalty, issue in (
                    ("end_labels", parent, "labels_points", "missing_or_wrong_labels"),
                    ("section_titles", block, "title_points", "missing_or_wrong_title"),
                ):
                    ok = all(any(e.dxftype() == "TEXT" and e.dxf.text == item["text"]
                                 and near_points(list(e.dxf.insert)[:2], item["position"], tol) for e in target)
                             for item in requirement[key])
                    if not ok:
                        report["marking_penalty_points"] += mark_rules[penalty]
                        report["issues"].append(issue)
            report["marking_penalty_points"] = min(mark_rules["budget_points"], report["marking_penalty_points"])
            report["marking_complete"] = not report["issues"]
        declaration = next((v for v in prediction["views"] if v.get("drawing_block") == name), {})
        geometry_ok &= declaration.get("type") == requirement["type"]
        report["geometry_ok"] = bool(geometry_ok and declarations_ok)
        if not report["geometry_ok"]:
            report["issues"].append("wrong_geometry_or_view_declaration")
        report.update(inspect_labels(doc,block,rules["readability"]))
        report["issues"].extend(sorted({issue["type"] for issue in report["readability_issues"]}))
        view_reports.append(report)
    if not declarations_ok:
        rejected.append({"id": "views", "reason": "Declared and inserted drawing views differ"})
    for handle, (name, entity) in entities.items():
        if entity.dxftype() == "DIMENSION" and handle not in used_handles:
            unsupported.append({"type": "unverified_drawn_dimension", "drawing_ref": handle, "drawing_block": name})
    return {"equations": equations, "nominal_equations": nominal_equations, "structures": structures, "rejected": rejected,
            "verified_annotation_ids": verified_ids,
            "unsupported": unsupported, "views": view_reports, "drawing_verified": True,
            "view_count": len(blocks)}
