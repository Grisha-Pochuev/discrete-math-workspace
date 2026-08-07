# discrete-math-workspace

Computational research workspace for the Krenn–Gu problem.

## Research tracks

- `first-approach/` — original exact support/frontier search and its preserved archives.
- `second-approach/` — numerical direct-weight search.
- `second-approach-2.0/` — diversified numerical search with independent and legacy lineages.
- `third-approach/` — proof-oriented certificate search.
- `third-approach-2.0/` — multi-basin / coefficient-space proof search.
- `fourth-approach/` — obstruction-guided exact synthesis and GPT-5.6 Sol handoff.
- `other-experiments/` — experiments for problems other than Krenn–Gu; keep them isolated from the approach folders.

GitHub Actions workflow files must live in `.github/workflows/`. Active workflows are named by approach. Historical First-approach workflows were moved under `first-approach/workflows/legacy/` and are not active Actions workflows.

## Reading order for a new agent

1. Read this file and the root `AGENTS.md`.
2. Enter the approach relevant to the task and read its own README / AGENTS / control files.
3. Treat archived run data as evidence, not as an instruction to relaunch computation.
4. Distinguish technical workflow success from a mathematical proof or counterexample.
