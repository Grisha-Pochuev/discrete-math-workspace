# Run 000 — exact rational-point search on the mixed Euler frontier

**Status:** design only. Do not launch the full matrix until implementation and smoke validation exist.

## 1. Scientific objective

Attack the four surviving mixed-orientation branches of the special one-parameter Euler family. The run is successful scientifically if it does either of the following:

1. finds a positive rational point that reconstructs to a genuine 3×3 semimagic square of nine distinct positive cubes; or
2. produces new exact, auditable rational-height coverage / local information that materially narrows one or more branches.

A null finite run is **not** a proof of impossibility for the original problem.

## 2. Exact Euler family

For a rational parameter `0 < u < 1/2`, define

```text
P(u) = 1 - u + 3u^2
Q(u) = 1 + u + 3u^2
C(u) = 1 - 2u - 3u^3
D(u) = 1 + 2u + 3u^3
```

with the exact identity

```text
P(u)^3 + Q(u)^3 = C(u)^3 + D(u)^3.
```

There are two edge orientations:

```text
A: top=(P,Q), alternative=(C,D)
B: top=(C,D), alternative=(P,Q)
```

Define top ratios and normalized alternative differences

```text
R_A(u) = P(u)/Q(u)
R_B(u) = C(u)/D(u)

F_A(u) = (D(u)^3 - C(u)^3) / Q(u)^3
F_B(u) = (Q(u)^3 - P(u)^3) / D(u)^3.
```

For ordered top bases `a < b < c`, with parameters `u,v,w` on edges `ab,bc,ac`, respectively, the exact ratio condition is

```text
R_Tac(w) = R_Tab(u) * R_Tbc(v).
```

The three absolute alternative differences after normalizing `c=1` are

```text
Delta_ab = R_Tbc(v)^3 * F_Tab(u)
Delta_bc = F_Tbc(v)
Delta_ac = F_Tac(w).
```

Exact row cancellation requires one of

```text
Delta_ab + Delta_bc = Delta_ac
Delta_ab + Delta_ac = Delta_bc
Delta_bc + Delta_ac = Delta_ab.
```

The homogeneous AAA and BBB cases are already excluded by proof and must not be searched again.

## 3. Reproducible branch generation — mandatory prerequisite

Do not trust a hand-copied high-degree polynomial.

Implementation must include an exact symbolic generator that:

1. enumerates all mixed type triples `(Tab,Tbc,Tac)` in `{A,B}^3 \ {AAA,BBB}` and all three cancellation placements;
2. forms the exact rational ratio and cancellation equations above;
3. eliminates `w` exactly;
4. clears denominators and takes primitive parts;
5. factors over `Q`;
6. removes factors corresponding to forbidden denominators, boundary parameters, duplicated top ratios, or previously proved sign-definite branches only with explicit exact certificates;
7. identifies the four genuinely sign-changing target factors;
8. asserts that their bidegrees are exactly
   `(26,22)`, `(27,27)`, `(27,27)`, `(26,24)` in the selected `(u,v)` ordering;
9. writes canonical coefficient files plus SHA-256 hashes.

A second independent checker must substitute random exact rational test points into both the pre-elimination system and the stored resultant/factor identities to detect transcription or normalization mistakes. Random tests are supplementary; the symbolic identities themselves must also be checked exactly.

## 4. Primary search algorithm

For each target branch polynomial `H_j(u,v) in Z[u,v]`:

### 4.1 Enumerate u exactly

Enumerate every reduced rational

```text
u = a/b,  gcd(a,b)=1,  0 < a < b/2
```

in increasing denominator blocks.

### 4.2 Specialize to a univariate polynomial

For each `u=a/b`, compute exactly

```text
G(v) = primitive_integer_polynomial( H_j(a/b, v) ).
```

No floating-point coefficients are allowed.

### 4.3 Modular projective-root sieve

Before expensive factorization, test `G` for a possible **projective** rational root modulo a fixed, recorded set of good primes. A rational root `v=c/d` reduces to a projective root `[c:d]` for every good prime, including the case `p | d`; therefore the sieve must check the homogenized polynomial and must not discard infinity incorrectly.

If any good prime has no projective root, reject this `u` exactly.

The prime list and bad-prime exclusions must be committed with the source and recorded in every run manifest.

### 4.4 Exact rational-root extraction

For survivors, use an exact FLINT-backed polynomial routine to find all degree-1 factors over `Q`. Full numerical root finding is not acceptable.

For every rational root `v` keep only `0 < v < 1/2`.

### 4.5 Reconstruct w from the original ratio equation

Do **not** accept a resultant point without reconstruction, because elimination may introduce extraneous factors.

Let

```text
r = R_Tab(u) * R_Tbc(v).
```

If `Tac=A`, solve exactly

```text
3(1-r) w^2 - (1+r) w + (1-r) = 0.
```

If `Tac=B`, solve exactly

```text
3(1+r) w^3 + 2(1+r) w - (1-r) = 0.
```

Extract rational roots only and require `0 < w < 1/2` plus exact equality

```text
R_Tac(w) = r.
```

### 4.6 Verify cancellation and reconstruct the square

Verify the selected cancellation equation with exact rationals.

Normalize the top row by `c=1`:

```text
a = R_Tac(w)
b = R_Tbc(v)
c = 1.
```

For an A-edge with parameter `x`, the alternative pair relative to its larger top base is

```text
(C(x)/Q(x), D(x)/Q(x)).
```

For a B-edge it is

```text
(P(x)/D(x), Q(x)/D(x)).
```

Thus:

- edge `bc` gives `(d,g)` directly relative to `c`;
- edge `ac` gives `(e,h)` directly relative to `c`;
- edge `ab` gives `(f,i)` after multiplying its normalized alternative pair by `b/c = R_Tbc(v)`.

Choose the pair swaps matching the cancellation signs. Clear all denominators by one LCM, divide the common gcd, then require:

- all nine integer bases positive;
- all nine bases pairwise distinct;
- all six cube sums exactly equal.

Any surviving candidate must also be checked by a second independent verifier that knows nothing about the Euler parametrization.

## 5. Full GitHub Actions allocation

Use exactly 20 GitHub-hosted Ubuntu jobs, four CPU workers per job: 80 CPU workers total.

```text
jobs  0..4   -> branch 0
jobs  5..9   -> branch 1
jobs 10..14  -> branch 2
jobs 15..19  -> branch 3
```

Each job starts four independent worker processes. Therefore each branch gets 5 machines = 20 CPU workers.

Within a branch, number workers `0..19`. Split denominator work into blocks of 64 consecutive denominator values. Branch worker `k` owns block IDs congruent to `k (mod 20)`. Process blocks in increasing block ID and checkpoint after every completed block.

This block-cyclic assignment makes the coverage deterministic and auditable without cross-runner coordination. The collector must report the exact set of completed blocks and the largest fully contiguous denominator ceiling for each branch; it must never infer coverage from elapsed time.

## 6. Runtime

Full compute budget per job:

```text
19,800 seconds = 5 h 30 min of search
```

GitHub job timeout:

```text
360 minutes = 6 h
```

The remaining ~30 minutes are reserved for checkout, dependency setup, validation, final checkpointing, compression, and artifact upload. Do not extend the worker runtime to the full six hours.

Each worker should receive a virtual-memory cap of approximately 2.5 GiB unless smoke measurements justify a lower cap. Disable accidental nested BLAS/OpenMP threading so four workers really use roughly four CPU cores rather than oversubscribing the runner.

## 7. Smoke run — mandatory

Before Run 000 full:

- one Ubuntu runner only;
- four worker processes;
- at most 10 minutes compute;
- generate all four branch polynomials from scratch;
- verify their canonical hashes and bidegrees;
- exercise modular sieve, exact factorization, `w` reconstruction, and candidate verifier on real search data;
- verify checkpoint/resume and collector logic;
- record actual `nproc`, CPU model, RAM, dependency versions, and throughput.

The smoke run determines whether block size 64 and the 2.5 GiB cap are appropriate. Changes after smoke require updating this spec or creating a new immutable spec.

## 8. Artifacts and acceptance

Every full job artifact must contain at least:

- source commit SHA;
- branch ID and exact branch-polynomial SHA-256;
- worker IDs;
- completed denominator block IDs;
- counts: `u` tested, modular rejects by prime, exact factorizations, rational `v` roots, reconstructed rational `w`, exact cancellations, distinct-square candidates;
- best near-misses only as diagnostic data, clearly labelled non-proofs;
- machine diagnostics and dependency versions;
- clean/timeout/failure status.

The collector accepts a run only if all claimed coverage is reconstructible from completed blocks and every candidate record passes the independent exact verifier.

If a shard fails, preserve successful shards and run a targeted rescue for missing blocks rather than recomputing the entire matrix.

## 9. Scientific interpretation

A full null Run 000 permits statements only of the form:

> On branch j, every reduced rational u=a/b in the explicitly certified completed denominator blocks was specialized; after an exact projective modular sieve and exact rational factorization, no positive rational point reconstructing to a distinct positive semimagic cube square was found.

It does **not** imply that the branch has no rational points, and it does not solve the original problem by impossibility.

## 10. Why this run is preferred

This run targets the current algebraic frontier directly. It is stronger than merely raising the old base bound or rerunning the older Morgenstern/Euler finite searches: for each tested rational `u`, exact univariate factorization finds **all rational v**, with no independent height bound on `v`.
