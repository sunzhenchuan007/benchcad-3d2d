# Implementation status

Updated 2026-10-16. **One repository, two CAD backends. SolidWorks has a local Case 13 pipeline result; FreeCAD is planned. Neither is a published, fully portable and calibrated benchmark runner.**

## In the repository

- Operator CLI for prepared SolidWorks runtimes: `tools/solidworks.py` supports
  init, doctor, run, status and results. No new CAD/model trial is implied;
  the controller/tool runtime still needs separate local preparation.
- Six registered T1 source cases: 01, 13, 15, 84, 86, 88; sixteen STEP/SLDPRT assets.
- Source path, size and SHA-256 checks; source readiness unchanged by this update.
- Bounded operation-log consumer and synthetic protocol tests, merged in PR #15. No vendor adapter, CAD execution or geometry scoring in that consumer.
- Shared architecture, input/output contract, backend documentation, local pilot report, and current metric policy.
- Historical dimension-chain materials retained for traceability, not used by the active evaluation route.

## Local evidence versus integrated implementation

| Component | Evidence / limitation |
|---|---|
| SolidWorks + Codex CLI | One local Case 13 drawing → DXF → independent reconstruction → IoU trial completed |
| Portable runner | Local controller and CAD scripts have not been migrated into the public backend directories |
| Geometry metric | Local normalized 24 rotations + 24 reflected orientations; selected IoU 0.9996046703, reflection used |
| Absolute dimensions | Input is not rescaled; scoring normalizes size and reports size diagnostics separately |
| Section JSON | Local script reads final native drawing; not AI-authored; not yet integrated with the public log consumer |
| Section score | Case 13 lacks approved GT; not scored |
| Collision score | 12 approximate text-bounds candidates in Case 13; no complete penalty |
| View efficiency | Category and reference-count policy documented; full scorer pending |
| Isolation | Some local boundaries tested; all tool/file access paths not fully accepted |
| FreeCAD | Documentation and acceptance checklist only; no end-to-end run claimed |
| Overall score | Not computed; weights and failure policies unfrozen |
| Expert reconstruction baseline | Deferred; no expert DXF → STEP baseline or denominator correction |

The pilot report is a checked reading edition of local records, not a public reproducibility package. Raw artifacts, logs and machine settings are not included. Its results do not promote the six source manifests to scoring-ready status. A self-comparison IoU of 1 is an evaluator check, not an AI result.

## Cases and annotation workbench

The source registry still contains six cases. A separate local selection names Drive T1 01–10 for the next batch; that is not ten completed or registered runs. Case 11 remains outside this publication.

The existing section workbench link is [2d.cuptlab.site](https://2d.cuptlab.site). Earlier work documented seven model pages, axis selection, compact GT drafts, annotator persistence and next-case navigation; Case 84 had no selectable detected axes. Its live deployment was not rechecked or modified in this update. Draft export is not GT acceptance, and UI ability does not establish backend scoring capability.

## Next work

1. Port the local SolidWorks controller with portable configuration and full access-boundary validation.
2. Implement and test the FreeCAD shared subset and final-state adapter.
3. Connect backend final state to the versioned event/manifest contract and real DXF evidence checks.
4. Approve GT, implement collision/view-efficiency scoring and controlled-defect checks.
5. Freeze reconstruction sampling, budgets, failure handling and score composition before leaderboard claims.

See [decisions and PR disposition](DECISIONS.md), [architecture](ARCHITECTURE.md), and [local pilot report](experiments/case013-solidworks-codex.md).
