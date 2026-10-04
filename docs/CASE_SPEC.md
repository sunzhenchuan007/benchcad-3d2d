# Case contract

## Source package

Each `cases/case_NNN/` directory contains `case.json` and a `sources/` subtree. Source assets are limited to `.step`, `.stp`, and `.sldprt`, case-insensitively. Existing source version folders are retained. No paired engineering drawings are required.

`case.json` uses `benchcad-3d2d-source/1` and records:

- Case ID, original T1 number, title, pilot group, and Drive folder URL.
- Every asset's relative path, type, byte count, SHA-256, Drive ID, URL, and original path.
- `status: source_collected`, `pairing_verified: false`, and `gt_extracted: false` for the initial import.
- Nullable `input_step` and `gt_source`. These remain unset until a source pair is selected and verified.

`registry.json` indexes exactly the case directories present in this repository. `tools/verify_sources.py` checks this source contract and file integrity only.

## Pair selection and GT extraction

Before declaring a case ready, compare the selected STEP with the final geometry in the selected SLDPRT or independently verified CQ program. Check units, coordinate frame, solids, dimensions, and shape; verify that the native file contains useful modeling features rather than only an imported body.

Extract a normalized feature representation, geometry references, continuous variables, discrete structure, and parameter dependencies. Filter suppressed and non-contributing history. Review the resulting independent parameter set against the final solid.

CQ is an alternative construction representation, not a guarantee of an identical feature history. No CQ reconstructions are included in the initial source import. A future extension adding CQ sources must revise and version the source contract and integrity checker together.

Do not infer readiness from a source folder named `verified` or `gt`. In particular, Case 88's original T1 `gt/gt.step` is a candidate **input** to the new 3D2D task.

## Planned evaluation boundary

The future evaluator exposes only the selected STEP and public tool instructions. Native CAD, parameter GT, and source notes remain unavailable to the tested model.

The planned submission contains a generated drawing, recognized features or an equivalent CQ construction, and machine-readable view and annotation records. Prediction IDs are matched to GT by geometry and normalized semantics; hidden GT IDs are not supplied as answers.

The generated drawing and its structured records must agree. Parameters present only in prediction JSON or known only to the geometry backend do not count as information expressed on the drawing.

The target input, GT, and submission layout is specified in [INPUT_OUTPUT.md](INPUT_OUTPUT.md), with a [worked JSON example](../examples/dimension_chain/README.md) and a [relation-search algorithm](RELATION_SEARCH.md). The full production schemas are to be frozen during implementation. The source metadata schema shipped here is not a claim that a model-submission verifier already exists.
