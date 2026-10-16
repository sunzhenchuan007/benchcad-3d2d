# BenchCAD 3D2D agent guide

Read `README.md`, `docs/DESIGN.md`, and `docs/CASE_SPEC.md` before changing the task contract or data.

- Confirm this checkout with `git rev-parse --show-toplevel` and `git status --short --branch` before commits and pushes.
- Use absolute repository paths for Git operations and preserve unrelated changes.
- Run `python tools/verify_sources.py` for source or registry changes. It is not a geometry or scoring check.
- Keep source assets to STEP and SLDPRT under the current contract; do not add paired drawings.
- Current evaluation uses independent drawing-to-STEP AI reconstruction, section GT and actual drawing quality checks. Dimension-chain/feature-tree scoring is historical; expert-DXF reconstruction correction is deferred. See docs/DESIGN.md and docs/DECISIONS.md.
- Do not expose native GT sources to the model or equate historical modeling order with the unique correct answer.
- Do not invent extraction results, model scores, or source-pair validation.
- Keep scoring proposals labeled until implemented and calibrated.
- Use DCO-signed commits and focused PRs with reviewable evidence.

- Maintain SolidWorks and FreeCAD as separate CAD backends in this repository; distinguish local evidence, published code, and planned functionality.
- Publish repository changes through an issue-linked PR. Do not publish raw local logs, machine-specific settings, private GT or credentials.
