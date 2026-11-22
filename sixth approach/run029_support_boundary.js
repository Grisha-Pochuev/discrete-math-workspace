"use strict";

// Dependency-free audit of the final one-zero and two-zero support layers for
// the fixed neutral representative declared by spec run-029.

const fs=require("fs"),path=require("path");
const n=8,V=[0,1,2,3,4,5,6,7];
const missingGraph=[[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,7],[0,7]];
const factors=[[[0,2],[1,3],[4,6],[5,7]],[[0,3],[1,5],[2,6],[4,7]],[[0,4],[1,6],[2,5],[3,7]]];
const cycles=[[0,3,5,6],[1,2,4,7]];
const stabilizer=[[0,1,2,3,4,5,6,7],[3,2,1,0,7,6,5,4],[4,5,6,7,0,1,2,3],[7,6,5,4,3,2,1,0]];
function ek(a,b){return a<b?`${a},${b}`:`${b},${a}`;}
const miss=new Set(missingGraph.map(e=>ek(...e))),G=[];
for(let a=0;a<n;++a)for(let b=a+1;b<n;++b)if(!miss.has(ek(a,b)))G.push([a,b]);
const H=new Map();for(let q=0;q<3;++q)for(const e of factors[q])H.set(ek(...e),q);
const D=G.filter(e=>!H.has(ek(...e))),DI=new Map(D.map((e,i)=>[ek(...e),i]));
function pms(vertices,edges){if(!vertices.length)return [[]];const a=vertices[0],out=[];for(const b of vertices.slice(1)){if(!edges.has(ek(a,b)))continue;for(const tail of pms(vertices.filter(v=>v!==a&&v!==b),edges))out.push([[a,b],...tail]);}return out;}
const PM=pms(V,new Set(G.map(e=>ek(...e)))),cross=PM.filter(M=>M.some(e=>H.has(ek(...e))));
function decode(k,U=V){const c={};for(const v of U){c[v]=k%3;k=Math.floor(k/3);}return c;}
function mixed(c){const a=c[0];return V.some(v=>c[v]!==a);}
function compatibleAnchor(M,c){for(const e of M){const q=H.get(ek(...e));if(q!==undefined&&(c[e[0]]!==q||c[e[1]]!==q))return false;}return true;}
function variable(e,c){const item=e[0]<e[1]?e:[e[1],e[0]];return 9*DI.get(ek(...item))+3*c[item[0]]+c[item[1]];}
const rows=[];
for(let k=0;k<3**n;++k){const c=decode(k);if(!mixed(c))continue;const terms=[];for(const M of PM){if(!compatibleAnchor(M,c))continue;terms.push(M.filter(e=>!H.has(ek(...e))).map(e=>variable(e,c)));}rows.push(terms);}
const cycleStates=cycles.map(U=>Array.from({length:81},(_,k)=>decode(k,U)));
const cycleTerms=cycles.map((U,z)=>{const S=new Set(U),E=new Set(D.filter(e=>S.has(e[0])&&S.has(e[1])).map(e=>ek(...e))),M=pms(U,E);if(M.length!==2)throw new Error("not C4");return cycleStates[z].map(c=>M.map(m=>m.map(e=>variable(e,c))));});
const forbidden=Array.from({length:81},()=>Array(81).fill(false));let forbiddenPairs=0;
for(let a=0;a<81;++a)for(let b=0;b<81;++b){const c={...cycleStates[0][a],...cycleStates[1][b]};if(mixed(c)&&!cross.some(M=>compatibleAnchor(M,c))){forbidden[a][b]=true;++forbiddenPairs;}}
function termActive(term,removed){return term.every(v=>!removed.has(v));}
function singletonFree(removed){for(const terms of rows){let count=0;for(const term of terms)if(termActive(term,removed)&&++count>1)break;if(count===1)return false;}return true;}
function zeroClosed(removed){const forced=cycleTerms.map(rows=>rows.map(pair=>Number(termActive(pair[0],removed))^Number(termActive(pair[1],removed))));for(let z=0;z<2;++z){let hasEscape=false;for(let target=0;target<81&&!hasEscape;++target){let blocked=false;for(let source=0;source<81;++source)if(forced[z][source]){const bad=z===0?forbidden[source][target]:forbidden[target][source];if(bad){blocked=true;break;}}if(!blocked)hasEscape=true;}if(!hasEscape)return true;}return false;}
function masksFromRemoved(removed){const masks=Array(8).fill(511);for(const v of removed)masks[Math.floor(v/9)]&=~(1<<(v%9));return masks;}
function transformMasks(masks,p){const out=Array(8).fill(0);for(let i=0;i<D.length;++i){const [u,v]=D[i],tu=p[u],tv=p[v],j=DI.get(ek(tu,tv));for(let r=0;r<3;++r)for(let c=0;c<3;++c)if(masks[i]&(1<<(3*r+c))){const bit=tu<tv?3*r+c:3*c+r;out[j]|=1<<bit;}}return out;}
function canonical(masks){let best=null;for(const p of stabilizer){const x=transformMasks(masks,p),k=x.map(v=>String(v).padStart(3,"0")).join(",");if(best===null||k<best.key)best={key:k,masks:x};}return best;}
function keyOfVariable(v){const e=D[Math.floor(v/9)],x=v%9;return[e[0],e[1],Math.floor(x/3),x%3];}
function grid(mask){return[0,1,2].map(r=>[0,1,2].map(c=>mask&(1<<(3*r+c))?"1":"0").join(""));}
function auditLayer(zeroCount){const total=zeroCount===1?72:72*71/2,orbits=new Map();let singletonFreeCount=0,zeroClosedCount=0,survivors=0;function visit(values){const removed=new Set(values);if(!singletonFree(removed))return;++singletonFreeCount;if(zeroClosed(removed)){++zeroClosedCount;return;}++survivors;const can=canonical(masksFromRemoved(removed)),old=orbits.get(can.key);if(old)++old.multiplicity;else orbits.set(can.key,{masks:can.masks,multiplicity:1});}
if(zeroCount===1){for(let a=0;a<72;++a)visit([a]);}else{for(let a=0;a<72;++a)for(let b=a+1;b<72;++b)visit([a,b]);}
const records=[...orbits.values()].sort((x,y)=>x.masks.join(",").localeCompare(y.masks.join(","))).map((rec,index)=>{const removed=[];for(let e=0;e<8;++e)for(let bit=0;bit<9;++bit)if(!(rec.masks[e]&(1<<bit)))removed.push(keyOfVariable(9*e+bit));return{orbit:index,multiplicity:rec.multiplicity,masks:rec.masks,missing_entries:removed,grids:rec.masks.map(grid)};});return{support_size:72-zeroCount,zero_count:zeroCount,total_masks:total,singleton_free:singletonFreeCount,excluded_by_cycle_cut:zeroClosedCount,surviving_masks:survivors,orbit_count:records.length,orbits:records};}
const result={schema_version:1,series:"run-029",mode:"exact_support_boundary",residual_variables:72,perfect_matchings:PM.length,mixed_rows:rows.length,forbidden_product_pairs:forbiddenPairs,stabilizer_size:stabilizer.length,layers:[auditLayer(2),auditLayer(1)]};
const output=path.join(__dirname,"local-runs","run-029-dense-boundary.json");fs.writeFileSync(output,JSON.stringify(result,null,2)+"\n");
console.log(JSON.stringify({...result,layers:result.layers.map(({orbits,...rest})=>rest)},null,2));
