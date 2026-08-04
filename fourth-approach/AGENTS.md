# Fourth approach agent instructions

These instructions are authoritative for all work under `fourth-approach/`.

## Mission

Prepare compact, exact, contrastive mathematical evidence for GPT-5.6 Sol. Do not optimize for attempt volume, file count, or a smaller residual unless it produces new mathematical information.

Every action must help answer at least one of:

1. What minimal structure forces impossibility?
2. Which obstruction mechanisms recur across non-isomorphic supports?
3. What one local edit creates or destroys an obstruction?
4. Why are the best Second approach candidates numerically close to feasibility?
5. Which strong candidates survive all known exact obstruction classes?
6. Which `n=6` mechanisms lift to larger even `n`?
7. What concise lemma should GPT-5.6 Sol test next?

## Repository is the source of truth

Read `README.md`, `ROADMAP.md`, `TRACKING.md`, `control.json`, `launch.json`, `watchdog-state.json`, and the active run specification before acting. Do not reconstruct state from chat memory when the repository records it.

Accepted run directories are immutable. Never rewrite an accepted archive. Reference upstream First, Second, and Third approach data by commit and path; do not edit their archives in place.

## Non-interference and concurrency

Before any action, inspect all GitHub Actions runs with `queued`, `pending`, `waiting`, `requested`, or `in_progress` status across every branch and workflow when access is available.

Never cancel, modify, supersede, or duplicate a healthy run. Another large matrix may consume the same account concurrency allowance. Do not launch a new large matrix while another large matrix is active or queued.

Never edit another approach's launch file.

## Hourly guarded launch authority

The user authorized an hourly managed mode. It is not open-ended blind continuation.

One activation may perform at most one meaningful transition:

- inspect and report a meaningful status change;
- repair one confirmed technical defect;
- run or trigger one smoke validation;
- rescue one completed artifact set;
- enable one scientifically registered run;
- accept and advance one completed stage;
- stop or pivot one stalled family.

A full run may be enabled only when:

1. its run index equals `control.json.next_run_index`;
2. its immutable run specification exists;
3. it answers one scientific question;
4. the real-path smoke workflow passed for the current execution code;
5. no conflicting large run is active or queued;
6. the previous accepted run has a committed immutable archive;
7. the run index, nonce, source SHA, and artifact set are not duplicates;
8. all input schemas and source commit requirements validate.

To launch, update only `fourth-approach/launch.json`, set `enabled=true`, and use a unique nonce. Never advance merely because a residual improved.

## Smoke and execution requirements

A long run must never be the first test of new code.

Required sequence:

```text
static validation
-> unit tests
-> real-path smoke
-> inspect smoke artifacts
-> full run
-> always-upload artifacts
-> collection
-> independent verification
-> immutable commit
```

The smoke must use the real `runner.py -> collect.py -> verify_run.py` path. Each shard repeats cheap configuration and syntax checks. Diagnostic directories and files must exist before computation starts.

Do not classify success from a short list of exit codes. Classify using the manifest, required files, logs, signal/timeout context, and resource evidence. A mathematical non-result is not a technical failure; missing files, invalid options, syntax errors, assertion failures, unexplained signals, or corrupted artifacts are technical failures.

## Failure handling

Preserve partial artifacts with `if: always()` and `if-no-files-found: warn`. If computation completed but collection failed, use the rescue workflow instead of recomputing.

On a technical failure:

1. inspect steps and logs;
2. preserve available artifacts;
3. identify a confirmed cause;
4. apply the smallest repair;
5. rerun the real-path smoke;
6. relaunch the same research index only with a new nonce;
7. never advance the stage after a rejected run.

Stop automatic continuation on any technical failure, rejected collection, unexpected data shape, inability to read/write the repository, or scientific stopping condition.

## One run, one scientific question

Every run specification must state:

- research question;
- immutable source commits and datasets;
- exact transformation or search space;
- control/comparison group where relevant;
- primary metrics;
- acceptance and stopping criteria;
- expected output schema;
- independent verification path;
- which result changes the next decision.

Do not mix canonicalization, minimization, degree expansion, and broad random search into one inseparable run.

## Exact evidence

A candidate marked exact must be verified as an exact symbolic identity. For important certificates store normalized exact coefficients, full restricted system, support definition, source hashes, and precise scope. Verify important claims with both the production checker and an independently implemented checker.

Never infer the full Krenn--Gu conjecture from a support-restricted `n=6,d=3` certificate.

## Canonicalization and minimality

Before counting an object as new, canonicalize at least under vertex permutations, color permutations, edge-end ordering, polynomial term ordering, and rational scaling/sign. Report raw and canonical counts separately and store the transformation to the canonical representative.

When minimizing, distinguish inclusion-minimal, minimum-cardinality, minimum-degree, and minimum-description-length. Test support variables, edge-color types, equations, multiplier monomials, polynomial terms, nonzero coefficients, degree, and rational complexity.

## Contrast pairs and Second approach bridge

Prefer one-edit pairs with exact edit, exact or numerical status on both sides, appearing/disappearing obstruction, and controlled confounders.

Keep old-basin and independently originated Second approach candidates separate. For each bridged candidate record numerical rank/residual, origin, canonical support, obstruction class, minimal certificate, highest tested degree if unresolved, nearest contrast pair, and status.

Absence of a searched certificate is not evidence of feasibility unless the searched class and limitations are explicit.

## Primary metrics

In order:

1. independently verified new canonical obstruction classes;
2. reduced certificate description length;
3. high-quality one-edit contrast pairs;
4. coverage of top Second approach candidates;
5. hard survivors;
6. transfer to larger `n`;
7. only then residual improvement.

Attempt count alone is not scientific success.

## Stopping and pivot

Stop repeating a family after two consecutive accepted runs produce none of: a new canonical class, materially smaller certificate, new contrast pair, increased important-candidate coverage, new hard survivor, or transfer evidence. Change the mathematical target or formulation; do not merely change the seed.

## GPT-5.6 Sol handoff

Surface the full problem, scope limitations, canonical obstruction taxonomy, simplest representative certificates, contrast pairs, strongest survivors, old-versus-independent comparison, candidate lemmas ranked by evidence, falsification tests, transfer evidence, and independent verifier instructions.

Do not make thousands of near-duplicate certificates the primary input. Bulk data belongs in machine-readable appendices.

Never claim the prize problem is solved without a full exact proof or independently checkable exact counterexample for the original admissible class.
