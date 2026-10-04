# Status

## Available

- Six source cases: 01, 13, 15, 84, 86, and 88.
- Sixteen STEP/SLDPRT assets with original version paths and source records.
- File-size and SHA-256 integrity verification.
- Revised task proposal covering feature recognition, degrees of freedom, dimensions, views, and proposed weights.
- Explicit target input/GT/submission layout and the dimension-chain search specification.
- A synthetic JSON relation example with manually derived expectations; no executed solver or complete CAD case is implied.

| Case | Files | Source state | Geometry pairing | GT extraction |
| --- | ---: | --- | --- | --- |
| 01 | 2 | Collected | Pending | Pending |
| 13 | 3 | Collected | Pending | Pending |
| 15 | 2 | Collected | Pending | Pending |
| 84 | 3 | Collected | Pending | Pending |
| 86 | 2 | Collected | Pending | Pending |
| 88 | 4 | Collected | Pending | Pending |

## Implementation sequence

1. Select and verify STEP/native pairs; inspect the feature classes present.
2. Implement native feature extraction and the common feature representation; reserve a CQ adapter.
3. Freeze GT and prediction schemas, references, tolerances, and supported feature classes.
4. Implement recognition scoring and structured drawing generation.
5. Implement dimensional constraints and geometric view verification.
6. Run the controlled perturbation tests in the design proposal, then calibrate weights on additional cases.

The source check in CI validates the package, not the CAD geometry or benchmark metrics. No model runs, completed verifier, or leaderboard results are included yet.
