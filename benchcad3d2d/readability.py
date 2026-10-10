"""Controlled vector label collisions, separate from dimensional correctness.

Font bounding boxes are conservative. This is not a complete drafting-standard
or arbitrary PDF/image visibility checker. Dimension/extension line crossings
without text involvement are not treated as label occlusion.
"""
from __future__ import annotations


def segment_hits_rectangle(start, end, rectangle):
    lower = 0.; upper = 1.
    for axis in (0,1):
        delta = end[axis]-start[axis]
        if abs(delta) < 1e-12:
            if not rectangle[axis] <= start[axis] <= rectangle[axis+2]:return False
        else:
            a = (rectangle[axis]-start[axis])/delta
            b = (rectangle[axis+2]-start[axis])/delta
            lower = max(lower,min(a,b)); upper = min(upper,max(a,b))
            if lower > upper:return False
    return True


def inspect_labels(doc, block, rules):
    from ezdxf import bbox
    margin = rules["clearance_mm"]
    labels = []; lines = []; issues = []; collision_keys = set()

    def visible(entity):
        layer = doc.layers.get(entity.dxf.layer)
        return not entity.dxf.get("invisible",0) and not layer.is_off() and not layer.is_frozen()

    for entity in block:
        if not visible(entity):continue
        owner = entity.dxf.handle
        graphics = doc.blocks[entity.dxf.geometry] if entity.dxftype() == "DIMENSION" else [entity]
        for graphic in graphics:
            if not visible(graphic):continue
            if graphic.dxftype() in ("TEXT","MTEXT"):
                extent = bbox.extents([graphic], fast=False)
                if not extent.has_data:
                    issues.append({"type":"unsupported_text_bounds","owner":owner});continue
                rect = [extent.extmin.x-margin,extent.extmin.y-margin,
                        extent.extmax.x+margin,extent.extmax.y+margin]
                labels.append((owner,rect,graphic.plain_text()))
            elif graphic.dxftype() == "LINE":
                lines.append((owner,list(graphic.dxf.start)[:2],list(graphic.dxf.end)[:2]))
    for i,(owner,rect,text) in enumerate(labels):
        for other,other_rect,other_text in labels[i+1:]:
            if owner == other:continue
            overlap = rect[0] < other_rect[2] and other_rect[0] < rect[2] and rect[1] < other_rect[3] and other_rect[1] < rect[3]
            if overlap:
                key = tuple(sorted([owner,other]))
                if key not in collision_keys:
                    collision_keys.add(key)
                    issues.append({"type":"text_text_collision","owners":[owner,other],"text":[text,other_text]})
        for other,start,end in lines:
            if owner == other:continue  # Own dimension graphics are designed together.
            if segment_hits_rectangle(start,end,rect):
                key = tuple(sorted([owner,other]))
                if key not in collision_keys:
                    collision_keys.add(key)
                    issues.append({"type":"text_line_collision","owners":[owner,other],"text":text})
    penalty = min(rules["budget_points"],len(collision_keys)*rules["collision_points"])
    return {"readability_complete":not issues,"readability_score":1-penalty/rules["budget_points"],
            "readability_penalty_points":penalty,"readability_issues":issues,
            "readability_scope":"font-based text boxes against text and LINE geometry in each controlled view"}
