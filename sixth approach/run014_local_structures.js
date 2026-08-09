"use strict";

const fs = require("fs"), path = require("path");
const core = require("./run012_local_structures.js");
const n = core.n;

function colourings(graph, special, endpoints, limit) {
  const label = Array(graph.edges.length).fill(-2); label[special] = -1;
  const edges = []; for (let e=0;e<label.length;++e) if (e!==special) edges.push(e);
  const counts = Array.from({length:n},()=>[0,0,0]), rem=Array(n).fill(0), out=[];
  for (const e of edges) for (const v of graph.edges[e]) ++rem[v];
  function possible(v) {
    const c=counts[v], r=rem[v];
    if (endpoints.includes(v)) {
      for (let q=0;q<3;++q) if(c[q]>1||c[q]+r<1)return false;
      return true;
    }
    let absent=0; for(let q=0;q<3;++q)if(c[q]===0)++absent;
    return absent<=r;
  }
  function rec(pos) {
    if(out.length>=limit)return;
    if(pos===edges.length){for(let v=0;v<n;++v)if(!possible(v))return;out.push(label.slice());return;}
    const e=edges[pos],[u,v]=graph.edges[e];--rem[u];--rem[v];
    for(let q=0;q<3;++q){label[e]=q;++counts[u][q];++counts[v][q];
      if(possible(u)&&possible(v))rec(pos+1);--counts[u][q];--counts[v][q];}
    label[e]=-2;++rem[u];++rem[v];
  }
  rec(0);return out;
}

const supports=[[0,1],[0,2],[1,2],[0,1,2]];
const started=Date.now();let graphs=0,labelings=0,cases=0,minimum=Infinity,firstZero=null;
for(let trial=0;trial<5000&&Date.now()-started<820000;++trial){
  const graph=core.complement4(core.randomCubic());if(!core.connected(graph))continue;++graphs;
  const pms=core.perfectMatchings(graph),special=core.randint(graph.edges.length);
  const endpoints=graph.edges[special], labs=colourings(graph,special,endpoints,64);labelings+=labs.length;
  for(const labels of labs)for(const A of supports)for(const B of supports){
    const data=new Map([[special,{centre:endpoints[0],leaf:endpoints[1],centreSupport:A,leafSupport:B}]]);
    const result=core.countInduced(graph,pms,labels,data);++cases;minimum=Math.min(minimum,result.mixedSingletons);
    if(result.mixedSingletons===0){firstZero={edges:graph.edges,special,endpoints,A,B,labels,
      perfectMatchings:pms.length,result};break;}
  }
  if(firstZero)break;
}
const summary={schema_version:1,series:"run-014",seed:2026080901,
 elapsed_seconds:(Date.now()-started)/1000,connected_graph_trials:graphs,
 local_colourings:labelings,support_cases:cases,minimum_mixed_singletons:Number.isFinite(minimum)?minimum:null,
 zero_record_found:firstZero!==null,first_zero_record:firstZero};
const out=path.join(__dirname,"local-runs","run-014-summary.json");fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");process.stdout.write(JSON.stringify(summary,null,2)+"\n");
