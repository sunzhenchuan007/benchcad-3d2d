"""Build audited native Case 84 GT and external controlled-DXF validation fixtures."""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases/case_084"
PARAMETER_SOURCES = {
    "base.width_x": ("草图1", "D1@草图1"),
    "base.width_z": ("草图1", "D2@草图1"),
    "neck.width_x": ("草图2", "D1@草图2"),
    "neck.width_z": ("草图2", "D2@草图2"),
    "lower.height": ("凸台-拉伸1", "D1@凸台-拉伸1"),
    "upper.height": ("基准面1", "D1@基准面1"),
}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_parameters(report):
    parameters = {}
    for name, (feature_name, dimension_name) in PARAMETER_SOURCES.items():
        feature = next(f for f in report["features"] if f["name"] == feature_name)
        dimension = next(d for d in feature["dimensions"] if d["name"].startswith(dimension_name + "@"))
        parameters[name] = round(float(dimension["system_value"]) * 1000, 8)
    return parameters


def load_construction():
    spec = importlib.util.spec_from_file_location("case84_construction", CASE / "gt/reconstruction.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def projected_segments(shape, direction, right):
    import cadquery as cq
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    algo = HLRBRep_Algo(); algo.Add(shape.wrapped)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0,0,0), gp_Dir(*direction), gp_Dir(*right))))
    algo.Update(); algo.Hide(); result = HLRBRep_HLRToShape(algo)
    segments = {}
    for layer, methods in (("OUTLINE", ("VCompound", "OutLineVCompound", "Rg1LineVCompound")),
                           ("HIDDEN", ("HCompound",))):
        for method in methods:
            compound = getattr(result, method)()
            if compound.IsNull():
                continue
            for edge in cq.Shape.cast(compound).Edges():
                points = [list(edge.startPoint().toTuple())[:2], list(edge.endPoint().toTuple())[:2]]
                points = sorted([[round(x, 7) for x in p] for p in points])
                if points[0] == points[1]:
                    continue
                key = tuple(tuple(p) for p in points)
                if key not in segments or layer == "OUTLINE":
                    segments[key] = {"layer": layer, "points": points}
    return [segments[k] for k in sorted(segments)]


def make_gt(parameters, shape, input_sha):
    p = parameters
    variables = {name: {"type": "length", "axis": ("z" if name.endswith("_z") else "y" if name.endswith("height") else "x"),
                        "value": value} for name, value in p.items()}
    entities = [
        {"id": "lower", "type": "faceted_rectangle_to_cross", "center": [0,p["lower.height"]/2,0], "axis": [0,1,0],
         "parameters": {name: p[name] for name in p if name != "upper.height"}},
        {"id": "upper", "type": "faceted_cross_to_rectangle", "center": [0,p["lower.height"]+p["upper.height"]/2,0], "axis": [0,1,0],
         "parameters": {name: p[name] for name in p if name != "lower.height"}},
    ]
    for entity in entities:
        refs = []
        for face in shape.Faces():
            bb = face.BoundingBox()
            if (entity["id"] == "lower" and bb.ymax <= p["lower.height"]+1e-5 or
                entity["id"] == "upper" and bb.ymax > p["lower.height"]+1e-5):
                vertices = sorted([[round(v.X,7),round(v.Y,7),round(v.Z,7)] for v in face.Vertices()])
                refs.append({"surface": "PLANE", "vertices_mm": vertices,
                             "fingerprint": hashlib.sha256(json.dumps(vertices).encode()).hexdigest()})
        entity["geometry_refs"] = refs
    structure = [
        {"entity":"lower", "type":"profile_transition", "value":"rectangle_to_cross"},
        {"entity":"upper", "type":"profile_transition", "value":"cross_to_rectangle"},
        {"entity":"upper", "type":"alignment", "value":"centered_xz"},
    ]
    views = []
    for name, direction, right in (("FRONT", [0,0,1], [1,0,0]),
                                   ("RIGHT", [-1,0,0], [0,0,1]),
                                   ("TOP", [0,-1,0], [1,0,0])):
        views.append({"drawing_block":"VIEW_"+name, "type":"orthographic", "direction":direction,
                      "right":right, "segments":projected_segments(shape,direction,right)})
    bx=p["base.width_x"]/2; bz=p["base.width_z"]/2
    nx=p["neck.width_x"]/2; nz=p["neck.width_z"]/2
    low=p["lower.height"]; high=low+p["upper.height"]
    bindings={}
    rows=[("width_x", "FRONT", "base.width_x", [[-bx,0],[bx,0]], "x", [0,-18]),
          ("width_z", "RIGHT", "base.width_z", [[-bz,0],[bz,0]], "x", [0,-18]),
          ("lower_height", "FRONT", "lower.height", [[-bx,0],[-bx,low]], "y", [-68,0]),
          ("upper_height", "FRONT", "upper.height", [[bx,low],[nx,high]], "y", [70,low]),
          ("neck_x", "TOP", "neck.width_x", [[-nx,nz],[nx,nz]], "x", [0,66]),
          ("neck_z", "TOP", "neck.width_z", [[nx,-nz],[nx,nz]], "y", [66,0]),
          ("overall_height", "FRONT", None, [[bx,0],[nx,high]], "y", [96,0])]
    for key, view, variable, anchors, axis, position in rows:
        bindings[key]={"drawing_block":"VIEW_"+view,"type":"length","anchors":anchors,"axis":axis,
                       "terms":{variable:1} if variable else {"lower.height":1,"upper.height":1},
                       "demo_value":p[variable] if variable else high,"demo_position":position}
    bindings["profile_note"]={"drawing_block":"VIEW_TOP","type":"structure_note",
        "text":"STRAIGHT FACETS; RECTANGLE-CROSS-RECTANGLE; CENTERED X/Z",
        "position":[-78,-80], "value":"faceted_centered_stations", "structures":structure,
        "required_centerlines":[[[-52,0],[52,0]],[[0,-52],[0,52]]], "equations":[]}
    return {"schema_version":"benchcad-3d2d-gt/0.1", "case_id":"case_084", "synthetic":False, "units":"mm",
            "scope":"Native-source development case: six linear parameters, centered planar station topology, controlled three-view DXF only",
            "geometry":{"input_sha256":input_sha,"anchors":{"origin.x":0,"origin.y":0,"origin.z":0},
                        "frame":"Source frame: Y=0 base, +Y upward; X/Z centered on base"},
            "variables":variables,"required_variables":list(variables),"entities":entities,"structure":structure,
            "view_requirements":views,"reference_view_count":3,"annotation_bindings":bindings,
            "parameter_sources":{name:{"feature":f,"dimension_prefix":d} for name,(f,d) in PARAMETER_SOURCES.items()},
            "normalization":"Final planar station transitions; original extrusion/loft/cut order is not the expected feature answer"}


def geometry_validation(parameters, source, native, rebuilt):
    p=parameters
    bx,bz,nx,nz,low,upper=(p[k] for k in ("base.width_x","base.width_z","neck.width_x","neck.width_z","lower.height","upper.height"))
    analytic_volume=low*(bx*bz-(bx-nx)*(bz-nz)/3)+upper*(nx*nz+(bx-nx)*nz/2+(bz-nz)*nx/2)
    pairs = []
    for name, candidate in (("native_export",native),("cq_reconstruction",rebuilt)):
        removed=source.cut(candidate).Volume(); added=candidate.cut(source).Volume()
        pairs.append({"candidate":name,"source_minus_candidate_mm3":removed,
                      "candidate_minus_source_mm3":added,"passed":removed<1e-5 and added<1e-5})
    for shape in (source,native,rebuilt):
        if not shape.isValid() or len(shape.Solids()) != 1 or len(shape.Faces()) != 26:
            raise ValueError("Expected valid one-solid 26-plane geometry")
        if any(f.geomType() != "PLANE" for f in shape.Faces()):
            raise ValueError("Nonplanar faces outside case scope")
    if not all(p["passed"] for p in pairs):
        raise ValueError("Native, CQ and input solids differ")
    if abs(source.Volume()-analytic_volume)>1e-5:
        raise ValueError("Source volume differs from independent pyramid/wedge calculation")
    return {"schema_version":"benchcad-3d2d-case-validation/1", "case_id":"case_084", "units":"mm",
            "valid":True,"solid_count":1,"face_count":26,"all_surfaces_planar":True,
            "source_volume_mm3":source.Volume(),"analytic_volume_mm3":analytic_volume,"parameters_mm":parameters,
            "comparison_tolerance_mm3":1e-5,"boolean_comparisons":pairs,
            "scope":"Geometry and audited final parameterization; not native history equivalence or production benchmark calibration"}


def draw(gt, folder, variant="good"):
    import ezdxf
    doc=ezdxf.new("R2018");doc.header["$INSUNITS"]=4
    doc.styles.get("Standard").dxf.font="Arial.ttf"
    for layer in ("OUTLINE","HIDDEN","CENTER","DIMS","NOTE"):
        doc.layers.new(layer)
    blocks={}
    prediction={"schema_version":"benchcad-3d2d-prediction/0.1","case_id":gt["case_id"],"units":"mm",
                "features":[{**copy.deepcopy(e),"id":"pred_"+e["id"]} for e in gt["entities"]],
                "views":[],"dimensions":[],"structure":[]}
    for req in gt["view_requirements"]:
        name=req["drawing_block"];block=doc.blocks.new(name);blocks[name]=block
        for segment in req["segments"]:
            block.add_line(*segment["points"], dxfattribs={"layer":segment["layer"]})
        block.add_text(name[5:],dxfattribs={"height":3,"insert":[-8,110],"layer":"NOTE"})
        prediction["views"].append({"id":name,"drawing_block":name,"type":"orthographic","direction":req["direction"]})
    for points in gt["annotation_bindings"]["profile_note"]["required_centerlines"]:
        blocks["VIEW_TOP"].add_line(*points,dxfattribs={"layer":"CENTER"})
    refs=list(gt["annotation_bindings"])
    refs.remove("overall_height")
    if variant in ("missing_dimension","conflict_and_missing","redundant_and_missing"):
        refs.remove("neck_z")
    if variant == "equivalent_total_height":
        refs.remove("upper_height");refs.append("overall_height")
    if variant in ("redundant_dimension","conflicting_dimension","conflict_and_missing","redundant_and_missing"):
        refs.append("overall_height")
    for ref in refs:
        b=gt["annotation_bindings"][ref];block=blocks[b["drawing_block"]]
        annotation={"id":"a_"+ref,"type":b["type"],"view_id":b["drawing_block"],"binding_ref":ref}
        if b["type"] == "structure_note":
            entity=block.add_text(b["text"],dxfattribs={"height":2,"insert":b["position"],"layer":"NOTE"})
            annotation["value"]=b["value"]
        else:
            value=b["demo_value"];text="<>"
            if ref == "overall_height" and variant in ("conflicting_dimension","conflict_and_missing"):
                value+=5;text=str(int(value))
            dim=block.add_linear_dim(base=b["demo_position"],p1=b["anchors"][0],p2=b["anchors"][1],
                angle=0 if b["axis"]=="x" else 90,text=text,dxfattribs={"layer":"DIMS"},
                override={"dimtxt":2.5,"dimasz":1,"dimtad":1})
            dim.render();entity=dim.dimension;annotation["value"]=value
        annotation["drawing_ref"]=entity.dxf.handle
        prediction["structure" if b["type"]=="structure_note" else "dimensions"].append(annotation)
    for name,origin in (("VIEW_FRONT",(0,0)),("VIEW_RIGHT",(185,0)),("VIEW_TOP",(0,-175))):
        if variant == "missing_view" and name == "VIEW_RIGHT":
            continue
        doc.modelspace().add_blockref(name,origin)
    if variant in ("json_only_dimension","missing_structure_note"):
        key="neck_z" if variant=="json_only_dimension" else "profile_note"
        annotation=next(a for a in prediction["dimensions"]+prediction["structure"] if a["binding_ref"]==key)
        blocks[annotation["view_id"]].delete_entity(doc.entitydb[annotation["drawing_ref"]])
    if variant == "wrong_profile":
        block=blocks["VIEW_TOP"];line=block.query('LINE[layer=="OUTLINE"]').first
        line.dxf.end=(line.dxf.end.x+4,line.dxf.end.y,0)
    if variant == "overlapping_labels":
        dims=prediction["dimensions"]
        a=next(x for x in dims if x["binding_ref"]=="neck_x")
        b=next(x for x in dims if x["binding_ref"]=="neck_z")
        labels=[doc.blocks[doc.entitydb[x["drawing_ref"]].dxf.geometry].query("MTEXT").first for x in (a,b)]
        labels[0].dxf.insert=labels[1].dxf.insert
    folder.mkdir(parents=True,exist_ok=True)
    doc.saveas(folder/"drawing.dxf");write(folder/"prediction.json",prediction)
    return prediction


def build(out, publish_metadata=True):
    import cadquery as cq
    from benchcad3d2d.contracts import read_json
    from benchcad3d2d.evaluator import evaluate
    metadata=read_json(CASE/"case.json")
    source_file=next(a for a in metadata["files"] if a["kind"]=="step")
    native_file=next(a for a in metadata["files"] if a["path"].endswith("2023.SLDPRT"))
    if sha(CASE/source_file["path"]) != source_file["sha256"] or sha(CASE/native_file["path"]) != native_file["sha256"]:
        raise ValueError("Selected original source hashes changed")
    report=read_json(CASE/"gt/native_features.json")
    if report["source_sha256"] != native_file["sha256"] or report["export"]["sha256"] != sha(CASE/"gt/native_export.step"):
        raise ValueError("Native extraction hashes disagree with selected sources")
    parameters=native_parameters(report)
    source=cq.importers.importStep(str(CASE/source_file["path"])).val()
    native=cq.importers.importStep(str(CASE/"gt/native_export.step")).val()
    rebuilt=load_construction().build(parameters)
    validation=geometry_validation(parameters,source,native,rebuilt)
    gt=make_gt(parameters,source,source_file["sha256"])
    rules=read_json(ROOT/"config/rules.v0.2.json")
    variants=["good","equivalent_total_height","redundant_dimension","conflicting_dimension","missing_dimension",
              "conflict_and_missing","redundant_and_missing","json_only_dimension","missing_structure_note",
              "missing_view","wrong_profile","overlapping_labels"]
    summary={}
    for variant in variants:
        folder=out/"submissions"/variant;prediction=draw(gt,folder,variant)
        result=evaluate(gt,prediction,rules,folder/"drawing.dxf","controlled-dxf")
        write(out/"reports"/(variant+".json"),result)
        expected=variant in ("good","equivalent_total_height","redundant_dimension")
        if result["whole_drawing_complete"] != expected:
            raise ValueError(f"Unexpected drawing outcome for {variant}: {result['score']}")
        summary[variant]={"score":result["score"],"complete":result["whole_drawing_complete"],
                          "dependency_count":result["dependency_diagnostics"]["dependency_count"],
                          "missing":result["underdetermined_required_variables"],
                          "view_issues":[v["issues"] for v in result["views"]]}
    write(out/"summary.json",summary)
    validation.update({"input_sha256":source_file["sha256"],"native_source_sha256":native_file["sha256"],
                       "native_export_sha256":sha(CASE/"gt/native_export.step"),
                       "native_features_sha256":sha(CASE/"gt/native_features.json"),
                       "reconstruction_sha256":sha(CASE/"gt/reconstruction.py"),"gt_sha256":None,
                       "controlled_reference_score":summary["good"]["score"],"calibrated":False,
                       "drawing_variants":summary,"native_open_warnings":report["open_warnings"],
                       "review_status":"geometric and developer review; expert calibration pending"})
    if publish_metadata:
        (CASE/"input").mkdir(exist_ok=True)
        shutil.copyfile(CASE/source_file["path"],CASE/"input/model.step")
        write(CASE/"gt/gt.json",gt)
        validation["gt_sha256"]=sha(CASE/"gt/gt.json")
        write(CASE/"gt/validation.json",validation)
        if metadata["schema_version"] == "benchcad-3d2d-source/2":
            metadata["artifacts"]=[{"path":a["path"],"bytes":(CASE/a["path"]).stat().st_size,
                                    "sha256":sha(CASE/a["path"])} for a in metadata["artifacts"]]
            write(CASE/"case.json",metadata)
    else:
        write(out/"gt.json",gt);write(out/"geometry_validation.json",validation)
    print(json.dumps({"case_id":"case_084","parameters":len(parameters),"variants":summary},ensure_ascii=True,indent=2))
    return gt,validation


if __name__ == "__main__":
    sys.path.insert(0,str(ROOT))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=ROOT/".outputs/case_084")
    parser.add_argument("--check-only",action="store_true",help="Write validation fixtures only, leave committed GT unchanged")
    args=parser.parse_args()
    build(args.out,publish_metadata=not args.check_only)
