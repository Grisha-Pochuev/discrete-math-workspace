"use strict";

// Generate the small, immutable context needed by the run-035 audit.
const fs = require("fs");
const path = require("path");

const SOURCES = [
  { index: 3, missing_type: "C8", orbit: 8, factors: [[[0,2],[1,3],[4,6],[5,7]],[[0,3],[1,6],[2,5],[4,7]],[[0,5],[1,4],[2,7],[3,6]]], residual_edges: [[0,4],[0,6],[1,5],[1,7],[2,4],[2,6],[3,5],[3,7]], residual_components: [[0,2,4,6],[1,3,5,7]] },
  { index: 7, missing_type: "C8", orbit: 36, factors: [[[0,2],[1,4],[3,6],[5,7]],[[0,3],[1,6],[2,5],[4,7]],[[0,5],[1,3],[2,7],[4,6]]], residual_edges: [[0,4],[0,6],[1,5],[1,7],[2,4],[2,6],[3,5],[3,7]], residual_components: [[0,2,4,6],[1,3,5,7]] },
  { index: 9, missing_type: "C8", orbit: 51, factors: [[[0,2],[1,5],[3,7],[4,6]],[[0,3],[1,6],[2,5],[4,7]],[[0,5],[1,4],[2,7],[3,6]]], residual_edges: [[0,4],[0,6],[1,3],[1,7],[2,4],[2,6],[3,5],[5,7]], residual_components: [[0,2,4,6],[1,3,5,7]] },
  { index: 10, missing_type: "C8", orbit: 52, factors: [[[0,3],[1,5],[2,6],[4,7]],[[0,4],[1,6],[2,5],[3,7]],[[0,5],[1,4],[2,7],[3,6]]], residual_edges: [[0,2],[0,6],[1,3],[1,7],[2,4],[3,5],[4,6],[5,7]], residual_components: [[0,2,4,6],[1,3,5,7]] },
  { index: 11, missing_type: "C8", orbit: 53, factors: [[[0,3],[1,6],[2,5],[4,7]],[[0,4],[1,5],[2,6],[3,7]],[[0,5],[1,4],[2,7],[3,6]]], residual_edges: [[0,2],[0,6],[1,3],[1,7],[2,4],[3,5],[4,6],[5,7]], residual_components: [[0,2,4,6],[1,3,5,7]] },
  { index: 14, missing_type: "C4+C4", orbit: 3, factors: [[[0,2],[1,3],[4,6],[5,7]],[[0,4],[1,5],[2,6],[3,7]],[[0,6],[1,7],[2,4],[3,5]]], residual_edges: [[0,5],[0,7],[1,4],[1,6],[2,5],[2,7],[3,4],[3,6]], residual_components: [[0,2,5,7],[1,3,4,6]] },
  { index: 18, missing_type: "C4+C4", orbit: 9, factors: [[[0,2],[1,4],[3,6],[5,7]],[[0,4],[1,5],[2,6],[3,7]],[[0,6],[1,7],[2,4],[3,5]]], residual_edges: [[0,5],[0,7],[1,3],[1,6],[2,5],[2,7],[3,4],[4,6]], residual_components: [[0,2,5,7],[1,3,4,6]] },
  { index: 19, missing_type: "C4+C4", orbit: 16, factors: [[[0,2],[1,4],[3,6],[5,7]],[[0,5],[1,3],[2,7],[4,6]],[[0,7],[1,6],[2,5],[3,4]]], residual_edges: [[0,4],[0,6],[1,5],[1,7],[2,4],[2,6],[3,5],[3,7]], residual_components: [[0,2,4,6],[1,3,5,7]] },
  { index: 20, missing_type: "C4+C4", orbit: 17, factors: [[[0,4],[1,5],[2,6],[3,7]],[[0,5],[1,4],[2,7],[3,6]],[[0,6],[1,7],[2,4],[3,5]]], residual_edges: [[0,2],[0,7],[1,3],[1,6],[2,5],[3,4],[4,6],[5,7]], residual_components: [[0,2,5,7],[1,3,4,6]] },
  { index: 21, missing_type: "C4+C4", orbit: 19, factors: [[[0,4],[1,5],[2,6],[3,7]],[[0,5],[1,6],[2,7],[3,4]],[[0,6],[1,7],[2,4],[3,5]]], residual_edges: [[0,2],[0,7],[1,3],[1,4],[2,5],[3,6],[4,6],[5,7]], residual_components: [[0,2,5,7],[1,3,4,6]] },
  { index: 22, missing_type: "C4+C4", orbit: 20, factors: [[[0,4],[1,5],[2,6],[3,7]],[[0,5],[1,7],[2,4],[3,6]],[[0,6],[1,4],[2,7],[3,5]]], residual_edges: [[0,2],[0,7],[1,3],[1,6],[2,5],[3,4],[4,6],[5,7]], residual_components: [[0,2,5,7],[1,3,4,6]] }
];

function key(a, b) { return a < b ? `${a},${b}` : `${b},${a}`; }
function edge(a, b) { return a < b ? [a, b] : [b, a]; }
function matchings(vertices, allowed) {
  if (!vertices.length) return [[]];
  const first = vertices[0], result = [];
  for (const other of vertices.slice(1)) {
    if (!allowed.has(key(first, other))) continue;
    for (const tail of matchings(vertices.filter(v => v !== first && v !== other), allowed)) result.push([edge(first, other), ...tail]);
  }
  return result;
}
function cycleOrder(component, residual) {
  const adjacent = new Map(component.map(v => [v, []]));
  for (const [a, b] of residual) if (adjacent.has(a) && adjacent.has(b)) { adjacent.get(a).push(b); adjacent.get(b).push(a); }
  const first = Math.min(...component), order = [first, Math.min(...adjacent.get(first))];
  while (order.length < 4) {
    const previous = order.at(-2), current = order.at(-1);
    order.push(adjacent.get(current).find(v => v !== previous));
  }
  if (!adjacent.get(first).includes(order.at(-1))) throw new Error("expected a four-cycle");
  return order;
}
function states(order) {
  const result = [];
  for (let value = 0; value < 81; value++) {
    let remaining = value, state = {};
    for (const vertex of order) { state[vertex] = remaining % 3; remaining = Math.floor(remaining / 3); }
    result.push(state);
  }
  return result;
}
function mixed(state) { return [1,2,3,4,5,6,7].some(vertex => state[vertex] !== state[0]); }

const ALL = (1n << 81n) - 1n;
const records = SOURCES.map(source => {
  const factors = source.factors.map(matching => matching.map(([a, b]) => edge(a, b)));
  const residual = source.residual_edges.map(([a, b]) => edge(a, b));
  const allowed = new Set([...factors.flat(), ...residual].map(([a, b]) => key(a, b)));
  const owner = new Map();
  for (let color = 0; color < 3; color++) for (const [a, b] of factors[color]) owner.set(key(a, b), color);
  const allMatchings = matchings([0,1,2,3,4,5,6,7], allowed);
  const cross = allMatchings.filter(matching => matching.some(([a, b]) => owner.has(key(a, b))));
  const orders = source.residual_components.map(component => cycleOrder(component, residual));
  const stateSets = orders.map(states), rows = [], closed = [ALL], seen = new Set([ALL.toString()]);
  for (const left of stateSets[0]) {
    let row = 0n;
    for (let rightIndex = 0; rightIndex < 81; rightIndex++) {
      const state = {...left, ...stateSets[1][rightIndex]};
      const permitted = !mixed(state) || cross.some(matching => matching.every(([a, b]) => !owner.has(key(a, b)) || (state[a] === owner.get(key(a, b)) && state[b] === owner.get(key(a, b)))));
      if (permitted) row |= 1n << BigInt(rightIndex);
    }
    rows.push(row);
    for (const prior of [...closed]) {
      const next = prior & row;
      if (!seen.has(next.toString())) { seen.add(next.toString()); closed.push(next); }
    }
  }
  const concepts = new Map();
  for (const intent of closed) {
    let extent = 0n;
    for (let index = 0; index < 81; index++) if ((intent & ~rows[index]) === 0n) extent |= 1n << BigInt(index);
    let closure = ALL;
    for (let index = 0; index < 81; index++) if ((extent >> BigInt(index)) & 1n) closure &= rows[index];
    concepts.set(`${extent}|${closure}`, [extent.toString(), closure.toString()]);
  }
  return { index: source.index, missing_type: source.missing_type, orbit: source.orbit, residual_edges: residual, cycle_orders: orders, concepts: [...concepts.values()] };
});

const output = process.argv[2];
if (!output) throw new Error("usage: node run035_hnf_context.js OUTPUT");
fs.writeFileSync(output, JSON.stringify({schema_version: 1, records}, null, 2) + "\n");
