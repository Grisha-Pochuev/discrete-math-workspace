"""Read pinned bytes, no solver."""
import hashlib, json, os, subprocess, time
from pathlib import Path
root = Path(__file__).resolve().parent
allc = json.loads((root / 'parents.json').read_text())
index = int(os.environ['JOB_INDEX'])
if not 0 <= index < 20: raise ValueError('index')
job = allc['jobs'][index]
c = dict(allc['common'], **allc['parents'][job['center']])
p = json.loads((root / 'sources.json').read_text())
a = json.loads((root / 'admission.json').read_text())
for n, h in p['text_sources'].items():
    if not hashlib.sha256((root / n).read_bytes()).hexdigest() == h:
        raise ValueError(n)
if not (a['status'] == 'PROBE_ONE_SHOT' and a['activation_epoch'] <= time.time() < a['expiry_epoch']):
    raise ValueError('validation failed')
if not (os.environ['GITHUB_RUN_ATTEMPT'] == '1' and os.environ['GITHUB_REPOSITORY'] == 'Grisha-Pochuev/discrete-math-workspace'):
    raise ValueError('validation failed')
out = Path('inputs')
out.mkdir(exist_ok=False)
want = c['artifact']
ep = 'repos/' + os.environ['GITHUB_REPOSITORY'] + '/actions/artifacts/' + str(want['id'])
m = json.loads(subprocess.check_output(['gh', 'api', ep], timeout=60))
for key in ('id', 'name', 'size_in_bytes', 'digest'):
    if not m[key] == want[key]:
        raise ValueError(key)
if not (not m['expired'] and m['workflow_run']['id'] == want['workflow_run']['id'] and (m['workflow_run']['head_sha'] == want['workflow_run']['head_sha'])):
    raise ValueError('validation failed')
with (out / 'parent.zip').open('xb') as f:
    subprocess.run(['gh', 'api', ep + '/zip'], stdout=f, check=True, timeout=180)
if not (out / 'parent.zip').stat().st_size == want['size_in_bytes']:
    raise ValueError('validation failed')
if not hashlib.sha256((out / 'parent.zip').read_bytes()).hexdigest() == want['digest'].split(':')[1]:
    raise ValueError('validation failed')
for name, key in [('a', 'coordinates_sha256'), ('b', 'reference_sha256')]:
    subprocess.run(['curl', '--fail', '--location', '--max-time', '300', '--max-filesize', '60000000', '--output', str(out / name), 'https://raw.githubusercontent.com/Grisha-Pochuev/discrete-math-workspace/inp/w_' + name + '.bin'], check=True, timeout=310)
    if not hashlib.sha256((out / name).read_bytes()).hexdigest() == c[key]:
        raise ValueError('validation failed')
if not time.time() < a['expiry_epoch']:
    raise ValueError('validation failed')
Path('o/input-receipt.json').write_text(json.dumps({'artifact_id': m['id'], 'digest': m['digest'], 'status': 'PINNED_INPUTS_PASS'}) + '\n')

