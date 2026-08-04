# Fourth approach

## Obstruction-guided exact synthesis for GPT-5.6 Sol

Status: **research workspace initialized; no Fourth approach compute workflow is active**.

The Fourth approach is not another undirected numerical search. Its purpose is to turn the accumulated results of the First, Second, and Third approaches into compact, exact, contrastive mathematical evidence that GPT-5.6 Sol can use to discover a general proof mechanism or identify the most credible counterexample frontier for the Krenn--Gu conjecture.

The core loop is:

```text
numerically strong supports from Second approach
        +
exact restricted obstructions from Third approach 2.0
        ->
canonical classes, minimal certificates, contrast pairs, hard survivors
        ->
reasoning package for GPT-5.6 Sol
        ->
new exact tests guided by the proposed lemmas
```

## Scientific objective

The main output is not a smaller floating-point residual. The main outputs are:

1. independently verified exact certificates for canonical support classes;
2. minimal obstruction cores;
3. pairs of nearby supports with different exact status;
4. a bridge between proof certificates and the best old-basin and independent Second approach candidates;
5. a small set of hard survivors not explained by known obstruction classes;
6. candidate lemmas and transfer tests from `n=6` to larger even `n`;
7. a concise, auditable handoff package for GPT-5.6 Sol.

## Current operating state

- The currently running Third approach 2.0 computation must finish and commit exactly through its existing collector.
- This folder does not modify, cancel, restart, or replace that run.
- No Fourth approach `launch.json` or GitHub Actions workflow exists yet.
- Full Fourth approach computations require an explicit scientific plan and an explicit user-approved launch.
- Monitoring may inspect health, preserve completed artifacts, and report results, but it must not autonomously start the next large Fourth approach run during the initial research phase.

## Planned structure

```text
fourth-approach/
├── README.md
├── AGENTS.md
├── ROADMAP.md
├── data/
│   └── README.md
├── runs/
├── tools/
├── reports/
└── sol-handoff/
    └── README.md
```

Directories are populated only when their contents exist. Every accepted computation receives its own immutable run directory and summary.

## Evidence hierarchy

From strongest to weakest:

1. independently checked exact symbolic identity;
2. exact identity checked by the production verifier only;
3. modular or interval evidence with a documented reconstruction path;
4. high-precision numerical lead;
5. ordinary floating-point lead.

No result may be described as proving the full conjecture unless it covers the complete admissible class for every required even `n`. A restricted exact certificate proves impossibility only for its recorded restricted system and support.

## Launch policy

The initial Fourth approach uses a **manual scientific launch gate**. This is deliberate: successive runs answer different questions and should be redesigned after inspecting the preceding evidence. Automation is suitable for health checks, collection, verification, and a bounded pre-approved batch, but not for open-ended autonomous continuation.

The binding rules are in `AGENTS.md`; the planned sequence is in `ROADMAP.md`.