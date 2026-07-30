# Third approach final report

Status: **paused after eight accepted long runs**.

The last completed workflow run (`30532177734`, research index `7`) was already collected and committed by the workflow in commit `9911920bf7a9c5cc5842e86278e3fb3e73c6daf9`. This report records the complete series and the decision not to launch run index `8`.

## Scope and interpretation

The third approach searched for numerical low-degree Nullstellensatz-style certificate candidates for **restricted `n=6, d=3` support families**. The optimized score is a validation residual with a coefficient-norm penalty; lower is better. A numerical score is not a proof. An exact proof candidate would still require exact coefficient reconstruction and symbolic verification of the full polynomial identity.

This series therefore evaluates the present restricted affine-certificate search design. It does not settle the full Krenn--Gu conjecture.

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
- Saved candidates in per-run archives: **3,200** entries before cross-run bank deduplication and truncation.
- Worker errors recorded in accepted summaries: **0**.
- Best score of the whole series: **0.24965130097292565**, found in run index `4`.
- Improvement of the global record relative to run `0`: **0.883%**.
- The last three runs did not improve the record; the final run was **1.885% worse** than the record.
- Median saved score improved from `0.3158977904` to `0.3028772510`, an improvement of about **4.12%**.

## Dynamics

### Best-candidate frontier

The per-run best scores were:

```text
0.2518749790
0.2563201818
0.2524222584
0.2509241098
0.2496513010  <- global record
0.2557589905
0.2531755545
0.2543583192
```

The global record changed only twice after the first run:

```text
run 0: 0.2518749790
run 3: 0.2509241098
run 4: 0.2496513010
runs 5-7: no further improvement
```

The frontier therefore showed a small early improvement followed by a three-run plateau. It did not move toward the near-zero residual that would motivate exact reconstruction.

### Typical saved candidates

The median saved score improved much more consistently than the best score. This means the search became better at producing generally decent candidates, but it did not discover a qualitatively new certificate family. In practical terms, the distribution improved while the frontier remained stuck.

### Reusing previous candidates

Parent-based mutation was genuinely active, but its yield declined. The fraction of saved parent-based candidates that improved their parent was approximately:

```text
run 1: 32.7%
run 2: 30.3%
run 3: 30.2%
run 4: 21.9%
run 5: 13.1%
run 6: 15.0%
run 7: 19.0%
```

This is evidence of local refinement and diminishing returns. Mutation continued to produce improvements relative to individual parents, but after run `4` those local improvements did not create a new global record.

### Diversity

The saved archives retained almost the maximum number of distinct support fingerprints (`397-400` out of 400), while structural buckets fluctuated between `55` and `63`. Thus the plateau was not merely caused by exact duplication of one support. The search continued to generate many syntactically distinct supports, but this diversity did not translate into better certificate scores. The final run had only `55` structural buckets, the lowest count in the series, but the whole sequence shows fluctuation rather than a clean monotone collapse.

## Scientific conclusion

The eight runs provide useful negative evidence about this **specific computational formulation**:

1. The restricted affine Nullstellensatz candidate family did not produce a residual remotely close to an exact identity.
2. Adaptive reuse of strong and structurally different parents improved ordinary candidates but did not break the best-score barrier.
3. Increasing fresh exploration to 60% also failed to produce a new record in three consecutive runs.
4. The best global improvement after more than one billion attempts was less than 1%.

Continuing the same code, degree, support regime, and objective is therefore low-value. The present third approach should remain paused unless its mathematical search space is changed substantially—for example by using a different certificate degree, a symmetry-reduced exact formulation, rational reconstruction around specially selected structures, or a SAT/SMT/Gröbner-style exact stage.

The archived candidates and summaries remain useful as data about which restricted structures were explored and where the affine numerical certificate model saturated. They should not be described as a proof or as evidence that the full conjecture is proved.

## Final repository state

- Last accepted run: `30532177734` / index `7`.
- Collector archive commit: `9911920bf7a9c5cc5842e86278e3fb3e73c6daf9`.
- `third-approach/control.json`: `enabled=false`.
- No successor run was launched.
