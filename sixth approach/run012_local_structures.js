"use strict";

const fs = require("fs");
const path = require("path");

const n = 8;
let rngState = 2026080901 >>> 0;
function rng() {
  rngState ^= rngState << 13;
  rngState ^= rngState >>> 17;
  rngState ^= rngState << 5;
  return rngState >>> 0;
}
function randint(k) { return rng() % k; }
function shuffle(a) {
  for (let i = a.length - 1; i > 0; --i) {
    const j = randint(i + 1);
    [a[i], a[j]] = [a[j], a[i]];
  }
}
function edgeKey(a, b) { return a < b ? `${a},${b}` : `${b},${a}`; }

function randomCubic() {
  for (let attempt = 0; attempt < 10000; ++attempt) {
    const stubs = [];
    for (let v = 0; v < n; ++v) for (let k = 0; k < 3; ++k) stubs.push(v);
    shuffle(stubs);
    const edges = [];
    const seen = new Set();
    let ok = true;
    for (let k = 0; k < stubs.length; k += 2) {
      const a = stubs[k], b = stubs[k + 1], key = edgeKey(a, b);
      if (a === b || seen.has(key)) { ok = false; break; }
      seen.add(key); edges.push([Math.min(a, b), Math.max(a, b)]);
    }
    if (ok) return seen;
  }
  throw new Error("failed to sample cubic complement");
}

function complement4(cubic) {
  const edges = [];
  const adj = Array.from({length: n}, () => []);
  for (let a = 0; a < n; ++a) for (let b = a + 1; b < n; ++b) {
    if (!cubic.has(edgeKey(a, b))) {
      const e = edges.length;
      edges.push([a, b]); adj[a].push(e); adj[b].push(e);
    }
  }
  return {edges, adj};
}

function connected(graph) {
  const seen = new Set([0]), stack = [0];
  while (stack.length) {
    const v = stack.pop();
    for (const e of graph.adj[v]) {
      const [a,b] = graph.edges[e], w = a ^ b ^ v;
      if (!seen.has(w)) { seen.add(w); stack.push(w); }
    }
  }
  return seen.size === n;
}

function perfectMatchings(graph) {
  const out = [];
  function rec(mask, chosen) {
    if (mask === 0) { out.push(chosen.slice()); return; }
    let v = 0; while (((mask >>> v) & 1) === 0) ++v;
    for (const e of graph.adj[v]) {
      const [a,b] = graph.edges[e], w = a ^ b ^ v;
      if ((mask >>> w) & 1) rec(mask & ~(1 << v) & ~(1 << w), chosen.concat(e));
    }
  }
  rec((1 << n) - 1, []);
  return out;
}

function unitColourings(graph, nonunit, centre, leaves, missing, limit) {
  const colour = Array(graph.edges.length).fill(-2);
  for (const e of nonunit) colour[e] = -1;
  const unitEdges = [];
  for (let e = 0; e < colour.length; ++e) if (colour[e] === -2) unitEdges.push(e);
  const incidentCounts = Array.from({length:n}, () => [0,0,0]);
  const answers = [];

  function localPossible(v, remainingIncident) {
    const counts = incidentCounts[v];
    if (v === centre) {
      for (let q = 0; q < 3; ++q) {
        const need = q === missing ? 0 : 1;
        if (counts[q] > need || counts[q] + remainingIncident < need) return false;
      }
      return true;
    }
    const isLeaf = leaves.includes(v);
    if (isLeaf) {
      for (let q = 0; q < 3; ++q)
        if (counts[q] > 1 || counts[q] + remainingIncident < 1) return false;
      return true;
    }
    let absent = 0;
    for (let q = 0; q < 3; ++q) if (counts[q] === 0) ++absent;
    return absent <= remainingIncident;
  }

  const remainingAt = Array.from({length:n}, () => 0);
  for (const e of unitEdges) for (const v of graph.edges[e]) ++remainingAt[v];
  function rec(pos) {
    if (answers.length >= limit) return;
    if (pos === unitEdges.length) {
      for (let v = 0; v < n; ++v) if (!localPossible(v, 0)) return;
      answers.push(colour.slice()); return;
    }
    const e = unitEdges[pos], [a,b] = graph.edges[e];
    --remainingAt[a]; --remainingAt[b];
    for (let q = 0; q < 3; ++q) {
      colour[e] = q; ++incidentCounts[a][q]; ++incidentCounts[b][q];
      if (localPossible(a, remainingAt[a]) && localPossible(b, remainingAt[b])) rec(pos + 1);
      --incidentCounts[a][q]; --incidentCounts[b][q];
    }
    colour[e] = -2; ++remainingAt[a]; ++remainingAt[b];
  }
  rec(0);
  return answers;
}

function countInduced(graph, pms, unitColours, nonunitData) {
  const counts = new Map();
  for (const pm of pms) {
    let assignments = [Array(n).fill(-1)], viable = true;
    for (const e of pm) {
      const [u,v] = graph.edges[e];
      if (unitColours[e] >= 0) {
        const q = unitColours[e];
        for (const a of assignments) {
          if ((a[u] >= 0 && a[u] !== q) || (a[v] >= 0 && a[v] !== q)) viable = false;
          a[u] = q; a[v] = q;
        }
        if (!viable) break;
      } else {
        const d = nonunitData.get(e), next = [];
        const leafSupport = d.leafSupport || [d.remoteColour];
        for (const a of assignments) for (const q of d.centreSupport) for (const z of leafSupport) {
          const b = a.slice();
          if ((b[d.centre] >= 0 && b[d.centre] !== q) ||
              (b[d.leaf] >= 0 && b[d.leaf] !== z)) continue;
          b[d.centre] = q; b[d.leaf] = z; next.push(b);
        }
        assignments = next;
        if (!assignments.length) { viable = false; break; }
      }
    }
    if (!viable) continue;
    for (const a of assignments) {
      const key = a.join("");
      counts.set(key, (counts.get(key) || 0) + 1);
    }
  }
  let mixedSingletons = 0, minimumMixed = Infinity;
  for (const [key, value] of counts) {
    if (![...key].every(ch => ch === key[0])) {
      if (value === 1) ++mixedSingletons;
      if (value < minimumMixed) minimumMixed = value;
    }
  }
  return {mixedSingletons, minimumMixed: Number.isFinite(minimumMixed) ? minimumMixed : null};
}

if (require.main === module) {
const started = Date.now();
let graphs = 0, localColourings = 0, supportCases = 0;
let minimumSingletons = Infinity, firstZero = null;
for (let trial = 0; trial < 2000 && Date.now() - started < 820000; ++trial) {
  const graph = complement4(randomCubic());
  if (!connected(graph)) continue;
  ++graphs;
  const pms = perfectMatchings(graph);
  const centre = randint(n);
  const neighbours = graph.adj[centre].slice(); shuffle(neighbours);
  const nonunit = neighbours.slice(0, 2);
  const leaves = nonunit.map(e => graph.edges[e][0] ^ graph.edges[e][1] ^ centre);
  const missing = randint(3);
  const colourings = unitColourings(graph, new Set(nonunit), centre, leaves, missing, 64);
  localColourings += colourings.length;
  for (const unitColours of colourings) {
    const off = [0,1,2].filter(q => q !== missing);
    const offMasks = [[off[0]], [off[1]], off];
    for (const offSupport of offMasks) for (const flags of [[1,0],[0,1],[1,1]]) {
      const nonunitData = new Map();
      for (let z = 0; z < 2; ++z) {
        const support = offSupport.slice(); if (flags[z]) support.push(missing);
        nonunitData.set(nonunit[z], {centre, leaf: leaves[z], remoteColour: missing, centreSupport: support});
      }
      const result = countInduced(graph, pms, unitColours, nonunitData);
      ++supportCases;
      if (result.mixedSingletons < minimumSingletons) minimumSingletons = result.mixedSingletons;
      if (result.mixedSingletons === 0) {
        firstZero = {edges: graph.edges, centre, leaves, nonunit, missing, offSupport, flags,
          unitColours, perfectMatchings: pms.length, result};
        break;
      }
    }
    if (firstZero) break;
  }
  if (firstZero) break;
}

const summary = {
  schema_version: 1,
  series: "run-012",
  seed: 2026080901,
  elapsed_seconds: (Date.now() - started) / 1000,
  connected_graph_trials: graphs,
  local_colourings: localColourings,
  support_cases: supportCases,
  minimum_mixed_singletons: Number.isFinite(minimumSingletons) ? minimumSingletons : null,
  zero_record_found: firstZero !== null,
  first_zero_record: firstZero
};
const out = path.join(__dirname, "local-runs", "run-012-summary.json");
fs.mkdirSync(path.dirname(out), {recursive: true});
fs.writeFileSync(out, JSON.stringify(summary, null, 2) + "\n");
process.stdout.write(JSON.stringify(summary, null, 2) + "\n");
}

module.exports = {
  n,
  randint,
  shuffle,
  randomCubic,
  complement4,
  connected,
  perfectMatchings,
  countInduced
};
