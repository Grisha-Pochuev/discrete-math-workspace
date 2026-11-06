"use strict";

const fs=require("fs"),path=require("path");
const n=6,pairs=[];
for(let a=0;a<n;++a)for(let b=a+1;b<n;++b)pairs.push([a,b]);
const P=new Set([0,1]),C=new Set([0,2]);

function edgeKey(a,b){return a<b?`${a},${b}`:`${b},${a}`;}
function orderedDistinct(k){const out=[];function rec(a){if(a.length===k){out.push(a.slice());return;}
  for(let v=0;v<n;++v)if(!a.includes(v)){a.push(v);rec(a);a.pop();}}rec([]);return out;}
function matchings4(v,E){const[a,b,c,d]=v;return[
  [[a,b],[c,d]],[[a,c],[b,d]],[[a,d],[b,c]]
].filter(M=>M.every(([x,y])=>E.has(edgeKey(x,y))));}
function hasPerfectMatching(vertices,E){if(vertices.length===0)return true;const a=vertices[0];
  for(let i=1;i<vertices.length;++i){const b=vertices[i];if(!E.has(edgeKey(a,b)))continue;
    const rest=vertices.slice(1,i).concat(vertices.slice(i+1));if(hasPerfectMatching(rest,E))return true;}
  return false;}
function fourConnected(edges,right){const R=6,T=7,N=8,adj=Array.from({length:N},()=>[]);
  function add(a,b){adj[a].push(b);adj[b].push(a);}for(const e of edges)add(...e);add(R,T);
  for(let q=0;q<3;++q){add(R,q);add(T,right[q]);}
  for(let mask=0;mask<(1<<N);++mask){let removed=0,start=-1,remain=0;
    for(let v=0;v<N;++v){removed+=(mask>>>v)&1;if(!((mask>>>v)&1)){++remain;if(start<0)start=v;}}
    if(removed>3)continue;const seen=new Set([start]),stack=[start];
    while(stack.length){const v=stack.pop();for(const w of adj[v])if(!((mask>>>w)&1)&&!seen.has(w)){seen.add(w);stack.push(w);}}
    if(seen.size!==remain)return false;
  }return true;}

function localClosure(edges,right,forced){const known=new Map();for(const[ek,tags]of forced)known.set(ek,new Map(tags));
  let changed=true;while(changed){changed=false;for(let v=0;v<n;++v){const incident=[];
    for(const e of edges)if(e.includes(v)){const ek=edgeKey(...e),w=e[0]===v?e[1]:e[0];incident.push({id:ek,w,tags:known.get(ek)||null});}
    for(let q=0;q<3;++q){if(v===q)incident.push({id:`R${q}`,w:6,tags:new Map([[v,q],[6,q]])});
      if(v===right[q])incident.push({id:`T${q}`,w:7,tags:new Map([[v,q],[7,q]])});}
    if(incident.length!==4)throw new Error("degree mismatch");
    const unknown=incident.filter(e=>!e.tags),columns=new Set(),root=[new Set(),new Set(),new Set()];
    for(const e of incident)if(e.tags){const q=e.tags.get(e.w),p=e.tags.get(v);columns.add(q);root[q].add(p);}
    if(columns.size+unknown.length<3)return false;
    if([0,1,2].some(i=>root[0].has(i)&&root[1].has(i)&&root[2].has(i)))return false;
    if(unknown.length===1&&columns.size===2){const q=[0,1,2].find(x=>!columns.has(x)),e=unknown[0];
      known.set(e.id,new Map([[v,q],[e.w,q]]));changed=true;}
  }}return true;}

function rankOneBranchFeasible(right,edges,E){const activeTag=new Map();
  for(const q of P)activeTag.set(q,String(q));for(const q of C)activeTag.set(right[q],String(q));
  const residual=[0,1,2,3,4,5].filter(v=>!activeTag.has(v));
  activeTag.set(residual[0],"H0");activeTag.set(residual[1],"H1");
  const base=[],rankOne=new Set();
  function forceMatching(M,tags){for(const e of M){const ek=edgeKey(...e);rankOne.add(ek);
    for(const v of e){const tag=tags.get(v);if(/^\d$/.test(tag))base.push(["a",`${ek}@${v}`,tag]);
      else base.push(["u",`${ek}@${v}`,`${tag}@${v}`]);}}}

  for(const a of P)for(const b of C)if(a!==b){const remain=[0,1,2,3,4,5].filter(v=>v!==a&&v!==right[b]),M=matchings4(remain,E);
    if(M.length===1)forceMatching(M[0],activeTag);}
  for(let q=0;q<3;++q)if(!(P.has(q)&&C.has(q))){const remain=[0,1,2,3,4,5].filter(v=>v!==q&&v!==right[q]),M=matchings4(remain,E);
    if(M.length===1)forceMatching(M[0],new Map(remain.map(v=>[v,String(q)])));}
  for(let a=0;a<3;++a)for(let b=0;b<3;++b)if(a!==b&&!(P.has(a)&&C.has(b))&&a!==right[b]){
    const remain=[0,1,2,3,4,5].filter(v=>v!==a&&v!==right[b]),M=matchings4(remain,E);if(M.length!==2)continue;
    for(const matching of M)for(const e of matching)rankOne.add(edgeKey(...e));
    for(const v of remain){const e0=M[0].find(e=>e.includes(v)),e1=M[1].find(e=>e.includes(v));
      base.push(["u",`${edgeKey(...e0)}@${v}`,`${edgeKey(...e1)}@${v}`]);}}

  function build(ops){const parent=new Map(),colours=new Map();
    function find(x){if(!parent.has(x))parent.set(x,x);if(parent.get(x)!==x)parent.set(x,find(parent.get(x)));return parent.get(x);}
    function union(a,b){a=find(a);b=find(b);if(a===b)return;parent.set(b,a);const ca=colours.get(a)||new Set(),cb=colours.get(b)||new Set();
      for(const q of cb)ca.add(q);colours.set(a,ca);}
    for(const op of base.concat(ops)){if(op[0]==="u")union(op[1],op[2]);else{const r=find(op[1]),s=colours.get(r)||new Set();s.add(op[2]);colours.set(r,s);}}
    for(const[x,s]of [...colours]){const r=find(x);if(r!==x){const t=colours.get(r)||new Set();for(const q of s)t.add(q);colours.set(r,t);}}
    if([...colours].some(([x,s])=>find(x)===x&&s.size>1))return null;return {find};}
  if(!build([]))return false;

  let states=[[]];
  for(let q=0;q<3;++q)if(!(P.has(q)&&C.has(q))){const remain=[0,1,2,3,4,5].filter(v=>v!==q&&v!==right[q]),M=matchings4(remain,E);
    if(M.length!==2||M.flat().some(e=>!rankOne.has(edgeKey(...e))))continue;const next=[];
    for(const state of states)for(const exception of remain){const additions=[];
      for(const v of remain)if(v!==exception){const e0=M[0].find(e=>e.includes(v)),e1=M[1].find(e=>e.includes(v));
        const n0=`${edgeKey(...e0)}@${v}`,n1=`${edgeKey(...e1)}@${v}`;
        additions.push(["u",n0,n1],["a",n0,String(q)]);}
      const ops=state.concat(additions),built=build(ops);if(!built)continue;
      const e0=M[0].find(e=>e.includes(exception)),e1=M[1].find(e=>e.includes(exception));
      const n0=`${edgeKey(...e0)}@${exception}`,n1=`${edgeKey(...e1)}@${exception}`;
      if(built.find(n0)===built.find(n1)){ops.push(["a",n0,String(q)]);if(!build(ops))continue;}next.push(ops);}
    states=next;if(states.length===0)return false;}
  return states.length>0;}

const vertexPermutations=orderedDistinct(6);
function canonical(record){let best=null;const operations=[
  {swapRoot:false,colour:[0,1,2]},{swapRoot:true,colour:[0,2,1]}
];
  for(const op of operations)for(const p of vertexPermutations){const items=[];
    for(const[a,b]of record.edges)items.push(`I${Math.min(p[a],p[b])},${Math.max(p[a],p[b])}`);items.push("X6,7");
    for(let q=0;q<3;++q){const colour=op.colour[q],r=op.swapRoot?7:6,t=op.swapRoot?6:7;
      items.push(`B${colour}:${Math.min(r,p[q])},${Math.max(r,p[q])}`);
      items.push(`B${colour}:${Math.min(t,p[record.right[q]])},${Math.max(t,p[record.right[q]])}`);}
    const s=items.sort().join("|");if(best===null||s<best)best=s;}
  return best;}

const graphsByDegree=new Map();
for(let mask=0;mask<(1<<pairs.length);++mask){const degree=Array(n).fill(0),edges=[];
  for(let e=0;e<pairs.length;++e)if((mask>>>e)&1){const[a,b]=pairs[e];++degree[a];++degree[b];edges.push([a,b]);}
  if(degree.some(d=>d<2||d>4))continue;const k=degree.join("");if(!graphsByDegree.has(k))graphsByDegree.set(k,[]);graphsByDegree.get(k).push(edges);}

const stages={degree_candidates:0,four_connected:0,active_minor_screen:0,zero_minor_screen:0,
  diagonal_minor_screen:0,pure_support_screen:0,local_screen:0};
const records=[];
for(const right of orderedDistinct(3)){
  let anchorsValid=true;for(const a of P)for(const b of C)if(right[b]===a)anchorsValid=false;
  for(let q=0;q<3;++q)if(!(P.has(q)&&C.has(q))&&right[q]===q)anchorsValid=false;
  if(!anchorsValid)continue;
  const boundary=Array(n).fill(0);for(let q=0;q<3;++q){++boundary[q];++boundary[right[q]];}
  const graphs=graphsByDegree.get(boundary.map(d=>4-d).join(""))||[];
  for(const edges of graphs){++stages.degree_candidates;if(!fourConnected(edges,right))continue;++stages.four_connected;
    const E=new Set(edges.map(e=>edgeKey(...e)));let valid=true;
    for(const a of P)for(const b of C)if(a!==b){const remain=[0,1,2,3,4,5].filter(v=>v!==a&&v!==right[b]);
      if(matchings4(remain,E).length===0)valid=false;}
    if(!valid)continue;++stages.active_minor_screen;
    for(let a=0;a<3&&valid;++a)for(let b=0;b<3&&valid;++b)if(a!==b&&!(P.has(a)&&C.has(b))&&a!==right[b]){
      const remain=[0,1,2,3,4,5].filter(v=>v!==a&&v!==right[b]);if(matchings4(remain,E).length===1)valid=false;}
    if(!valid)continue;++stages.zero_minor_screen;

    const forced=new Map();
    for(let q=0;q<3&&valid;++q)if(!(P.has(q)&&C.has(q))){const remain=[0,1,2,3,4,5].filter(v=>v!==q&&v!==right[q]),M=matchings4(remain,E);
      if(M.length===0){valid=false;break;}if(M.length!==1)continue;
      for(const[x,y]of M[0]){const ek=edgeKey(x,y),tags=new Map([[x,q],[y,q]]);if(forced.has(ek)){
        const old=forced.get(ek);if(old.get(x)!==q||old.get(y)!==q){valid=false;break;}}else forced.set(ek,tags);}}
    if(!valid)continue;++stages.diagonal_minor_screen;

    for(let q=0;q<3&&valid;++q){const allowed=new Set();for(const e of edges){const ek=edgeKey(...e);
        if(!forced.has(ek)||[...forced.get(ek).values()].every(x=>x===q))allowed.add(ek);}
      if(P.has(q)&&C.has(q))allowed.add(edgeKey(6,7));allowed.add(edgeKey(6,q));allowed.add(edgeKey(7,right[q]));
      if(!hasPerfectMatching([0,1,2,3,4,5,6,7],allowed))valid=false;}
    if(!valid)continue;++stages.pure_support_screen;if(!localClosure(edges,right,forced))continue;++stages.local_screen;

    const activeVertices=new Set([...P,...[...C].map(q=>right[q])]);
    const residual=[0,1,2,3,4,5].filter(v=>!activeVertices.has(v)),residualEdge=edgeKey(...residual);
    let highRank=true;for(const a of P)for(const b of C)if(a!==b){const remain=[0,1,2,3,4,5].filter(v=>v!==a&&v!==right[b]),M=matchings4(remain,E);
      if(M.length===1&&!M[0].some(e=>edgeKey(...e)===residualEdge))highRank=false;}
    records.push({right:right.slice(),edges:edges.map(e=>e.slice()),high_rank_branch:highRank,
      rank_one_branch:rankOneBranchFeasible(right,edges,E)});
  }
}

const orbitMap=new Map();for(const record of records){const k=canonical(record);if(!orbitMap.has(k))orbitMap.set(k,{count:0,representative:record});orbitMap.get(k).count++;}
const orbits=[...orbitMap.keys()].sort().map((k,id)=>({orbit_id:id,multiplicity:orbitMap.get(k).count,...orbitMap.get(k).representative}));
const highRankOrbits=orbits.filter(o=>o.high_rank_branch).map(o=>o.orbit_id);
const rankOneOrbits=orbits.filter(o=>o.rank_one_branch).map(o=>o.orbit_id);
const residueOrbits=[...new Set(highRankOrbits.concat(rankOneOrbits))].sort((a,b)=>a-b);
const orbitSizes=orbits.map(o=>o.multiplicity).sort((a,b)=>a-b);

const expectedStages={degree_candidates:1119,four_connected:969,active_minor_screen:753,zero_minor_screen:177,
  diagonal_minor_screen:147,pure_support_screen:135,local_screen:135};
if(JSON.stringify(stages)!==JSON.stringify(expectedStages)||orbits.length!==14||
  JSON.stringify(orbitSizes)!==JSON.stringify([3,6,6,6,6,12,12,12,12,12,12,12,12,12])||
  JSON.stringify(highRankOrbits)!==JSON.stringify([5,13])||JSON.stringify(rankOneOrbits)!==JSON.stringify([1,5])||
  JSON.stringify(residueOrbits)!==JSON.stringify([1,5,13]))throw new Error("intersection census mismatch");

const summary={schema_version:1,series:"run-022",mode:"exact_intersection_boundary",support_shape:[2,2],
  support_intersection:1,stages,orbit_count:orbits.length,orbit_sizes:orbitSizes,
  branch_orbits:{higher_rank:highRankOrbits,rank_one:rankOneOrbits,union:residueOrbits},
  residues:orbits.filter(o=>residueOrbits.includes(o.orbit_id))};
const out=path.join(__dirname,"local-runs","run-022-summary.json");fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");
process.stdout.write(JSON.stringify({series:summary.series,stages,orbit_count:orbits.length,branch_orbits:summary.branch_orbits},null,2)+"\n");
