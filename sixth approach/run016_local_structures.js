"use strict";

const fs=require("fs"),path=require("path");
const n=12,edge=(u,v)=>u<v?[u,v]:[v,u],code=([u,v])=>16*u+v;
let state=2026080901>>>0;function rng(){state^=state<<13;state^=state>>>17;state^=state<<5;return state>>>0;}

function generate(vertices,forbidden,chosen,out){
  if(!vertices.length){out.push(chosen.slice());return;}const u=vertices[0];
  for(let i=1;i<vertices.length;++i){const e=edge(u,vertices[i]);if(forbidden.has(code(e)))continue;
    const rest=vertices.slice(1);rest.splice(i-1,1);chosen.push(e);generate(rest,forbidden,chosen,out);chosen.pop();}
}
function disjoint(a,b){const seen=new Set(a.map(code));return b.every(e=>!seen.has(code(e)));}
function connected(factors,R){const adj=Array.from({length:n},()=>[]);for(const M of [...factors,R])for(const [u,v]of M){adj[u].push(v);adj[v].push(u);}
 const seen=new Set([0]),stack=[0];while(stack.length){const u=stack.pop();for(const v of adj[u])if(!seen.has(v)){seen.add(v);stack.push(v);}}return seen.size===n;}
function graphPMs(factors,R){const adj=Array.from({length:n},()=>[]),pair=new Map();
 for(let q=0;q<3;++q)for(const e of factors[q]){const k=code(e);pair.set(k,[q,q]);adj[e[0]].push(e);adj[e[1]].push(e);}
 for(const e of R){const k=code(e),d=[0,0,0,0,1,1,1,1,2,2,2,2];pair.set(k,[d[e[0]],d[e[1]]]);adj[e[0]].push(e);adj[e[1]].push(e);}
 const counts=new Uint16Array(3**n),touched=[];
 function rec(mask,colourCode){if(mask===0){if(counts[colourCode]++===0)touched.push(colourCode);return;}
  let u=0;while((mask&(1<<u))===0)++u;for(const e of adj[u]){const v=e[0]^e[1]^u;if((mask&(1<<v))===0)continue;
   const p=pair.get(code(e));rec(mask&~(1<<u)&~(1<<v),colourCode+p[0]*3**u+p[1]*3**v);}}
 rec((1<<n)-1,0);let singleton=0;for(const z of touched)if(counts[z]===1){let x=z,first=x%3,mixed=false;
  for(let v=1;v<n;++v){x=Math.floor(x/3);if(x%3!==first){mixed=true;break;}}if(mixed)++singleton;}
 return {singleton,perfectMatchings:touched.reduce((s,z)=>s+counts[z],0),inducedColourings:touched.length};}

const R=[[0,1],[2,3],[4,5],[6,7],[8,9],[10,11]];
const fixed=[[[0,2],[1,3]],[[4,6],[5,7]],[[8,10],[9,11]]];
const free=[[4,5,6,7,8,9,10,11],[0,1,2,3,8,9,10,11],[0,1,2,3,4,5,6,7]];
const forbidden=new Set([...R,...fixed.flat()].map(code));
const completions=free.map(vertices=>{const out=[];generate(vertices,forbidden,[],out);return out;});
if(require.main===module){
const started=Date.now();let sampled=0,simple=0,connectedCount=0,minimum=Infinity,firstZero=null;
while(sampled<1000000&&Date.now()-started<820000){++sampled;
 const a=completions[0][rng()%completions[0].length],b=completions[1][rng()%completions[1].length],c=completions[2][rng()%completions[2].length];
 const m0=[...fixed[0],...a],m1=[...fixed[1],...b],m2=[...fixed[2],...c];
 if(!disjoint(m0,m1)||!disjoint(m0,m2)||!disjoint(m1,m2))continue;++simple;const factors=[m0,m1,m2];
 if(!connected(factors,R))continue;++connectedCount;const result=graphPMs(factors,R);minimum=Math.min(minimum,result.singleton);
 if(result.singleton===0){firstZero={factors,remainder:R,duplicated:[0,0,0,0,1,1,1,1,2,2,2,2],result};break;}}
const summary={schema_version:1,series:"run-016",seed:2026080901,elapsed_seconds:(Date.now()-started)/1000,
 samples:sampled,simple_systems:simple,connected_systems:connectedCount,completion_counts:completions.map(x=>x.length),
 minimum_mixed_singletons:Number.isFinite(minimum)?minimum:null,zero_record_found:firstZero!==null,first_zero_record:firstZero};
const out=path.join(__dirname,"local-runs","run-016-summary.json");fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");process.stdout.write(JSON.stringify(summary,null,2)+"\n");
}

module.exports={R,fixed,completions,disjoint,connected,graphPMs};
