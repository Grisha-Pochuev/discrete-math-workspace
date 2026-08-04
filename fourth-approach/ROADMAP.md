# Fourth approach roadmap

This roadmap is sequential. A later stage is not launched merely because the previous compute job finished. Each stage begins only after the preceding evidence has been reviewed and its outputs satisfy `AGENTS.md`.

## Stage 0 — ingest the completed Third approach 2.0 frontier

Wait for the currently running Third approach 2.0 run to finish and commit through its existing collector. Do not change that run.

Then freeze source commit identifiers for:

- all accepted Third approach 2.0 exact-certificate archives;
- the best old-basin Second approach candidates;
- the best independently originated Second approach candidates;
- relevant exact obstruction data from the First approach;
- the ordinary Third approach negative and plateau report.

Output: `reports/source-inventory.md` and machine-readable source manifest.

## Stage 1 — canonicalization and independent verification

Scientific question: how many mathematically distinct exact obstruction classes are present after removing symmetry and duplicate representation?

Tasks:

- canonicalize supports under vertex and color permutations;
- normalize exact certificates;
- group certificates by canonical support and structural signature;
- run an independent exact verifier;
- report raw, canonical, verified, rejected, and ambiguous counts separately.

Primary success metric: independently verified canonical classes, not raw certificate count.

## Stage 2 — certificate minimization

Scientific question: what is the smallest exact mechanism that explains each obstruction class?

Tasks:

- remove support variables and edge-color types;
- remove equations and multiplier monomials;
- reduce multiplier degree;
- sparsify coefficients;
- reduce rational coefficient complexity;
- preserve exact verification after every accepted reduction.

Outputs:

- simplest representative per obstruction class;
- explicit minimality notion and tested reductions;
- description-length statistics.

## Stage 3 — one-edit deletion contrasts

Scientific question: which individual support elements are necessary for an exact obstruction?

For each selected minimal obstruction support `S`, test canonical children `S - {e}`.

Record whether each child:

- remains exactly closed by the same mechanism;
- is exactly closed by a different mechanism;
- requires a higher tested certificate degree;
- remains unresolved;
- becomes numerically strong.

Primary output: one-edit pairs where an obstruction disappears or changes type.

## Stage 4 — one-edit addition contrasts

Scientific question: which individual additions create an obstruction or move a support across the exact frontier?

For selected unresolved or numerically strong supports `S`, test canonical neighbors `S + {e}`.

Prefer pairs controlling all structure except the single added edge-color variable.

Primary output: causal contrast pairs useful for lemma discovery and falsification.

## Stage 5 — bridge to the old Second approach basin

Scientific question: why are the historically best numerical candidates close to feasibility?

Use a stratified target set:

- absolute numerical champions;
- structurally diverse old-basin candidates;
- support-mutated descendants;
- representatives across residual quantiles.

For each target, report known obstruction class, minimal certificate, tested degree, nearest contrast pair, and unresolved status.

## Stage 6 — bridge to independent Second approach lineages

Repeat Stage 5 without mixing old-basin and independent-lineage statistics.

Compare:

- obstruction-class coverage;
- certificate size and degree;
- hard-survivor rate;
- structural distance to exact closed supports;
- residual distribution conditioned on obstruction type.

Scientific decision: determine whether the same finite taxonomy plausibly explains both origins.

## Stage 7 — targeted higher-degree search on hard survivors

Scientific question: are important unresolved supports outside the known low-degree certificate class or merely computationally harder instances?

Select only a small canonical set satisfying all of:

- strong numerical status;
- no known low-degree exact certificate;
- no simple First approach obstruction;
- structural diversity;
- independent verification of all inputs.

Test bounded degree expansion and exact methods. Do not run broad degree-4/5 search over the full space.

Outputs distinguish:

- newly closed supports;
- technically incomplete tests;
- genuine survivors relative to a precisely stated search class.

## Stage 8 — transfer tests beyond `n=6`

Scientific question: can any minimal obstruction mechanism become a general lemma?

Initial tests should be hypothesis-driven rather than broad random search:

- embed an `n=6` obstruction core into `n=8`;
- test invariance under adding a matched vertex pair;
- test local-to-global combinations on overlapping six-vertex subsets;
- search for parameterized coefficient patterns;
- identify mechanisms depending only on a bounded local configuration.

A common exact template at `n=6` and `n=8` is more valuable than thousands of new `n=6` certificates.

## Stage 9 — GPT-5.6 Sol reasoning cycle

Prepare the compact handoff described in `sol-handoff/README.md`.

Ask Sol to:

1. propose structural lemmas explaining the minimal classes;
2. test each lemma against all contrast pairs and hard survivors;
3. repair falsified lemmas using the smallest counterexamples;
4. derive consequences for arbitrary even `n`;
5. specify new exact computations that distinguish competing generalizations.

Every Sol proposal must return to an exact falsification loop before it is treated as progress.

## Initial launch decision

Stages 0 and much of Stage 1 are data-processing and verification work. They should be implemented before creating a 20-job Fourth approach compute workflow.

When a large run becomes justified, its launch remains manual unless a finite, pre-approved batch meets the bounded automation conditions in `AGENTS.md`.