# Semimagic cubes

Isolated research track for the open problem of a `3 x 3` semimagic square of nine pairwise-distinct positive cubes.

## Goal

Find nine distinct positive integers `a,...,i` such that the cubes in

```text
a^3 b^3 c^3
d^3 e^3 f^3
g^3 h^3 i^3
```

have one common sum in all three rows and all three columns; alternatively obtain a proof that no such square exists.

## Current mathematical frontier

The general problem has been reduced to three alternative representations of sums of two cubes plus one exact cancellation condition. Several infinite special classes and large finite searches have already been exhausted. The current priority is the four surviving mixed-orientation branches of the one-parameter Euler family. After eliminating the third parameter they give irreducible rational curves of bidegrees `(26,22)`, `(27,27)`, `(27,27)`, and `(26,24)`.

The first compute track in this directory is designed to search these four curves for positive rational points with exact arithmetic.

## Layout

- `AGENTS.md` — operating and scientific guardrails.
- `control.json` — durable launch state; full compute is disabled until implementation and smoke validation are complete.
- `specs/` — immutable specifications for compute runs.
- `reports/` — mathematical handoffs and run summaries.
- `runs/` — accepted compact run archives.
- `src/` — implementation once added.

GitHub Actions workflow files must remain under `.github/workflows/` and should use the prefix `semimagic-cubes-`.

## Important

A finite null search is not a proof of impossibility. Floating point may rank candidates but may never decide an equality. Any candidate must be rechecked with exact integer/rational arithmetic and by an independent verifier.
