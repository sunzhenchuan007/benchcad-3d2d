# Contributing

This project develops a STEP-to-drawing benchmark with feature recognition as a major scored component. Current work starts from the six pilot cases and the [design proposal](docs/DESIGN.md).

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
- Use the final feature structure and parameter constraints to construct GT. Do not require paired drawings.
- Keep model-visible STEP input separate from private GT sources.
- Accept equivalent constructions. Do not grade raw CQ text or original feature order as the answer.
- Do not fabricate parameters, sources, extraction results, or successful validation.
- Mark unsupported feature classes explicitly; they must not silently pass.
- Keep score proposals distinct from implemented and calibrated metrics.
- Commit with a DCO sign-off (`git commit -s`) using the contributor's configured identity.

The initial commit is a source and design baseline. It does not certify the six cases for benchmark scoring.
