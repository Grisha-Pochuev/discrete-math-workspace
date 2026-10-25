"use strict";

const fs = require("fs");
const path = require("path");

const m = 6;
const noncoordinateSupports = [[0,1], [0,2], [1,2], [0,1,2]];
const internalPairs = [];
for (let x = 0; x < m; ++x) for (let y = x + 1; y < m; ++y) internalPairs.push([x,y]);

function orderedDistinct(k) {
  const out = [];
  function rec(a) {
    if (a.length === k) { out.push(a.slice()); return; }
    for (let v = 0; v < m; ++v) if (!a.includes(v)) { a.push(v); rec(a); a.pop(); }
  }
  rec([]); return out;
}

function edgeKey(x, y) { return x < y ? `${x},${y}` : `${y},${x}`; }

function perfectMatchings4(vertices, edgeSet) {
  const [a,b,c,d] = vertices;
  return [
    [[a,b],[c,d]], [[a,c],[b,d]], [[a,d],[b,c]]
  ].filter(pm => pm.every(([x,y]) => edgeSet.has(edgeKey(x,y))));
}

function fourConnected(internalEdges, rightAnchors) {
  const R=6,T=7,n=8,adj=Array.from({length:n},()=>[]);
  function add(x,y){adj[x].push(y);adj[y].push(x);}
  for(const [x,y] of internalEdges)add(x,y);
  add(R,T);
  for(let q=0;q<3;++q){add(R,q);add(T,rightAnchors[q]);}
  for(let removed=0;removed<(1<<n);++removed){
    let bits=0,start=-1,remain=0;
    for(let v=0;v<n;++v){bits+=(removed>>>v)&1;if(((removed>>>v)&1)===0){++remain;if(start<0)start=v;}}
    if(bits>3)continue;
    const seen=new Set([start]),stack=[start];
    while(stack.length){const v=stack.pop();for(const w of adj[v])if(((removed>>>w)&1)===0&&!seen.has(w)){seen.add(w);stack.push(w);}}
    if(seen.size!==remain)return false;
  }
  return true;
}

const graphsByDegree = new Map();
for (let mask=0; mask<(1<<internalPairs.length); ++mask) {
  const degrees=Array(m).fill(0),edges=[];
  for(let e=0;e<internalPairs.length;++e)if((mask>>>e)&1){const [x,y]=internalPairs[e];++degrees[x];++degrees[y];edges.push([x,y]);}
  if(degrees.some(d=>d<2||d>4))continue;
  const key=degrees.join("");
  if(!graphsByDegree.has(key))graphsByDegree.set(key,[]);
  graphsByDegree.get(key).push(edges);
}

function inspect(P,C,rightAnchors,internalEdges){
  const edgeSet=new Set(internalEdges.map(e=>edgeKey(e[0],e[1])));
  for(const a of P)for(const b of C)if(rightAnchors[b]===a)return {ok:false,reason:"active_anchor_collision"};
  const forcedHalfLine=new Map();
  let activeOffDiagonal=0,uniqueSimple=0,multipleSimple=0;
  for(const a of P)for(const b of C)if(a!==b){
    ++activeOffDiagonal;
    const deleted=new Set([a,rightAnchors[b]]);
    const vertices=[0,1,2,3,4,5].filter(v=>!deleted.has(v));
    const pms=perfectMatchings4(vertices,edgeSet);
    if(pms.length===0)return {ok:false,reason:"nonzero_minor_has_no_matching"};
    const forced=new Map();
    for(const q of P)if(q!==a)forced.set(q,q);
    for(const q of C)if(q!==b){
      const v=rightAnchors[q];
      if(forced.has(v)&&forced.get(v)!==q)return {ok:false,reason:"factor_vertex_colour_collision"};
      forced.set(v,q);
    }
    if(P.length+C.length>=5){
      if(pms.length===1){
        ++uniqueSimple;
        const pm=pms[0];
        for(const [x,y] of pm)for(const v of [x,y])if(forced.has(v)){
          const key=`${edgeKey(x,y)}:${v}`,colour=forced.get(v);
          if(forcedHalfLine.has(key)&&forcedHalfLine.get(key)!==colour)
            return {ok:false,reason:"forced_half_line_conflict"};
          forcedHalfLine.set(key,colour);
        }
      }else ++multipleSimple;
    }
  }
  return {ok:true,activeOffDiagonal,uniqueSimple,multipleSimple,
    forcedHalfLines:[...forcedHalfLine.entries()].map(([key,colour])=>({key,colour}))};
}

function triangleCount(edges){
  const set=new Set(edges.map(e=>edgeKey(e[0],e[1])));let count=0;
  for(let a=0;a<m;++a)for(let b=a+1;b<m;++b)for(let c=b+1;c<m;++c)
    if(set.has(edgeKey(a,b))&&set.has(edgeKey(a,c))&&set.has(edgeKey(b,c)))++count;
  return count;
}

const leftAnchors=[0,1,2];
const rightAssignments=orderedDistinct(3);
const started=Date.now(),records=[];
let cases=0,degreeGraphs=0,fourConnectedGraphs=0,survivors=0;
const rejectionReasons={};
for(const P of noncoordinateSupports)for(const C of noncoordinateSupports){
  const profile={left_support:P,right_support:C,cases:0,degree_graphs:0,four_connected:0,survivors:0,
    rejections:{},signature_counts:{},examples:[]};
  for(const rightAnchors of rightAssignments){
    ++cases;++profile.cases;
    const boundary=Array(m).fill(0);
    for(const v of leftAnchors)++boundary[v];
    for(const v of rightAnchors)++boundary[v];
    const need=boundary.map(d=>4-d),key=need.join("");
    const graphs=graphsByDegree.get(key)||[];
    for(const internalEdges of graphs){
      ++degreeGraphs;++profile.degree_graphs;
      if(!fourConnected(internalEdges,rightAnchors))continue;
      ++fourConnectedGraphs;++profile.four_connected;
      const result=inspect(P,C,rightAnchors,internalEdges);
      if(!result.ok){
        rejectionReasons[result.reason]=(rejectionReasons[result.reason]||0)+1;
        profile.rejections[result.reason]=(profile.rejections[result.reason]||0)+1;
        continue;
      }
      ++survivors;++profile.survivors;
      const signature=`triangles=${triangleCount(internalEdges)};unique=${result.uniqueSimple};multiple=${result.multipleSimple}`;
      profile.signature_counts[signature]=(profile.signature_counts[signature]||0)+1;
      if(profile.examples.length<2)profile.examples.push({right_anchors:rightAnchors,internal_edges:internalEdges,result});
    }
  }
  records.push(profile);
}

const summary={schema_version:1,series:"run-019",mode:"exact_paired_boundary",external_vertices:m,
  support_profiles:noncoordinateSupports.length**2,anchor_assignments_per_profile:rightAssignments.length,
  incidence_cases:cases,degree_graphs:degreeGraphs,four_connected_graphs:fourConnectedGraphs,
  survivors,rejection_reasons:rejectionReasons,elapsed_seconds:(Date.now()-started)/1000,profiles:records};
const out=path.join(__dirname,"local-runs","run-019-summary.json");
fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");
process.stdout.write(JSON.stringify({series:summary.series,incidence_cases:cases,degree_graphs:degreeGraphs,
  four_connected_graphs:fourConnectedGraphs,survivors,rejection_reasons:rejectionReasons,
  elapsed_seconds:summary.elapsed_seconds},null,2)+"\n");
