"""Independent STEP/DXF view evidence, without case templates or JSON scoring.

OpenCascade HLR and Boolean operations rebuild claimed orthographic views and
planar full sections. Submitted coordinates, names and checksums are claims;
only the actual DXF entities are compared. General annotation semantics remain
unimplemented and this module deliberately never emits an overall score.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path

from .contracts import ContractError, number, require


class ProjectionUnsupported(ValueError):
    pass


def vector(value, size, label):
    require(isinstance(value, list) and len(value) == size, f"{label}: expected {size} numbers")
    return tuple(number(x, label) for x in value)


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


@dataclass(frozen=True)
class Frame:
    origin: tuple
    right: tuple
    up: tuple
    normal: tuple
    sheet_origin: tuple
    angle: float
    scale: float

    @classmethod
    def read(cls, view):
        require(view.get("projection", {}).get("type") == "orthographic", "Only orthographic projection is implemented")
        p, s = view["projection"], view["sheet"]
        origin = vector(p["origin_mm"], 3, "projection origin")
        right, up, normal = [vector(p[k], 3, k) for k in ("right", "up", "normal")]
        require(all(abs(dot(v, v)-1) <= 1e-6 for v in (right, up, normal)), "View axes must be unit vectors")
        require(abs(dot(right, up)) <= 1e-6 and
                math.dist(cross(right, up), normal) <= 1e-6, "View frame must be orthonormal and right-handed")
        scale = number(s["scale"], "sheet scale")
        require(1e-6 <= scale <= 1e6, "Sheet scale out of supported range")
        return cls(origin, right, up, normal, vector(s["origin_mm"], 2, "sheet origin"),
                   math.radians(number(s["rotation_deg"], "sheet rotation")), scale)

    def project(self, point):
        offset = sub(point, self.origin)
        return (dot(offset, self.right), dot(offset, self.up))

    def to_sheet(self, point):
        x, y = point; c, s = math.cos(self.angle), math.sin(self.angle)
        return (self.sheet_origin[0]+self.scale*(c*x-s*y),
                self.sheet_origin[1]+self.scale*(s*x+c*y))

    def from_sheet(self, point):
        x, y = [(point[i]-self.sheet_origin[i])/self.scale for i in range(2)]
        c, s = math.cos(self.angle), math.sin(self.angle)
        return (c*x+s*y, -s*x+c*y)


def check_ref(ref):
    require(isinstance(ref, list) and 1 <= len(ref) <= 16 and
            all(isinstance(h, str) and h and all(c in "0123456789ABCDEF" for c in h) for h in ref),
            "drawing_ref must be an uppercase DXF handle path")


def fields(document, required, allowed, label):
    require(isinstance(document,dict), f"{label} must be an object")
    require(set(required) <= set(document) and set(document) <= set(allowed), f"{label}: missing or unknown fields")


def validate_submission(prediction):
    top=("schema_version","case_id","units","input_sha256","drawing_sha256","features","views","dimensions","structure","auxiliary")
    fields(prediction,top,top,"prediction/0.2")
    require(prediction.get("schema_version") == "benchcad-3d2d-prediction/0.2", "General views require prediction/0.2")
    require(prediction.get("units") == "mm" and isinstance(prediction.get("case_id"), str)
            and bool(prediction["case_id"]), "Invalid case ID or units")
    for key in ("input_sha256", "drawing_sha256"):
        value = prediction.get(key)
        require(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value), f"Invalid {key}")
    for key in ("features", "views", "dimensions", "structure", "auxiliary"):
        require(isinstance(prediction.get(key), list), f"{key} must be an array")
    require(len(prediction["features"]) <= 512 and len(prediction["auxiliary"]) <= 20000, "Submission resource limit")
    fids = [f["id"] for f in prediction["features"]]
    require(all(isinstance(i,str) and i for i in fids) and len(set(fids))==len(fids), "Invalid feature IDs")
    for feature in prediction["features"]:
        fields(feature,("id","type","geometry_refs"),("id","type","geometry_refs","center","axis","parameters"),"feature")
        require(isinstance(feature.get("type"),str) and feature["type"], "Missing feature type")
        require(isinstance(feature.get("geometry_refs"),list) and feature["geometry_refs"], "Feature needs public geometry references")
    views = prediction["views"]
    require(1 <= len(views) <= 64, "Expected 1 to 64 views")
    ids = [v["id"] for v in views]
    require(all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids), "Invalid/duplicate view IDs")
    for view in views:
        fields(view,("id","type","projection","sheet","geometry"),("id","type","projection","sheet","geometry","section"),"view")
        fields(view["projection"],("type","origin_mm","right","up","normal"),("type","origin_mm","right","up","normal"),"projection")
        fields(view["sheet"],("origin_mm","rotation_deg","scale"),("origin_mm","rotation_deg","scale"),"sheet")
        fields(view["geometry"],("visible","hidden","hidden_policy","cut_edges","hatches"),("visible","hidden","hidden_policy","cut_edges","hatches"),"view geometry")
    frames = {v["id"]: Frame.read(v) for v in views}
    for view in views:
        require(view.get("type") in ("orthographic", "full_section"), "Unsupported view type")
        geometry = view["geometry"]
        for key in ("visible", "hidden", "cut_edges", "hatches"):
            require(isinstance(geometry.get(key), list), f"Missing geometry.{key}")
            require(len(geometry[key]) <= 20000, "Too many geometry references")
            for ref in geometry[key]: check_ref(ref)
        require(geometry["visible"], "Visible geometry references are required")
        require(geometry.get("hidden_policy") in ("omit", "all"), "hidden_policy must be omit or all")
        require(geometry["hidden_policy"] == "all" or not geometry["hidden"], "Hidden geometry contradicts omit policy")
        if view["type"] == "orthographic":
            require(not geometry["cut_edges"] and not geometry["hatches"] and "section" not in view,
                    "Orthographic view cannot declare section evidence")
            continue
        section = view["section"]
        section_fields=("kind","parent_view_id","point_mm","normal","retained_side","label","markers")
        fields(section,section_fields,section_fields,"section")
        require(section.get("kind") == "planar_full", "Only planar full sections are implemented")
        require(section.get("parent_view_id") in frames and section["parent_view_id"] != view["id"], "Invalid section parent")
        parent = next(v for v in views if v["id"] == section["parent_view_id"])
        require(parent["type"] == "orthographic", "Section parent must be an orthographic view")
        vector(section["point_mm"], 3, "section point")
        n = vector(section["normal"], 3, "section normal")
        require(abs(dot(n, n)-1) <= 1e-6, "Section normal must be a unit vector")
        require(abs(abs(dot(n, frames[view["id"]].normal))-1) <= 1e-6,
                "Section projection must be normal to its cutting plane")
        require(section.get("retained_side") in ("positive", "negative"), "Invalid retained side")
        sign = 1 if section["retained_side"] == "positive" else -1
        require(sign*dot(n, frames[view["id"]].normal) < 0, "Retained half must be behind the cutting plane as seen by viewer")
        require(abs(dot(n, frames[parent["id"]].normal)) <= 1e-6,
                "Parent must show cutting plane edge-on for a single cutting trace")
        require(isinstance(section.get("label"), str) and section["label"], "Missing section label")
        marks = section["markers"]
        fields(marks,("traces","arrows","labels","title"),("traces","arrows","labels","title"),"section markers")
        require(isinstance(marks.get("traces"), list) and marks["traces"], "Missing trace references")
        require(isinstance(marks.get("arrows"), list) and len(marks["arrows"]) == 2, "Expected two section arrows")
        require(isinstance(marks.get("labels"), list) and len(marks["labels"]) == 2, "Expected two end labels")
        for ref in marks["traces"]+marks["labels"]+[marks["title"]]: check_ref(ref)
        for arrow in marks["arrows"]:
            fields(arrow,("drawing_ref","tip_vertex"),("drawing_ref","tip_vertex"),"section arrow")
            check_ref(arrow["drawing_ref"])
            require(type(arrow.get("tip_vertex")) is int and 0 <= arrow["tip_vertex"] <= 2, "Invalid arrow tip vertex")
        require(geometry["cut_edges"] and geometry["hatches"], "Section must have actual cut edges and hatch boundaries")
    annotations = prediction["dimensions"]+prediction["structure"]
    require(len(annotations) <= 512, "Too many annotations")
    aids = [a["id"] for a in annotations]
    require(all(isinstance(i, str) and i for i in aids) and len(aids) == len(set(aids)), "Invalid annotation IDs")
    annotation_refs = set()
    for annotation in annotations:
        require(annotation.get("view_id") in frames, "Unknown annotation view")
        check_ref(annotation["drawing_ref"])
        require("binding_ref" not in annotation and "terms" not in annotation,
                "General submissions must not use private GT bindings or equation coefficients")
        annotation_fields=("id","view_id","type","value","drawing_ref","attachments")
        if annotation in prediction["dimensions"]:
            fields(annotation,annotation_fields+("measurement",),annotation_fields+("measurement","reference"),"dimension")
            fields(annotation["measurement"],("kind",),("kind","direction_model"),"measurement")
        else:fields(annotation,annotation_fields,annotation_fields,"structure annotation")
        require(annotation.get("attachments"), "Annotation must declare geometry attachments")
        require(tuple(annotation["drawing_ref"]) not in annotation_refs, "Drawing entity reused for multiple annotation claims")
        annotation_refs.add(tuple(annotation["drawing_ref"]))
        if annotation in prediction["dimensions"]:
            require(annotation.get("type") in ("length","signed_distance","depth","diameter","radius","angle"), "Unknown dimension type")
            number(annotation["value"],"dimension value")
            require(annotation.get("measurement",{}).get("kind") in ("true_length","projected_length","angle"), "Missing measurement interpretation")
        else:
            require(annotation.get("type") in ("symmetry","alignment","termination","multiplicity","equality","structure_note"), "Unknown structure annotation")
        require(isinstance(annotation["attachments"],list), "attachments must be an array")
        for attachment in annotation["attachments"]:
            fields(attachment,("geometry_ref","selector"),("geometry_ref","selector","point_mm","feature_id"),"attachment")
            require(isinstance(attachment,dict) and attachment.get("selector") in
                    ("point_on_geometry","center","axis","start","end","surface"), "Invalid geometry selector")
    geometry_refs = [r for f in prediction["features"] for r in f["geometry_refs"]]
    geometry_refs += [a["geometry_ref"] for d in annotations for a in d["attachments"]]
    for ref in geometry_refs:
        fields(ref,("kind","fingerprint"),("kind","fingerprint"),"public geometry reference")
        require(ref.get("kind") in ("face","edge") and isinstance(ref.get("fingerprint"),str)
                and len(ref["fingerprint"])==64 and all(c in "0123456789abcdef" for c in ref["fingerprint"]), "Invalid public geometry reference")
    for aux in prediction["auxiliary"]:
        fields(aux,("drawing_ref","role"),("drawing_ref","role"),"auxiliary")
        check_ref(aux["drawing_ref"])
        require(aux.get("role") in ("centerline", "text"), "Invalid auxiliary role")
    return frames


class Drawing:
    """Resolve entity instances, including nested INSERT transforms, by handle path."""
    def __init__(self, path):
        import ezdxf
        self.doc = ezdxf.readfile(str(path))
        require(self.doc.header.get("$INSUNITS") == 4, "DXF must explicitly use millimeters")
        require(not any(len(layout) for layout in self.doc.layouts if layout.name != "Model"),
                "Paper-space content is not implemented; use modelspace entities")
        self.used = set()
        self.paths = {}
        def walk(layout, prefix=()):
            require(len(prefix) < 16, "DXF INSERT recursion limit")
            for entity in layout:
                path = prefix+(entity.dxf.handle,)
                require(len(self.paths) < 20000, "DXF entity limit")
                if entity.dxftype() == "INSERT":
                    require(entity.mcount == 1, "Array INSERT is not implemented")
                    walk(self.doc.blocks[entity.dxf.name], path)
                else:
                    self.paths[path] = entity
        walk(self.doc.modelspace())

    def resolve(self, ref):
        check_ref(ref)
        require(tuple(ref) in self.paths, "DXF entity path does not exist in modelspace")
        matrices = []
        layout = self.doc.modelspace()
        for i, handle in enumerate(ref):
            entity = self.doc.entitydb.get(handle)
            require(entity is not None and any(e is entity for e in layout), "Wrong DXF instance path")
            layer = self.doc.layers.get(entity.dxf.layer)
            require(not entity.dxf.get("invisible", 0) and not layer.is_off() and not layer.is_frozen(), "Drawing evidence is hidden")
            if i != len(ref)-1:
                require(entity.dxftype() == "INSERT", "Instance path must traverse INSERT entities")
                matrices.append(entity.matrix44())
                layout = self.doc.blocks[entity.dxf.name]
        self.used.add(tuple(ref))
        return entity, matrices

    @staticmethod
    def world(point, matrices):
        from ezdxf.math import Vec3
        p = Vec3(point)
        for matrix in reversed(matrices): p = matrix.transform(p)
        require(abs(p.z) <= 1e-6, "Only planar DXF sheet geometry is implemented")
        return (p.x, p.y)

    def polylines(self, refs, frame, tolerance, hatch=False):
        from ezdxf.path import make_path, from_hatch
        result = []
        for ref in refs:
            entity, matrices = self.resolve(ref)
            if hatch:
                require(entity.dxftype() == "HATCH" and not entity.dxf.solid_fill, "Section evidence must be patterned HATCH")
                require(entity.dxf.hatch_style == 0, "Hatch must preserve internal holes")
                require(entity.pattern is not None and entity.pattern.lines and entity.dxf.pattern_scale > 0,
                        "Hatch must contain a drawable pattern")
                paths = list(from_hatch(entity))
            else:
                require(entity.dxftype() in ("LINE", "ARC", "CIRCLE", "ELLIPSE", "LWPOLYLINE", "POLYLINE", "SPLINE"), "Unsupported outline entity")
                paths = [make_path(entity)]
            # INSERT transforms can magnify local tessellation errors. Sample using
            # the combined stretch, then compare in model millimeters.
            stretch = 1.0
            for matrix in matrices:
                stretch *= max(matrix.transform_direction((1,0,0)).magnitude,
                               matrix.transform_direction((0,1,0)).magnitude)
            for path in paths:
                points = [frame.from_sheet(self.world(p, matrices))
                          for p in path.flattening(tolerance*frame.scale/(16*max(stretch, 1e-12)), segments=8)]
                require(2 <= len(points) <= 100000, "Invalid/too complex DXF curve")
                result.append(points)
        return result


def shape_polylines(shape, tolerance, frame=None):
    import cadquery as cq
    from OCP.BRepLib import BRepLib
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    if shape.IsNull(): return []
    BRepLib.BuildCurves3d_s(shape)
    result = []
    for edge in cq.Shape.cast(shape).Edges():
        curve = BRepAdaptor_Curve(edge.wrapped)
        sample = GCPnts_QuasiUniformDeflection(curve, tolerance/16)
        require(sample.IsDone() and 2 <= sample.NbPoints() <= 100000, "Cannot sample projected STEP edge")
        points = [(sample.Value(i).X(), sample.Value(i).Y(), sample.Value(i).Z())
                  for i in range(1, sample.NbPoints()+1)]
        result.append([frame.project(p) if frame else p[:2] for p in points])
    return result


def rebuild(shape, view, tolerance):
    """OCP exact HLR; full sections keep the material behind the cut plane."""
    import cadquery as cq
    from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir, gp_Pln
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Section
    frame = Frame.read(view)
    cut, cut_shape = [], None
    retained = shape
    if view["type"] == "full_section":
        section = view["section"]
        point, normal = section["point_mm"], section["normal"]
        plane = gp_Pln(gp_Pnt(*point), gp_Dir(*normal))
        operation = BRepAlgoAPI_Section(shape.wrapped, plane, False)
        operation.Build()
        require(operation.IsDone(), "STEP section operation failed")
        cut_shape = operation.Shape()
        cut = shape_polylines(cut_shape, tolerance, frame)
        require(cut, "Cutting plane does not intersect the input solid")
        sign = 1 if section["retained_side"] == "positive" else -1
        interior = gp_Pnt(*[p+sign*n for p, n in zip(point, normal)])
        half = BRepPrimAPI_MakeHalfSpace(BRepBuilderAPI_MakeFace(plane).Face(), interior).Solid()
        common = BRepAlgoAPI_Common(shape.wrapped, half)
        common.Build()
        require(common.IsDone() and not common.Shape().IsNull(), "Retained section Boolean failed")
        retained = cq.Shape.cast(common.Shape())
        require(retained.Solids() and retained.Volume() > 1e-9, "Section has no retained solid")
        require(shape.Volume()-retained.Volume() > max(1e-9,shape.Volume()*1e-10),
                "Cutting plane must cross the solid interior")
    algo = HLRBRep_Algo()
    algo.Add(retained.wrapped)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(*frame.origin), gp_Dir(*frame.normal), gp_Dir(*frame.right))))
    algo.Update(); algo.Hide()
    result = HLRBRep_HLRToShape(algo)
    visible = sum((shape_polylines(getattr(result, method)(), tolerance)
                   for method in ("VCompound", "OutLineVCompound", "Rg1LineVCompound")), [])
    hidden = sum((shape_polylines(getattr(result, method)(), tolerance)
                  for method in ("HCompound", "OutLineHCompound", "Rg1LineHCompound")), [])
    return {"visible": visible, "hidden": hidden, "cut_edges": cut}, cut_shape


def compare_curves(expected, observed, tolerance):
    """Two-way sampled point-to-segment distance, not one-way containment.

    Curve deflection is <= tolerance/16 (DXF Bezier approximation may add error).
    Along-polyline spacing is <= tolerance/2. This is a bounded-resolution
    geometric check, not an exact analytic Hausdorff-distance proof.
    """
    import numpy as np
    def segments(polylines):
        pairs = [(a,b) for line in polylines for a,b in zip(line,line[1:]) if math.dist(a,b) > 1e-12]
        require(len(pairs) <= 20000, "Too many comparison segments")
        return np.asarray(pairs, dtype=float).reshape((-1,2,2))
    a, b = segments(expected), segments(observed)
    if not len(a) or not len(b):
        return {"ok": not len(a) and not len(b), "expected_to_drawing_mm": None,
                "drawing_to_expected_mm": None}
    def distance(source, target):
        counts = np.maximum(1, np.ceil(np.linalg.norm(source[:,1]-source[:,0], axis=1)/(tolerance/2))).astype(int)
        require(int(counts.sum()+len(counts)) <= 200000, "Projection sampling budget exceeded")
        points = np.concatenate([start+np.linspace(0,1,n+1)[:,None]*(end-start)
                                 for (start,end),n in zip(source,counts)])
        starts, delta = target[:,0], target[:,1]-target[:,0]
        norm = np.sum(delta*delta, axis=1)
        maximum = 0.0
        for begin in range(0,len(points),256):
            chunk = points[begin:begin+256]; best = np.full(len(chunk),np.inf)
            for j in range(0,len(target),512):
                offset = chunk[:,None,:]-starts[None,j:j+512,:]
                t = np.clip(np.sum(offset*delta[None,j:j+512,:],axis=2)/norm[None,j:j+512],0,1)
                squared = np.sum((offset-t[:,:,None]*delta[None,j:j+512,:])**2,axis=2)
                best = np.minimum(best,np.min(squared,axis=1))
            maximum = max(maximum,float(np.sqrt(best.max())))
        return maximum
    ab, ba = distance(a,b), distance(b,a)
    return {"ok": max(ab,ba) <= tolerance, "expected_to_drawing_mm": ab, "drawing_to_expected_mm": ba}


def section_markers(drawing, view, frames, cut_shape, tolerance):
    section, marks = view["section"], view["section"]["markers"]
    parent = frames[section["parent_view_id"]]
    normal, point = section["normal"], section["point_mm"]
    coefficients = (dot(normal,parent.right),dot(normal,parent.up))
    length = math.hypot(*coefficients)
    require(length > 1e-9, "Cannot project cutting trace into parent")
    direction = (-coefficients[1]/length,coefficients[0]/length)
    offset = dot(normal,sub(parent.origin,point))
    expected = shape_polylines(cut_shape,tolerance,parent)
    bounds = [dot(p,direction) for line in expected for p in line]
    low, high = min(bounds),max(bounds)
    traces = drawing.polylines(marks["traces"],parent,tolerance)
    require(all(len(line)==2 for line in traces), "Cutting traces must be straight LINE segments")
    intervals = []
    for line in traces:
        require(all(abs(dot(p,coefficients)+offset)/length <= tolerance for p in line), "Cutting trace disagrees with 3D cutting plane")
        intervals.append(sorted(dot(p,direction) for p in line))
    intervals.sort()
    reached = low
    for left,right in intervals:
        if right < reached-tolerance: continue
        require(left <= reached+tolerance, "Cutting trace has a gap over the section")
        reached = max(reached,right)
        if reached >= high-tolerance: break
    require(reached >= high-tolerance, "Cutting trace does not span the section")
    endpoints = (min(i[0] for i in intervals),max(i[1] for i in intervals))
    nearby = max(5.0,0.05*(high-low))
    arrow_positions = []
    for arrow in marks["arrows"]:
        entity,matrices = drawing.resolve(arrow["drawing_ref"])
        require(entity.dxftype()=="SOLID", "Section arrow must be an actual triangular SOLID")
        vertices = [parent.from_sheet(drawing.world(entity.dxf.get(f"vtx{i}"),matrices)) for i in range(4)]
        require(math.dist(vertices[2],vertices[3]) <= tolerance, "Section arrow must have three vertices")
        tip = vertices[arrow["tip_vertex"]]
        base = [vertices[i] for i in range(3) if i != arrow["tip_vertex"]]
        heading = sub(tip,tuple((a+b)/2 for a,b in zip(*base)))
        magnitude = math.hypot(*heading)
        sign = 1 if section["retained_side"]=="positive" else -1
        require(magnitude > tolerance and dot(heading,coefficients)*sign/(magnitude*length) >= math.cos(math.radians(1)),
                "Section arrows disagree with viewing direction")
        require(abs(dot(tip,coefficients)+offset)/length <= nearby, "Section arrow is detached from cutting trace")
        arrow_positions.append(dot(tip,direction))
    require(all(abs(a-b)<=nearby for a,b in zip(sorted(arrow_positions),endpoints)), "Section arrows must mark opposite trace ends")
    label_positions = []
    for ref in marks["labels"]:
        entity,matrices = drawing.resolve(ref)
        require(entity.dxftype() in ("TEXT","MTEXT") and entity.plain_text().strip()==section["label"], "Missing/wrong section end label")
        pos = parent.from_sheet(drawing.world(entity.dxf.insert,matrices))
        require(abs(dot(pos,coefficients)+offset)/length <= nearby, "Section label is detached from trace")
        label_positions.append(dot(pos,direction))
    require(all(abs(a-b)<=nearby for a,b in zip(sorted(label_positions),endpoints)), "Section labels must mark opposite trace ends")
    title,_ = drawing.resolve(marks["title"])
    label = section["label"]
    require(title.dxftype() in ("TEXT","MTEXT") and title.plain_text().strip()==f"{label}-{label}", "Missing/wrong section title")
    return {"ok":True,"trace_span_model_mm":[low,high]}


def geometry_catalog(input_step):
    """Public neutral references, generated from input STEP without private GT.

    These are geometry fingerprints, not feature labels or native face indices.
    The catalog algorithm is versioned; rebuild it in the same evaluator runtime.
    """
    try:
        import cadquery as cq
    except ImportError as exc:
        raise ProjectionUnsupported("STEP inspection requires CadQuery/OCP") from exc
    from .contracts import digest
    input_step=Path(input_step)
    require(input_step.is_file() and input_step.suffix.lower() in (".step",".stp"),"Missing input STEP")
    imported=cq.importers.importStep(str(input_step)).vals()
    model=imported[0] if len(imported)==1 else cq.Compound.makeCompound(imported)
    require(model.isValid() and model.Solids(),"STEP must contain valid solids")
    def xyz(point):return [round(v,6) for v in point.toTuple()]
    def bounds(shape):
        box=shape.BoundingBox()
        return [round(getattr(box,k),6) for k in ("xmin","ymin","zmin","xmax","ymax","zmax")]
    def edge_signature(edge):
        samples=[xyz(edge.positionAt(t)) for t in (0,0.25,0.5,0.75,1)]
        samples=min(samples,list(reversed(samples)))
        return {"curve":edge.geomType(),"length_mm":round(edge.Length(),6),"bounds_mm":bounds(edge),"samples_mm":samples}
    edges=[]
    for edge in model.Edges():
        signature=edge_signature(edge)
        edges.append({"kind":"edge","fingerprint":digest(signature),**signature})
    faces=[]
    for face in model.Faces():
        signature={"surface":face.geomType(),"area_mm2":round(face.Area(),6),"center_mm":xyz(face.Center()),
                   "bounds_mm":bounds(face),"edges":sorted(digest(edge_signature(e)) for e in face.Edges())}
        faces.append({"kind":"face","fingerprint":digest(signature),**signature})
    return {"schema_version":"benchcad-3d2d-geometry-catalog/0.1","units":"mm",
            "input_sha256":hashlib.sha256(input_step.read_bytes()).hexdigest(),
            "faces":sorted(faces,key=lambda x:x["fingerprint"]),"edges":sorted(edges,key=lambda x:x["fingerprint"]),
            "scope":"Neutral STEP geometry only; no private features, dimension targets or GT relations."}


def verify_views(input_step, drawing_path, prediction, tolerance=0.1):
    frames = validate_submission(prediction)
    tolerance = number(tolerance,"projection tolerance")
    require(tolerance > 0, "Projection tolerance must be positive")
    input_step, drawing_path = Path(input_step),Path(drawing_path)
    require(input_step.is_file() and input_step.suffix.lower() in (".step",".stp"), "Missing input STEP")
    require(drawing_path.is_file() and drawing_path.suffix.lower()==".dxf", "Missing DXF drawing")
    hashes = {"input_sha256":hashlib.sha256(input_step.read_bytes()).hexdigest(),
              "drawing_sha256":hashlib.sha256(drawing_path.read_bytes()).hexdigest()}
    require(all(prediction[k]==v for k,v in hashes.items()), "Submission file hash mismatch")
    try:
        import cadquery as cq
        import ezdxf  # noqa: F401 - explicit optional dependency boundary
    except ImportError as exc:
        raise ProjectionUnsupported("View verification requires CadQuery/OCP and ezdxf") from exc
    imported = cq.importers.importStep(str(input_step)).vals()
    model = imported[0] if len(imported)==1 else cq.Compound.makeCompound(imported)
    require(model.isValid() and model.Solids(), "STEP must contain valid solids")
    drawing = Drawing(drawing_path)
    reports, rejected = [],[]
    catalog=geometry_catalog(input_step)
    available={(r["kind"],r["fingerprint"]) for r in catalog["faces"]+catalog["edges"]}
    claimed_refs=[r for f in prediction["features"] for r in f["geometry_refs"]]
    claimed_refs += [a["geometry_ref"] for d in prediction["dimensions"]+prediction["structure"] for a in d["attachments"]]
    for ref in claimed_refs:
        if (ref["kind"],ref["fingerprint"]) not in available:
            rejected.append({"geometry_ref":ref,"reason":"Geometry reference is absent from public STEP catalog"})
    owners = {}
    for view in prediction["views"]:
        report = {"id":view["id"],"type":view["type"],"geometry_ok":False,"issues":[]}
        try:
            expected,cut_shape = rebuild(model,view,tolerance)
            geometry = view["geometry"]
            for kind in ("visible","hidden","cut_edges","hatches"):
                for ref in geometry[kind]:
                    key = tuple(ref)
                    require(key not in owners or owners[key]==view["id"], "Drawing geometry reused in different views")
                    owners[key]=view["id"]
            checks = {}
            kinds = ["visible"]+(["hidden"] if geometry["hidden_policy"]=="all" else [])
            if view["type"]=="full_section": kinds += ["cut_edges","hatches"]
            for kind in kinds:
                observed = drawing.polylines(geometry[kind],frames[view["id"]],tolerance,hatch=kind=="hatches")
                checks[kind] = compare_curves(expected["cut_edges" if kind=="hatches" else kind],observed,tolerance)
                if not checks[kind]["ok"]: report["issues"].append(f"{kind}_geometry_mismatch")
            report["comparisons"]=checks
            if view["type"]=="full_section":
                report["section_markers"]=section_markers(drawing,view,frames,cut_shape,tolerance)
            report["geometry_ok"]=not report["issues"]
        except (ContractError,ValueError,KeyError,TypeError,AttributeError,RuntimeError) as exc:
            report["issues"].append(str(exc))
        reports.append(report)
    # No unreferenced/JSON-only annotation can become drawing evidence.
    for annotation in prediction["dimensions"]+prediction["structure"]:
        try:
            require(tuple(annotation["drawing_ref"]) not in owners, "Annotation reuses a geometric outline")
            entity,_ = drawing.resolve(annotation["drawing_ref"])
            require(entity.dxftype()=="DIMENSION" if annotation in prediction["dimensions"] else entity.dxftype() in ("TEXT","MTEXT"),
                    "Annotation entity type mismatch")
        except (ContractError,KeyError,ValueError,AttributeError) as exc:
            rejected.append({"id":annotation["id"],"reason":str(exc)})
    for auxiliary in prediction["auxiliary"]:
        try:
            require(tuple(auxiliary["drawing_ref"]) not in drawing.used, "Auxiliary reference reuses drawing evidence")
            entity,_ = drawing.resolve(auxiliary["drawing_ref"])
            if auxiliary["role"]=="text":
                require(entity.dxftype() in ("TEXT","MTEXT"), "Auxiliary text must be actual text")
            else:
                require(entity.dxftype()=="LINE", "Auxiliary centerline must be LINE")
                linetype=entity.dxf.linetype
                if linetype=="BYLAYER":linetype=drawing.doc.layers.get(entity.dxf.layer).dxf.linetype
                require(linetype.upper().startswith("CENTER"), "Auxiliary centerline needs a CENTER linetype")
        except (ContractError,KeyError,ValueError,AttributeError) as exc:
            rejected.append({"drawing_ref":auxiliary["drawing_ref"],"reason":str(exc)})
    unclassified = [list(path) for path in drawing.paths if path not in drawing.used]
    ok = all(v["geometry_ok"] for v in reports) and not rejected and not unclassified
    return {"schema_version":"benchcad-3d2d-view-report/0.1","case_id":prediction["case_id"],
            "status":"views_verified" if ok else "fail","score":None,"whole_drawing_complete":False,
            "view_evidence_verified":ok,"tolerance_model_mm":tolerance,**hashes,"views":reports,
            "rejected":rejected,"unclassified_entities":unclassified,
            "verified_annotation_ids":[],
            "unverified_feature_ids":[f["id"] for f in prediction["features"]],
            "unverified_annotation_ids":[a["id"] for a in prediction["dimensions"]+prediction["structure"]],
            "limitations":["General annotation attachment/semantics and feature scoring are not implemented.",
                           "Views passing this check do not establish dimension completeness or an overall score.",
                           "Orthographic projection and planar full sections only; perspective, offset/half/broken sections are unsupported.",
                           "Bounded-resolution curve comparison; visibility semantics use OpenCascade HLR.",
                           "DXF modelspace and nested single INSERT instances; paper-space viewports are unsupported."]}
