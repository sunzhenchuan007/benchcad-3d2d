"""Render the actual source solid and actual validation DXF for review."""
from __future__ import annotations
import argparse
from pathlib import Path


def render(base, case):
    import cadquery as cq
    import ezdxf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from OCP.BRepTools import BRepTools_WireExplorer
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import Configuration, ColorPolicy, BackgroundPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    shape=cq.importers.importStep(str(case/"input/model.step")).val()
    polys=[];colors=[]
    light=np.array([-.3,-.5,.8]);light/=np.linalg.norm(light)
    for face in shape.Faces():
        explorer=BRepTools_WireExplorer(face.outerWire().wrapped);points=[]
        while explorer.More():
            vertex=cq.Vertex(explorer.CurrentVertex())
            points.append((vertex.X,vertex.Z,vertex.Y));explorer.Next()
        polys.append(points)
        normal=face.normalAt();brightness=.55+.45*max(0,np.dot([normal.x,normal.z,normal.y],light))
        colors.append(np.array([.60,.77,.90])*brightness)
    fig=plt.figure(figsize=(8,7));ax=fig.add_subplot(111,projection="3d")
    ax.add_collection3d(Poly3DCollection(polys,facecolors=colors,edgecolors="#203c50",linewidths=.7))
    ax.set(xlim=(-50,50),ylim=(-50,50),zlim=(0,100),xlabel="X",ylabel="Z",zlabel="Y")
    ax.set_box_aspect((1,1,1));ax.view_init(25,-52);ax.set_title("Case 84 - original STEP")
    fig.savefig(case/"preview.png",dpi=145,bbox_inches="tight");plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,10),facecolor="white")
    doc=ezdxf.readfile(base/"submissions/good/drawing.dxf")
    config=Configuration(color_policy=ColorPolicy.BLACK,background_policy=BackgroundPolicy.WHITE)
    frontend=Frontend(RenderContext(doc),MatplotlibBackend(ax,adjust_figure=False),config=config)
    frontend.draw_layout(doc.modelspace(),finalize=True)
    ax.set_aspect("equal");ax.set_axis_off();ax.set_title("Case 84 - controlled three-view validation drawing",pad=12)
    fig.savefig(base/"drawing_review.png",dpi=160,bbox_inches="tight",facecolor="white");plt.close(fig)
    return case/"preview.png",base/"drawing_review.png"


if __name__ == "__main__":
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base",type=Path,default=root/".outputs/case_084")
    parser.add_argument("--case",type=Path,default=root/"cases/case_084")
    print(render(**vars(parser.parse_args())))
