"use strict";

const fs=require("fs"),path=require("path");
const n=6,pairs=[],P=new Set([0,1]),C=new Set([0,1]);
for(let a=0;a<n;++a)for(let b=a+1;b<n;++b)pairs.push([a,b]);

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

const permutations=orderedDistinct(6);
function canonical(record){let best=null;const operations=[
  {swapRoot:false,colour:[0,1,2]},{swapRoot:false,colour:[1,0,2]},
  {swapRoot:true,colour:[0,1,2]},{swapRoot:true,colour:[1,0,2]}
];
  for(const op of operations)for(const p of permutations){const items=[];
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
    records.push({right:right.slice(),edges:edges.map(e=>e.slice())});
  }
}

const orbitMap=new Map();for(const record of records){const k=canonical(record);if(!orbitMap.has(k))orbitMap.set(k,{count:0,representative:record});orbitMap.get(k).count++;}
const orbits=[...orbitMap.keys()].sort().map((k,id)=>({orbit_id:id,multiplicity:orbitMap.get(k).count,...orbitMap.get(k).representative}));
const familyByOrbit=["paired_diagonal_collision","paired_diagonal_collision","paired_diagonal_collision",
  "cross_diagonal_collision","cross_diagonal_collision","cross_diagonal_collision","single_collision_chain",
  "mixed_bipartite_rank","aligned_bipartite","mixed_bipartite_zero_grid"];
const families={};for(const orbit of orbits){const name=familyByOrbit[orbit.orbit_id];if(!families[name])families[name]={labelled_count:0,orbit_ids:[]};
  families[name].labelled_count+=orbit.multiplicity;families[name].orbit_ids.push(orbit.orbit_id);}
const orbitSizes=orbits.map(o=>o.multiplicity).sort((a,b)=>a-b);

const expectedStages={degree_candidates:1488,four_connected:1272,active_minor_screen:1140,zero_minor_screen:132,
  diagonal_minor_screen:132,pure_support_screen:132,local_screen:132};
const expectedFamilyCounts={paired_diagonal_collision:42,cross_diagonal_collision:42,single_collision_chain:24,
  mixed_bipartite_rank:6,aligned_bipartite:6,mixed_bipartite_zero_grid:12};
if(JSON.stringify(stages)!==JSON.stringify(expectedStages)||orbits.length!==10||
  JSON.stringify(orbitSizes)!==JSON.stringify([6,6,6,6,12,12,12,24,24,24])||
  Object.entries(expectedFamilyCounts).some(([k,v])=>families[k].labelled_count!==v))throw new Error("equal boundary census mismatch");

const summary={schema_version:1,series:"run-023",mode:"exact_equal_boundary",support_shape:[2,2],
  support_intersection:2,stages,orbit_count:orbits.length,orbit_sizes:orbitSizes,families,orbits};
const out=path.join(__dirname,"local-runs","run-023-summary.json");fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");
process.stdout.write(JSON.stringify({series:summary.series,stages,orbit_count:orbits.length,families},null,2)+"\n");
