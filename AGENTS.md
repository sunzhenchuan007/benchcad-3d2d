# BenchCAD 3D2D agent guide

Read `README.md`, `docs/DESIGN.md`, and `docs/CASE_SPEC.md` before changing the task contract or data.

- Confirm this checkout with `git rev-parse --show-toplevel` and `git status --short --branch` before commits and pushes.
- Use absolute repository paths for Git operations and preserve unrelated changes.
- Run `python tools/verify_sources.py` for source or registry changes. It is not a geometry or scoring check.
- Keep source assets to STEP and SLDPRT under the current contract; do not add paired drawings.
- Feature recognition is part of the main task. GT comes from native features or equivalent CQ construction, normalized against final geometry.
- Do not expose native GT sources to the model or equate historical modeling order with the unique correct answer.
- Do not invent extraction results, model scores, or source-pair validation.
- Keep scoring proposals labeled until implemented and calibrated.
- Use DCO-signed commits and focused PRs with reviewable evidence.
- Publish future repository changes through an issue-linked PR from a work branch; do not push changes directly to the default branch.
