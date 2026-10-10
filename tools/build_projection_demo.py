"""General view evidence fixtures, outside the case registry and without GT."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchcad3d2d.projection import Frame, dot, rebuild, shape_polylines, verify_views


def write_json(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2)+"\n").encode("utf-8"))


def view_spec(name, right, up, normal, offset, angle, scale=1):
    return {"id":name,"type":"orthographic",
            "projection":{"type":"orthographic","origin_mm":[0,0,0],"right":right,"up":up,"normal":normal},
            "sheet":{"origin_mm":offset,"rotation_deg":angle,"scale":scale},
            "geometry":{"visible":[],"hidden":[],"hidden_policy":"omit","cut_edges":[],"hatches":[]}}


def specs():
    # Non-axis-aligned orientation, including a non-horizontal section normal.
    normal = [v/math.sqrt(14) for v in (1,2,3)]
    right = [2/math.sqrt(5),-1/math.sqrt(5),0]
    up = [3/math.sqrt(70),6/math.sqrt(70),-5/math.sqrt(70)]
    top = view_spec("top",[1,0,0],[0,1,0],[0,0,1],[160,110],31,0.75)
    front = view_spec("front",[1,0,0],[0,0,1],[0,-1,0],[-80,-120],-47,1.25)
    side = view_spec("side",[0,1,0],[0,0,1],[1,0,0],[300,20],19,0.6)
    oblique = view_spec("oblique",right,up,normal,[-210,120],123,0.9)
    section = view_spec("section",[0.8,-0.6,0],[0,0,1],[-0.6,-0.8,0],[170,-110],67,1.1)
    section["type"]="full_section"
    section["section"]={"kind":"planar_full","parent_view_id":"top","point_mm":[-28,0,0],
                         "normal":[-0.6,-0.8,0],"retained_side":"negative","label":"B",
                         "markers":{"traces":[],"arrows":[],"labels":[],"title":[]}}
    return [top,front,side,oblique,section]


def make_fixture(folder, variant="good"):
    import cadquery as cq
    import ezdxf
    from ezdxf.math import Matrix44
    folder = Path(folder); folder.mkdir(parents=True,exist_ok=True)
    model = cq.importers.importStep(str(ROOT/"examples/plate_holes/model.step")).val()
    (folder/"model.step").write_bytes((ROOT/"examples/plate_holes/model.step").read_bytes())
    doc = ezdxf.new("R2018"); doc.header["$INSUNITS"]=4
    views=specs()
    for view in views:
        frame = Frame.read(view)
        expected,cut_shape = rebuild(model,view,0.1)
        # Arbitrary block names and nested INSERTs. Sheet transforms are actual
        # DXF transforms, not merely a change to JSON camera declarations.
        block = doc.blocks.new(f"part_{view['id']}")
        wrapper = doc.blocks.new(f"container_{view['id']}")
        inner = wrapper.add_blockref(block.name,(0,0))
        outer = doc.modelspace().add_blockref(wrapper.name,frame.sheet_origin,
            dxfattribs={"rotation":math.degrees(frame.angle),"xscale":frame.scale,"yscale":frame.scale})
        prefix=[outer.dxf.handle,inner.dxf.handle]
        # Put visible and cut geometry on separate entity paths; cut edges may
        # legitimately coincide with the projected retained-solid boundary.
        for kind in ("visible","cut_edges"):
            for line in expected[kind]:
                entity=block.add_lwpolyline(line)
                view["geometry"][kind].append(prefix+[entity.dxf.handle])
        if view["type"]!="full_section":continue
        # Section boundary wires are grouped by the CAD kernel, preserving holes.
        wires=cq.Wire.combine(cq.Shape.cast(cut_shape).Edges(),tol=1e-6)
        hatch=block.add_hatch()
        hatch.set_pattern_fill("ANSI31",scale=2)
        hatch.dxf.hatch_style=0
        for wire in wires:
            lines=shape_polylines(wire.wrapped,0.1,frame)
            points=[]
            for line in lines:
                if points and math.dist(points[-1],line[-1]) < math.dist(points[-1],line[0]):line=list(reversed(line))
                points.extend(line if not points else line[1:])
            hatch.paths.add_polyline_path(points,is_closed=True,flags=0)
        view["geometry"]["hatches"].append(prefix+[hatch.dxf.handle])
        parent=next(v for v in views if v["id"]==view["section"]["parent_view_id"])
        pf=Frame.read(parent)
        parent_block=doc.blocks.get("part_top")
        parent_prefix=parent["geometry"]["visible"][0][:-1]
        section=view["section"]; markers=section["markers"]
        n=section["normal"]; p=section["point_mm"]
        coefficients=(dot(n,pf.right),dot(n,pf.up))
        direction=(-coefficients[1],coefficients[0])
        origin=(p[0],p[1])
        cut_in_parent=shape_polylines(cut_shape,0.1,pf)
        extents=[dot((q[0]-origin[0],q[1]-origin[1]),direction) for line in cut_in_parent for q in line]
        ends=[(origin[0]+direction[0]*t,origin[1]+direction[1]*t) for t in (min(extents)-8,max(extents)+8)]
        trace=parent_block.add_line(*ends)
        markers["traces"].append(parent_prefix+[trace.dxf.handle])
        heading=(-coefficients[0],-coefficients[1])
        for tip in ends:
            base=(tip[0]-4*heading[0],tip[1]-4*heading[1])
            corners=[tip,(base[0]+1.2*direction[0],base[1]+1.2*direction[1]),
                         (base[0]-1.2*direction[0],base[1]-1.2*direction[1])]
            arrow=parent_block.add_solid(corners)
            markers["arrows"].append({"drawing_ref":parent_prefix+[arrow.dxf.handle],"tip_vertex":0})
            label=parent_block.add_text(section["label"],dxfattribs={"height":2.5,"insert":(tip[0]+3*heading[0],tip[1]+3*heading[1])})
            markers["labels"].append(parent_prefix+[label.dxf.handle])
        title=block.add_text("B-B",dxfattribs={"height":2.5,"insert":(0,45)})
        markers["title"]=prefix+[title.dxf.handle]
    prediction={"schema_version":"benchcad-3d2d-prediction/0.2","case_id":"plate_holes_general_views",
                "units":"mm","features":[],"views":views,"dimensions":[],"structure":[],"auxiliary":[]}
    if variant=="wrong_direction":
        views[3]["projection"].update(right=[1,0,0],up=[0,0,1],normal=[0,-1,0])
    if variant=="wrong_cut_plane":views[-1]["section"]["point_mm"][0]+=7
    if variant=="missing_geometry":
        ref=views[0]["geometry"]["visible"].pop()
        doc.entitydb[ref[-1]].destroy()
    if variant=="extra_geometry":
        extra=doc.blocks.get("part_top").add_line((100,100),(120,100))
        views[0]["geometry"]["visible"].append(views[0]["geometry"]["visible"][0][:-1]+[extra.dxf.handle])
    if variant=="reversed_arrows":
        for arrow in views[-1]["section"]["markers"]["arrows"]:
            entity=doc.entitydb[arrow["drawing_ref"][-1]]
            tip=entity.dxf.vtx0
            entity.transform(Matrix44.translate(-tip.x,-tip.y,0) @ Matrix44.z_rotate(math.pi) @ Matrix44.translate(tip.x,tip.y,0))
    if variant=="missing_trace":
        doc.entitydb[views[-1]["section"]["markers"]["traces"][0][-1]].destroy()
    if variant=="wrong_hatch":
        entity=doc.entitydb[views[-1]["geometry"]["hatches"][0][-1]]
        entity.transform(Matrix44.translate(4,0,0))
    if variant=="json_only_section":
        for ref in views[-1]["geometry"]["visible"]+views[-1]["geometry"]["cut_edges"]+views[-1]["geometry"]["hatches"]:
            doc.entitydb[ref[-1]].destroy()
    drawing=folder/"drawing.dxf"; doc.saveas(drawing)
    prediction["input_sha256"]=hashlib.sha256((folder/"model.step").read_bytes()).hexdigest()
    prediction["drawing_sha256"]=hashlib.sha256(drawing.read_bytes()).hexdigest()
    write_json(folder/"prediction.json",prediction)
    return prediction


def main():
    variants=("good","wrong_direction","wrong_cut_plane","missing_geometry","extra_geometry","reversed_arrows",
              "missing_trace","wrong_hatch","json_only_section")
    summaries=[]
    for variant in variants:
        folder=ROOT/".outputs/general_views"/variant
        prediction=make_fixture(folder,variant)
        report=verify_views(folder/"model.step",folder/"drawing.dxf",prediction)
        write_json(folder/"report.json",report)
        summaries.append({"variant":variant,"status":report["status"],"score":report["score"],
                          "issues":[issue for view in report["views"] for issue in view["issues"]]})
    write_json(ROOT/".outputs/general_views/summary.json",summaries)
    print(json.dumps(summaries,ensure_ascii=False,indent=2))
    return 0 if all(s["status"]==("views_verified" if s["variant"]=="good" else "fail") for s in summaries) else 1


if __name__=="__main__":sys.exit(main())
