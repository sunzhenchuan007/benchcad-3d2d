# Case contract

## Source package

Each `cases/case_NNN/` directory contains `case.json` and a `sources/` subtree. Source assets are limited to `.step`, `.stp`, and `.sldprt`, case-insensitively. Existing source version folders are retained. No paired engineering drawings are required.

`case.json` uses `benchcad-3d2d-source/1` and records:

- Case ID, original T1 number, title, pilot group, and Drive folder URL.
- Every asset's relative path, type, byte count, SHA-256, Drive ID, URL, and original path.
- `status: source_collected`, `pairing_verified: false`, and `gt_extracted: false` for the initial import.
- Nullable `input_step` and `gt_source`. These remain unset until a source pair is selected and verified.

`registry.json` indexes exactly the case directories present in this repository. `tools/verify_sources.py` checks this source contract and file integrity only.

## Native pairing and parameter GT (historical optional route)

The current [evaluation design](DESIGN.md) uses the selected standardized STEP as
the geometric reference and manually annotated section requirements as section
GT. Full native feature extraction and dimensional-chain reconstruction are no
longer required before running this route. Historical native-pairing and GT
extraction flags still describe the evidence actually collected; this document
change does not alter those flags or upgrade case readiness.

Before declaring a case ready, compare the selected STEP with the final geometry in the selected SLDPRT or independently verified CQ program. Check units, coordinate frame, solids, dimensions, and shape; verify that the native file contains useful modeling features rather than only an imported body.

Extract a normalized feature representation, geometry references, continuous variables, discrete structure, and parameter dependencies. Filter suppressed and non-contributing history. Review the resulting independent parameter set against the final solid.

CQ is an alternative construction representation, not a guarantee of an identical feature history. No CQ reconstructions are included in the initial source import. A future extension adding CQ sources must revise and version the source contract and integrity checker together.

Do not infer readiness from a source folder named `verified` or `gt`. In particular, Case 88's original T1 `gt/gt.step` is a candidate **input** to the new 3D2D task.

## Planned evaluation boundary

The drawing AI receives the selected standardized STEP and public tool instructions.
Neutral geometric references may be computed from that exact STEP. Native CAD,
manual section targets and expert drawing references remain unavailable to it.

The current submission is a DXF drawing and JSON describing its actual sections
and their view/drawing associations. Recognition of holes and other features is
assessed through the resulting drawing, reconstructed geometry and section
expression; a separate feature-tree or dimension-chain JSON is not required.

An independent verification AI reconstructs STEP from the submitted DXF only.
The original STEP, reference STEP, submission JSON and private GT are not mounted
in its workspace. A script compares the reconstructed and reference solids using
volume IoU. Other checks inspect section positions and actual DXF annotation
collisions, with weights and acceptance policies still to be calibrated.

The drawing and its section records must agree; a section declared only in JSON
does not prove it is present on the drawing. The target boundaries are specified
in [INPUT_OUTPUT.md](INPUT_OUTPUT.md). Historical [dimension-chain examples](../examples/dimension_chain/README.md)
and [relation-search algorithms](RELATION_SEARCH.md) are retained for reference.
Production schemas remain unfrozen. The source metadata schema does not establish
that a complete model-submission scorer already exists.
