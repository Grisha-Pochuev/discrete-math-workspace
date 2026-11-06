                "weight_min_abs": result["weight_min_abs"],
                "optimality": result["optimality"],
                "numerical_success": result["success"],
                "top_mixed_residuals": top_residuals,
                "residual_basin_fingerprint": basin_fingerprint,
                "improved_parent": improved_parent,
                "parent_improvement_fraction": improvement_fraction,
                "elapsed_seconds": time.time() - attempt_started,
            }
            append_jsonl(attempts_path, summary)
            score = float(result["max_error"])
            if len(best) < 8 or score < max(item[0] for item in best):
                payload = dict(summary)
                active = np.asarray(result["active"], dtype=np.int16)
                x = np.asarray(result["x"], dtype=np.complex128)
                payload["active_variables"] = [int(v) for v in active]
                payload["active_weights"] = complex_pairs(x[active])
                if "legacy_rooted" not in payload:
                    payload["legacy_rooted"] = lane in engine.LEGACY_LANES
                if not payload.get("lineage_origin"):
                    payload["lineage_origin"] = (
                        "legacy" if payload["legacy_rooted"] else "independent"
                    )
                if not payload.get("lineage_root"):
                    payload["lineage_root"] = candidate_id
                payload["lineage_depth"] = int(payload.get("lineage_depth", 0) or 0)
                candidate_path = root / f"candidate-{candidate_id}.json.gz"
                with gzip.open(
                    candidate_path, "wt", encoding="utf-8", compresslevel=9
                ) as out:
                    json.dump(payload, out, sort_keys=True, separators=(",", ":"))
                    out.write("\n")
                best.append((score, candidate_path.name))
                best.sort()
                while len(best) > 8:
                    _, old_name = best.pop()
                    old_path = root / old_name
                    if old_path.exists():
                        old_path.unlink()
                atomic_json(
                    root / "best.json",
                    {
                        "worker_id": worker_id,
                        "lane": lane,
                        "updated_at": time.time(),
                        "best": [
                            {"max_error": value, "file": name}
                            for value, name in best
                        ],
                    },
                )
        except BaseException as exc:
            errors += 1
            append_jsonl(
                attempts_path,
                {
                    "attempt": attempt,
                    "seed": seed,
                    **error_context,
                    "error": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                    "elapsed_seconds": time.time() - attempt_started,
                },
            )
        attempt += 1
        atomic_json(
            root / "checkpoint.json",
            {
                "worker_id": worker_id,
                "global_worker_id": global_worker_id,
                "lane": lane,
                "lane_plan_version": lane_plan_version,
                "legacy_strategy": legacy_strategy,
                "independent_strategy": independent_strategy,
                "attempts": attempt,
                "optimized_attempts": optimized,
                "skipped_known_obstruction": skipped,
                "errors": errors,
                "best_score": best[0][0] if best else None,
                "started_at": started,
                "updated_at": time.time(),
                "deadline": deadline,
            },
        )

    atomic_json(
        root / "complete.json",
        {
            "worker_id": worker_id,
            "global_worker_id": global_worker_id,
            "lane": lane,
            "lane_plan_version": lane_plan_version,
            "legacy_strategy": legacy_strategy,
            "independent_strategy": independent_strategy,
            "attempts": attempt,
            "optimized_attempts": optimized,
            "skipped_known_obstruction": skipped,
            "errors": errors,
            "best_score": best[0][0] if best else None,
            "started_at": started,
            "finished_at": time.time(),
            "stop_reason": "deadline" if time.time() >= deadline else "attempt_cap",
        },
    )


def runner_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--run-index", type=int, required=True)
    parser.add_argument("--base-seed", type=int, required=True)
    parser.add_argument("--seconds", type=int, default=21000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-nfev", type=int, default=300)
    parser.add_argument("--max-attempts", type=int, default=0)
    parser.add_argument("--lane-plan-version", type=int, default=2)
    parser.add_argument("--legacy-strategy", default="micro_polish")
    parser.add_argument("--independent-strategy", default="balanced")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.lane_plan_version not in engine.LANE_PLANS:
        raise ValueError(f"unknown lane plan version: {args.lane_plan_version}")
    if args.legacy_strategy not in engine.ALLOWED_LEGACY_STRATEGIES:
        raise ValueError(f"unknown legacy strategy: {args.legacy_strategy}")
    if args.independent_strategy not in engine.ALLOWED_INDEPENDENT_STRATEGIES:
        raise ValueError(f"unknown independent strategy: {args.independent_strategy}")
    if args.workers != 4 and args.max_attempts == 0:
        raise ValueError("long runs require exactly four workers per job")
    args.output.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[1]
    start = time.time()
    deadline = start + max(60, args.seconds - 600)
    processes: list[mp.Process] = []
    for worker_id in range(args.workers):
        process = mp.Process(
            target=worker_main,
            args=(
                str(repo),
                str(args.output),
                args.run_index,
                args.job_id,
                worker_id,
                args.base_seed,
                deadline,
                args.max_nfev,
                args.max_attempts,
                args.lane_plan_version,
                args.legacy_strategy,
                args.independent_strategy,
            ),
            daemon=False,
        )
        process.start()
        processes.append(process)

    while time.time() < deadline and any(p.is_alive() for p in processes):
        time.sleep(5)
    for process in processes:
        if process.is_alive():
            process.terminate()
    for process in processes:
        process.join(timeout=30)
        if process.is_alive():
            os.kill(process.pid, signal.SIGKILL)
            process.join(timeout=5)

    worker_manifests = []
    for worker_id, process in enumerate(processes):
        checkpoint = args.output / f"worker-{worker_id}" / "checkpoint.json"
        complete = args.output / f"worker-{worker_id}" / "complete.json"
        source = complete if complete.exists() else checkpoint
        info = (
            json.loads(source.read_text(encoding="utf-8"))
            if source.exists()
            else {
                "worker_id": worker_id,
                "lane": engine.lane_for(
                    args.job_id, worker_id, args.lane_plan_version
                ),
                "missing_checkpoint": True,
            }
        )
