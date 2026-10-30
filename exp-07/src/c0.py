#!/usr/bin/env python3
import argparse,json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    root=Path(a.root); summaries=[]; verified=[]
    for p in sorted(root.rglob('summary-*.json')):
        try:summaries.append(json.loads(p.read_text()))
        except Exception as e:summaries.append({'file':str(p),'parse_error':str(e)})
    for p in sorted(root.rglob('verified.json')):
        try:verified.append(json.loads(p.read_text()))
        except Exception as e:verified.append({'file':str(p),'parse_error':str(e)})
    by_type={str(i):{'workers':0,'pair_tests':0,'ratio_hits':0,'near_hits':0,'complete_workers':0,'timed_workers':0} for i in range(6)}
    for s in summaries:
        if 'type' not in s:continue
        x=by_type[str(s['type'])];x['workers']+=1;x['pair_tests']+=s.get('pair_tests',0);x['ratio_hits']+=s.get('ratio_hits',0);x['near_hits']+=s.get('near_hits',0)
        x['timed_workers']+=int(bool(s.get('timed_out_cleanly')));x['complete_workers']+=int(not s.get('timed_out_cleanly',False))
    sols=[];exact_cancel=0
    for v in verified:
        exact_cancel+=v.get('exact_cancellations',0);sols.extend(v.get('solutions',[]))
    out={'schema_version':1,'worker_summaries':len(summaries),'verification_groups':len(verified),'by_type':by_type,'exact_cancellations':exact_cancel,'solutions':sols}
    Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
