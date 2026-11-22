"use strict";

const fs=require("fs"),path=require("path"),n=8,V=[0,1,2,3,4,5,6,7],R=[[0,1],[2,3],[4,5],[6,7]];
function edge(a,b){return a<b?[a,b]:[b,a];}
function ek(a,b){return a<b?`${a},${b}`:`${b},${a}`;}
function mk(M){return M.map(e=>e.join("")).join("|");}
function tk(T){return T.map(mk).join(";");}
function pms(v){if(!v.length)return[[]];const a=v[0],out=[];for(let i=1;i<v.length;++i){const b=v[i],w=v.slice(1,i).concat(v.slice(i+1));
  for(const m of pms(w))out.push([edge(a,b),...m].sort((x,y)=>x[0]-y[0]||x[1]-y[1]));}return out;}
function disjoint(A,B){const S=new Set(A.map(e=>ek(...e)));return B.every(e=>!S.has(ek(...e)));}
function connected(E){const A=Array.from({length:n},()=>[]);for(const[a,b]of E){A[a].push(b);A[b].push(a);}const seen=new Set([0]),st=[0];
  while(st.length){const a=st.pop();for(const b of A[a])if(!seen.has(b)){seen.add(b);st.push(b);}}return seen.size===n;}
function perms(a){if(!a.length)return[[]];const out=[];for(let i=0;i<a.length;++i)for(const t of perms(a.slice(0,i).concat(a.slice(i+1))))out.push([a[i],...t]);return out;}
function vertexMaps(){const out=[];for(const p of perms([0,1,2,3]))for(let f=0;f<16;++f){const m=Array(n);for(let i=0;i<4;++i)for(let s=0;s<2;++s)
  m[2*i+s]=2*p[i]+(s^((f>>>i)&1));out.push(m);}return out;}
function transform(T,vm,cp){const U=Array(3);for(let q=0;q<3;++q)U[cp[q]]=T[q].map(([a,b])=>edge(vm[a],vm[b])).sort((x,y)=>x[0]-y[0]||x[1]-y[1]);return U;}
function factorOrbits(){const all=pms(V),allowed=all.filter(m=>disjoint(m,R)),triples=new Map();for(const a of allowed)for(const b of allowed){if(!disjoint(a,b))continue;
  for(const c of allowed){if(!disjoint(a,c)||!disjoint(b,c)||!connected([...R,...a,...b,...c]))continue;const T=[a,b,c];triples.set(tk(T),T);}}
  const labelled=triples.size,vm=vertexMaps(),cp=perms([0,1,2]),reps=[];while(triples.size){const k=[...triples.keys()].sort()[0],T=triples.get(k);reps.push(T);
    for(const v of vm)for(const p of cp)triples.delete(tk(transform(T,v,p)));}return{labelled,reps};}
function graphPms(vertices,local){const out=[];function rec(rem,M){if(!rem.size){out.push(M.slice());return;}const a=Math.min(...rem);for(const[k,{e:[u,v]}]of local){
    if(u!==a&&v!==a)continue;const b=u===a?v:u;if(!rem.has(b))continue;const next=new Set(rem);next.delete(a);next.delete(b);M.push(k);rec(next,M);M.pop();}}
  rec(new Set(vertices),[]);return out;}
function ckey(c){let k=0,p=1;for(const q of c){k+=q*p;p*=3;}return k;}
function decode(k){const c=[];for(let i=0;i<n;++i){c.push(k%3);k=Math.floor(k/3);}return c;}
function induced(M,local,roots=null,pair=null){const c=Array(n).fill(-1);if(roots){c[roots[0]]=pair[0];c[roots[1]]=pair[1];}
  for(const k of M){const{e:[a,b],c:[x,y]}=local.get(k);if((c[a]>=0&&c[a]!==x)||(c[b]>=0&&c[b]!==y))return null;c[a]=x;c[b]=y;}return c;}
function audit(T,kind,index,d){const distinguished=kind==="R"?R[index]:T[0][index],[r,t]=distinguished,local=new Map();for(let q=0;q<3;++q)for(let i=0;i<4;++i){
  if(kind==="M0"&&q===0&&i===index)continue;const[a,b]=T[q][i];local.set(ek(a,b),{e:[a,b],c:[q,q]});}for(let i=0;i<4;++i){
  if(kind==="R"&&i===index)continue;const[a,b]=R[i];local.set(ek(a,b),{e:[a,b],c:[d[a],d[b]]});}
  const A=graphPms(V,local),B=graphPms(V.filter(v=>v!==r&&v!==t),local),counts=new Map();function bump(c,f){if(!c||c.some(q=>q<0))return;
    const k=ckey(c),z=counts.get(k)||[0,0];++z[f];counts.set(k,z);}for(const M of A)bump(induced(M,local),0);for(const M of B)for(let a=0;a<3;++a)for(let b=0;b<3;++b)
    bump(induced(M,local,[r,t],[a,b]),1);let witnesses=0;for(const[k,[a,b]]of counts){const c=decode(k);if(!c.every(q=>q===c[0])&&a===1&&b===0)++witnesses;}return witnesses;}
function fresh(kind){return{kind,configurations:0,minimum_witnesses:null,histogram:new Map(),failures:[]};}
function add(S,w,record){++S.configurations;S.minimum_witnesses=S.minimum_witnesses===null?w:Math.min(S.minimum_witnesses,w);S.histogram.set(w,(S.histogram.get(w)||0)+1);
  if(w===0&&S.failures.length<10)S.failures.push(record);}
function finish(S){return{kind:S.kind,configurations:S.configurations,minimum_witnesses:S.minimum_witnesses,witness_count_histogram:Object.fromEntries([...S.histogram].sort((a,b)=>a[0]-b[0])),failures:S.failures};}

const started=Date.now(),{labelled,reps}=factorOrbits(),sr=fresh("remainder_edge"),sc=fresh("colour_zero_edge");for(let orbit=0;orbit<reps.length;++orbit){const T=reps[orbit];
  for(let index=0;index<4;++index){const roots=R[index],free=V.filter(v=>!roots.includes(v));for(let a=0;a<3**6;++a){let x=a;const d=Array(n).fill(-1);for(const v of free){d[v]=x%3;x=Math.floor(x/3);}
      add(sr,audit(T,"R",index,d),{orbit,index,d});}for(let a=0;a<3**8;++a){let x=a;const d=Array(n);for(const v of V){d[v]=x%3;x=Math.floor(x/3);}
      add(sc,audit(T,"M0",index,d),{orbit,index,d});}}}
const summary={schema_version:1,series:"run-025",mode:"exact_one_edge_deletion",n,connected_labelled_factor_triples:labelled,factor_triple_orbits:reps.length,
  remainder_edge:finish(sr),colour_zero_edge:finish(sc),elapsed_seconds:(Date.now()-started)/1000};
const expectedR={2:2,3:57,4:228,5:2250,6:7906,7:28837,8:27582,9:36834,10:610,11:3622,12:84,13:688,14:1544,15:3480};
const expectedC={2:54,3:22,4:2242,5:8877,6:38714,7:58892,8:242284,9:228441,10:368330,11:332,12:25208,13:1936,14:10080,15:6840,16:31264};
if(labelled!==27456||reps.length!==39||sr.configurations!==113724||sc.configurations!==1023516||sr.minimum_witnesses!==2||sc.minimum_witnesses!==2||
  sr.failures.length||sc.failures.length||JSON.stringify(Object.fromEntries(sr.histogram))!==JSON.stringify(expectedR)||JSON.stringify(Object.fromEntries(sc.histogram))!==JSON.stringify(expectedC))
  throw new Error("one-edge deletion census mismatch");
const out=path.join(__dirname,"local-runs","run-025-summary.json");fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");
process.stdout.write(JSON.stringify({series:summary.series,mode:summary.mode,factor_triple_orbits:summary.factor_triple_orbits,remainder_edge:summary.remainder_edge,
  colour_zero_edge:summary.colour_zero_edge,elapsed_seconds:summary.elapsed_seconds},null,2)+"\n");
