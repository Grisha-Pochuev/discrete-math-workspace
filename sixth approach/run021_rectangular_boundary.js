"use strict";

const fs=require("fs"),path=require("path");
const n=6,pairs=[];
for(let a=0;a<n;++a)for(let b=a+1;b<n;++b)pairs.push([a,b]);
const hSupports=[[0],[1],[2],[0,1],[0,2],[1,2],[0,1,2]];

function edgeKey(a,b){return a<b?`${a},${b}`:`${b},${a}`;}
function orderedDistinct(k){const out=[];function rec(a){if(a.length===k){out.push(a.slice());return;}
  for(let v=0;v<n;++v)if(!a.includes(v)){a.push(v);rec(a);a.pop();}}rec([]);return out;}
function matchings4(v,E){if(v.length!==4)throw new Error("four vertices required");const[a,b,c,d]=v;
  return [[[a,b],[c,d]],[[a,c],[b,d]],[[a,d],[b,c]]]
    .filter(M=>M.every(([x,y])=>E.has(edgeKey(x,y))));}
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

function localClosure(edges,right,forced,hSupport){const known=new Map();
  for(const[ek,tags]of forced){const converted=new Map();
    for(const[v,t]of tags)converted.set(v,t==="H"?(hSupport.length===1?hSupport[0]:"H"):Number(t));
    known.set(ek,converted);}
  function supportOf(tag){return tag==="H"?hSupport:[tag];}
  let changed=true;
  while(changed){changed=false;
    for(let v=0;v<n;++v){const incident=[];
      for(const e of edges)if(e[0]===v||e[1]===v){const ek=edgeKey(...e),w=e[0]===v?e[1]:e[0];
        incident.push({id:ek,w,tags:known.get(ek)||null});}
      for(let q=0;q<3;++q){if(v===q)incident.push({id:`R${q}`,w:6,tags:new Map([[v,q],[6,q]])});
        if(v===right[q])incident.push({id:`T${q}`,w:7,tags:new Map([[v,q],[7,q]])});}
      if(incident.length!==4)throw new Error("degree mismatch");
      const unknown=incident.filter(e=>!e.tags),pureColumns=new Set(),rootByColumn=[new Set(),new Set(),new Set()];
      for(const e of incident)if(e.tags){const neighbour=supportOf(e.tags.get(e.w));
        if(neighbour.length===1){const q=neighbour[0];pureColumns.add(q);const root=supportOf(e.tags.get(v));
          if(root.length===1)rootByColumn[q].add(root[0]);}}
      if(pureColumns.size+unknown.length<3)return {ok:false,reason:"full_column_shortage"};
      if([0,1,2].some(i=>rootByColumn[0].has(i)&&rootByColumn[1].has(i)&&rootByColumn[2].has(i)))
        return {ok:false,reason:"constant_coordinate_map"};
      if(unknown.length===1&&incident.filter(e=>e.tags).every(e=>supportOf(e.tags.get(e.w)).length===1)&&pureColumns.size===2){
        const missing=[0,1,2].find(q=>!pureColumns.has(q)),e=unknown[0];
        known.set(e.id,new Map([[v,missing],[e.w,missing]]));changed=true;
      }
    }
  }
  return {ok:true};
}

const graphsByDegree=new Map();
for(let mask=0;mask<(1<<pairs.length);++mask){const degree=Array(n).fill(0),edges=[];
  for(let e=0;e<pairs.length;++e)if((mask>>>e)&1){const[a,b]=pairs[e];++degree[a];++degree[b];edges.push([a,b]);}
  if(degree.some(d=>d<2||d>4))continue;const k=degree.join("");
  if(!graphsByDegree.has(k))graphsByDegree.set(k,[]);graphsByDegree.get(k).push(edges);}

const stages={degree_candidates:0,four_connected:0,active_minor_screen:0,zero_minor_screen:0,diagonal_minor_screen:0,final_residue:0};
const localRejections={},residueCounts={},examples={};
for(const right of orderedDistinct(3)){
  if(right[0]<3||right[1]<3||right[2]===2)continue;
  const boundary=Array(n).fill(0);for(let q=0;q<3;++q){++boundary[q];++boundary[right[q]];}
  const graphs=graphsByDegree.get(boundary.map(d=>4-d).join(""))||[];
  const factorTag=new Map([[0,"0"],[1,"1"],[2,"2"],[right[0],"0"],[right[1],"1"]]);
  if(factorTag.size!==5)throw new Error("active factor collision");
  const z=[0,1,2,3,4,5].find(v=>!factorTag.has(v));factorTag.set(z,"H");
  for(const edges of graphs){++stages.degree_candidates;if(!fourConnected(edges,right))continue;++stages.four_connected;
    const E=new Set(edges.map(e=>edgeKey(...e))),forced=new Map();let valid=true,hMust2=false;
    for(let a=0;a<3&&valid;++a)for(let b=0;b<2&&valid;++b)if(a!==b){
      const deleted=new Set([a,right[b]]),remain=[0,1,2,3,4,5].filter(v=>!deleted.has(v));
      const M=matchings4(remain,E);if(M.length===0){valid=false;break;}if(M.length>1)continue;
      for(const[x,y]of M[0]){const ek=edgeKey(x,y);if(!forced.has(ek))forced.set(ek,new Map());const old=forced.get(ek);
        for(const v of[x,y]){const t=factorTag.get(v);if(old.has(v)&&old.get(v)!==t){valid=false;break;}old.set(v,t);}}
    }
    if(!valid)continue;++stages.active_minor_screen;
    for(const a of[0,1]){if(a===right[2])continue;
      const remain=[0,1,2,3,4,5].filter(v=>v!==a&&v!==right[2]);
      if(matchings4(remain,E).length===1){valid=false;break;}}
    if(!valid)continue;++stages.zero_minor_screen;
    const diagonalRemain=[0,1,2,3,4,5].filter(v=>v!==2&&v!==right[2]);
    const diagonalMatchings=matchings4(diagonalRemain,E);if(diagonalMatchings.length===0)continue;
    if(diagonalMatchings.length===1)for(const[x,y]of diagonalMatchings[0]){const ek=edgeKey(x,y);
      if(!forced.has(ek))forced.set(ek,new Map());const old=forced.get(ek);
      for(const v of[x,y]){if(old.has(v)){const t=old.get(v);if(t==="H")hMust2=true;else if(t!=="2"){valid=false;break;}}
        else old.set(v,"2");}}
    if(!valid)continue;++stages.diagonal_minor_screen;

    const possible=[];
    for(const hs of hSupports){if(hMust2&&(hs.length!==1||hs[0]!==2))continue;let pure=true;
      for(let colour=0;colour<3&&pure;++colour){const allowed=new Set();
        for(const e of edges){const ek=edgeKey(...e);if(!forced.has(ek)){allowed.add(ek);continue;}
          let ok=true;for(const v of e){const tag=forced.get(ek).get(v);
            if(tag==="H"?!hs.includes(colour):Number(tag)!==colour){ok=false;break;}}if(ok)allowed.add(ek);}
        if(colour<2)allowed.add(edgeKey(6,7));allowed.add(edgeKey(6,colour));allowed.add(edgeKey(7,right[colour]));
        pure=hasPerfectMatching([0,1,2,3,4,5,6,7],allowed);}
      if(!pure)continue;const closure=localClosure(edges,right,forced,hs);
      if(closure.ok)possible.push(hs.join(""));else localRejections[closure.reason]=(localRejections[closure.reason]||0)+1;}
    if(possible.length===0)continue;++stages.final_residue;
    const residue=right[2]>=3?"paired_bipartite":`inactive_anchor_hits_left_${right[2]}`;
    residueCounts[residue]=(residueCounts[residue]||0)+1;
    if(!examples[residue])examples[residue]={right_anchors:right,residual_vertex:z,internal_edges:edges,
      forced_edges:[...forced.entries()].map(([e,m])=>[e,[...m.entries()]]),possible_residual_supports:possible};
  }
}

if(stages.degree_candidates!==852||stages.four_connected!==756||stages.final_residue!==18||
  residueCounts.paired_bipartite!==6||residueCounts.inactive_anchor_hits_left_0!==6||
  residueCounts.inactive_anchor_hits_left_1!==6)throw new Error("rectangular census mismatch");

const summary={schema_version:1,series:"run-021",mode:"exact_rectangular_boundary",support_shape:[3,2],
  stages,local_rejections:localRejections,residue_counts:residueCounts,examples};
const out=path.join(__dirname,"local-runs","run-021-summary.json");fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");
process.stdout.write(JSON.stringify({series:summary.series,stages,residue_counts:residueCounts},null,2)+"\n");
