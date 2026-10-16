# Review checklist

## Source changes

- [ ] Case number and source links identify the intended original.
- [ ] Source package still follows the versioned STEP/SLDPRT contract.
- [ ] Paths, sizes and hashes pass tools/verify_sources.py.
- [ ] Alternative versions and provenance are preserved.
- [ ] Readiness reflects evidence; no automatic upgrade from a folder name or pilot result.

## Current task and GT

- [ ] Input STEP hash, units and coordinate frame are fixed; any neutral cache is declared.
- [ ] Section GT is approved and bound to the correct geometry; draft annotations are not treated as final.
- [ ] Required, optional and alternative rules are explicit; tolerances and angle requirements are versioned.
- [ ] GT, native design history and evaluator outputs are not exposed to the drawing AI.
- [ ] Reconstruction AI sees only final DXF, its rendered PNG and general instructions.
- [ ] Full dimension chains and expert-DXF reconstruction baselines are not reintroduced as mandatory tasks.

## CAD backend and submission

- [ ] Native save/reopen, DXF export, preview and state extraction are distinguished by producer and stage.
- [ ] Derived state is bound to the final native/export version; AI claims are not accepted as execution evidence.
- [ ] Actual DXF evidence is checked independently; hashes alone do not prove drawing correctness.
- [ ] Unsupported complex sections fail explicitly rather than being treated as ordinary full sections.
- [ ] Local pilot evidence, published code, planned FreeCAD capability and complete acceptance are labeled separately.
- [ ] Backend dependencies and installation do not require installing the other CAD backend.

## Evaluation and reporting

- [ ] Metric version and allowed normalization/rotation/reflection policy are recorded.
- [ ] Mirror-inclusive selected IoU is distinguished from rotation-only IoU and absolute-size diagnostics.
- [ ] Identical-geometry controls are not reported as AI scores; diagnostic corrections are not new AI attempts.
- [ ] Collision candidates are not automatically counted as confirmed violations.
- [ ] Equivalent valid layouts are accepted; fewer views do not excuse missing required content.
- [ ] Missing GT, invalid geometry, unsupported functionality, timeouts and infrastructure failures are explicit.
- [ ] Time, token, cached input, cost assumptions and attempt counts use consistent units without double counting.
- [ ] No total-score or leaderboard claim is made without calibrated complete components.
- [ ] Raw local logs, host configuration and private material are excluded from publication.

Historical feature-tree and dimension-chain validation has separate research value, but is not this checklist's active scoring route.
