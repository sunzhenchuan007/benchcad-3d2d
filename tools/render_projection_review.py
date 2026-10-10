"""Render actual general-view DXF; review labels are outside drawing evidence."""
from pathlib import Path


def main():
    import ezdxf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import Configuration, ColorPolicy, BackgroundPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    root=Path(__file__).resolve().parents[1]
    base=root/".outputs/general_views/good"
    doc=ezdxf.readfile(base/"drawing.dxf")
    fig,ax=plt.subplots(figsize=(14,8),facecolor="white")
    frontend=Frontend(RenderContext(doc),MatplotlibBackend(ax,adjust_figure=False),
                      config=Configuration(color_policy=ColorPolicy.BLACK,background_policy=BackgroundPolicy.WHITE))
    frontend.draw_layout(doc.modelspace(),finalize=True)
    labels=[(-210,65,"Oblique projection / 123 deg / 0.9x"),
            (160,170,"XY / 31 deg / 0.75x"),(-80,-190,"XZ / -47 deg / 1.25x"),
            (300,-25,"YZ / 19 deg / 0.6x"),(170,-175,"Oblique planar section B-B / 67 deg / 1.1x")]
    for x,y,label in labels:ax.text(x,y,label,ha="center",va="center",fontsize=9,color="#234463")
    ax.set_aspect("equal");ax.set_axis_off()
    ax.set_title("Actual DXF: independent STEP projection checks (view evidence only)",pad=14)
    fig.savefig(base/"review.png",dpi=145,bbox_inches="tight",facecolor="white")
    plt.close(fig)
    print(base/"review.png")


if __name__=="__main__":main()
