"use strict";

const fs = require("fs");
const path = require("path");
const core = require("./run012_local_structures.js");
const n = core.n;

function diagonalColourings(graph, nonunit, offdiag, centre, leaves, missing, limit) {
  const colour = Array(graph.edges.length).fill(-2);
  for (const e of nonunit) colour[e] = -1;
  for (const [e,a,b] of offdiag) colour[e] = -3 - 3 * a - b;
  const edges = [];
  for (let e = 0; e < colour.length; ++e) if (colour[e] === -2) edges.push(e);
  const counts = Array.from({length:n}, () => [0,0,0]);
  const remaining = Array(n).fill(0);
  for (const e of edges) for (const v of graph.edges[e]) ++remaining[v];
  const answers = [];
  function possible(v) {
    const c = counts[v], r = remaining[v];
    if (v === centre) {
      for (let q = 0; q < 3; ++q) {
        const need = q === missing ? 0 : 1;
        if (c[q] > need || c[q] + r < need) return false;
      }
      return true;
    }
    if (leaves.includes(v)) {
      for (let q = 0; q < 3; ++q) if (c[q] > 1 || c[q] + r < 1) return false;
      return true;
    }
    let absent = 0;
    for (let q = 0; q < 3; ++q) if (c[q] === 0) ++absent;
    return absent <= r;
  }
  function rec(pos) {
    if (answers.length >= limit) return;
    if (pos === edges.length) {
      for (let v = 0; v < n; ++v) if (!possible(v)) return;
      answers.push(colour.slice()); return;
    }
    const e = edges[pos], [u,v] = graph.edges[e];
    --remaining[u]; --remaining[v];
    for (let q = 0; q < 3; ++q) {
      colour[e] = q; ++counts[u][q]; ++counts[v][q];
      if (possible(u) && possible(v)) rec(pos + 1);
      --counts[u][q]; --counts[v][q];
    }
    colour[e] = -2; ++remaining[u]; ++remaining[v];
  }
  rec(0);
  return answers;
}

function countWithOffdiag(graph, pms, labels, nonunitData, offdiagMap) {
  const counts = new Map();
  for (const pm of pms) {
    let assignments = [Array(n).fill(-1)];
    for (const e of pm) {
      const [u,v] = graph.edges[e];
      if (nonunitData.has(e)) {
        const d = nonunitData.get(e), next = [];
        for (const old of assignments) for (const q of d.centreSupport) {
          const a = old.slice();
          if ((a[d.centre] >= 0 && a[d.centre] !== q) ||
              (a[d.leaf] >= 0 && a[d.leaf] !== d.remoteColour)) continue;
          a[d.centre] = q; a[d.leaf] = d.remoteColour; next.push(a);
        }
        assignments = next;
      } else {
        const pair = offdiagMap.get(e);
        const cu = pair ? pair[0] : labels[e], cv = pair ? pair[1] : labels[e];
        const next = [];
        for (const old of assignments) {
          if ((old[u] >= 0 && old[u] !== cu) || (old[v] >= 0 && old[v] !== cv)) continue;
          const a = old.slice(); a[u] = cu; a[v] = cv; next.push(a);
        }
        assignments = next;
      }
      if (!assignments.length) break;
    }
    for (const a of assignments) {
      const key = a.join(""); counts.set(key, (counts.get(key) || 0) + 1);
    }
  }
  let singletons = 0, min = Infinity;
  for (const [key,val] of counts) if (![...key].every(ch => ch === key[0])) {
    if (val === 1) ++singletons;
    if (val < min) min = val;
  }
  return {mixedSingletons: singletons, minimumMixed: Number.isFinite(min) ? min : null};
}

const started = Date.now();
let graphs = 0, labelings = 0, supportCases = 0, minimum = Infinity, firstZero = null;
for (let trial = 0; trial < 5000 && Date.now() - started < 820000; ++trial) {
  const graph = core.complement4(core.randomCubic());
  if (!core.connected(graph)) continue;
  ++graphs;
  const pms = core.perfectMatchings(graph);
  const centre = core.randint(n);
  const around = graph.adj[centre].slice(); core.shuffle(around);
  const nonunit = around.slice(0,2);
  const leaves = nonunit.map(e => graph.edges[e][0] ^ graph.edges[e][1] ^ centre);
  const ordinary = [];
  for (let v = 0; v < n; ++v) if (v !== centre && !leaves.includes(v)) ordinary.push(v);
  const eligible = [];
  for (let e = 0; e < graph.edges.length; ++e) {
    const [u,v] = graph.edges[e];
    if (!nonunit.includes(e) && ordinary.includes(u) && ordinary.includes(v)) eligible.push(e);
  }
  core.shuffle(eligible);
  const chosen = [];
  const used = new Set();
  for (const e of eligible) {
    const [u,v] = graph.edges[e];
    if (!used.has(u) && !used.has(v) && core.randint(2)) {
      chosen.push(e); used.add(u); used.add(v);
    }
  }
  const offdiag = [];
  for (const e of chosen) {
    let a = core.randint(3), b = core.randint(3);
    if (a === b) b = (b + 1 + core.randint(2)) % 3;
    const [u,v] = graph.edges[e];
    offdiag.push([e, a, b]);
  }
  const offdiagMap = new Map(offdiag.map(x => [x[0], [x[1],x[2]]]));
  const missing = core.randint(3);
  const colourings = diagonalColourings(graph, new Set(nonunit), offdiag, centre, leaves, missing, 64);
  labelings += colourings.length;
  for (const labels of colourings) {
    const off = [0,1,2].filter(q => q !== missing);
    for (const O of [[off[0]],[off[1]],off]) for (const flags of [[1,0],[0,1],[1,1]]) {
      const data = new Map();
      for (let z = 0; z < 2; ++z) {
        const support = O.slice(); if (flags[z]) support.push(missing);
        data.set(nonunit[z], {centre, leaf: leaves[z], remoteColour: missing, centreSupport: support});
      }
      const result = countWithOffdiag(graph, pms, labels, data, offdiagMap);
      ++supportCases; minimum = Math.min(minimum, result.mixedSingletons);
      if (result.mixedSingletons === 0) {
        firstZero = {edges:graph.edges, centre, leaves, nonunit, missing, O, flags,
          offdiag, labels, perfectMatchings:pms.length, result};
        break;
      }
    }
    if (firstZero) break;
  }
  if (firstZero) break;
}
const summary = {
  schema_version:1, series:"run-013", seed:2026080901,
  elapsed_seconds:(Date.now()-started)/1000,
  connected_graph_trials:graphs, local_colourings:labelings, support_cases:supportCases,
  minimum_mixed_singletons:Number.isFinite(minimum)?minimum:null,
  zero_record_found:firstZero!==null, first_zero_record:firstZero
};
const out = path.join(__dirname,"local-runs","run-013-summary.json");
fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");
process.stdout.write(JSON.stringify(summary,null,2)+"\n");
