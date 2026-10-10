# General view evidence validation

Local validation on 2026-10-10, using the existing CadQuery/OCP, ezdxf and NumPy environment:

- Full suite: **67 tests passed, no skips**.
- Source integrity: **6 cases, 16 archived CAD assets, 30,455,221 bytes**. Source/selected-case manifests were not changed.
- JSON Schema: the prediction/0.2 schema is valid; all nine generated submissions satisfy its structural contract. Structurally valid wrong answers still fail geometric verification.
- Independent analytic test: a manually constructed DXF CIRCLE matches a cylinder's STEP projection under translation, rotation and scaling. This test does not use the projection generator to construct the answer.
- Neutral STEP face/edge catalogs are repeatable; they contain no GT feature names or required variables.

`tools/build_projection_demo.py` uses the existing plate-hole demonstration and creates five views: XY, XZ, YZ, an oblique orthographic projection, and an oblique planar full section. Each view has a different sheet position, rotation and scale, with nested INSERT instances and arbitrary block names. Outputs stay in `.outputs/general_views/`, outside the registry.

| Submission | Expected and observed result |
| --- | --- |
| Correct five-view drawing | views_verified; no overall score |
| Wrong projection direction in JSON | fail: actual visible geometry does not match rebuilt projection |
| Wrong cutting plane in JSON | fail: contours, cut edges, hatch boundaries and cutting trace disagree |
| Missing drawn geometry | fail: expected-to-drawing comparison |
| Extra drawn geometry | fail: drawing-to-expected comparison |
| Reversed section arrows | fail: arrows disagree with viewing direction |
| Missing actual cutting trace | fail: referenced DXF evidence absent |
| Displaced hatch boundary | fail: hatch boundary disagrees with cut material |
| JSON-only section declaration | fail: actual section entities absent |

Additional regressions reject file hash mismatches, invalid/left-handed camera frames, private GT bindings, self-reported scores, unclassified actual lines, and reused annotation evidence. Feature JSON with a valid neutral face reference remains explicitly **unverified as a feature**, even when view geometry passes.

The new report always uses `score: null` and `whole_drawing_complete: false`; `views_verified` does not mean complete engineering drawing. General annotation attachments, dimension semantics, required-feature view coverage, readability, complex sections and production calibration remain open under issue #5. The existing development scorer now exposes the different JSON/drawing evidence sources in `score_basis` without changing its weights or historical fixture scores.

Remote CI is separate from these local results; consult the issue-linked PR checks for the exact committed revision. Rerun with:

```sh
python -m unittest discover -s tests -v
python tools/verify_sources.py
python tools/build_projection_demo.py
python tools/render_projection_review.py
```
