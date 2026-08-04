# Fourth approach agent instructions

These instructions are authoritative for all work under `fourth-approach/`.

## Mission

The Fourth approach exists primarily to prepare mathematically useful evidence for GPT-5.6 Sol. It must transform large computational archives into compact exact objects from which a reasoning model can infer, test, refine, and possibly prove structural lemmas for the Krenn--Gu conjecture.

Do not optimize for the volume of attempts, the number of files, or a smaller floating-point score unless the change produces new mathematical information.

## Central question

Every action should help answer at least one of the following:

1. What minimal structure forces impossibility?
2. Which obstruction types recur across non-isomorphic supports?
3. What single local change creates or destroys an obstruction?
4. Why do the best Second approach candidates remain numerically close to feasibility?
5. Which strong candidates survive all known exact obstruction classes?
6. Which `n=6` mechanisms persist or lift to larger even `n`?
7. What concise lemma should GPT-5.6 Sol attempt to prove next?

## Non-interference rule

Before any repository action, inspect all GitHub Actions runs with `queued`, `pending`, or `in_progress` status across every branch and workflow when the necessary access is available.

Never cancel, modify, supersede, or duplicate a healthy running computation. In particular, do not touch an active Third approach 2.0 run or its launch configuration. Let its own collector commit its archive.

Creating or editing Fourth approach research documents must not modify another approach's launch file.

## Launch policy

### Initial phase: manual scientific gate

Every full Fourth approach run requires explicit user approval after the previous result has been inspected. The monitoring task may:

- inspect workflow health and concurrency;
- diagnose technical failures;
- preserve and collect already computed artifacts;
- run or recommend a bounded smoke test;
- prepare the next configuration without enabling it;
- report whether the pre-registered success criteria were met.

The monitoring task must **not** autonomously start the next full Fourth approach run during the initial phase.

This rule exists because Fourth approach runs are sequential experiments with different scientific questions, not interchangeable repetitions.

### Later bounded automation

Automatic continuation may be enabled only for a user-approved finite batch when all of the following hold:

1. the workflow has passed a real-path smoke test;
2. at least two preceding runs of the same family completed and collected without technical repair;
3. the run family has fixed inputs, fixed metrics, and a finite count;
4. every successor configuration is specified in advance;
5. no other large matrix is active or queued;
6. the automation stops on technical failure, rejected collection, unexpected data shape, or scientific stopping condition;
7. the user explicitly approved that bounded batch.

Never create open-ended automatic continuation merely because the numerical score improved.

## One run, one scientific question

Before enabling a full run, create a run specification containing:

- research question;
- source datasets and immutable commit identifiers;
- exact transformation or search space;
- control or comparison group;
- pre-registered primary metrics;
- acceptance criteria;
- scientific stopping criteria;
- expected output schema;
- independent verification plan;
- what result would change the next decision.

A run that mixes canonicalization, minimization, degree expansion, and broad random search without separable outputs is invalid.

## Evidence and verification

A candidate marked exact must be checked as an exact symbolic identity. Floating-point proximity is not exactness.

For important certificates:

1. verify with the production verifier;
2. verify with an independently implemented checker that does not reuse the same simplification code;
3. store the normalized exact coefficients;
4. store the complete restricted system and support definition;
5. store hashes of all source inputs;
6. record the precise scope of what the certificate proves.

Never infer a statement about all admissible graphs from a certificate for a support-restricted `n=6,d=3` subsystem.

## Canonicalization requirements

Before counting a support or certificate as new, canonicalize under all symmetries explicitly allowed by the representation, including at minimum:

- vertex permutations;
- color permutations;
- normalization of edge-end ordering;
- normalization of polynomial terms;
- normalization of rational certificate scaling and sign.

Record both the canonical identifier and the transformation from the original object. Report raw counts and canonical counts separately.

## Minimality requirements

When minimizing an obstruction, test removal or simplification of:

- support variables or edge-color types;
- selected GHZ equations;
- multiplier monomials;
- polynomial terms;
- nonzero certificate coefficients;
- multiplier degree;
- numerator and denominator complexity.

Do not call a certificate minimal without stating the tested notion of minimality. Inclusion-minimal, minimum-cardinality, minimum-degree, and minimum-description-length are different claims.

## Contrast-pair requirements

A contrast pair must contain:

- canonical parent and child identifiers;
- the exact edit between them;
- exact status for each side when known;
- best numerical status when exact status is unknown;
- which obstruction appears or disappears;
- all confounders controlled by construction.

Prefer one-edit pairs. Multi-edit pairs must state why a one-edit decomposition was unavailable.

## Bridge to Second approach

Keep old-basin and independently originated Second approach candidates as separate lineages. Never merge their statistics before reporting them separately.

For every bridged candidate record:

- numerical rank and residual;
- origin and lineage;
- canonical support identifier;
- known exact obstruction class;
- minimal certificate if found;
- highest tested certificate degree if not found;
- nearest exact contrast pair;
- status: closed, unresolved, or technically untested.

Absence of a certificate is not evidence of feasibility unless the searched certificate class and its limitations are stated.

## Metrics

Primary metrics, in order of importance:

1. independently verified new canonical obstruction classes;
2. reduction in certificate description length;
3. high-quality one-edit contrast pairs;
4. coverage of top Second approach candidates;
5. number and quality of hard survivors;
6. transfer of a mechanism to larger `n`;
7. only then numerical residual improvement.

Do not use attempt count as a scientific success metric by itself.

## Run acceptance

A run is accepted only when:

- its preflight and real-path smoke test passed;
- the expected jobs and artifacts are present;
- technical failures are distinguished from mathematical non-results;
- all summaries reproduce from immutable raw artifacts;
- exact claims pass their declared verification path;
- canonical counts are reproducible;
- the archive is committed with source commit identifiers and checksums.

Preserve partial artifacts after failure. Do not relabel a technical failure as a mathematical non-result.

## GPT-5.6 Sol handoff standard

The handoff must be answer-oriented, compact, and auditable. It should contain:

1. the exact full problem and the limited scope of current computations;
2. a taxonomy of canonical obstruction mechanisms;
3. the simplest representative certificate of each mechanism;
4. contrast pairs that support or falsify candidate lemmas;
5. the strongest unresolved supports;
6. old-basin versus independent-lineage comparison;
7. proposed general lemmas ranked by evidence;
8. explicit falsification tests for each proposed lemma;
9. transfer evidence for larger `n` when available;
10. independent verifier instructions.

Do not give Sol thousands of near-duplicate certificates as the primary input. Put bulk data in appendices or machine-readable files and surface the smallest diverse representatives.

## Scientific stopping and pivot rules

Stop repeating a run family when two consecutive accepted runs produce none of:

- a new canonical obstruction class;
- a materially smaller certificate;
- a new high-quality contrast pair;
- increased coverage of important Second approach candidates;
- a new hard survivor;
- transfer evidence to larger `n`.

A lower residual alone does not override this stopping rule.

When a family stalls, change the mathematical search space, exact formulation, or target set. Do not merely change the random seed and continue indefinitely.

## Repository discipline

- Store all Fourth approach materials under `fourth-approach/` except the dedicated workflow file when one is eventually created under `.github/workflows/`.
- Do not edit First, Second, or Third approach archives in place.
- Reference upstream data by commit and path; copy only normalized derived data needed for reproducibility.
- Use immutable per-run directories.
- Keep a human-readable summary next to every machine-readable result.
- Record confirmed facts, inferences, and hypotheses separately.
- Never claim that the prize problem is solved without a full exact proof or independently checkable exact counterexample for the original admissible class.