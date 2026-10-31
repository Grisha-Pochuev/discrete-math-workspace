        info["exitcode"] = process.exitcode
        worker_manifests.append(info)

    manifest = {
        "schema_version": 2,
        "approach": "second-approach-2.0-independent-basin-counterexample-search",
        "run_index": args.run_index,
        "job_id": args.job_id,
        "base_seed": args.base_seed,
        "workers": args.workers,
        "lane_plan_version": args.lane_plan_version,
        "legacy_strategy": args.legacy_strategy,
        "independent_strategy": args.independent_strategy,
        "lane_assignments": [
            engine.lane_for(args.job_id, worker_id, args.lane_plan_version)
            for worker_id in range(args.workers)
        ],
        "max_nfev": args.max_nfev,
        "max_attempts_per_worker": args.max_attempts,
        "stopping_policy": (
            "time_only" if args.max_attempts <= 0 else "time_or_attempt_cap"
        ),
        "requested_seconds": args.seconds,
        "started_at": start,
        "finished_at": time.time(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "worker_manifests": worker_manifests,
    }
    atomic_json(args.output / "manifest.json", manifest)
    return 0



# ---- collector implementation ----

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def load_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def atomic_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def score(item: dict[str, Any]) -> tuple[float, float]:
    return float(item.get("max_error", 1e300)), float(item.get("total_l2", 1e300))


def lineage_root(item: dict[str, Any]) -> str:
    return str(item.get("lineage_root") or item.get("candidate_id") or "unknown")


def is_independent(item: dict[str, Any]) -> bool:
    if bool(item.get("legacy_rooted", False)):
        return False
    if str(item.get("lineage_origin", "")) == "independent":
        return True
    lane = str(item.get("lane", ""))
    if lane in FRESH_INDEPENDENT_LANES | INHERITED_INDEPENDENT_LANES:
        return True
    return lineage_root(item).startswith("sa20-")


def is_fresh_independent(item: dict[str, Any]) -> bool:
    return is_independent(item) and not item.get("parent_candidate_id")


def is_inherited_independent(item: dict[str, Any]) -> bool:
    return is_independent(item) and bool(item.get("parent_candidate_id"))


def normalize_candidate(item: dict[str, Any]) -> dict[str, Any]:
    item = dict(item)
    independent = is_independent(item)
    item.setdefault("legacy_rooted", not independent)
    item.setdefault("lineage_origin", "independent" if independent else "legacy")
    item.setdefault("lineage_root", lineage_root(item))
    item.setdefault("lineage_depth", 0 if not item.get("parent_candidate_id") else 1)
    return item


def select_bank(
    candidates: list[dict[str, Any]], limit: int = 1200
) -> list[dict[str, Any]]:
    """Retain strong candidates while protecting diverse independent lineages."""
    by_id: dict[str, dict[str, Any]] = {}
    for raw in candidates:
        item = normalize_candidate(raw)
        candidate_id = str(item.get("candidate_id", ""))
        if candidate_id:
            by_id[candidate_id] = item
    ranked = sorted(by_id.values(), key=score)
    independent = [item for item in ranked if is_independent(item)]
    legacy = [item for item in ranked if not is_independent(item)]

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    support_counts: Counter[str] = Counter()
    basin_counts: Counter[str] = Counter()
    lineage_counts: Counter[str] = Counter()
    lane_counts: Counter[str] = Counter()

    def add(
        item: dict[str, Any],
        *,
        support_cap: int,
        basin_cap: int,
        lineage_cap: int,
        lane_cap: int | None = None,
    ) -> bool:
        candidate_id = str(item.get("candidate_id", ""))
        if not candidate_id or candidate_id in selected_ids:
            return False
        lane = str(item.get("lane", "unknown"))
        support = str(
            item.get("support_fingerprint", item.get("support_mask_hex", "unknown"))
        )
        basin = str(item.get("residual_basin_fingerprint", "unknown"))
        root = lineage_root(item)
        if support_counts[support] >= support_cap:
            return False
        if basin_counts[basin] >= basin_cap:
            return False
        if lineage_counts[root] >= lineage_cap:
            return False
        if lane_cap is not None and lane_counts[lane] >= lane_cap:
            return False
        selected.append(item)
        selected_ids.add(candidate_id)
        support_counts[support] += 1
        basin_counts[basin] += 1
        lineage_counts[root] += 1
        lane_counts[lane] += 1
        return True

    # One best representative from every independent lineage first. This is
    # the key inheritance guarantee for the new basins.
    seen_roots: set[str] = set()
    for item in independent:
        root = lineage_root(item)
        if root in seen_roots:
            continue
        add(item, support_cap=3, basin_cap=20, lineage_cap=1)
        seen_roots.add(root)
        if len(selected) >= 320:
            break

    # Fill a large independent reserve, allowing several generations per line.
    for item in independent:
        add(item, support_cap=3, basin_cap=25, lineage_cap=8)
        if len(selected) >= 780:
            break

    # Preserve several distinct old-basin lineages and tactics, but do not let
    # them displace the inherited independent population.
    seen_legacy_roots: set[str] = set()
    for item in legacy:
        root = lineage_root(item)
        if root in seen_legacy_roots:
            continue
        add(item, support_cap=4, basin_cap=30, lineage_cap=1)
        seen_legacy_roots.add(root)
        if len(selected) >= 980:
            break
    for item in legacy:
        add(item, support_cap=4, basin_cap=35, lineage_cap=10)
        if len(selected) >= 1080:
            break

    # Finally fill any remaining space with the strongest still-diverse items.
    for item in ranked:
        add(item, support_cap=5, basin_cap=45, lineage_cap=12)
        if len(selected) >= limit:
            break
    return selected[:limit]


def best_or_none(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return min(items, key=score) if items else None


def lineage_summary(items: list[dict[str, Any]], limit: int = 40) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[lineage_root(item)].append(item)
    rows: list[dict[str, Any]] = []
    for root, members in grouped.items():
        members.sort(key=score)
        best = members[0]
        parent_based = [item for item in members if item.get("parent_candidate_id")]
        improvements = [item for item in parent_based if item.get("improved_parent")]
        rows.append(
            {
                "lineage_root": root,
                "best_candidate_id": str(best.get("candidate_id")),
                "best_max_error": float(best.get("max_error", 1e300)),
