# Third approach final report

Status: **paused after eight accepted long runs**.

The last completed workflow run (`30532177734`, research index `7`) was collected and committed in `9911920bf7a9c5cc5842e86278e3fb3e73c6daf9`. This report records the series and the decision not to launch run index `8`.

## Scope and interpretation

This track evaluated one restricted low-degree certificate-search formulation. The optimized score is a validation residual with a coefficient-norm penalty; lower is better. A numerical score is not exact verification and requires an independent reconstruction/checking stage before stronger conclusions are allowed.

## Complete run table

| Index | GitHub run | Policy fresh / elite / diverse | Attempts | Best score | Median saved score | Structural buckets | Support fingerprints | Parent improvements saved | Jobs | Worker errors |
|---:|---:|:---:|---:|---:|---:|---:|---:|---:|:---:|---:|
| 0 | 30374839615 | 100 / 0 / 0 | 135,362,934 | 0.2518749790 | 0.3158977904 | 58 | 400 | 0 | 20/20 | 0 |
| 1 | 30402187471 | 45 / 35 / 20 | 131,334,894 | 0.2563201818 | 0.3148193881 | 60 | 400 | 87 | 20/20 | 0 |
| 2 | 30420705510 | 45 / 35 / 20 | 131,763,317 | 0.2524222584 | 0.3110865044 | 63 | 400 | 83 | 20/20 | 0 |
| 3 | 30441345989 | 60 / 20 / 20 | 135,289,576 | 0.2509241098 | 0.3093906761 | 61 | 397 | 74 | 20/20 | 0 |
| 4 | 30467633005 | 40 / 40 / 20 | 136,133,532 | **0.2496513010** | 0.3064182248 | 58 | 400 | 68 | 20/20 | 0 |
| 5 | 30493977537 | 60 / 20 / 20 | 133,898,348 | 0.2557589905 | 0.3080481907 | 57 | 400 | 34 | 20/20 | 0 |
| 6 | 30512061952 | 60 / 20 / 20 | 135,118,284 | 0.2531755545 | 0.3066426796 | 63 | 400 | 36 | 20/20 | 0 |
| 7 | 30532177734 | 60 / 20 / 20 | 138,715,291 | 0.2543583192 | **0.3028772510** | 55 | 399 | 44 | 20/20 | 0 |

## Aggregate facts

- Accepted long runs: **8**.
- Completed compute jobs: **160/160**.
- Total numerical attempts: **1,077,616,176**.
- Saved per-run candidate entries before cross-run bank deduplication/truncation: **3,200**.
- Worker errors in accepted summaries: **0**.
- Best score of the series: **0.24965130097292565**, found in run index `4`.
- Improvement of the global record relative to run `0`: **0.883%**.
- The last three runs did not improve the record.
- Median saved score improved from `0.3158977904` to `0.3028772510`, about **4.12%**.

## Dynamics

Best scores by run:

```text
0.2518749790
0.2563201818
0.2524222584
0.2509241098
0.2496513010
0.2557589905
0.2531755545
0.2543583192
```

The global record improved only through run index `4` and then plateaued for three runs. Typical saved candidates improved more consistently than the frontier, indicating better local refinement without discovery of a qualitatively stronger family.

Parent-based mutation remained active but showed diminishing returns. Saved archives retained almost the maximum number of distinct support fingerprints (`397-400` out of 400), while structural buckets ranged from `55` to `63`, so the plateau was not caused merely by exact duplication of one support.

## Conclusion

The eight runs provide useful negative evidence about this specific computational formulation. More than one billion attempts produced less than a 1% improvement in the best score, and the final three runs did not improve the global record. Continuing the same code and search regime is therefore low-value unless the search space or verification strategy changes substantially.

The archived candidates and summaries remain useful for cross-track comparison and later structural analysis.

## Final repository state

- Last accepted run: `30532177734` / index `7`.
- Collector archive commit: `9911920bf7a9c5cc5842e86278e3fb3e73c6daf9`.
- `third-approach/control.json`: `enabled=false`.
- No successor run was launched.
