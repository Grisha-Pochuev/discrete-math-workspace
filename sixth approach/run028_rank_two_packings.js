"use strict";

const fs=require("fs"),path=require("path");
const jobs=[
  ["two_anchor_extra","run028a_two_anchor_extra.js"],
  ["two_star_pairs","run028b_two_star_pairs.js"],
  ["star_remainder","run028c_star_remainder.js"],
  ["two_asymmetric_extra","run028d_two_asymmetric_extra.js"]
];
const started=Date.now(),subruns={};
for(const[name,file]of jobs){
  subruns[name]=require(path.join(__dirname,file));
}
const a=subruns.two_anchor_extra.stats,b=subruns.two_star_pairs.stats,c=subruns.star_remainder.stats.by_size,d=subruns.two_asymmetric_extra.stats;
if(a.base_labelings!==17064||a.total_support_masks!==8156592||a.surviving_support_masks!==0||b.ordered_structures!==306819||b.support_configurations!==3051243||b.singleton_free!==0||c[1].support_tuples!==118786824||c[1].survivors!==0||c[2].support_tuples!==2673262800||c[2].survivors!==0||d.ordered_structures!==3987||d.support_configurations!==1905786||d.survivors!==0)throw new Error("rank-two packing census mismatch");
const summary={schema_version:1,series:"run-028",mode:"exact_rank_two_packings",n:8,subruns,elapsed_seconds:(Date.now()-started)/1000};
const out=path.join(__dirname,"local-runs","run-028-summary.json");fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(summary,null,2)+"\n");process.stdout.write(JSON.stringify(summary,null,2)+"\n");
