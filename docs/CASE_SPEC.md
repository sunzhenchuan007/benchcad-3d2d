# Case contract

## Source package

Each `cases/case_NNN/` directory contains `case.json` and a `sources/` subtree. Source assets are limited to `.step`, `.stp`, and `.sldprt`, case-insensitively. Existing source version folders are retained. No paired engineering drawings are required.

`case.json` uses `benchcad-3d2d-source/1` and records:

- Case ID, original T1 number, title, pilot group, and Drive folder URL.
- Every asset's relative path, type, byte count, SHA-256, Drive ID, URL, and original path.
- `status: source_collected`, `pairing_verified: false`, and `gt_extracted: false` for the initial import.
- Nullable `input_step` and `gt_source`. These remain unset until a source pair is selected and verified.

`registry.json` indexes exactly the case directories present in this repository. `tools/verify_sources.py` checks this source contract and file integrity only.

## Selected development cases (source/2, registry/2)

Registry version 2 accepts unchanged source/1 collected entries alongside selected source/2 entries. Case 84 is the first selected entry, with `status: development_ready`, `pairing_verified: true`, and `gt_extracted: true`. This means an audited native-derived parameterization and the controlled development verifier can be rerun; it does not mean production calibration, arbitrary drawing support or expert acceptance.

The selected entry sets `input_step: input/model.step`, `gt_source` to an existing archived SLDPRT, `gt_file: gt/gt.json`, and `validation_file: gt/validation.json`. Its artifact manifest records portable paths, byte counts and SHA-256 for exactly: the selected STEP, GT, CQ reconstruction, raw native extraction report, native comparison STEP, validation report, README and 3D preview. Archived sources remain STEP/SLDPRT only; CQ construction belongs to private `gt/`, and paired reference drawings are not added to cases.

The integrity checker validates every artifact and its evidence links, rejects unlisted files (apart from Python bytecode caches), and checks the input matches an original STEP. It does **not** rerun geometry or infer semantics from a readiness flag. `tools/verify_case84_geometry.py` independently compares the native-exported and parameter-reconstructed solids against the selected input, regenerates GT, and exercises actual controlled DXF fixtures. Native extraction can be repeated on a licensed SOLIDWORKS/pywin32 host using `tools/extract_native_features.py`; ordinary CI uses the captured native evidence and recomputes the geometry comparisons.

GT schemas remain development version 0.1; the source lifecycle contract is independently versioned. Other five source cases remain unselected and are not ready for scoring. The plate-hole synthetic demonstration lives under `examples/plate_holes/`, outside the case registry.

## Pair selection and GT extraction

Before declaring a case ready, compare the selected STEP with the final geometry in the selected SLDPRT or independently verified CQ program. Check units, coordinate frame, solids, dimensions, and shape; verify that the native file contains useful modeling features rather than only an imported body.

Extract a normalized feature representation, geometry references, continuous variables, discrete structure, and parameter dependencies. Filter suppressed and non-contributing history. Review the resulting independent parameter set against the final solid.

CQ is an alternative construction representation, not a guarantee of an identical feature history. No CQ reconstructions are included in the initial source import. A future extension adding CQ sources must revise and version the source contract and integrity checker together.

Do not infer readiness from a source folder named `verified` or `gt`. In particular, Case 88's original T1 `gt/gt.step` is a candidate **input** to the new 3D2D task.

## Planned evaluation boundary

The future evaluator exposes only the selected STEP and public tool instructions. Native CAD, parameter GT, and source notes remain unavailable to the tested model.

The planned submission contains a generated drawing, recognized features or an equivalent CQ construction, and machine-readable view and annotation records. Prediction IDs are matched to GT by geometry and normalized semantics; hidden GT IDs are not supplied as answers.

The generated drawing and its structured records must agree. Parameters present only in prediction JSON or known only to the geometry backend do not count as information expressed on the drawing.

The target input, GT, and submission layout is specified in [INPUT_OUTPUT.md](INPUT_OUTPUT.md), with a [worked JSON example](../examples/dimension_chain/README.md) and a [relation-search algorithm](RELATION_SEARCH.md). The [v0.1 framework](FRAMEWORK.md) provides development schemas and an executable solver plus a controlled-DXF adapter. Production schemas remain unfrozen. This source metadata schema does not establish that the six source cases have valid GT or are ready for model-submission scoring.
