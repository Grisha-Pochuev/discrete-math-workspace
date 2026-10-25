# Compute summary — 2026-08-17

This is the compact accepted operational summary for the current track.

## g0

- GitHub Actions run: `32036067787`
- Source commit: `04f4f2d4bbe5ea0f35f9fb47fe1b537e91b866c4`
- 20 matrix jobs completed successfully.
- Parameter ceiling: 1100.
- Roughly 131.59 billion pair tests.
- Exact multiplicative ratio hits: 2, both in class 0.
- Near records at relative gap <= 1e-14: 0.
- Exact cancellations reported by the rational verifier: 0.
- Accepted solutions: 0.
- The finite range completed quickly; no global impossibility conclusion follows.

## g1

- GitHub Actions run: `32038711869`
- Source commit: `a725b02318289845dbda2cef5742104142f6f4ca`
- 20 matrix jobs plus collector completed successfully.
- Parameter ceiling supplied to each worker: 2350.
- Search budget per worker: 19,800 seconds (5.5 hours).
- All 20 workers ended by their clean internal time limit; therefore the full ceiling 2350 was NOT exhausted.
- Total pair tests: `1,365,872,658,020`.
- Exact multiplicative ratio hits: 2, both in class 0 (AAB).
- Near records at relative gap <= 1e-14: 0.
- Exact cancellations reported by the rational verifier: 0.
- Accepted solutions: 0.

Continuous completed first-parameter denominator coverage inferred from the shard summaries:

| class | label | continuous denominator coverage |
|---:|:---:|---:|
| 0 | AAB | 1592 |
| 1 | ABA | 1732 |
| 2 | ABB | 1561 |
| 3 | BAA | 1422 |
| 4 | BAB | 1408 |
| 5 | BBA | 1487 |

For every completed first parameter, the lookup structure used the full parameter list constructed with ceiling 2350. Cyclic sharding also checked many first parameters above the continuous boundaries, but those higher regions are not contiguous and must not be described as completely covered.

## Important audit caveat

`src/w0.cpp` counts exact multiplicative ratio hits, but in the current version writes a candidate record only after the floating relative-gap filter succeeds. Therefore the two exact ratio hits were not persisted as explicit triples for independent rational replay because neither passed the `1e-14` near filter.

Before treating a future null run as a strong computational certificate, change the worker so EVERY exact ratio hit is persisted and rationally checked, independently of the floating prefilter. This should be a separate scientific-code change, not silently mixed into this repository reorganization.

## Current interpretation

No solution was found. These runs give strong negative evidence inside the searched mixed one-parameter Euler-family region, but they do not solve the original general problem and they do not prove the entire Euler family impossible.
