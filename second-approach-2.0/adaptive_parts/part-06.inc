                "best_lane": str(best.get("lane", "unknown")),
                "best_support_fingerprint": str(
                    best.get("support_fingerprint", best.get("support_mask_hex", "unknown"))
                ),
                "best_residual_basin_fingerprint": str(
                    best.get("residual_basin_fingerprint", "unknown")
                ),
                "max_depth": max(int(item.get("lineage_depth", 0) or 0) for item in members),
                "promoted_candidates": len(members),
                "parent_based_candidates": len(parent_based),
                "parent_improvements": len(improvements),
            }
        )
    rows.sort(key=lambda row: float(row["best_max_error"]))
    return rows[:limit]


def collect_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--conclusion", required=True)
    parser.add_argument("--expected-jobs", type=int, default=20)
    parser.add_argument("--min-jobs", type=int, default=16)
    args = parser.parse_args()

    root = args.repo / "second-approach-2.0"
    manifests: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []

    for path in sorted(args.artifacts.rglob("manifest.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if document.get("approach") == "second-approach-2.0-independent-basin-counterexample-search":
                document["_source"] = path.relative_to(args.artifacts).as_posix()
                manifests.append(document)
        except Exception:
            continue
    if not manifests:
        raise RuntimeError("no readable Second approach 2.0 manifests found")
    run_indexes = {int(item["run_index"]) for item in manifests}
    base_seeds = {int(item["base_seed"]) for item in manifests}
    if len(run_indexes) != 1 or len(base_seeds) != 1:
        raise RuntimeError(
            f"mixed run configuration in artifacts: indexes={run_indexes}, seeds={base_seeds}"
        )
    run_index = next(iter(run_indexes))
    base_seed = next(iter(base_seeds))
    output = root / "runs" / f"run-{run_index:03d}-{args.run_id}"
    if output.exists():
        print(f"archive already exists: {output}")
        return 0
    output.mkdir(parents=True)
    promoted_dir = output / "promoted"
    promoted_dir.mkdir()

    for path in sorted(args.artifacts.rglob("attempts.jsonl")):
        source_label = path.relative_to(args.artifacts).as_posix()
        try:
            for record in read_jsonl(path):
                record["_source"] = source_label
                attempts.append(record)
        except Exception as exc:
            attempts.append(
                {
                    "error": "attempt_log_read_error",
                    "message": str(exc),
                    "_source": source_label,
                }
            )
    for path in sorted(args.artifacts.rglob("candidate-*.json.gz")):
        try:
            payload = normalize_candidate(load_gzip_json(path))
            payload["_source"] = path.relative_to(args.artifacts).as_posix()
            payloads.append(payload)
        except Exception as exc:
            attempts.append(
                {
                    "error": "candidate_read_error",
                    "message": str(exc),
                    "_source": path.relative_to(args.artifacts).as_posix(),
                }
            )

    job_ids = sorted({int(item["job_id"]) for item in manifests})
    missing_jobs = sorted(set(range(args.expected_jobs)) - set(job_ids))
    optimized = [item for item in attempts if "max_error" in item]
    failures = [item for item in attempts if "error" in item]
    skipped = [item for item in attempts if item.get("skipped_known_obstruction")]
    numerical_successes = [item for item in optimized if item.get("numerical_success")]
    optimized.sort(key=score)
    payloads.sort(key=score)
    accepted = len(job_ids) >= args.min_jobs and bool(payloads) and bool(optimized)

    lane_attempt_counts = Counter(str(item.get("lane", "unknown")) for item in attempts)
    lane_optimized_counts = Counter(str(item.get("lane", "unknown")) for item in optimized)
    lane_promoted_counts = Counter(str(item.get("lane", "unknown")) for item in payloads)
    family_counts = Counter(str(item.get("family", "unknown")) for item in attempts)
    strategy_counts = Counter(str(item.get("strategy", "none")) for item in optimized)
    obstruction_counts = Counter(str(item.get("exact_obstruction", "unknown")) for item in attempts)
    support_fingerprints = {
        str(item.get("support_fingerprint"))
        for item in payloads
        if item.get("support_fingerprint")
    }
    basin_fingerprints = {
        str(item.get("residual_basin_fingerprint"))
        for item in payloads
        if item.get("residual_basin_fingerprint")
    }
    lineage_roots = {lineage_root(item) for item in payloads}

    independent_payloads = [item for item in payloads if is_independent(item)]
    fresh_independent_payloads = [item for item in payloads if is_fresh_independent(item)]
    inherited_independent_payloads = [
        item for item in payloads if is_inherited_independent(item)
    ]
    legacy_payloads = [item for item in payloads if not is_independent(item)]
    old_rooted = [item for item in payloads if bool(item.get("legacy_rooted", False))]
    parent_based = [item for item in payloads if item.get("parent_candidate_id")]
    parent_improvements = [item for item in parent_based if item.get("improved_parent")]
    independent_parent_based = [
        item for item in inherited_independent_payloads if item.get("parent_candidate_id")
    ]
    independent_parent_improvements = [
        item for item in independent_parent_based if item.get("improved_parent")
    ]
    legacy_parent_based = [
        item for item in legacy_payloads if item.get("parent_candidate_id")
    ]
    legacy_parent_improvements = [
        item for item in legacy_parent_based if item.get("improved_parent")
    ]

    lane_best: dict[str, float] = {}
    for item in optimized:
        lane = str(item.get("lane", "unknown"))
        lane_best[lane] = min(lane_best.get(lane, 1e300), float(item["max_error"]))

    top_row_counts: Counter[str] = Counter()
    for item in independent_payloads[:300]:
        rows = tuple(int(row["row"]) for row in item.get("top_mixed_residuals", [])[:6])
        if rows:
            top_row_counts[",".join(map(str, rows))] += 1

    lane_plan_versions = {int(item.get("lane_plan_version", 1)) for item in manifests}
    legacy_strategies = {str(item.get("legacy_strategy", "legacy_v1")) for item in manifests}
    independent_strategies = {
        str(item.get("independent_strategy", "fresh_only_v1")) for item in manifests
    }
    lane_plan_version = next(iter(lane_plan_versions)) if len(lane_plan_versions) == 1 else -1
    legacy_strategy = next(iter(legacy_strategies)) if len(legacy_strategies) == 1 else "mixed"
    independent_strategy = (
        next(iter(independent_strategies)) if len(independent_strategies) == 1 else "mixed"
    )

    best_fresh = best_or_none(fresh_independent_payloads)
    best_inherited = best_or_none(inherited_independent_payloads)
    best_independent = best_or_none(independent_payloads)
    summary = {
        "schema_version": 2,
        "approach": "second-approach-2.0-independent-basin-counterexample-search",
        "run_id": args.run_id,
        "run_index": run_index,
        "base_seed": base_seed,
        "lane_plan_version": lane_plan_version,
