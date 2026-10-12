# Status

## Current direction

The current [design](DESIGN.md) accepts standardized STEP input and DXF plus section JSON output. Dimensional-chain verification is retired from this evaluation route. An independent AI reconstructs STEP from DXF only; geometry IoU, section-position requirements and drawing-quality checks provide the proposed evaluation components. Weights and failure policies remain unfrozen.

## Published in this repository

- Six registered source cases: 01, 13, 15, 84, 86, and 88.
- Sixteen STEP/SLDPRT assets with original version paths and source records.
- File-size and SHA-256 integrity verification.
- Updated design and target input/output boundaries.
- Historical dimension-chain specification and synthetic JSON example, retained for reference.

| Case | Files | Source state | Geometry pairing | GT extraction |
| --- | ---: | --- | --- | --- |
| 01 | 2 | Collected | Pending | Pending |
| 13 | 3 | Collected | Pending | Pending |
| 15 | 2 | Collected | Pending | Pending |
| 84 | 3 | Collected | Pending | Pending |
| 86 | 2 | Collected | Pending | Pending |
| 88 | 4 | Collected | Pending | Pending |

This documentation change does not modify source assets, case manifests or registry readiness. Development work on other branches is separate from evidence published on the default branch.

## Deployed annotation workbench and local development

The [section workbench](https://2d.cuptlab.site) is online with seven STEP model pages (1, 11, 13, 15, 84, 86, 88). It supports standard views, axis snapping/highlighting, axial/transverse position rules, optional plane-angle requirements and compact draft JSON export/import. It remembers the annotator in the current browser and offers next-case navigation. STEP uploads are processed through an authenticated upload endpoint. Browser annotation records remain local until exported.

Case 84 has no detected selectable rotational axes and currently supports model viewing rather than axis annotation. Case 11 is a separate experiment and is not added to the six-case source registry by this PR.

The workbench and upload flow have browser QA evidence; local STEP-IoU development components have geometry checks. Their implementation files, private GT and deployment credentials are outside this documentation-only change. A STEP compared with itself yielding IoU 1 is a scorer self-check, not an AI reconstruction result.

## Pending for the new evaluation route

1. Freeze the drawing and section submission interface, including supported section types and actual DXF evidence bindings.
2. Complete necessary/recommended GT classification and matching policy; current webpage drafts do not yet contain this classification.
3. Execute and calibrate DXF-only AI reconstruction on trusted expert drawings with actual file isolation.
4. Connect reconstruction output to reproducible IoU reports and define alignment, resolution and failure handling.
5. Complete general DXF annotation collision checks, section-JSON-to-drawing consistency and view-redundancy reports.
6. Calibrate penalties and weights with controlled drawing defects, then validate on independent cases.

No end-to-end model scores, calibrated overall metric or leaderboard results are claimed. CI source checks validate the source package, not CAD geometry, reconstruction reliability or drawing quality.
