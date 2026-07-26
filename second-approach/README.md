# Second approach

This directory is an independent, counterexample-oriented research track for the Krenn–Gu problem.

The existing frontier search is valuable for enumerating sparse closed supports and certifying why they fail. This second approach is deliberately different: it searches for dense, nonlinear candidates and complex edge weights that avoid the three currently observed exact obstructions.

## Purpose

- search directly for counterexample candidates rather than only classifying sparse supports;
- explore denser supports, especially beyond the well-sampled size-30 region;
- preserve near-solutions and unresolved cases instead of discarding them;
- separate heuristic evidence from exact verification;
- provide reproducible data for later mathematical analysis.

## Bias-control rules

1. Do not require a candidate to contain many two-term mixed equations.
2. Do not rank candidates by how easily the existing obstruction analyzer can reject them.
3. Preserve every candidate with unusually small mixed residuals or unusually strong monochromatic amplitudes.
4. Record failed and unresolved attempts, not only successful certificates.
5. Use deterministic seeds, complete configurations, and checksums for every substantial run.
6. Validate promising candidates independently with higher precision and exact algebra whenever possible.

## Directory layout

- `plans/` — experimental designs and hypotheses;
- `runs/` — one subdirectory per compute run;
- `candidates/` — compact candidate records and promoted near-solutions;
- `analysis/` — comparisons, clustering, and mathematical interpretation;
- `schemas/` — stable formats for configurations and results.

This track must remain separate from the existing frontier archives so the two search strategies can be compared without mixing their assumptions or evidence.
