import datetime,os,time,json
from pathlib import Path
from common import *
def inspect(p,name,run,head,now,seconds):
 need(p['total_count']==len(p['jobs']),'jobs truncated');hits=[j for j in p['jobs'] if j['name']==name];need(len(hits)<=1,'ambiguous job')
 if not hits:return None
 j=hits[0];need((j['run_id'],j['run_attempt'],j['head_sha'])==(run,1,head),'job identity')
 if j['status']=='queued' or j['started_at'] is None:return None
 need(j['status']=='in_progress','job terminal');start=datetime.datetime.fromisoformat(j['started_at'].replace('Z','+00:00'));need(start.tzinfo is not None and start.timestamp()<=now+5,'job start');deadline=start.timestamp()+21600-60;need(deadline-now>=seconds+1500,'job budget');return deadline
def main():
 source_gate();active_gate();until=time.monotonic()+90;Path('o').mkdir(exist_ok=True);i=0
 while time.monotonic()<until:
  p=api(f'repos/{REPO}/actions/runs/{os.environ["GITHUB_RUN_ID"]}/attempts/1/jobs?per_page=100');Path(f'o/timing-{i}.json').write_text(json.dumps(p));i+=1
  d=inspect(p,os.environ['EXPECTED_JOB_NAME'],int(os.environ['GITHUB_RUN_ID']),os.environ['GITHUB_SHA'],time.time(),int(os.environ['SECONDS_REQUESTED']))
  if d is not None:
   with open(os.environ['GITHUB_ENV'],'a') as f:f.write(f'JOB_DEADLINE={d}\n')
   return
  time.sleep(3)
 raise ValueError('timing unavailable')
if __name__=='__main__':main()
