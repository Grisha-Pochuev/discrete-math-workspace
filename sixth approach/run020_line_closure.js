"use strict";

const fs = require("fs");
const path = require("path");

const n = 6;
const pairs = [];
for (let a = 0; a < n; ++a) for (let b = a + 1; b < n; ++b) pairs.push([a,b]);

function edgeKey(a,b) { return a < b ? `${a},${b}` : `${b},${a}`; }

function permutations(a) {
  if (a.length === 0) return [[]];
  const out = [];
  for (let i = 0; i < a.length; ++i) {
    const rest = a.slice(0,i).concat(a.slice(i+1));
    for (const p of permutations(rest)) out.push([a[i],...p]);
  }
  return out;
}

function matchings4(v,E) {
  const [a,b,c,d] = v;
  return [[[a,b],[c,d]],[[a,c],[b,d]],[[a,d],[b,c]]]
    .filter(M => M.every(([x,y]) => E.has(edgeKey(x,y))));
}

function hasPerfectMatching(vertices,E) {
  if (vertices.length === 0) return true;
  const a = vertices[0];
  for (let i = 1; i < vertices.length; ++i) {
    const b = vertices[i];
    if (!E.has(edgeKey(a,b))) continue;
    const rest = vertices.slice(1,i).concat(vertices.slice(i+1));
    if (hasPerfectMatching(rest,E)) return true;
  }
  return false;
}

function triangleCount(E) {
  let count = 0;
  for (let a=0;a<n;++a) for (let b=a+1;b<n;++b) for (let c=b+1;c<n;++c)
    if (E.has(edgeKey(a,b)) && E.has(edgeKey(a,c)) && E.has(edgeKey(b,c))) ++count;
  return count;
}

const cubicGraphs = [];
for (let mask=0; mask<(1<<pairs.length); ++mask) {
  const degree=Array(n).fill(0), edges=[];
  for (let e=0;e<pairs.length;++e) if ((mask>>>e)&1) {
    const [a,b]=pairs[e]; ++degree[a]; ++degree[b]; edges.push([a,b]);
  }
  if (degree.every(d=>d===3)) cubicGraphs.push(edges);
}

const categoryCounts={}, signatureCounts={}, examples={};
let accepted=0;
for (const right of permutations([3,4,5])) for (const edges of cubicGraphs) {
  const E=new Set(edges.map(e=>edgeKey(...e)));
  const local=[0,1,2,null,null,null];
  for (let q=0;q<3;++q) local[right[q]]=q;
  const forced=new Map();
  let unique=0,multiple=0,valid=true;

  for (let a=0;a<3&&valid;++a) for (let b=0;b<3&&valid;++b) if (a!==b) {
    const deleted=new Set([a,right[b]]);
    const remain=[0,1,2,3,4,5].filter(v=>!deleted.has(v));
    const matchings=matchings4(remain,E);
    if (matchings.length===0) { valid=false; break; }
    if (matchings.length>1) { ++multiple; continue; }
    ++unique;
    for (const [x,y] of matchings[0]) {
      const k=edgeKey(x,y), value=`${local[x]},${local[y]}`;
      if (forced.has(k) && forced.get(k)!==value) { valid=false; break; }
      forced.set(k,value);
    }
  }
  if (!valid) continue;
  ++accepted;

  const triangles=triangleCount(E);
  const topology=triangles===0?"paired_bipartite":triangles===2?"triangular_pair":"other";
  const unforced=edges.filter(e=>!forced.has(edgeKey(...e)));
  const forcedDegree=Array(n).fill(0);
  for (const k of forced.keys()) for (const v of k.split(",").map(Number)) ++forcedDegree[v];
  const equalFullColumnVertices=[];
  const soleUnforcedRequirements=new Map();
  for (let v=0;v<n;++v) {
    const neighbourColours=new Set([local[v]]);
    for (const [a,b] of edges) if (forced.has(edgeKey(a,b))) {
      if (a===v) neighbourColours.add(local[b]);
      if (b===v) neighbourColours.add(local[a]);
    }
    if (neighbourColours.size===3) equalFullColumnVertices.push(v);
    const incidentUnforced=unforced.filter(([a,b])=>a===v||b===v);
    if (incidentUnforced.length===1 && neighbourColours.size===2) {
      const missing=[0,1,2].find(q=>!neighbourColours.has(q));
      const k=edgeKey(...incidentUnforced[0]);
      if (!soleUnforcedRequirements.has(k)) soleUnforcedRequirements.set(k,[]);
      soleUnforcedRequirements.get(k).push({vertex:v,colour:missing});
    }
  }
  const oppositeRequirementConflicts=[...soleUnforcedRequirements.entries()].filter(([,requirements])=>
    requirements.length===2 && requirements[0].colour!==requirements[1].colour);

  const purePossible=[];
  for (let colour=0;colour<3;++colour) {
    const allowed=new Set(unforced.map(e=>edgeKey(...e)));
    for (const [k,value] of forced) {
      const [x,y]=value.split(",").map(Number);
      if (x===colour && y===colour) allowed.add(k);
    }
    allowed.add(edgeKey(6,7));
    allowed.add(edgeKey(6,colour));
    allowed.add(edgeKey(7,right[colour]));
    purePossible.push(hasPerfectMatching([0,1,2,3,4,5,6,7],allowed));
  }

  let category;
  if (topology==="paired_bipartite") category="paired_bipartite_residue";
  else if (!purePossible.every(Boolean)) category="missing_pure_support";
  else if (equalFullColumnVertices.length) category="equal_full_column_lines";
  else if (oppositeRequirementConflicts.length) category="opposite_unit_requirements";
  else category="unclassified";
  categoryCounts[category]=(categoryCounts[category]||0)+1;

  const udeg=Array(n).fill(0);
  for (const [a,b] of unforced) { ++udeg[a]; ++udeg[b]; }
  const signature=[topology,`unique=${unique}`,`multiple=${multiple}`,`forced=${forced.size}`,
    `unforced_degrees=${udeg.slice().sort((a,b)=>a-b).join("")}`,
    `pure=${purePossible.map(Number).join("")}`,
    `equal_full_column=${equalFullColumnVertices.length}`,
    `opposite_conflicts=${oppositeRequirementConflicts.length}`,category].join(";");
  signatureCounts[signature]=(signatureCounts[signature]||0)+1;
  if (!examples[signature]) examples[signature]={right_anchors:right,internal_edges:edges,
    forced_edges:[...forced.entries()],unforced_edges:unforced,forced_degrees:forcedDegree,
    equal_full_column_vertices:equalFullColumnVertices,
    sole_unforced_requirements:[...soleUnforcedRequirements.entries()],
    opposite_requirement_conflicts:oppositeRequirementConflicts};
}

if (accepted!==366 || categoryCounts.paired_bipartite_residue!==6 ||
    categoryCounts.missing_pure_support!==216 ||
    categoryCounts.equal_full_column_lines!==108 ||
    categoryCounts.opposite_unit_requirements!==36 || categoryCounts.unclassified)
  throw new Error("closure census mismatch");

const summary={schema_version:1,series:"run-020",mode:"exact_line_closure",
  cubic_graphs:cubicGraphs.length,boundary_assignments:6,accepted,
  category_counts:categoryCounts,signature_counts:signatureCounts,examples};
const out=path.join(__dirname,"local-runs","run-020-summary.json");
fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");
process.stdout.write(JSON.stringify({series:summary.series,accepted,category_counts:categoryCounts,
  signatures:Object.keys(signatureCounts).length},null,2)+"\n");
