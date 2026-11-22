"""Freeze exact control and10 donor replacement bundles; no solver/network."""
import json,hashlib,sys,shutil,time
from pathlib import Path
import numpy as np
import materialize as M
R=Path(__file__).resolve().parent

def freeze(job,wid):
 t0=time.monotonic();R=M.OUTROOT;report,products,context=M.screen(job,wid);m,inst,h,pop,vals,base,ref=context
 p=M.C/'unpacked'/str(job)/'o/run'/f'{wid:02d}';cp=p/'2/ck.txt'
 raw=cp.read_bytes().splitlines(keepends=True);M.need(len(raw)==201,'raw line shape')
 for i,v in enumerate(vals):M.need(int(raw[1+2*i].split()[1])==v,'source stored exact cost')
 m=dict(m);m['source_run']='43959844209';m['source_slot']=f'job{job}/worker{wid}/2';m['ordered_population_sha256']=hashlib.sha256(np.asarray(pop,dtype='<i8').tobytes()).hexdigest();m['checkpoint_format']='text'
 dest=R/'bundles';dest.mkdir(exist_ok=True)
 sourceproof={'source_context_sha256':report['parent_context_sha256'],'source_checkpoint_sha256':report['parent_checkpoint_sha256'],'native_rng_resume':False,'generation_and_children':'preserved as source history; initialization mutations are not solver children'}
 out=[]
 for mode in ('control','mild','strong'):
  folder=dest/f'j{job}_w{wid}_{mode}';M.need(not folder.exists(),'fresh bundle');folder.mkdir()
  for name in ('instance','vertices','base'):
   rec=m['files'][name];shutil.copyfile(p/'inputs'/rec['file'],folder/rec['file'])
  newpop=list(pop);newvals=list(vals);blocks=raw.copy();mh=list(h);proof=dict(sourceproof)
  if mode=='control':
   shutil.copyfile(cp,folder/'checkpoint.txt');proof['kind']='verified_final_continuation'
  else:
   cap={'mild':100,'strong':500}[mode];d=products[mode];M.need(len(d)==10,'ten donors')
   existing={M.topo(t,inst.n) for t in pop};newhashes=set()
   for index,(tour,value,meta) in zip(report['replacement_rows'],d):
    M.need(value-ref<=cap,'donor gap cap');M.need(meta['new_edge_count']>=({'mild':2,'strong':6}[mode]),'novel-edge minimum');M.need(not np.isin(meta['new_edges_vs_all_inputs'],inst.fkeys).any(),'new edge is fixed');M.need(meta['topology_sha256'] not in existing|newhashes,'duplicate donor');newhashes.add(meta['topology_sha256'])
    newpop[index]=tour;newvals[index]=value;blocks[1+2*index]=f'{len(tour)} {value}\n'.encode();blocks[2+2*index]=(' '.join(map(str,tour+1))+'\n').encode()
   mh[8]=str(min(newvals));mh[10]='input';blocks[0]=(' '.join(mh)+'\n').encode();(folder/'checkpoint.txt').write_bytes(b''.join(blocks))
   keep=set(range(100))-set(report['replacement_rows']);M.need(len(keep)==90,'best90')
   for i in keep:M.need(blocks[1+2*i:3+2*i]==raw[1+2*i:3+2*i],'untouched raw source pair')
   proof.update(kind='derived_population',replacement_rows=report['replacement_rows'],preserved_best90_raw=True,perturbation_steps=1 if mode=='mild' else 3,max_donor_gap=cap,input_union_pins=report['input_union_pins'],input_edge_union_sha256=report['input_edge_union_sha256'],donors=report['modes'][mode])
  mm=dict(m);mm['files']={k:dict(v) for k,v in m['files'].items()};mm['files']['checkpoint']={'file':'checkpoint.txt','sha256':M.sha(folder/'checkpoint.txt')};mm['identity_evidence']=proof;mm['ordered_population_sha256']=hashlib.sha256(np.asarray(newpop,dtype='<i8').tobytes()).hexdigest();M.E.atomic_json(folder/'context.json',mm)
  got=M.E.admit(folder,wide=True);M.need(got[4]==newvals,'full100 exact costs');M.need(all(np.array_equal(a,b) for a,b in zip(got[3],newpop)),'ordered identity')
  record={'mode':mode,'bundle':str(folder),'context_sha256':M.sha(folder/'context.json'),'checkpoint_sha256':M.sha(folder/'checkpoint.txt'),'gaps':[int(v-ref) for v in newvals],'ordered_population_sha256':mm['ordered_population_sha256'],'initialization_not_search':True,'source_job':job,'source_worker':wid}
  out.append(record)
 report['outputs']=out;report['seconds']=time.monotonic()-t0;report['status']='EXACT_INPUTS_PASS_NOT_SEARCHED';(R/f'RECEIPT_{job}_{wid}.json').write_text(json.dumps(report,indent=2)+'\n');print(job,wid,[(r['mode'],max(r['gaps'])) for r in out],flush=True)
if __name__=='__main__':freeze(int(sys.argv[1]),int(sys.argv[2]))
