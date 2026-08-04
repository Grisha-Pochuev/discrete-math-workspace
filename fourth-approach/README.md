# Fourth approach

## Obstruction-guided exact synthesis for GPT-5.6 Sol

Status: **safe execution infrastructure installed; run 000 is disabled until the real-path smoke workflow passes**.

The Fourth approach is not another undirected numerical search. Its purpose is to transform the accumulated First, Second, and Third approach archives into compact, exact, contrastive evidence from which GPT-5.6 Sol can infer and test structural lemmas for the Krenn--Gu conjecture.

```text
strong numerical supports from Second approach
        +
exact restricted obstructions from Third approach 2.0
        ->
canonical classes, minimal certificates, contrast pairs, hard survivors
        ->
compact GPT-5.6 Sol handoff
        ->
new exact falsification tests guided by proposed lemmas
```

## Scientific outputs

The main outputs are:

1. independently verified exact certificates for canonical support classes;
2. minimal obstruction cores;
3. one-edit contrast pairs;
4. a bridge to old-basin and independent Second approach candidates;
5. a small set of hard survivors;
6. transfer tests from `n=6` to larger even `n`;
7. a concise, auditable package for GPT-5.6 Sol.

A smaller floating-point residual is secondary and never sufficient by itself.

## Current frontier

Third approach 2.0 run `30911346279` / research index `4` completed, was accepted with `20/20` jobs, and was committed in `ae97833ea31d9aa359939b2a540aeac3d391cad8`. Fourth approach run 000 will freeze the current source frontier before any canonicalization or minimization.

## Execution files

```text
fourth-approach/
├── AGENTS.md
├── TRACKING.md
├── ROADMAP.md
├── control.json
├── launch.json
├── watchdog-state.json
├── run-specs/
├── schema.py
├── inventory.py
├── runner.py
├── collect.py
├── verify_run.py
├── tests/
├── tools/
├── runs/
├── reports/
└── sol-handoff/
```

GitHub Actions workflows:

- `fourth-approach-smoke.yml` — static checks, unit tests, real runner, real collector, and independent verifier;
- `fourth-approach-compute.yml` — guarded shard computation and immutable archive collection;
- `fourth-approach-rescue.yml` — collection of completed artifacts without recomputation.

## Hourly guarded automation

The scheduled task may advance at most one meaningful transition per activation. It must inspect all active and queued workflows, require a smoke pass for the current code, avoid duplicate run indices and nonces, preserve partial artifacts, prefer rescue over recomputation, and stop on technical failure, rejected collection, unexpected schema, or a scientific stopping rule.

The initial `launch.json` is disabled. The hourly task may enable run 000 only after the smoke workflow passes and no conflicting large matrix is active or queued.

The binding rules are in `AGENTS.md` and `TRACKING.md`; the research sequence is in `ROADMAP.md`.

## Evidence hierarchy

From strongest to weakest:

1. independently checked exact symbolic identity;
2. exact identity checked by the production verifier;
3. modular or interval evidence with a documented reconstruction path;
4. high-precision numerical lead;
5. ordinary floating-point lead.

No restricted certificate may be described as proving the full conjecture. The original admissible class and all even `n >= 6` remain the final target.
