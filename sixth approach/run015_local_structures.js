"use strict";

const fs=require("fs"),path=require("path"),core=require("./run012_local_structures.js");
const n=core.n,all=[0,1,2],dense=[[0,1],[0,2],[1,2],[0,1,2]];

function makePacking(graph){
  const unused=new Set(all.concat([3,4,5,6,7])), components=[],data=new Map(), required=new Map();
  let guard=0;
  while(unused.size>=2&&guard++<20){
    const vertices=[...unused];core.shuffle(vertices);const c=vertices[0], options=[];
    for(const e of graph.adj[c]){const [u,v]=graph.edges[e],w=u^v^c;if(unused.has(w))options.push([e,w]);}
    if(!options.length){unused.delete(c);continue;}
    core.shuffle(options);
    const wantStar=unused.size>=3&&options.length>=2&&core.randint(3)===0;
    if(wantStar){
      const i=core.randint(3),off=all.filter(q=>q!==i),O=core.randint(3)===2?off:[off[core.randint(2)]];
      const flags=[[1,0],[0,1],[1,1]][core.randint(3)], picked=options.slice(0,2), leaves=[];
      required.set(c,new Set(all.filter(q=>q!==i)));unused.delete(c);
      for(let z=0;z<2;++z){const [e,l]=picked[z],S=O.slice();if(flags[z])S.push(i);
        data.set(e,{centre:c,leaf:l,centreSupport:S,remoteColour:i});leaves.push(l);
        required.set(l,new Set(all));unused.delete(l);}
      components.push({type:"star2",centre:c,leaves,missing:i,off:O,flags,edges:picked.map(x=>x[0])});
    }else{
      const [e,l]=options[0],type=core.randint(2)===0?"star1":"double";unused.delete(c);unused.delete(l);
      required.set(c,new Set(all));required.set(l,new Set(all));
      if(type==="star1"){
        const i=core.randint(3),S=dense[core.randint(dense.length)];
        data.set(e,{centre:c,leaf:l,centreSupport:S,remoteColour:i});
        components.push({type,edge:e,centre:c,leaf:l,remote:i,support:S});
      }else{
        const A=dense[core.randint(dense.length)],B=dense[core.randint(dense.length)];
        data.set(e,{centre:c,leaf:l,centreSupport:A,leafSupport:B});
        components.push({type,edge:e,endpoints:[c,l],A,B});
      }
    }
    if(core.randint(3)===0)break;
  }
  return {components,data,required};
}

function colourings(graph,data,required,limit){
  const label=Array(graph.edges.length).fill(-2),edges=[];
  for(const e of data.keys())label[e]=-1;
  for(let e=0;e<label.length;++e)if(label[e]===-2)edges.push(e);
  const counts=Array.from({length:n},()=>[0,0,0]),rem=Array(n).fill(0),out=[];
  for(const e of edges)for(const v of graph.edges[e])++rem[v];
  function possible(v){const c=counts[v],r=rem[v],req=required.get(v);
    if(req){for(let q=0;q<3;++q){const need=req.has(q)?1:0;if(c[q]>need||c[q]+r<need)return false;}return true;}
    let absent=0;for(let q=0;q<3;++q)if(c[q]===0)++absent;return absent<=r;
  }
  function rec(pos){if(out.length>=limit)return;if(pos===edges.length){for(let v=0;v<n;++v)if(!possible(v))return;out.push(label.slice());return;}
    const e=edges[pos],[u,v]=graph.edges[e];--rem[u];--rem[v];
    for(let q=0;q<3;++q){label[e]=q;++counts[u][q];++counts[v][q];if(possible(u)&&possible(v))rec(pos+1);--counts[u][q];--counts[v][q];}
    label[e]=-2;++rem[u];++rem[v];}
  rec(0);return out;
}

const started=Date.now();let graphs=0,packings=0,labelings=0,cases=0,minimum=Infinity,firstZero=null;
const typeCounts={star1:0,star2:0,double:0};
for(let trial=0;trial<10000&&Date.now()-started<820000;++trial){
  const graph=core.complement4(core.randomCubic());if(!core.connected(graph))continue;++graphs;
  const packing=makePacking(graph);if(!packing.components.length)continue;++packings;
  for(const c of packing.components)++typeCounts[c.type];
  const labs=colourings(graph,packing.data,packing.required,32);labelings+=labs.length;
  if(!labs.length)continue;const pms=core.perfectMatchings(graph);
  for(const labels of labs){const result=core.countInduced(graph,pms,labels,packing.data);++cases;minimum=Math.min(minimum,result.mixedSingletons);
    if(result.mixedSingletons===0){firstZero={edges:graph.edges,components:packing.components,labels,perfectMatchings:pms.length,result};break;}}
  if(firstZero)break;
}
const summary={schema_version:1,series:"run-015",seed:2026080901,elapsed_seconds:(Date.now()-started)/1000,
 connected_graph_trials:graphs,packings,type_counts:typeCounts,local_colourings:labelings,support_cases:cases,
 minimum_mixed_singletons:Number.isFinite(minimum)?minimum:null,zero_record_found:firstZero!==null,first_zero_record:firstZero};
const out=path.join(__dirname,"local-runs","run-015-summary.json");fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");process.stdout.write(JSON.stringify(summary,null,2)+"\n");
