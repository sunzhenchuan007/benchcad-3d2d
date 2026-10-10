"""Render actual DXF artifacts for visual review; never synthesizes dimensions."""
from __future__ import annotations

import argparse
from pathlib import Path


def render(base):
    import ezdxf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import Configuration, ColorPolicy, BackgroundPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    variants = [("good", "正确：中心距 56，厚度 20"),
                ("redundant_dimension", "重复：中心距 56 画两次"),
                ("conflicting_dimension", "矛盾：中心距 56 与 60"),
                ("missing_dimension", "缺失：未画厚度 20"),
                ("conflict_and_missing", "矛盾＋缺失：56 / 60，无厚度"),
                ("redundant_and_missing", "重复＋缺失：56 两次，无厚度")]
    font = FontProperties(fname="C:/Windows/Fonts/msyh.ttc")
    figure, axes = plt.subplots(2, 3, figsize=(18, 16), facecolor="white")
    for ax, (name, title) in zip(axes.flat, variants):
        doc = ezdxf.readfile(base/"submissions"/name/"drawing.dxf")
        config = Configuration(color_policy=ColorPolicy.BLACK, background_policy=BackgroundPolicy.WHITE)
        frontend = Frontend(RenderContext(doc), MatplotlibBackend(ax, adjust_figure=False), config=config)
        def monochrome(entity, properties):
            properties.color = "#000000"
        frontend.push_property_override_function(monochrome)
        frontend.draw_layout(doc.modelspace(), finalize=True)
        ax.set_xlim(-94, 94); ax.set_ylim(-160, 70); ax.set_aspect("equal", adjustable="box")
        ax.set_title(title, fontproperties=font, fontsize=12, pad=14, color="black")
        ax.set_axis_off()
    figure.tight_layout()
    output = base/"drawing_comparison.png"
    figure.savefig(output, dpi=160, facecolor="white")
    plt.close(figure)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path(__file__).resolve().parents[1]/".outputs/controlled_c002")
    print(render(parser.parse_args().base))
