#!/usr/bin/env python3
"""Build the compact, auditable GPT-5.6 Sol handoff after accepted Run 006."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--source-run", type=Path, required=True)
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--source-sha", required=True)
    a = p.parse_args()

    repo = a.repo.resolve()
    source = (repo / a.source_run).resolve() if not a.source_run.is_absolute() else a.source_run.resolve()
    summary = read_json(source / "summary.json")
    handoff6 = read_json(source / "gpt-sol-handoff.json")
    validation = read_json(source / "worker-validation.json")
    control_path = repo / "fourth-approach" / "control.json"
    launch_path = repo / "fourth-approach" / "launch.json"
    control = read_json(control_path)

    if summary.get("accepted") is not True:
        raise SystemExit("Run 006 is not accepted")
    metrics = summary.get("metrics", {})
    if int(metrics.get("workers_present", -1)) != 60 or int(metrics.get("workers_expected", -1)) != 60:
        raise SystemExit("Run 006 is not 60/60")
    if int(metrics.get("invalid_or_missing_workers", -1)) != 0:
        raise SystemExit("Run 006 has invalid/missing workers")
    if validation.get("errors"):
        raise SystemExit(f"Run 006 worker validation errors: {validation['errors'][:3]}")

    history = list(control.get("run_history", []))
    by_index = {int(item.get("run_index", -1)): item for item in history}
    run4 = by_index.get(4, {})
    run5 = by_index.get(5, {})
    run6 = by_index.get(6, {})

    evidence = {
        "schema_version": 1,
        "purpose": "compact exact/numerical frontier for GPT-5.6 Sol; no bounded-search survivor is a counterexample",
        "source_run_006": str(a.source_run),
        "source_run_006_id": int(summary["run_id"]),
        "facts": {
            "run004": {
                "fixed_support_exact_classes": int(run4.get("metrics", {}).get("source_support_classes", 0)),
                "independently_reverified": int(run4.get("metrics", {}).get("independently_reverified", 0)),
                "three_term_certificates": int(run4.get("metrics", {}).get("term_count_distribution", {}).get("3", 0)),
                "supports_changed": int(run4.get("metrics", {}).get("supports_changed", 0)),
            },
            "run005": {
                "candidate_records": int(run5.get("metrics", {}).get("candidate_records", 0)),
                "exactly_covered_candidates": int(run5.get("metrics", {}).get("exactly_covered_candidates", 0)),
                "radius2_samples": int(run5.get("metrics", {}).get("radius2_samples", 0)),
                "radius2_exact_hits": int(run5.get("metrics", {}).get("radius2_exact_hits", 0)),
            },
            "run006": {
                "selected_candidates": int(metrics.get("selected_candidates", 0)),
                "workers_present": int(metrics.get("workers_present", 0)),
                "total_attempts": int(metrics.get("total_attempts", 0)),
                "maximum_tested_multiplier_degree": int(metrics.get("maximum_tested_multiplier_degree", 0)),
                "exactly_closed": int(metrics.get("exactly_closed", 0)),
                "survivors": int(metrics.get("survivors", 0)),
                "groups": metrics.get("groups", {}),
            },
        },
        "strongest_survivors_by_group": handoff6.get("strongest_survivors_by_group", {}),
        "exact_closures_from_run006": handoff6.get("exact_closures", []),
        "interpretation": [
            "Run 004 gives exact three-term certificates on 2594 fixed supports; those exact mechanisms do not transfer directly to the numerical pools tested in Run 005.",
            "Run 005 found no exact hit among the complete radius-1 scans and more than twenty million radius-2 samples across 1300 candidates.",
            "Run 006 tested 60 diverse hard survivors with randomized support-restricted Nullstellensatz descriptor families through multiplier degree 5 and found no exact closure.",
            "These are bounded negative results only. They do not prove satisfiability, do not produce a counterexample, and do not establish a global degree lower bound.",
        ],
        "lemma_falsification_prompts": [
            "Find a support-local invariant that separates the 2594 exactly obstructed Run-004 supports from all 60 Run-006 survivors and verify it under S6 x S3 symmetry.",
            "Test whether exact obstruction depends on a small critical subset of mixed-color matching equations rather than on higher multiplier degree alone.",
            "Search for one-edit contrast pairs along paths from Run-006 survivors toward exact Run-004 support classes while preserving all three monochromatic perfect matchings.",
            "If a candidate structural invariant survives n=6 falsification, formulate the corresponding n=8 statement before spending on an n=8 search.",
        ],
        "recommended_heavy_next_step": {
            "run_index": 8,
            "task": "stage8_adaptive_exact_lemma_cycle",
            "reason": "degree-3/4/5 random descriptors gave zero closures; next search should use new adaptive degree-5/6/7 descriptor families with independent exact verification and duplicated coverage of the strongest survivors",
            "github_machines": 20,
            "workers": 80,
        },
    }

    run_dir = repo / "fourth-approach" / "runs" / f"run-007-{a.run_id}"
    if run_dir.exists():
        old = read_json(run_dir / "summary.json")
        return 0 if old.get("accepted") else 3
    run_dir.mkdir(parents=True)
    write_json(run_dir / "gpt-sol-frontier.json", evidence)

    md = [
        "# GPT-5.6 Sol handoff after Fourth approach Run 006",
        "",
        f"Source Run 006: `{summary['run_id']}` (accepted, 60/60 workers).",
        "",
        "## What is exact",
        "",
        f"- Run 004: {evidence['facts']['run004']['fixed_support_exact_classes']} fixed-support exact classes; {evidence['facts']['run004']['three_term_certificates']} reduced to three-term certificates.",
        f"- Run 005: {evidence['facts']['run005']['candidate_records']} numerical candidates compared against exact mechanisms; exact coverage = {evidence['facts']['run005']['exactly_covered_candidates']}.",
        f"- Run 006: {evidence['facts']['run006']['selected_candidates']} diverse survivors, {evidence['facts']['run006']['total_attempts']} bounded certificate attempts, exact closures = {evidence['facts']['run006']['exactly_closed']}.",
        "",
        "## What is not proved",
        "",
        "A Run-006 survivor is not a counterexample. Failure to find a certificate through degree 5 in the sampled descriptor families is only a bounded negative result.",
        "",
        "## Questions for Sol",
        "",
    ]
    md.extend(f"- {q}" for q in evidence["lemma_falsification_prompts"])
    md += [
        "",
        "## Next compute",
        "",
        "Run 008 is an adaptive exact-certificate lemma cycle on 20 GitHub machines / 80 workers. It changes the descriptor family rather than merely repeating Run 006.",
        "",
    ]
    (run_dir / "SOL_HANDOFF.md").write_text("\n".join(md), encoding="utf-8")

    out_summary = {
        "schema_version": 1,
        "approach": "fourth-approach-obstruction-guided-exact-synthesis",
        "accepted": True,
        "run_id": a.run_id,
        "run_index": 7,
        "task": "stage7_gpt_sol_handoff",
        "source_sha": a.source_sha,
        "source_run_006": int(summary["run_id"]),
        "metrics": {
            "source_workers": int(metrics.get("workers_present", 0)),
            "source_survivors": int(metrics.get("survivors", 0)),
            "source_exact_closures": int(metrics.get("exactly_closed", 0)),
            "lemma_falsification_prompts": len(evidence["lemma_falsification_prompts"]),
        },
        "next_run_index": 8,
        "next_task": "stage8_adaptive_exact_lemma_cycle",
    }
    write_json(run_dir / "summary.json", out_summary)
    checks = []
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            checks.append(f"{sha256(path)}  {path.name}")
    (run_dir / "checksums.sha256").write_text("\n".join(checks) + "\n", encoding="utf-8")

    history.append({
        "accepted": True,
        "run_id": a.run_id,
        "run_index": 7,
        "task": "stage7_gpt_sol_handoff",
        "metrics": out_summary["metrics"],
    })
    control.update(
        completed_runs=int(control.get("completed_runs", 0)) + 1,
        current_stage=8,
        current_stage_name="adaptive_exact_lemma_cycle",
        last_run_id=a.run_id,
        last_run_index=7,
        last_run_accepted=True,
        next_run_index=8,
        next_task="stage8_adaptive_exact_lemma_cycle",
        next_spec_path="fourth-approach/run-specs/run-008-stage8-adaptive-exact-lemma-cycle.json",
        recommended_next_action="launch_run_008_on_20_github_machines",
        scientific_stopping_rule="review Run 008 exact closures/survivors before any n=8 transfer",
        minimum_free_concurrency_slots=0,
        run_history=history,
    )
    write_json(control_path, control)
    write_json(launch_path, {
        "schema_version": 1,
        "enabled": False,
        "run_index": 7,
        "task": "stage7_gpt_sol_handoff",
        "spec_path": "fourth-approach/run-specs/run-007-stage7-gpt-sol-handoff.json",
        "jobs": 1,
        "minimum_jobs": 1,
        "runtime_seconds": 900,
        "max_attempts": 0,
        "nonce": f"fourth-run-007-completed-{a.run_id}",
    })
    print(json.dumps(out_summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
