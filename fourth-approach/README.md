# Fourth approach

This directory contains the current synthesis track built on archived outputs from the earlier approaches.

Its role is to combine previously generated exact and numerical evidence into compact, auditable structures for later analysis and targeted verification.

## Main outputs

- canonicalized records;
- minimized certificates or descriptors;
- contrast pairs;
- hard-survivor sets;
- cross-track comparison data;
- compact handoff packages;
- targeted follow-up tests.

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

GitHub Actions workflows for this track remain under `.github/workflows/`.

## Automation rules

The automation layer may advance at most one meaningful transition per activation. It must inspect active and queued workflows, avoid duplicate run indices and nonces, preserve partial artifacts, prefer rescue over recomputation, and stop on technical failure, rejected collection, unexpected schema, or an explicit stopping rule.

## Evidence hierarchy

Treat independently checked exact output as stronger than reconstructed, interval, or numerical evidence. A successful workflow only establishes that the configured computation completed; interpretation remains a separate step.
