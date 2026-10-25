"use strict";

const fs=require("fs"),path=require("path"),core=require("./run016_local_structures.js");
const started=Date.now();let triples=0,simple=0,connectedCount=0,minimum=Infinity,firstZero=null;
for(const a of core.completions[0])for(const b of core.completions[1])for(const c of core.completions[2]){++triples;
 const m0=[...core.fixed[0],...a],m1=[...core.fixed[1],...b],m2=[...core.fixed[2],...c];
 if(!core.disjoint(m0,m1)||!core.disjoint(m0,m2)||!core.disjoint(m1,m2))continue;++simple;
 const factors=[m0,m1,m2];if(!core.connected(factors,core.R))continue;++connectedCount;
 const result=core.graphPMs(factors,core.R);minimum=Math.min(minimum,result.singleton);
 if(result.singleton===0&&!firstZero)firstZero={factors,remainder:core.R,
  duplicated:[0,0,0,0,1,1,1,1,2,2,2,2],result};}
const summary={schema_version:1,series:"run-017",elapsed_seconds:(Date.now()-started)/1000,
 completion_counts:core.completions.map(x=>x.length),completion_triples:triples,simple_systems:simple,
 connected_systems:connectedCount,minimum_mixed_singletons:Number.isFinite(minimum)?minimum:null,
 zero_record_found:firstZero!==null,first_zero_record:firstZero};
const out=path.join(__dirname,"local-runs","run-017-summary.json");fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");process.stdout.write(JSON.stringify(summary,null,2)+"\n");
