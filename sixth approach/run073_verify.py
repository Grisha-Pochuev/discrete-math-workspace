#!/usr/bin/env python3
"""Independently replay a positive survivor of the full factored probe."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path


N = 8


def decode(index):
    values = []
    for _ in range(N):
        values.append(index % 3)
        index //= 3
    return tuple(values)


def perfect_matchings(vertices):
    vertices = tuple(vertices)
    if not vertices:
        yield ()
        return
    first = vertices[0]
    for position in range(1, len(vertices)):
        second = vertices[position]
        remaining = vertices[1:position] + vertices[position + 1:]
        edge = (min(first, second), max(first, second))
        for tail in perfect_matchings(remaining):
            yield (edge,) + tail


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def ratio_key(left, right):
    counts = Counter(left)
    counts.subtract(right)
    vector = tuple(sorted((entry, count) for entry, count in counts.items() if count))
    negative = tuple((entry, -count) for entry, count in vector)
    return min(vector, negative)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--types", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-acceptance", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--event-no-good", type=Path, action="append", default=[])
    parser.add_argument("--event-acceptance", type=Path, action="append", default=[])
    parser.add_argument("--rectangle-bundle", type=Path, action="append", default=[])
    parser.add_argument("--rectangle-acceptance", type=Path, action="append", default=[])
    parser.add_argument("--symmetry-bundle", type=Path, action="append", default=[])
    parser.add_argument("--symmetry-acceptance", type=Path, action="append", default=[])
    parser.add_argument("--pairing-audit", type=Path, action="append", default=[])
    parser.add_argument("--pairing-acceptance", type=Path, action="append", default=[])
    parser.add_argument("--pairing-symmetry-bundle", type=Path, action="append", default=[])
    parser.add_argument("--pairing-symmetry-acceptance", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(args.event_no_good) != len(args.event_acceptance):
        raise AssertionError("every event no-good needs one acceptance")
    if len(args.rectangle_bundle) != len(args.rectangle_acceptance):
        raise AssertionError("every rectangle bundle needs one acceptance")
    if len(args.symmetry_bundle) != len(args.symmetry_acceptance):
        raise AssertionError("every symmetry bundle needs one acceptance")
    if len(args.pairing_audit) != len(args.pairing_acceptance):
        raise AssertionError("every pairing audit needs one acceptance")
    if len(args.pairing_symmetry_bundle) != len(args.pairing_symmetry_acceptance):
        raise AssertionError("every pairing symmetry bundle needs one acceptance")
    types = json.loads(args.types.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    acceptance = json.loads(args.manifest_acceptance.read_text(encoding="utf-8"))
    probe = json.loads(args.probe.read_text(encoding="utf-8"))
    types_sha = hashlib.sha256(args.types.read_bytes()).hexdigest()
    manifest_sha = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    if not acceptance.get("accepted") or acceptance["manifest_sha256"] != manifest_sha:
        raise AssertionError("manifest acceptance mismatch")
    if probe["types_sha256"] != types_sha or probe["manifest_sha256"] != manifest_sha:
        raise AssertionError("probe identity mismatch")
    if probe.get("schema") != "run-073-result-v1":
        raise AssertionError("unexpected result schema")
    if probe["solver_status"] not in ("FEASIBLE", "OPTIMAL"):
        raise AssertionError("probe has no positive survivor")
    type_row = next(row for row in types["types"] if row["type_index"] == probe["type_index"])
    triple = tuple(tuple(tuple(edge) for edge in matching) for matching in type_row["canonical_triple"])
    pure = {(edge, owner, owner) for owner, matching in enumerate(triple) for edge in matching}
    extras = {(tuple(item[0]), item[1], item[2]) for item in probe["active_pure_extras"]}
    fourth_entries = {(tuple(item[0]), item[1], item[2]) for item in probe["active_fourth_entries"]}
    if len(extras) != probe["pure_extra_count"] or len(fourth_entries) != probe["fourth_entry_count"]:
        raise AssertionError("support cardinality mismatch")
    support_cost = 37 * len(extras) + len(fourth_entries)
    if probe["support_cost"] != support_cost:
        raise AssertionError("support cost mismatch")
    if probe.get("objective_upper_bound") is not None and support_cost > int(probe["objective_upper_bound"]):
        raise AssertionError("support exceeds the declared objective bound")
    if not probe.get("fix_dense_support") and not probe.get("fixed_support_sha256") and probe.get("objective") != support_cost:
        raise AssertionError("optimization objective mismatch")
    active = pure | extras | fourth_entries
    all_matchings = tuple(perfect_matchings(range(N)))
    pure_edges = {edge for matching in triple for edge in matching}
    fourths = tuple(matching for matching in all_matchings if not (set(matching) & pure_edges))
    fourth = fourths[probe["fourth_index"]]
    graph_edges = pure_edges | set(fourth)
    matchings = tuple(matching for matching in all_matchings if set(matching) <= graph_edges)
    catalogue = tuple(tuple(tuple(edge) for edge in matching) for matching in manifest["matching_catalogue"])
    if catalogue != matchings:
        raise AssertionError("matching catalogue mismatch")

    histogram = Counter()
    binomial_ratios = defaultdict(list)
    trinomial_ratios = defaultdict(list)
    for state in range(3 ** N):
        colours = decode(state)
        if len(set(colours)) == 1:
            continue
        terms = []
        for matching_index, matching in enumerate(matchings):
            entries = tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
            if all(entry in active for entry in entries):
                terms.append((matching_index, entries))
        histogram[len(terms)] += 1
        if len(terms) == 1:
            raise AssertionError("probe survivor has a mixed singleton")
        target = binomial_ratios if len(terms) == 2 else trinomial_ratios if len(terms) == 3 else None
        if target is not None:
            for left, right in itertools.combinations(range(len(terms)), 2):
                target[ratio_key(terms[left][1], terms[right][1])].append((state, terms[left][0], terms[right][0]))
    conflicts = set(binomial_ratios) & set(trinomial_ratios)
    occurrences = sum(
        1 for ratio in conflicts
        for left in binomial_ratios[ratio]
        for right in trinomial_ratios[ratio]
        if left[0] != right[0]
    )
    if occurrences or conflicts:
        raise AssertionError("probe survivor retains a direct two-row obstruction")
    binomial_pairing_contradictions = 0
    for state in range(3 ** N):
        colours = decode(state)
        if len(set(colours)) == 1:
            continue
        terms = []
        for matching_index, matching in enumerate(matchings):
            entries = tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
            if all(entry in active for entry in entries):
                terms.append((matching_index, entries))
        if len(terms) < 3 or len(terms) % 2 == 0:
            continue
        by_ratio = defaultdict(list)
        for left, right in itertools.combinations(range(len(terms)), 2):
            key = ratio_key(terms[left][1], terms[right][1])
            if key in binomial_ratios:
                by_ratio[key].append((left, right))
        needed = (len(terms) - 1) // 2
        for pairs in by_ratio.values():
            for chosen in itertools.combinations(pairs, needed):
                if len({position for pair in chosen for position in pair}) == 2 * needed:
                    binomial_pairing_contradictions += 1
                    break
            if binomial_pairing_contradictions:
                break
        if binomial_pairing_contradictions:
            break
    if binomial_pairing_contradictions:
        raise AssertionError("probe survivor has an odd-row binomial-pairing contradiction")
    five_term_star_violations = 0
    for state in range(3 ** N):
        colours = decode(state)
        if len(set(colours)) == 1:
            continue
        terms = []
        for matching_index, matching in enumerate(matchings):
            entries = tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
            if all(entry in active for entry in entries):
                terms.append((matching_index, entries))
        if len(terms) != 5:
            continue
        edges = []
        for left, right in itertools.combinations(range(5), 2):
            if ratio_key(terms[left][1], terms[right][1]) in binomial_ratios:
                edges.append({left, right})
        if edges and not set.intersection(*edges):
            five_term_star_violations += 1
    if five_term_star_violations:
        raise AssertionError("probe survivor violates the complete five-term star condition")
    cascade_aggregate_states = list(map(int, probe.get("cascade_aggregate_states", [])))
    cascade_aggregate_violations = 0
    for state in cascade_aggregate_states:
        colours = decode(state)
        terms = []
        for matching_index, matching in enumerate(matchings):
            entries = tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
            if all(entry in active for entry in entries):
                terms.append((matching_index, entries))
        if len(terms) != 4:
            continue
        b_edges = []
        q_edges = []
        for left, right in itertools.combinations(range(4), 2):
            key = ratio_key(terms[left][1], terms[right][1])
            if key in binomial_ratios:
                b_edges.append({left, right})
            if key in trinomial_ratios:
                q_edges.append({left, right})
        cascade_aggregate_violations += sum(
            left.isdisjoint(right) for left in b_edges for right in q_edges
        )
    if cascade_aggregate_violations:
        raise AssertionError("probe survivor violates an enabled three-row cascade aggregate")
    pairing_audit_hashes = []
    triggered_pairing_audits = 0
    for audit_path, audit_acceptance_path in zip(args.pairing_audit, args.pairing_acceptance):
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit_acceptance = json.loads(audit_acceptance_path.read_text(encoding="utf-8"))
        audit_sha = hashlib.sha256(audit_path.read_bytes()).hexdigest()
        if not audit_acceptance.get("accepted") or audit_acceptance.get("audit_sha256") != audit_sha:
            raise AssertionError("pairing audit acceptance mismatch")
        if audit["types_sha256"] != types_sha or audit["type_index"] != probe["type_index"] or audit["fourth_index"] != probe["fourth_index"]:
            raise AssertionError("pairing audit identity mismatch")
        for witness in audit["witnesses"]:
            state = int(witness["target_state"])
            colours = decode(state)
            actual = []
            entries_by_matching = {}
            for matching_index, matching in enumerate(matchings):
                entries = tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
                if all(entry in active for entry in entries):
                    actual.append(matching_index)
                    entries_by_matching[matching_index] = entries
            target = list(map(int, witness["target_matching_indices"]))
            if actual != target:
                continue
            all_ratios_realized = True
            for pair in witness["paired_positions"]:
                left_position, right_position = map(int, pair)
                key = ratio_key(entries_by_matching[target[left_position]], entries_by_matching[target[right_position]])
                if key not in binomial_ratios:
                    all_ratios_realized = False
                    break
            triggered_pairing_audits += int(all_ratios_realized)
        pairing_audit_hashes.append(audit_sha)
    if triggered_pairing_audits:
        raise AssertionError("probe survivor violates an accepted generalized pairing no-good")
    pairing_symmetry_hashes = []
    triggered_pairing_symmetry_events = 0
    for bundle_path, bundle_acceptance_path in zip(args.pairing_symmetry_bundle, args.pairing_symmetry_acceptance):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        bundle_acceptance = json.loads(bundle_acceptance_path.read_text(encoding="utf-8"))
        bundle_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        if not bundle_acceptance.get("accepted") or bundle_acceptance.get("bundle_sha256") != bundle_sha:
            raise AssertionError("pairing symmetry bundle acceptance mismatch")
        if bundle["types_sha256"] != types_sha or bundle["manifest_sha256"] != manifest_sha or bundle["type_index"] != probe["type_index"] or bundle["fourth_index"] != probe["fourth_index"]:
            raise AssertionError("pairing symmetry bundle identity mismatch")
        for event in bundle["events"]:
            state = int(event["target_state"])
            colours = decode(state)
            actual = []
            entries_by_matching = {}
            for matching_index, matching in enumerate(matchings):
                entries = tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
                if all(entry in active for entry in entries):
                    actual.append(matching_index)
                    entries_by_matching[matching_index] = entries
            target = list(map(int, event["target_matching_indices"]))
            if actual != target:
                continue
            all_ratios_realized = True
            for pair in event["paired_positions"]:
                left_position, right_position = map(int, pair)
                key = ratio_key(entries_by_matching[target[left_position]], entries_by_matching[target[right_position]])
                if key not in binomial_ratios:
                    all_ratios_realized = False
                    break
            triggered_pairing_symmetry_events += int(all_ratios_realized)
        pairing_symmetry_hashes.append(bundle_sha)
    if triggered_pairing_symmetry_events:
        raise AssertionError("probe survivor violates an accepted pairing symmetry event")
    uniform_term_counts = []
    uniform_binomial_conflicts = []
    base = sum(3 ** position for position in range(N))
    for colour in range(3):
        state = colour * base
        colours = decode(state)
        terms = []
        for matching_index, matching in enumerate(matchings):
            entries = tuple((edge, colour, colour) for edge in matching)
            if all(entry in active for entry in entries):
                terms.append((matching_index, entries))
        uniform_term_counts.append(len(terms))
        if len(terms) == 2:
            key = ratio_key(terms[0][1], terms[1][1])
            if key in binomial_ratios:
                uniform_binomial_conflicts.append({
                    "colour": colour,
                    "uniform_matching_indices": [terms[0][0], terms[1][0]],
                    "mixed_sources": len(binomial_ratios[key]),
                })
    if uniform_binomial_conflicts:
        raise AssertionError("probe survivor forces a required uniform amplitude to zero")
    if any(not any(entry[0] == edge for entry in fourth_entries) for edge in fourth):
        raise AssertionError("one fourth-factor edge has empty support")
    event_hashes = []
    triggered_events = 0
    for event_path, event_acceptance_path in zip(args.event_no_good, args.event_acceptance):
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event_acceptance = json.loads(event_acceptance_path.read_text(encoding="utf-8"))
        event_sha = hashlib.sha256(event_path.read_bytes()).hexdigest()
        if not event_acceptance.get("accepted") or event_acceptance.get("event_sha256") != event_sha:
            raise AssertionError("event no-good acceptance mismatch")
        if event["types_sha256"] != types_sha or event["type_index"] != probe["type_index"] or event["fourth_index"] != probe["fourth_index"]:
            raise AssertionError("event no-good identity mismatch")
        triggered = True
        for row in event["rows"]:
            state = int(row["state"])
            colours = decode(state)
            actual = []
            for matching_index, matching in enumerate(matchings):
                entries = tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
                if all(entry in active for entry in entries):
                    actual.append(matching_index)
            if actual != list(map(int, row["active_matching_indices"])):
                triggered = False
                break
        triggered_events += int(triggered)
        event_hashes.append(event_sha)
    if triggered_events:
        raise AssertionError("probe survivor violates an accepted sparse quotient event")
    rectangle_hashes = []
    triggered_rectangle_events = 0
    for bundle_path, rectangle_acceptance_path in zip(args.rectangle_bundle, args.rectangle_acceptance):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        rectangle_acceptance = json.loads(rectangle_acceptance_path.read_text(encoding="utf-8"))
        bundle_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        if not rectangle_acceptance.get("accepted") or rectangle_acceptance.get("bundle_sha256") != bundle_sha:
            raise AssertionError("rectangle bundle acceptance mismatch")
        if bundle["types_sha256"] != types_sha or bundle["type_index"] != probe["type_index"] or bundle["fourth_index"] != probe["fourth_index"]:
            raise AssertionError("rectangle bundle identity mismatch")
        for event in bundle["events"]:
            rows = [*event["source_rows"], {
                "state": event["target_state"],
                "active_matching_indices": event["target_active_matching_indices"],
            }]
            triggered = True
            for row in rows:
                state = int(row["state"])
                colours = decode(state)
                actual = []
                for matching_index, matching in enumerate(matchings):
                    entries = tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
                    if all(entry in active for entry in entries):
                        actual.append(matching_index)
                if actual != list(map(int, row["active_matching_indices"])):
                    triggered = False
                    break
            triggered_rectangle_events += int(triggered)
        rectangle_hashes.append(bundle_sha)
    if triggered_rectangle_events:
        raise AssertionError("probe survivor violates an accepted rectangle event")
    symmetry_hashes = []
    triggered_symmetry_events = 0
    for bundle_path, symmetry_acceptance_path in zip(args.symmetry_bundle, args.symmetry_acceptance):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        symmetry_acceptance = json.loads(symmetry_acceptance_path.read_text(encoding="utf-8"))
        bundle_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        if not symmetry_acceptance.get("accepted") or symmetry_acceptance.get("bundle_sha256") != bundle_sha:
            raise AssertionError("symmetry bundle acceptance mismatch")
        if (bundle["types_sha256"] != types_sha or bundle["manifest_sha256"] != manifest_sha
                or bundle["type_index"] != probe["type_index"]
                or bundle["fourth_index"] != probe["fourth_index"]):
            raise AssertionError("symmetry bundle identity mismatch")
        for event in bundle["events"]:
            triggered = True
            for row in event["rows"]:
                state = int(row["state"])
                colours = decode(state)
                actual = []
                for matching_index, matching in enumerate(matchings):
                    entries = tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
                    if all(entry in active for entry in entries):
                        actual.append(matching_index)
                if actual != list(map(int, row["active_matching_indices"])):
                    triggered = False
                    break
            triggered_symmetry_events += int(triggered)
        symmetry_hashes.append(bundle_sha)
    if triggered_symmetry_events:
        raise AssertionError("probe survivor violates an accepted symmetry event")
    payload = {
        "schema": "run-073-result-acceptance-v1",
        "method": "dependency-free matching reconstruction, full row replay, and direct Laurent grouping",
        "types_sha256": types_sha,
        "manifest_sha256": manifest_sha,
        "probe_sha256": hashlib.sha256(args.probe.read_bytes()).hexdigest(),
        "pure_extra_count": len(extras),
        "fourth_entry_count": len(fourth_entries),
        "support_cost": support_cost,
        "matching_histogram": {str(key): value for key, value in sorted(histogram.items())},
        "direct_obstruction_occurrences": occurrences,
        "binomial_pairing_contradictions": binomial_pairing_contradictions,
        "five_term_star_violations": five_term_star_violations,
        "cascade_aggregate_states": cascade_aggregate_states,
        "cascade_aggregate_violations": cascade_aggregate_violations,
        "pairing_audit_sha256": pairing_audit_hashes,
        "triggered_pairing_audits": triggered_pairing_audits,
        "pairing_symmetry_bundle_sha256": pairing_symmetry_hashes,
        "triggered_pairing_symmetry_events": triggered_pairing_symmetry_events,
        "uniform_term_counts": uniform_term_counts,
        "uniform_binomial_conflicts": uniform_binomial_conflicts,
        "event_no_good_sha256": event_hashes,
        "triggered_event_no_goods": triggered_events,
        "rectangle_bundle_sha256": rectangle_hashes,
        "triggered_rectangle_events": triggered_rectangle_events,
        "symmetry_bundle_sha256": symmetry_hashes,
        "triggered_symmetry_events": triggered_symmetry_events,
        "accepted": True,
    }
    payload["canonical_acceptance_sha256"] = hashlib.sha256(canonical(payload)).hexdigest()
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
