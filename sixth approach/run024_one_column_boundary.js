"use strict";

const fs=require("fs"),path=require("path");
const n=6,pairs=[];
for(let a=0;a<n;++a)for(let b=a+1;b<n;++b)pairs.push([a,b]);
const shapes=[
  {name:"three_by_one",P:[0,1,2],C:[0],colourPerms:[[0,1,2],[0,2,1]]},
  {name:"two_by_one",P:[0,1],C:[0],colourPerms:[[0,1,2]]}
];
function key(a,b){return a<b?`${a},${b}`:`${b},${a}`;}
function orderedDistinct(k){const out=[];function rec(a){if(a.length===k){out.push(a.slice());return;}
  for(let v=0;v<n;++v)if(!a.includes(v)){a.push(v);rec(a);a.pop();}}rec([]);return out;}
function matchings4(v,E){const[a,b,c,d]=v;return[
  [[a,b],[c,d]],[[a,c],[b,d]],[[a,d],[b,c]]
].filter(M=>M.every(([x,y])=>E.has(key(x,y))));}
function hasPM(vertices,E){if(vertices.length===0)return true;const a=vertices[0];
  for(let i=1;i<vertices.length;++i){const b=vertices[i];if(!E.has(key(a,b)))continue;
    const rest=vertices.slice(1,i).concat(vertices.slice(i+1));if(hasPM(rest,E))return true;}return false;}
function fourConnected(edges,right){const R=6,T=7,N=8,adj=Array.from({length:N},()=>[]);
  function add(a,b){adj[a].push(b);adj[b].push(a);}for(const e of edges)add(...e);add(R,T);
  for(let q=0;q<3;++q){add(R,q);add(T,right[q]);}
  for(let mask=0;mask<(1<<N);++mask){let removed=0,start=-1,remain=0;
    for(let v=0;v<N;++v){removed+=(mask>>>v)&1;if(!((mask>>>v)&1)){++remain;if(start<0)start=v;}}
    if(removed>3)continue;const seen=new Set([start]),stack=[start];while(stack.length){const v=stack.pop();
      for(const w of adj[v])if(!((mask>>>w)&1)&&!seen.has(w)){seen.add(w);stack.push(w);}}
    if(seen.size!==remain)return false;}return true;}
function localClosure(edges,right,forced){const known=new Map();for(const[ek,tags]of forced)known.set(ek,new Map(tags));
  let changed=true;while(changed){changed=false;for(let v=0;v<n;++v){const incident=[];
    for(const e of edges)if(e.includes(v)){const ek=key(...e),w=e[0]===v?e[1]:e[0];incident.push({id:ek,w,tags:known.get(ek)||null});}
    for(let q=0;q<3;++q){if(v===q)incident.push({id:`R${q}`,w:6,tags:new Map([[v,q],[6,q]])});
      if(v===right[q])incident.push({id:`T${q}`,w:7,tags:new Map([[v,q],[7,q]])});}
    if(incident.length!==4)throw new Error("degree mismatch");const unknown=incident.filter(e=>!e.tags),cols=new Set(),root=[new Set(),new Set(),new Set()];
    for(const e of incident)if(e.tags){const q=e.tags.get(e.w),p=e.tags.get(v);cols.add(q);root[q].add(p);}
    if(cols.size+unknown.length<3)return false;
    if([0,1,2].some(i=>root[0].has(i)&&root[1].has(i)&&root[2].has(i)))return false;
    if(unknown.length===1&&cols.size===2){const q=[0,1,2].find(x=>!cols.has(x)),e=unknown[0];known.set(e.id,new Map([[v,q],[e.w,q]]));changed=true;}
  }}return true;}

const vertexPermutations=orderedDistinct(6);
function canonical(shape,record){let best=null;for(const swapRoot of[false,true])for(const cp of shape.colourPerms)for(const p of vertexPermutations){const items=[];
    for(const[a,b]of record.edges)items.push(`I${Math.min(p[a],p[b])},${Math.max(p[a],p[b])}`);items.push("X6,7");
    for(let q=0;q<3;++q){const colour=cp[q],r=swapRoot?7:6,t=swapRoot?6:7;
      items.push(`B${colour}:${Math.min(r,p[q])},${Math.max(r,p[q])}`);
      items.push(`B${colour}:${Math.min(t,p[record.right[q]])},${Math.max(t,p[record.right[q]])}`);}
    const s=items.sort().join("|");if(best===null||s<best)best=s;}return best;}

const graphsByDegree=new Map();
for(let mask=0;mask<(1<<pairs.length);++mask){const degree=Array(n).fill(0),edges=[];
  for(let e=0;e<pairs.length;++e)if((mask>>>e)&1){const[a,b]=pairs[e];++degree[a];++degree[b];edges.push([a,b]);}
  if(degree.some(d=>d<2||d>4))continue;const k=degree.join("");if(!graphsByDegree.has(k))graphsByDegree.set(k,[]);graphsByDegree.get(k).push(edges);}

const results={};
for(const shape of shapes){const P=new Set(shape.P),C=new Set(shape.C),stages={degree_candidates:0,four_connected:0,active_minor_screen:0,
    zero_minor_screen:0,diagonal_minor_screen:0,pure_support_screen:0,local_screen:0},records=[];
  for(const right of orderedDistinct(3)){let validAnchors=true;for(const a of P)for(const b of C)if(right[b]===a)validAnchors=false;
    for(let q=0;q<3;++q)if(!(P.has(q)&&C.has(q))&&right[q]===q)validAnchors=false;if(!validAnchors)continue;
    const boundary=Array(n).fill(0);for(let q=0;q<3;++q){++boundary[q];++boundary[right[q]];}
    const graphs=graphsByDegree.get(boundary.map(d=>4-d).join(""))||[];
    for(const edges of graphs){++stages.degree_candidates;if(!fourConnected(edges,right))continue;++stages.four_connected;
      const E=new Set(edges.map(e=>key(...e)));let ok=true;
      for(const a of P)for(const b of C)if(a!==b){const remain=[0,1,2,3,4,5].filter(v=>v!==a&&v!==right[b]);if(matchings4(remain,E).length===0)ok=false;}
      if(!ok)continue;++stages.active_minor_screen;
      for(let a=0;a<3&&ok;++a)for(let b=0;b<3&&ok;++b)if(a!==b&&!(P.has(a)&&C.has(b))&&a!==right[b]){
        const remain=[0,1,2,3,4,5].filter(v=>v!==a&&v!==right[b]);if(matchings4(remain,E).length===1)ok=false;}
      if(!ok)continue;++stages.zero_minor_screen;const forced=new Map();
      for(let q=0;q<3&&ok;++q)if(!(P.has(q)&&C.has(q))){const remain=[0,1,2,3,4,5].filter(v=>v!==q&&v!==right[q]),M=matchings4(remain,E);
        if(M.length===0){ok=false;break;}if(M.length!==1)continue;for(const[x,y]of M[0]){const ek=key(x,y),tags=new Map([[x,q],[y,q]]);
          if(forced.has(ek)){const old=forced.get(ek);if(old.get(x)!==q||old.get(y)!==q){ok=false;break;}}else forced.set(ek,tags);}}
      if(!ok)continue;++stages.diagonal_minor_screen;
      for(let q=0;q<3&&ok;++q){const allowed=new Set();for(const e of edges){const ek=key(...e);
          if(!forced.has(ek)||[...forced.get(ek).values()].every(x=>x===q))allowed.add(ek);}
        if(P.has(q)&&C.has(q))allowed.add(key(6,7));allowed.add(key(6,q));allowed.add(key(7,right[q]));
        if(!hasPM([0,1,2,3,4,5,6,7],allowed))ok=false;}
      if(!ok)continue;++stages.pure_support_screen;if(!localClosure(edges,right,forced))continue;++stages.local_screen;
      const minors={};for(let a=0;a<3;++a)for(let b=0;b<3;++b){if(a===right[b]){minors[`D${a}${b}`]="collision";continue;}
        const remain=[0,1,2,3,4,5].filter(v=>v!==a&&v!==right[b]);minors[`D${a}${b}`]=matchings4(remain,E).map(M=>M.map(e=>key(...e)));}
      records.push({right:right.slice(),edges:edges.map(e=>e.slice()),minors});
    }
  }
  const orbitMap=new Map();for(const record of records){const k=canonical(shape,record);if(!orbitMap.has(k))orbitMap.set(k,{count:0,representative:record});orbitMap.get(k).count++;}
  const orbits=[...orbitMap.keys()].sort().map((k,id)=>({orbit_id:id,multiplicity:orbitMap.get(k).count,...orbitMap.get(k).representative}));
  results[shape.name]={support_rows:shape.P.length,support_columns:shape.C.length,stages,orbit_count:orbits.length,
    orbit_sizes:orbits.map(o=>o.multiplicity).sort((a,b)=>a-b),orbits};
}

function minorKey(m){return typeof m==="string"?m:m.map(M=>M.slice().sort().join("+")).sort().join("|");}
function sameMinor(o,a,b){return minorKey(o.minors[a])===minorKey(o.minors[b]);}
const a=results.three_by_one,b=results.two_by_one;
const expectedA={degree_candidates:1437,four_connected:1227,active_minor_screen:1041,zero_minor_screen:87,
  diagonal_minor_screen:63,pure_support_screen:63,local_screen:63};
const expectedB={degree_candidates:1812,four_connected:1530,active_minor_screen:1434,zero_minor_screen:72,
  diagonal_minor_screen:48,pure_support_screen:48,local_screen:48};
if(JSON.stringify(a.stages)!==JSON.stringify(expectedA)||a.orbit_count!==7||
  JSON.stringify(a.orbit_sizes)!==JSON.stringify([3,6,6,12,12,12,12])||
  !a.orbits.slice(0,4).every(o=>sameMinor(o,"D02","D11"))||!sameMinor(a.orbits[4],"D11","D22")||
  JSON.stringify(b.stages)!==JSON.stringify(expectedB)||b.orbit_count!==10||
  JSON.stringify(b.orbit_sizes)!==JSON.stringify([3,3,3,3,6,6,6,6,6,6])||
  !sameMinor(b.orbits[0],"D00","D21")||!sameMinor(b.orbits[1],"D02","D11")||!sameMinor(b.orbits[2],"D00","D22")||
  !b.orbits.slice(3,6).every(o=>sameMinor(o,"D01","D22"))||!sameMinor(b.orbits[6],"D10","D22")||!sameMinor(b.orbits[7],"D11","D22"))
  throw new Error("one-column census mismatch");

const families={
  three_by_one:{zero_pure_collision:{orbit_ids:[0,1,2,3],labelled_count:42},dual_pure_collision:{orbit_ids:[4],labelled_count:3},
    unique_minor_chain:{orbit_ids:[5],labelled_count:12},aligned_bipartite:{orbit_ids:[6],labelled_count:6}},
  two_by_one:{paired_minor_collisions:{orbit_ids:[0,1,2,3,4,5,6,7],labelled_count:36},
    mixed_bipartite:{orbit_ids:[8],labelled_count:6},aligned_bipartite:{orbit_ids:[9],labelled_count:6}}
};
const summary={schema_version:1,series:"run-024",mode:"exact_one_column_boundary",families,results};
const out=path.join(__dirname,"local-runs","run-024-summary.json");fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");
process.stdout.write(JSON.stringify({series:summary.series,three_by_one:{stages:a.stages,orbit_count:a.orbit_count,families:families.three_by_one},
  two_by_one:{stages:b.stages,orbit_count:b.orbit_count,families:families.two_by_one}},null,2)+"\n");
