# Initial counterexample-oriented plan

## Research question

Can a dense support and a carefully tuned system of complex edge weights satisfy all monochromatic target amplitudes while cancelling every mixed coloring, without triggering the three obstruction types seen in the sparse frontier search?

## Search strategy

### 1. Dense support families

Explore supports above the well-sampled sparse region, beginning with sizes 31–45 and then extending upward. Include:

- random dense supports;
- symmetry-guided supports;
- perturbations of known closed supports;
- supports selected to avoid one-term and two-term mixed amplitudes;
- full-support and near-full-support test families.

### 2. Direct nonlinear weight search

For each support, optimize complex edge weights against an objective that:

- minimizes all mixed-color amplitudes;
- keeps the three monochromatic target amplitudes nonzero and balanced;
- fixes scale and phase gauges to prevent artificial divergence;
- rewards candidates that evade the existing exact obstruction analyzer.

Use several independent seeds and more than one optimization method. A candidate is interesting even when it is only a near-solution, provided its full residual profile is saved.

### 3. Adversarial search against known certificates

Generate candidates specifically designed to avoid:

- inconsistent sign relations;
- reduction of a mixed amplitude to a single monomial;
- reduction of a monochromatic target to zero.

The goal is not to assume these certificates are complete, but to search where they are least informative.

### 4. Promotion and validation

Promote candidates when they achieve unusually low mixed residuals while maintaining nontrivial target amplitudes. Then:

1. rerun at higher precision;
2. test stability under perturbation;
3. cluster equivalent or near-equivalent candidates;
4. attempt algebraic-number reconstruction;
5. apply exact symbolic checks where feasible.

## Required outputs for every run

- exact configuration and random seeds;
- support masks and support sizes;
- normalized complex weights for promoted candidates;
- complete mixed and monochromatic residual summaries;
- status under all existing exact obstruction checks;
- convergence history and numerical precision;
- logs, checksums, and a compact human-readable summary.

## Interpretation rule

Failure to find a candidate is evidence only about the tested family and optimization method. It must not be reported as a proof of the conjecture.
