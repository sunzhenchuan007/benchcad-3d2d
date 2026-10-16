# Contributing

This project evaluates STEP-to-drawing AI through independent reconstruction, section requirements and drawing quality. SolidWorks and FreeCAD are separate CAD backends in one repository. See the [current design](docs/DESIGN.md) and [implementation status](docs/STATUS.md).

## Contribution loop

1. Open a case or implementation proposal with source evidence and a bounded deliverable.
2. For a case, retain STEP and SLDPRT provenance and verify the selected geometry pair.
3. Update `case.json` and `registry.json` when source metadata changes.
4. Run `python tools/verify_sources.py` and any checks required by the implementation change.
5. Submit a focused PR that links the issue, states what was verified, and lists unresolved items.
6. Have a reviewer use [REVIEWING.md](docs/REVIEWING.md).

Prefer one case per data PR; changes to the corresponding registry entry are allowed. Framework or documentation PRs should state their scope separately.

## Engineering rules

- Preserve source geometry and distinct versions; document intentional replacements.
- Use selected STEP geometry as the reconstruction reference and approved human section requirements as section GT. Full dimension-chain extraction and expert-DXF reconstruction correction are not prerequisites.
- Keep model-visible STEP input separate from private GT sources.
- Accept equivalent valid drawing layouts and expressions. Do not grade raw CQ text or original feature order as the answer.
- Do not fabricate parameters, sources, extraction results, or successful validation.
- Mark unsupported view/section types and extraction gaps explicitly; they must not silently pass.
- State backend, CAD/tool/model versions, budgets and metric version for every run.
- Keep local evidence separate from published executable capability; do not publish credentials, host settings, raw private logs or unapproved GT.
- Keep score proposals distinct from implemented and calibrated metrics.
- Commit with a DCO sign-off (`git commit -s`) using the contributor's configured identity.

The initial commit is a source and design baseline. It does not certify the six cases for benchmark scoring.
