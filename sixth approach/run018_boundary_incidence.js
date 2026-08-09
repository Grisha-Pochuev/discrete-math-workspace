"use strict";

const fs = require("fs");
const path = require("path");

const vertices = [0, 1, 2, 3, 4];
const I = 0, A = 1, B = 2;

function orderedDistinct(k) {
  const out = [];
  function rec(prefix) {
    if (prefix.length === k) {
      out.push(prefix.slice());
      return;
    }
    for (const v of vertices) {
      if (prefix.includes(v)) continue;
      prefix.push(v);
      rec(prefix);
      prefix.pop();
    }
  }
  rec([]);
  return out;
}

const pairs = orderedDistinct(2);
const triples = orderedDistinct(3);
const permutations = orderedDistinct(5);

function distinct(values) {
  return new Set(values).size === values.length;
}

function complementPair(values) {
  const removed = new Set(values);
  const left = vertices.filter(v => !removed.has(v));
  if (left.length !== 2) throw new Error("expected a two-vertex complement");
  return left[0] < left[1] ? `${left[0]},${left[1]}` : `${left[1]},${left[0]}`;
}

function inspectAssignment(activeMask, anchors) {
  const constraints = new Map();
  let conflict = null;

  function add(values, kind, colour, source) {
    const key = complementPair(values);
    const current = constraints.get(key) || {zero: false, nonzero: false, pure: new Set(), sources: []};
    if (kind === "zero") current.zero = true;
    if (kind === "nonzero") current.nonzero = true;
    if (kind === "pure") {
      current.nonzero = true;
      current.pure.add(colour);
    }
    current.sources.push(source);
    constraints.set(key, current);
    if (current.zero && current.nonzero) conflict = {key, reason: "zero_nonzero", sources: current.sources};
    if (current.pure.size > 1) conflict = {key, reason: "two_pure_colours", sources: current.sources};
  }

  const u = {[A]: anchors.ua, [B]: anchors.ub};
  const s = {[I]: anchors.si, [A]: anchors.sa, [B]: anchors.sb};
  const t = {[I]: anchors.ti, [A]: anchors.ta, [B]: anchors.tb};

  if (s[I] === t[I]) return {rejected: "same_i_terminal"};
  for (const q of [A, B]) {
    if ((activeMask & (1 << (q - 1))) && (u[q] === s[I] || u[q] === t[I])) {
      return {rejected: "active_anchor_collision"};
    }
  }

  for (const q of [A, B]) {
    for (const beta of [A, B]) for (const gamma of [A, B]) {
      const deletion = [u[q], s[beta], t[gamma]];
      if (q === beta && q === gamma) {
        if (!distinct(deletion)) return {rejected: "missing_pure_diagonal"};
        add(deletion, "pure", q, `off:${q}${beta}${gamma}`);
      } else if (distinct(deletion)) {
        add(deletion, "zero", null, `off:${q}${beta}${gamma}`);
      }
      if (conflict) return {rejected: conflict.reason, conflict};
    }

    const active = (activeMask & (1 << (q - 1))) !== 0;
    const iiDeletion = [u[q], s[I], t[I]];
    if (active) {
      if (!distinct(iiDeletion)) return {rejected: "active_corner_collision"};
      add(iiDeletion, "nonzero", null, `corner:${q}ii`);
    } else if (distinct(iiDeletion)) {
      add(iiDeletion, "zero", null, `corner:${q}ii`);
    }
    if (conflict) return {rejected: conflict.reason, conflict};

    for (const d of [A, B]) {
      const id = [u[q], s[I], t[d]];
      const di = [u[q], s[d], t[I]];
      if (distinct(id)) add(id, "zero", null, `strip:${q}i${d}`);
      if (conflict) return {rejected: conflict.reason, conflict};
      if (distinct(di)) add(di, "zero", null, `strip:${q}${d}i`);
      if (conflict) return {rejected: conflict.reason, conflict};
    }
  }

  return {
    rejected: null,
    constraints: [...constraints.entries()].map(([edge, value]) => ({
      edge,
      zero: value.zero,
      nonzero: value.nonzero,
      pure: [...value.pure],
      sources: value.sources
    }))
  };
}

function inspectLeafEdgeAssignment(activeMask, anchors, sharedColour, externalOffColour) {
  const constraints = new Map();
  let conflict = null;
  function add(values, kind, colour, source) {
    const key = complementPair(values);
    const current = constraints.get(key) || {zero: false, nonzero: false, pure: new Set(), sources: []};
    if (kind === "zero") current.zero = true;
    if (kind === "nonzero") current.nonzero = true;
    if (kind === "pure") { current.nonzero = true; current.pure.add(colour); }
    current.sources.push(source); constraints.set(key, current);
    if (current.zero && current.nonzero) conflict = {key, reason: "zero_nonzero", sources: current.sources};
    if (current.pure.size > 1) conflict = {key, reason: "two_pure_colours", sources: current.sources};
  }

  const u = {[A]: anchors.ua, [B]: anchors.ub};
  const s = {[I]: anchors.si, [externalOffColour]: anchors.sd};
  const t = {[I]: anchors.ti, [externalOffColour]: anchors.td};
  if (s[I] === t[I]) return {rejected: "same_i_terminal"};
  for (const q of [A, B]) if ((activeMask & (1 << (q - 1))) && (u[q] === s[I] || u[q] === t[I]))
    return {rejected: "active_anchor_collision"};

  for (const q of [A, B]) {
    for (const beta of [I, externalOffColour]) for (const gamma of [I, externalOffColour]) {
      const deletion = [u[q], s[beta], t[gamma]];
      if (beta === externalOffColour && gamma === externalOffColour && q === externalOffColour) {
        if (!distinct(deletion)) return {rejected: "missing_pure_diagonal"};
        add(deletion, "pure", q, `edge-off:${q}${beta}${gamma}`);
      } else if (beta === I && gamma === I) {
        const active = (activeMask & (1 << (q - 1))) !== 0;
        if (active) {
          if (!distinct(deletion)) return {rejected: "active_corner_collision"};
          add(deletion, "nonzero", null, `edge-corner:${q}ii`);
        } else if (distinct(deletion)) add(deletion, "zero", null, `edge-corner:${q}ii`);
      } else if (distinct(deletion)) {
        add(deletion, "zero", null, `edge-strip:${q}${beta}${gamma}`);
      }
      if (conflict) return {rejected: conflict.reason, conflict};
    }
  }
  return {
    rejected: null,
    constraints: [...constraints.entries()].map(([edge, value]) => ({
      edge, zero: value.zero, nonzero: value.nonzero, pure: [...value.pure], sources: value.sources
    })),
    tensor_constraints: [
      {deleted: u[sharedColour], type: "pure", colour: sharedColour},
      {deleted: u[externalOffColour], type: "zero"}
    ]
  };
}

function inspectCiZeroAssignment(activeMask, anchors) {
  const constraints = new Map();
  let conflict = null;
  function add(values, kind, colour, source) {
    const key = complementPair(values);
    const current = constraints.get(key) || {zero: false, nonzero: false, pure: new Set(), sources: []};
    if (kind === "zero") current.zero = true;
    if (kind === "pure") { current.nonzero = true; current.pure.add(colour); }
    current.sources.push(source); constraints.set(key, current);
    if (current.zero && current.nonzero) conflict = {key, reason: "zero_nonzero", sources: current.sources};
    if (current.pure.size > 1) conflict = {key, reason: "two_pure_colours", sources: current.sources};
  }
  const u = {[A]: anchors.ua, [B]: anchors.ub};
  const s = {[I]: anchors.si, [A]: anchors.sa, [B]: anchors.sb};
  const t = {[I]: anchors.ti, [A]: anchors.ta, [B]: anchors.tb};
  for (const q of [A, B]) if ((activeMask & (1 << (q - 1))) && u[q] === t[I])
    return {rejected: "active_anchor_collision"};
  for (const q of [A, B]) {
    for (const beta of [A, B]) for (const gamma of [A, B]) {
      const deletion = [u[q], s[beta], t[gamma]];
      if (q === beta && q === gamma) {
        if (!distinct(deletion)) return {rejected: "missing_pure_diagonal"};
        add(deletion, "pure", q, `zero-off:${q}${beta}${gamma}`);
      } else if (distinct(deletion)) add(deletion, "zero", null, `zero-off:${q}${beta}${gamma}`);
      if (conflict) return {rejected: conflict.reason, conflict};
    }
    for (const d of [A, B]) {
      const deletion = [u[q], s[I], t[d]];
      if (distinct(deletion)) add(deletion, "zero", null, `zero-strip:${q}i${d}`);
      if (conflict) return {rejected: conflict.reason, conflict};
    }
  }
  return {
    rejected: null,
    constraints: [...constraints.entries()].map(([edge, value]) => ({
      edge, zero: value.zero, nonzero: value.nonzero, pure: [...value.pure], sources: value.sources
    })),
    tensor_constraints: [{deleted: t[I], type: "pure", colour: I}]
  };
}

function inspectCiZeroLeafEdgeAssignment(activeMask, anchors, sharedColour, externalOffColour) {
  const constraints = new Map();
  let conflict = null;
  function add(values, kind, colour, source) {
    const key = complementPair(values);
    const current = constraints.get(key) || {zero: false, nonzero: false, pure: new Set(), sources: []};
    if (kind === "zero") current.zero = true;
    if (kind === "pure") { current.nonzero = true; current.pure.add(colour); }
    current.sources.push(source); constraints.set(key, current);
    if (current.zero && current.nonzero) conflict = {key, reason: "zero_nonzero", sources: current.sources};
    if (current.pure.size > 1) conflict = {key, reason: "two_pure_colours", sources: current.sources};
  }
  const u = {[A]: anchors.ua, [B]: anchors.ub};
  const s = {[I]: anchors.si, [externalOffColour]: anchors.sd};
  const t = {[I]: anchors.ti, [externalOffColour]: anchors.td};
  for (const q of [A, B]) if ((activeMask & (1 << (q - 1))) && u[q] === t[I])
    return {rejected: "active_anchor_collision"};
  for (const q of [A, B]) {
    let deletion = [u[q], s[externalOffColour], t[externalOffColour]];
    if (q === externalOffColour) {
      if (!distinct(deletion)) return {rejected: "missing_pure_diagonal"};
      add(deletion, "pure", q, `zero-edge-off:${q}${externalOffColour}${externalOffColour}`);
    } else if (distinct(deletion)) add(deletion, "zero", null, `zero-edge-off:${q}${externalOffColour}${externalOffColour}`);
    if (conflict) return {rejected: conflict.reason, conflict};
    deletion = [u[q], s[I], t[externalOffColour]];
    if (distinct(deletion)) add(deletion, "zero", null, `zero-edge-strip:${q}i${externalOffColour}`);
    if (conflict) return {rejected: conflict.reason, conflict};
  }
  return {
    rejected: null,
    constraints: [...constraints.entries()].map(([edge, value]) => ({
      edge, zero: value.zero, nonzero: value.nonzero, pure: [...value.pure], sources: value.sources
    })),
    tensor_constraints: [
      {deleted: t[I], type: "pure", colour: I},
      {deleted: u[sharedColour], type: "pure", colour: sharedColour},
      {deleted: u[externalOffColour], type: "zero"}
    ]
  };
}

function isFourConnected(internalEdges, anchors, leafEdge = false) {
  const R = 5, S = 6, T = 7, n = 8;
  const adj = Array.from({length: n}, () => []);
  function edge(x, y) { adj[x].push(y); adj[y].push(x); }
  for (const [x, y] of internalEdges) edge(x, y);
  edge(R, S); edge(R, T); edge(R, anchors.ua); edge(R, anchors.ub);
  if (leafEdge) {
    edge(S, T); edge(S, anchors.si); edge(S, anchors.sd);
    edge(T, anchors.ti); edge(T, anchors.td);
  } else {
    edge(S, anchors.si); edge(S, anchors.sa); edge(S, anchors.sb);
    edge(T, anchors.ti); edge(T, anchors.ta); edge(T, anchors.tb);
  }
  for (let removed = 0; removed < (1 << n); ++removed) {
    let bits = 0;
    for (let v = 0; v < n; ++v) bits += (removed >>> v) & 1;
    if (bits > 3) continue;
    let start = -1, remaining = 0;
    for (let v = 0; v < n; ++v) if (((removed >>> v) & 1) === 0) {
      ++remaining;
      if (start < 0) start = v;
    }
    const seen = new Set([start]), stack = [start];
    while (stack.length) {
      const v = stack.pop();
      for (const w of adj[v]) if (((removed >>> w) & 1) === 0 && !seen.has(w)) {
        seen.add(w); stack.push(w);
      }
    }
    if (seen.size !== remaining) return false;
  }
  return true;
}

function tensorScreen(internalEdges, constraints, tensorConstraints) {
  if (!tensorConstraints || tensorConstraints.length === 0) return {ok: true, forced_pure: []};
  const edgeSet = new Set(internalEdges.map(([x, y]) => x < y ? `${x},${y}` : `${y},${x}`));
  const forcedPure = new Map();
  for (const c of constraints) if (c.pure && c.pure.length) forcedPure.set(c.edge, c.pure[0]);
  for (const tc of tensorConstraints) {
    const rem = vertices.filter(v => v !== tc.deleted);
    const matchings = [
      [[rem[0], rem[1]], [rem[2], rem[3]]],
      [[rem[0], rem[2]], [rem[1], rem[3]]],
      [[rem[0], rem[3]], [rem[1], rem[2]]]
    ].filter(pm => pm.every(([x, y]) => edgeSet.has(x < y ? `${x},${y}` : `${y},${x}`)));
    if (tc.type === "zero") {
      if (matchings.length === 1) return {ok: false, reason: "unique_matching_cannot_zero"};
      continue;
    }
    if (tc.type === "pure") {
      if (matchings.length === 0) return {ok: false, reason: "pure_tensor_has_no_matching"};
      if (matchings.length === 1) {
        for (const [x, y] of matchings[0]) {
          const key = x < y ? `${x},${y}` : `${y},${x}`;
          if (forcedPure.has(key) && forcedPure.get(key) !== tc.colour)
            return {ok: false, reason: "unique_pure_colour_conflict"};
          forcedPure.set(key, tc.colour);
        }
      }
    }
  }
  return {ok: true, forced_pure: [...forcedPure.entries()].map(([edge, colour]) => ({edge, colour}))};
}

function completeInternalGraph(anchors, constraints, leafEdge = false, tensorConstraints = []) {
  const boundaryDegree = Array(5).fill(0);
  const boundaryKeys = leafEdge ? ["ua", "ub", "si", "sd", "ti", "td"]
                                : ["ua", "ub", "si", "sa", "sb", "ti", "ta", "tb"];
  for (const key of boundaryKeys)
    ++boundaryDegree[anchors[key]];
  const need = boundaryDegree.map(d => 4 - d);
  if (need.some(d => d < 0 || d > 4)) return {completions: 0, fourConnected: 0, examples: []};

  const state = new Map(constraints.map(c => [c.edge, c]));
  const internalPairs = [];
  for (let x = 0; x < 5; ++x) for (let y = x + 1; y < 5; ++y) internalPairs.push([x, y]);
  internalPairs.sort((e1, e2) => {
    const c1 = state.get(`${e1[0]},${e1[1]}`), c2 = state.get(`${e2[0]},${e2[1]}`);
    const p1 = c1 && c1.nonzero ? 0 : c1 && c1.zero ? 1 : 2;
    const p2 = c2 && c2.nonzero ? 0 : c2 && c2.zero ? 1 : 2;
    return p1 - p2;
  });

  let rawCompletions = 0, completions = 0, fourConnected = 0;
  const tensorRejections = {};
  const examples = [], fourConnectedEdges = [], degree = Array(5).fill(0), chosen = [];
  function rec(pos) {
    if (pos === internalPairs.length) {
      if (degree.some((d, v) => d !== need[v])) return;
      ++rawCompletions;
      const screen = tensorScreen(chosen, constraints, tensorConstraints);
      if (!screen.ok) {
        tensorRejections[screen.reason] = (tensorRejections[screen.reason] || 0) + 1;
        return;
      }
      ++completions;
      const fc = isFourConnected(chosen, anchors, leafEdge);
      if (fc) { ++fourConnected; fourConnectedEdges.push(chosen.map(e => e.slice())); }
      if (examples.length < 4) examples.push({edges: chosen.map(e => e.slice()), four_connected: fc,
        forced_pure: screen.forced_pure});
      return;
    }
    const [x, y] = internalPairs[pos], key = `${x},${y}`, c = state.get(key);
    const forcedOn = c && c.nonzero, forcedOff = c && c.zero;
    if (!forcedOn) rec(pos + 1);
    if (!forcedOff && degree[x] < need[x] && degree[y] < need[y]) {
      ++degree[x]; ++degree[y]; chosen.push([x, y]);
      rec(pos + 1);
      chosen.pop(); --degree[x]; --degree[y];
    }
  }
  rec(0);
  return {raw_completions: rawCompletions, completions, fourConnected,
    tensor_rejections: tensorRejections, examples, four_connected_edges: fourConnectedEdges};
}

function canonicalLeafEdge(anchors, edges) {
  let best = null;
  for (const p of permutations) {
    const a = [anchors.ua, anchors.ub, anchors.si, anchors.sd, anchors.ti, anchors.td].map(v => p[v]);
    const es = edges.map(([x, y]) => {
      const px = p[x], py = p[y]; return px < py ? `${px}${py}` : `${py}${px}`;
    }).sort();
    const key = `${a.join("")}|${es.join(".")}`;
    if (best === null || key < best) best = key;
  }
  return best;
}

const started = Date.now();
const byMask = {};
let total = 0;
for (const activeMask of [1, 2, 3]) {
  const reasons = {};
  let assignments = 0, incidenceSurvivors = 0, degreeSurvivors = 0;
  let internalCompletions = 0, fourConnectedCompletions = 0;
  const examples = [];
  for (const [ua, ub] of pairs) for (const [si, sa, sb] of triples) for (const [ti, ta, tb] of triples) {
    ++assignments;
    const anchors = {ua, ub, si, sa, sb, ti, ta, tb};
    const result = inspectAssignment(activeMask, anchors);
    if (result.rejected) {
      reasons[result.rejected] = (reasons[result.rejected] || 0) + 1;
    } else {
      ++incidenceSurvivors;
      const completion = completeInternalGraph(anchors, result.constraints, false, result.tensor_constraints || []);
      internalCompletions += completion.completions;
      fourConnectedCompletions += completion.fourConnected;
      if (completion.completions > 0) {
        ++degreeSurvivors;
        if (examples.length < 20) examples.push({anchors, constraints: result.constraints, completion});
      } else {
        reasons.no_four_regular_completion = (reasons.no_four_regular_completion || 0) + 1;
      }
    }
  }
  total += assignments;
  byMask[activeMask] = {
    assignments,
    incidence_survivors: incidenceSurvivors,
    four_regular_assignment_survivors: degreeSurvivors,
    internal_graph_completions: internalCompletions,
    four_connected_completions: fourConnectedCompletions,
    rejection_reasons: reasons,
    examples
  };
}

const leafEdgeByMask = {};
for (const activeMask of [1, 2, 3]) {
  const reasons = {};
  let assignments = 0, incidenceSurvivors = 0, degreeSurvivors = 0;
  let internalCompletions = 0, fourConnectedCompletions = 0;
  const examples = [];
  for (const [ua, ub] of pairs) for (const [si, sd] of pairs) for (const [ti, td] of pairs) {
    ++assignments;
    const anchors = {ua, ub, si, sd, ti, td};
    const result = inspectLeafEdgeAssignment(activeMask, anchors, A, B);
    if (result.rejected) {
      reasons[result.rejected] = (reasons[result.rejected] || 0) + 1;
    } else {
      ++incidenceSurvivors;
      const completion = completeInternalGraph(anchors, result.constraints, true, result.tensor_constraints || []);
      internalCompletions += completion.completions;
      fourConnectedCompletions += completion.fourConnected;
      if (completion.completions > 0) {
        ++degreeSurvivors;
        if (examples.length < 20) examples.push({anchors, constraints: result.constraints,
          tensor_constraints: result.tensor_constraints, completion});
      } else reasons.no_four_regular_completion = (reasons.no_four_regular_completion || 0) + 1;
    }
  }
  total += assignments;
  leafEdgeByMask[activeMask] = {
    assignments,
    incidence_survivors: incidenceSurvivors,
    four_regular_assignment_survivors: degreeSurvivors,
    internal_graph_completions: internalCompletions,
    four_connected_completions: fourConnectedCompletions,
    rejection_reasons: reasons,
    examples
  };
}


function enumerateCiZero(leafEdge) {
  const output = {};
  for (const activeMask of [1, 2, 3]) {
    const reasons = {};
    let assignments = 0, incidenceSurvivors = 0, degreeSurvivors = 0;
    let internalCompletions = 0, fourConnectedCompletions = 0;
    const orbitCounts = new Map();
    const examples = [];
    const runOne = anchors => {
      ++assignments;
      const result = leafEdge ? inspectCiZeroLeafEdgeAssignment(activeMask, anchors, A, B)
                              : inspectCiZeroAssignment(activeMask, anchors);
      if (result.rejected) {
        reasons[result.rejected] = (reasons[result.rejected] || 0) + 1;
        return;
      }
      ++incidenceSurvivors;
      const completion = completeInternalGraph(anchors, result.constraints, leafEdge, result.tensor_constraints || []);
      internalCompletions += completion.completions;
      fourConnectedCompletions += completion.fourConnected;
      if (leafEdge) for (const edges of completion.four_connected_edges || []) {
        const key = canonicalLeafEdge(anchors, edges);
        orbitCounts.set(key, (orbitCounts.get(key) || 0) + 1);
      }
      if (completion.completions > 0) {
        ++degreeSurvivors;
        if (examples.length < 20) examples.push({anchors, constraints: result.constraints,
          tensor_constraints: result.tensor_constraints, completion});
      } else reasons.no_four_regular_completion = (reasons.no_four_regular_completion || 0) + 1;
    };
    if (leafEdge) {
      for (const [ua, ub] of pairs) for (const [si, sd] of pairs) for (const [ti, td] of pairs)
        runOne({ua, ub, si, sd, ti, td});
    } else {
      for (const [ua, ub] of pairs) for (const [si, sa, sb] of triples) for (const [ti, ta, tb] of triples)
        runOne({ua, ub, si, sa, sb, ti, ta, tb});
    }
    total += assignments;
    output[activeMask] = {
      assignments, incidence_survivors: incidenceSurvivors,
      four_regular_assignment_survivors: degreeSurvivors,
      internal_graph_completions: internalCompletions,
      four_connected_completions: fourConnectedCompletions,
      four_connected_orbit_count: orbitCounts.size,
      four_connected_orbits: [...orbitCounts.entries()].map(([key, count]) => ({key, count})),
      rejection_reasons: reasons, examples
    };
  }
  return output;
}

const ciZeroByMask = enumerateCiZero(false);
const ciZeroLeafEdgeByMask = enumerateCiZero(true);

const summary = {
  schema_version: 1,
  series: "run-018",
  mode: "exact_boundary_incidence",
  external_vertices: vertices.length,
  active_masks: [1, 2, 3],
  assignments_checked: total,
  elapsed_seconds: (Date.now() - started) / 1000,
  no_leaf_edge_by_mask: byMask,
  leaf_edge_by_mask: leafEdgeByMask,
  ci_zero_no_leaf_edge_by_mask: ciZeroByMask,
  ci_zero_leaf_edge_by_mask: ciZeroLeafEdgeByMask
};

const out = path.join(__dirname, "local-runs", "run-018-summary.json");
fs.mkdirSync(path.dirname(out), {recursive: true});
fs.writeFileSync(out, JSON.stringify(summary, null, 2) + "\n");
process.stdout.write(JSON.stringify({
  series: summary.series,
  assignments_checked: total,
  elapsed_seconds: summary.elapsed_seconds,
  no_leaf_edge: Object.fromEntries(Object.entries(byMask).map(([k, v]) => [k, {
    incidence: v.incidence_survivors, four_regular: v.four_regular_assignment_survivors,
    four_connected: v.four_connected_completions
  }])),
  leaf_edge: Object.fromEntries(Object.entries(leafEdgeByMask).map(([k, v]) => [k, {
    incidence: v.incidence_survivors, four_regular: v.four_regular_assignment_survivors,
    four_connected: v.four_connected_completions
  }])),
  ci_zero_no_leaf_edge: Object.fromEntries(Object.entries(ciZeroByMask).map(([k, v]) => [k, {
    incidence: v.incidence_survivors, four_regular: v.four_regular_assignment_survivors,
    four_connected: v.four_connected_completions
  }])),
  ci_zero_leaf_edge: Object.fromEntries(Object.entries(ciZeroLeafEdgeByMask).map(([k, v]) => [k, {
    incidence: v.incidence_survivors, four_regular: v.four_regular_assignment_survivors,
    four_connected: v.four_connected_completions
  }]))
}, null, 2) + "\n");
