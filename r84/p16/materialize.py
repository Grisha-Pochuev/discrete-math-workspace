"""Lossless parent population import. No solver or network."""
import argparse,hashlib,json,pathlib,shutil,sys
import numpy as np

def need(v,m):
 if not v:raise ValueError(m)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def digest(pop):return hashlib.sha256(b''.join(t.astype('<i8').tobytes() for t in pop)).hexdigest()
def materialize(parent,output,engine_source,source_job,worker,arm,exact_audit):
 sys.path.insert(0,str(pathlib.Path(engine_source)/'engine'));import paired_engine as E
 parent,output=map(pathlib.Path,(parent,output));need(arm in ('initial','final'),'arm');need(source_job in (12,17) and 0<=worker<4,'source identity')
 ctx=json.load(open(parent/'inputs/context.json'));run=json.load(open(parent/'run.json'));need(run['source_context_sha256']==sha(parent/'inputs/context.json'),'parent context')
 need(run['complete'] and run['branches']['2']['status']=='completed_budget','parent runtime')
 for name in ('instance','vertices','base'):
  r=ctx['files'][name];need(sha(parent/'inputs'/r['file'])==r['sha256'],'parent file '+name)
 inst=E.Instance(parent/'inputs'/ctx['files']['instance']['file'],ctx['fixm'],wide=True)
 need(inst.n==80000 and ctx['population']==100 and ctx['children']==30 and ctx['fixm']==200000,'frozen dimensions')
 cp=parent/'2'/('input.txt' if arm=='initial' else 'ck.txt')
 need(sha(cp)==(run['branches']['2']['input_sha256'] if arm=='initial' else run['branches']['2']['checkpoint']['sha256']),'source checkpoint identity')
 hdr,pop,values=E.read_text_checkpoint(cp,inst,100)
 a=json.load(open(exact_audit));need(a['status']=='PASS' and a['job']==source_job,'independent audit source')
 aw=a['workers'][worker];need(aw['worker']==worker,'worker audit')
 need([v-aw['local_reference_cost'] for v in values]==aw[arm+'_gaps'],'lossless exact costs')
 need([E.edgekey(t) for t in pop]==aw[arm+'_topologies'],'lossless ordered topologies')
 if arm=='initial':need(digest(pop)==ctx['ordered_population_sha256'],'original ordered identity')
 output.mkdir(parents=True,exist_ok=False)
 for name in ('instance','vertices','base'):
  fn=ctx['files'][name]['file'];shutil.copyfile(parent/'inputs'/fn,output/fn)
 shutil.copyfile(cp,output/'checkpoint.txt')
 result=json.loads(json.dumps(ctx));result['files']['checkpoint']={'file':'checkpoint.txt','sha256':sha(cp)};result['checkpoint_format']='text';result['ordered_population_sha256']=digest(pop)
 result.update(source_job=source_job,source_worker=worker,arm=arm);result['source_run']='44016972185';result['source_slot']=f'{source_job}:{worker}:{arm}';result['identity_evidence']='p15 immutable artifact SHA, exact audit and lossless byte checkpoint import'
 result['continuation']={'protocol':'four-worker-cshift-continuation-v1','source_run':44016972185,'source_head':'c35aa35474983d26debe372608d397fc8fa8ce48','source_job':source_job,'source_worker':worker,'arm':arm,'source_context_sha256':sha(parent/'inputs/context.json'),'source_checkpoint_sha256':sha(cp),'source_audit_sha256':sha(exact_audit),'ordered_population_sha256':digest(pop),'geometry_changed':False,'enrichment':False,'rng_state_restored':False}
 (output/'context.json').write_text(json.dumps(result,indent=2)+'\n')
 _,_,oh,op,ov,_,_=E.admit(output,wide=True);need(oh==hdr and ov==values and digest(op)==digest(pop),'import readback')
 return {'context_sha256':sha(output/'context.json'),'checkpoint_sha256':sha(cp),'ordered_population_sha256':digest(pop),'initial_gaps':aw[arm+'_gaps'],'status':'LOSSLESS_EXACT_PASS'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--parent',required=True);p.add_argument('--output',required=True);p.add_argument('--engine-source',required=True);p.add_argument('--source-job',type=int,required=True);p.add_argument('--worker',type=int,required=True);p.add_argument('--arm',required=True);p.add_argument('--exact-audit',required=True);a=p.parse_args();print(json.dumps(materialize(**vars(a))))
