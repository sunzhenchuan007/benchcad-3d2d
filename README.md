# BenchCAD 3D2D

**Feature understanding and dimension-complete engineering drawings from STEP solids.**

模型输入 STEP 实体，识别特征及其参数关系，并生成能够完整表达零件几何的二维工程图。GT 从 SLDPRT 特征树或等价的 CadQuery 程序提取，依据独立参数与约束构建，不依赖配套工程图。

This repository contains the task proposal and six pilot cases from T1: **01, 13, 15, 84, 86, and 88**. Only STEP and SLDPRT source assets are included. Source collection and integrity checks are complete; native CAD pairing, feature extraction, and the scoring implementation remain to be completed.

## Repository layout

```text
cases/<case_id>/
├── case.json          # source records, hashes, candidate files, readiness
└── sources/           # STEP and SLDPRT; original version folders preserved
docs/
├── DESIGN.md          # full task and verifier proposal in Chinese
├── CASE_SPEC.md       # source case contract and planned evaluation boundary
├── REVIEWING.md       # data and semantic review checklist
└── STATUS.md          # current evidence and implementation status
registry.json         # pilot case index
tools/verify_sources.py
```

## Start here

- [Task and scoring proposal](docs/DESIGN.md)
- [Case contract](docs/CASE_SPEC.md)
- [Input and output layout](docs/INPUT_OUTPUT.md)
- [Dimension-chain search algorithm](docs/RELATION_SEARCH.md)
- [Worked JSON example](examples/dimension_chain/README.md)
- [Contributing](CONTRIBUTING.md)
- [Review checklist](docs/REVIEWING.md)
- [Status and next implementation steps](docs/STATUS.md)

```bash
python tools/verify_sources.py
```

The command verifies source paths, file types, sizes, SHA-256 hashes, and registry consistency. It does **not** extract a feature tree, validate CAD geometry, or score a model. Python 3.10 or later is sufficient; no third-party dependencies are required.

## Task boundary

| Item | Role |
| --- | --- |
| STEP solid | Model input, with geometry inspection and measurement tools |
| SLDPRT feature tree or equivalent CQ program | Private GT construction source |
| Recognized features and relations | Model output, included in the main score |
| Generated drawing and structured annotations | Model output for dimensional and view verification |

The dataset package contains GT source material. A future evaluator must expose only the selected STEP and public tool contract to the model, not the entire case directory.

## Proposed scoring

| Component | Initial weight |
| --- | ---: |
| Feature recognition | 40% |
| Dimensional and structural completeness | 35% |
| View expression | 20% |
| Expression efficiency | 5% |

These weights are a proposal, not calibrated benchmark results. Feature recognition accepts normalized equivalent feature structures or CQ constructions; it does not require reproducing the original modeling history. Whole-drawing completeness is reported separately from the aggregate score.

## Pilot cases

| Group | Cases | Purpose |
| --- | --- | --- |
| Basic pipeline | 84, 88 | Source extraction, parameter GT, and drawing output |
| Equivalent dimensions | 01, 13 | Alternative dimension chains and cross-view constraints |
| Complex structure | 86, 15 | Larger feature structures and section-view verification |

The groups define the first experiment, not a measured difficulty ranking. Multiple source versions remain distinct until their geometry and units have been checked.

The repository organization follows [BenchCAD 2 main](https://github.com/BenchCAD-org/benchcad-2/tree/5d47436e375ba635979ca441f3cc89403da311a2): a concise entry point, explicit case contracts, provenance records, contribution and review guidance, and focused CI. This is a separate project; the BenchCAD 2 family validator is not a 3D2D verifier.
