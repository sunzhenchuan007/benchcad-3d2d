"""Build and grade a synthetic CQ/STEP + actual DXF two-hole development case.

Generated artifacts live outside cases/ and do not alter the source-only registry.
Requires cadquery and ezdxf; no SLDPRT or arbitrary-drawing extraction is claimed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchcad3d2d.contracts import read_json
from benchcad3d2d.evaluator import evaluate
from tools.run_framework_demo import write


def make_gt(step_sha256):
    variables = {f"plate.{key}": {"type": "length", "value": value} for key, value in [("length", 120), ("width", 56), ("thickness", 20)]}
    parameters = {"counterbore_diameter": 16, "pilot_diameter": 10, "counterbore_depth": 6, "depth": 15}
    entities = []
    for hid, x in [("H1", -28), ("H2", 28)]:
        entities.append({"id": hid, "type": "stepped_blind_hole", "center": [x, 0, 20], "axis": [0, 0, 1], "parameters": parameters})
        for axis, value in [("x", x), ("y", 0)]:
            variables[f"{hid}.center.{axis}"] = {"axis": axis, "value": value}
        for key, value in parameters.items():
            variables[f"{hid}.{key}"] = {"type": "diameter" if "diameter" in key else "depth", "value": value}
    specs = [
        ("g01", "VIEW_TOP", "length", "x", [[-60,-28],[60,-28]], {"plate.length":1}, 120, [0,-62]),
        ("g02", "VIEW_TOP", "length", "y", [[-60,-28],[-60,28]], {"plate.width":1}, 56, [-75,0]),
        ("g03", "VIEW_SECTION", "length", "y", [[60,0],[60,20]], {"plate.thickness":1}, 20, [75,10]),
        ("g04", "VIEW_TOP", "signed_distance", "x", [[-28,0],[28,0]], {"H1.center.x":-1,"H2.center.x":1}, 56, [0,40]),
        ("g05", "VIEW_SECTION", "diameter", "x", [[-36,18],[-20,18]], {"H1.counterbore_diameter":1}, 16, [-28,46]),
        ("g06", "VIEW_SECTION", "diameter", "x", [[-33,9],[-23,9]], {"H1.pilot_diameter":1}, 10, [-28,30]),
        ("g07", "VIEW_SECTION", "depth", "y", [[20,14],[20,20]], {"H2.counterbore_depth":1}, 6, [85,17]),
        ("g08", "VIEW_SECTION", "depth", "y", [[-23,5],[-23,20]], {"H1.depth":1}, 15, [-75,13]),
        ("g09", "VIEW_TOP", "signed_distance", "x", [[0,0],[-28,0]], {"H1.center.x":1}, -28, [-14,40]),
        ("g10", "VIEW_TOP", "signed_distance", "x", [[0,0],[28,0]], {"H2.center.x":1}, 28, [14,46]),
        ("g14", "VIEW_TOP", "length", "x", [[-60,0],[-28,0]], {"plate.length":0.5,"H1.center.x":1}, 32, [-44,48]),
        ("g15", "VIEW_TOP", "length", "x", [[28,0],[60,0]], {"plate.length":0.5,"H2.center.x":-1}, 32, [44,48])
    ]
    bindings = {ref: {"drawing_block": block, "type": kind, "axis": axis, "anchors": anchors,
                      "terms": terms, "demo_value": value, "demo_position": pos}
                for ref, block, kind, axis, anchors, terms, value, pos in specs}
    bindings["g11"] = {"drawing_block":"VIEW_TOP", "type":"symmetry", "text":"HOLES SYMMETRIC ABOUT X=0", "position":[-53,-38],
                       "required_centerlines":[[[0,-35],[0,35]]], "equations":[{"terms":{"H1.center.x":1,"H2.center.x":1},"value":0}]}
    bindings["g12"] = {"drawing_block":"VIEW_TOP", "type":"alignment", "text":"BOTH HOLE AXES ON Y=0", "position":[-53,-43],
                       "required_centerlines":[[[-45,0],[45,0]]], "equations":[{"terms":{f"{h}.center.y":1},"value":0} for h in ["H1","H2"]]}
    conditions = [{"entity":h,"type":"termination","value":"blind"} for h in ["H1","H2"]]
    bindings["g13"] = {"drawing_block":"VIEW_TOP", "type":"termination", "text":"2X IDENTICAL COUNTERBORED BLIND HOLES", "position":[-53,-48],
                       "value":"blind", "structures":conditions,
                       "equations":[{"terms":{f"H1.{key}":1,f"H2.{key}":-1},"value":0} for key in parameters]}
    edges = []
    for cx in [-28,28]:
        edges += [[[cx-8,20],[cx-8,14]],[[cx+8,20],[cx+8,14]],[[cx-8,14],[cx-5,14]],[[cx+5,14],[cx+8,14]],
                  [[cx-5,14],[cx-5,5]],[[cx+5,14],[cx+5,5]],[[cx-5,5],[cx+5,5]]]
    arrow_segments = [[[x,0],[x,-10]] for x in [-68,68]]
    arrow_heads = [[[x,-10],[x-1.5,-6.5],[x+1.5,-6.5]] for x in [-68,68]]
    return {"schema_version":"benchcad-3d2d-gt/0.1", "case_id":"synthetic_c002_framework", "synthetic":True, "units":"mm",
            "scope":"15 explicit linear length/position parameters, two blind-hole structures and controlled top/full-section DXF",
            "geometry":{"anchors":{"origin.x":0,"origin.y":0,"origin.z":0},"input_sha256":step_sha256,"frame":"plate-centered XY; Z=0 at underside"},
            "variables":variables,"required_variables":list(variables),"entities":entities,"structure":conditions,
            "annotation_bindings":bindings,"reference_view_count":2,
            "view_requirements":[
                {"drawing_block":"VIEW_TOP","type":"orthographic",
                 "segments":[{"layer":"OUTLINE","points":p} for p in [[[-60,-28],[60,-28]],[[60,-28],[60,28]],[[60,28],[-60,28]],[[-60,28],[-60,-28]]]],
                 "circles":[{"center":[x,0],"radius":r} for x in [-28,28] for r in [5,8]]},
                {"drawing_block":"VIEW_SECTION","type":"full_section","parent_block":"VIEW_TOP",
                 "cut_plane":{"point_mm":[0,0,10],"normal":[0,1,0]},"cutting_trace":[[-68,0],[68,0]],
                 "segments":[{"layer":"CUT_EDGE","points":p} for p in edges],"arrow_segments":arrow_segments,"arrow_heads":arrow_heads,
                 "end_labels":[{"text":"A","position":[x,4]} for x in [-68,68]],"section_titles":[{"text":"A-A","position":[-6,35]}]}
            ]}


def draw(gt, folder, variant):
    import ezdxf
    doc = ezdxf.new("R2018"); doc.header["$INSUNITS"] = 4
    doc.styles.get("Standard").dxf.font = "Arial.ttf"
    for layer in ["OUTLINE","HOLE","CUT_EDGE","CENTER","HATCH_SECTION","DIMS","NOTE","CUTTING_PLANE","CUT_ARROW"]:
        doc.layers.new(layer)
    top = doc.blocks.new("VIEW_TOP"); sec = doc.blocks.new("VIEW_SECTION")
    def line(block, points, layer):
        return block.add_line(*points, dxfattribs={"layer":layer})
    for req in gt["view_requirements"]:
        block = top if req["drawing_block"] == "VIEW_TOP" else sec
        for segment in req["segments"]:
            if variant != "fake_section" or block is top:
                line(block, segment["points"], segment["layer"])
        for circle in req.get("circles",[]):
            block.add_circle(circle["center"],circle["radius"],dxfattribs={"layer":"HOLE"})
    for p in [[[0,-35],[0,35]],[[-45,0],[45,0]]]:line(top,p,"CENTER")
    for p in [[[-60,0],[60,0]],[[-60,0],[-60,20]],[[60,0],[60,20]]]:line(sec,p,"OUTLINE")
    for a,b in [(-60,-36),(-20,20),(36,60)]:line(sec,[[a,20],[b,20]],"OUTLINE")
    for x in [-48,-44,-12,-8,4,8,44,48]:
        for z in [3,10,17]:line(sec,[[x,z],[x+2,z+2]],"HATCH_SECTION")
    prediction = {"schema_version":"benchcad-3d2d-prediction/0.1","case_id":gt["case_id"],"units":"mm",
                  "features":[{**copy.deepcopy(e),"id":f"p{i}"} for i,e in enumerate(gt["entities"],1)],
                  "views":[{"id":"top","drawing_block":"VIEW_TOP","type":"orthographic"},
                           {"id":"section","drawing_block":"VIEW_SECTION","type":"full_section","cut_plane":{"point_mm":[0,0,10],"normal":[0,1,0]}}],
                  "dimensions":[],"structure":[]}
    refs = [f"g{i:02}" for i in range(1,9)] + ["g11","g12","g13"]
    if variant == "equivalent_direct":refs = [r for r in refs if r not in ["g04","g11"]] + ["g09","g10"]
    if variant == "equivalent_edge_offsets":refs = [r for r in refs if r not in ["g04","g11"]] + ["g14","g15"]
    if variant in ("redundant_edge_offsets", "conflicting_edge_offsets"):refs += ["g14","g15"]
    if variant == "missing_spacing":refs.remove("g04")
    if variant in ("missing_dimension", "conflict_and_missing", "redundant_and_missing"):
        refs.remove("g03")  # Independent plate thickness is missing.
    if variant in ("redundant_dimension", "redundant_and_missing", "conflicting_dimension", "conflict_and_missing"):
        refs.append("g04")  # A second, actual spacing dimension.
    occurrences = {}
    for ref in refs:
        binding = gt["annotation_bindings"][ref]; block = top if binding["drawing_block"] == "VIEW_TOP" else sec
        view_id = "top" if block is top else "section"
        annotation = {"id":"a_"+ref,"view_id":view_id,"type":binding["type"],"binding_ref":ref}
        occurrences[ref] = occurrences.get(ref, 0)+1
        repeated = occurrences[ref] > 1
        if repeated:annotation["id"] += "_extra"
        if binding["type"] in ["symmetry","alignment","termination"]:
            entity = block.add_text(binding["text"],dxfattribs={"layer":"NOTE","height":2,"insert":binding["position"]})
            if binding["type"] == "termination":annotation["value"] = "blind"
        else:
            points = copy.deepcopy(binding["anchors"])
            if variant == "wrong_anchor" and ref == "g04":points = [[-20,0],[36,0]]
            value = binding["demo_value"]
            text = "%%c"+str(int(abs(value))) if binding["type"] == "diameter" else "<>"
            if variant == "conflicting_edge_offsets" and ref == "g14":value = 34; text = "34"
            position = copy.deepcopy(binding["demo_position"])
            if repeated:
                position[1] = 58
                if variant in ("conflicting_dimension", "conflict_and_missing"):
                    value = 60; text = "60"  # Visible nominal 60 conflicts with visible 56.
            dim = block.add_linear_dim(base=position,p1=points[0],p2=points[1],
                                       angle=0 if binding["axis"] == "x" else 90,text=text,dxfattribs={"layer":"DIMS"},
                                       override={"dimtxt":2.5,"dimasz":1,"dimtad":1})
            dim.render();entity = dim.dimension;annotation["value"] = value
        annotation["drawing_ref"] = entity.dxf.handle
        prediction["structure" if binding["type"] == "termination" else "dimensions"].append(annotation)
    cut_y = 6 if variant == "wrong_cutting_line" else 0
    if variant != "missing_cutting_line":line(top,[[-68,cut_y],[68,cut_y]],"CUTTING_PLANE")
    if variant != "missing_arrows":
        for x in [-68,68]:
            line(top,[[x,0],[x,-10]],"CUT_ARROW")
            top.add_solid([(x,-10),(x-1.5,-6.5),(x+1.5,-6.5)],dxfattribs={"layer":"CUT_ARROW"})
    if variant != "missing_labels":
        for x in [-68,68]:top.add_text("A",dxfattribs={"insert":(x,4),"height":3,"layer":"NOTE"})
    sec.add_text("B-B" if variant == "wrong_title" else "A-A",dxfattribs={"insert":(-6,35),"height":3,"layer":"NOTE"})
    doc.modelspace().add_blockref("VIEW_TOP",(0,0));doc.modelspace().add_blockref("VIEW_SECTION",(0,-140))
    if variant == "redundant_view":
        extra = doc.blocks.new("VIEW_EXTRA");line(extra,[[-60,0],[60,0]],"OUTLINE")
        doc.modelspace().add_blockref("VIEW_EXTRA",(0,-210))
        prediction["views"].append({"id":"extra","drawing_block":"VIEW_EXTRA","type":"orthographic"})
    if variant == "spoofed_plane":prediction["views"][1]["cut_plane"]["point_mm"][1] = 6
    if variant == "missing_feature":prediction["features"] = prediction["features"][:1]
    if variant in ("overlapping_labels", "label_on_outline"):
        target = next(a for a in prediction["dimensions"] if a["binding_ref"] == "g05")
        label = doc.blocks[doc.entitydb[target["drawing_ref"]].dxf.geometry].query("MTEXT").first
        if variant == "overlapping_labels":
            other = next(a for a in prediction["dimensions"] if a["binding_ref"] == "g06")
            other_label = doc.blocks[doc.entitydb[other["drawing_ref"]].dxf.geometry].query("MTEXT").first
            label.dxf.insert = other_label.dxf.insert
        else:label.dxf.insert = (-28,5)  # Text overlaps actual blind-hole floor.
    if variant in ("json_only_dimension", "json_only_note"):
        claims = prediction["structure"] if variant == "json_only_note" else prediction["dimensions"]
        annotation = next(a for a in claims if a["binding_ref"] == ("g13" if variant == "json_only_note" else "g04"))
        block_name, entity = next((b.name, doc.entitydb[annotation["drawing_ref"]]) for b in (top,sec)
                                  if annotation["drawing_ref"] in {e.dxf.handle for e in b})
        doc.blocks[block_name].delete_entity(entity)  # JSON stays unchanged.
    folder.mkdir(parents=True,exist_ok=True);doc.saveas(folder/"drawing.dxf");write(folder/"prediction.json",prediction)
    return prediction


def build(out):
    import cadquery as cq
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    out.mkdir(parents=True,exist_ok=True);input_dir = out/"input";input_dir.mkdir(exist_ok=True)
    solid = cq.Workplane("XY").box(120,56,20,centered=(True,True,False))
    for x in [-28,28]:
        solid = solid.cut(cq.Workplane("XY",origin=(x,0,5)).circle(5).extrude(15))
        solid = solid.cut(cq.Workplane("XY",origin=(x,0,14)).circle(8).extrude(6))
    step = input_dir/"model.step";cq.exporters.export(solid,str(step));loaded = cq.importers.importStep(str(step))
    cylinders = []
    # Direct shape enumeration avoids Workplane's obsolete HashCode path in
    # existing installations that pair older CadQuery with newer OCP.
    for face in loaded.val().Faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() == GeomAbs_Cylinder:
            cylinder = surface.Cylinder();loc = cylinder.Axis().Location();bbox = face.BoundingBox()
            cylinders.append([round(loc.X(),4),round(loc.Y(),4),round(cylinder.Radius(),4),round(bbox.zmin,4),round(bbox.zmax,4)])
    expected = sorted([[x,0,r,z0,z1] for x in [-28,28] for r,z0,z1 in [(8,14,20),(5,5,14)]])
    shape = loaded.val();expected_volume = 120*56*20-2*math.pi*(25*9+64*6)
    require_ok = shape.isValid() and len(shape.Solids()) == 1 and sorted(cylinders) == expected and abs(shape.Volume()-expected_volume)<1e-5
    if not require_ok:raise RuntimeError("Generated GT and re-imported STEP disagree")
    sha = hashlib.sha256(step.read_bytes()).hexdigest();gt = make_gt(sha)
    write(out/"gt/gt.json",gt)
    write(out/"gt/source_validation.json",{"input_sha256":sha,"valid":shape.isValid(),"solids":1,"cylinders":cylinders,"volume_mm3":shape.Volume(),"analytic_volume_mm3":expected_volume,"source":"explicit equivalent CQ construction; not native extraction"})
    rules = read_json(ROOT/"config/rules.v0.2.json");summary = {}
    variants = ["good","equivalent_direct","missing_spacing","wrong_anchor","missing_cutting_line","wrong_cutting_line","missing_arrows","missing_labels","wrong_title","fake_section","spoofed_plane","redundant_view","missing_feature",
                "redundant_dimension", "conflicting_dimension", "missing_dimension", "conflict_and_missing", "redundant_and_missing", "json_only_dimension", "json_only_note", "overlapping_labels", "label_on_outline", "equivalent_edge_offsets", "redundant_edge_offsets", "conflicting_edge_offsets"]
    for variant in variants:
        folder = out/"submissions"/variant;prediction = draw(gt,folder,variant)
        report = evaluate(gt,prediction,rules,folder/"drawing.dxf",mode="controlled-dxf")
        write(out/"reports"/(variant+".json"),report)
        summary[variant] = {"score":report["score"],"complete":report["whole_drawing_complete"],"status":report["status"],
                            "required_parameters":len(gt["required_variables"]),"correct_parameters":len(report["dimensions"]["correct"]),
                            "issues":[issue for view in report["views"] for issue in view["issues"]]}
        summary[variant].update({"dependency_count":report["dependency_diagnostics"]["dependency_count"],
                                 "dependency_participants":report["dependency_diagnostics"]["participating_annotation_ids"],
                                 "nominal_conflicts":report["drawn_nominal_diagnostics"]["conflicts"],
                                 "missing_variables":report["underdetermined_required_variables"],
                                 "rejected_annotations":report["rejected_annotations"]})
    write(out/"summary.json",summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser();parser.add_argument("--out",type=Path,default=ROOT/".outputs/controlled_c002")
    args = parser.parse_args();print(json.dumps(build(args.out),ensure_ascii=False,indent=2))
