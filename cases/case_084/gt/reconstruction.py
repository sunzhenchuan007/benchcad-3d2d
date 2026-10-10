"""Audited final-geometry parameterization for Case 84; not original CAD history.

Six dimensions define the centered rectangular/cross/rectangular stations.
The fixed planar face connectivity was inspected against the source STEP.
No STEP is imported in this construction.
"""
from __future__ import annotations

# Coordinate tags: +/-3 = outer half-width, +/-1 = neck half-width;
# Y tags: 0 = base, 2 = shoulder, 3 = top. These are labels, not multipliers.
FACE_TOPOLOGY = [
    [[3,0,3],[3,0,-3],[3,2,-1],[3,2,1]],
    [[3,0,-3],[-3,0,-3],[-1,2,-3],[1,2,-3]],
    [[-3,2,1],[-3,2,-1],[-3,0,-3],[-3,0,3]],
    [[-3,0,3],[3,0,3],[1,2,3],[-1,2,3]],
    [[3,0,-3],[3,0,3],[-3,0,3],[-3,0,-3]],
    [[1,3,1],[1,3,-1],[-1,3,-1],[-1,3,1]],
    [[-3,2,1],[-1,3,1],[-1,3,-1],[-3,2,-1]],
    [[-1,3,1],[-1,2,3],[1,2,3],[1,3,1]],
    [[1,3,-1],[1,2,-3],[-1,2,-3],[-1,3,-1]],
    [[1,3,1],[3,2,1],[3,2,-1],[1,3,-1]],
    [[1,2,-3],[1,3,-1],[1,2,-1]],
    [[1,3,-1],[3,2,-1],[1,2,-1]],
    [[1,3,1],[1,2,3],[1,2,1]],
    [[3,2,1],[1,3,1],[1,2,1]],
    [[-1,3,-1],[-1,2,-3],[-1,2,-1]],
    [[-3,2,-1],[-1,3,-1],[-1,2,-1]],
    [[-1,2,3],[-1,3,1],[-1,2,1]],
    [[-1,3,1],[-3,2,1],[-1,2,1]],
    [[-3,0,3],[-1,2,1],[-3,2,1]],
    [[-3,0,3],[-1,2,3],[-1,2,1]],
    [[3,0,3],[1,2,1],[1,2,3]],
    [[3,0,3],[3,2,1],[1,2,1]],
    [[3,0,-3],[1,2,-3],[1,2,-1]],
    [[3,0,-3],[1,2,-1],[3,2,-1]],
    [[-3,0,-3],[-3,2,-1],[-1,2,-1]],
    [[-3,0,-3],[-1,2,-1],[-1,2,-3]],
]


def build(parameters):
    import cadquery as cq
    p = parameters
    for outer, inner in (("base.width_x", "neck.width_x"), ("base.width_z", "neck.width_z")):
        if not 0 < p[inner] < p[outer]:
            raise ValueError("Neck must be positive and narrower than base")
    if p["lower.height"] <= 0 or p["upper.height"] <= 0:
        raise ValueError("Transition heights must be positive")
    def point(tag):
        x, y, z = tag
        return cq.Vector(
            (1 if x > 0 else -1) * p["base.width_x" if abs(x) == 3 else "neck.width_x"] / 2,
            {0: 0, 2: p["lower.height"], 3: p["lower.height"] + p["upper.height"]}[y],
            (1 if z > 0 else -1) * p["base.width_z" if abs(z) == 3 else "neck.width_z"] / 2,
        )
    faces = [cq.Face.makeFromWires(cq.Wire.makePolygon([point(v) for v in polygon], close=True))
             for polygon in FACE_TOPOLOGY]
    shape = cq.Solid.makeSolid(cq.Shell.makeShell(faces))
    if not shape.isValid() or shape.Volume() <= 0:
        raise ValueError("Invalid reconstructed faceted solid")
    return shape
