"""One bounded stage with unchanged runner."""
import argparse, json, sys, time
from pathlib import Path
p = argparse.ArgumentParser()
for k in ('source', 'prepared', 'output'):
    p.add_argument('--' + k, type=Path, required=True)
p.add_argument('--deadline', type=float, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parent
cfg = json.loads((root / 'admission.json').read_text())
if not (cfg['status'] == 'APPROVED_ONE_SHOT' and cfg['activation_epoch'] <= time.time() < cfg['expiry_epoch']):
    raise ValueError('validation failed')
if not (cfg['seconds'] == 180 and cfg['operator'] == 2 and (a.deadline - time.time() > 810)):
    raise ValueError('validation failed')
sys.path.insert(0, str(a.source))
import run_experiment as runner
r = runner.run(a.prepared / 'expanded150', a.prepared / 'k', a.output, 180, cfg['seed'], '2', 6000, a.deadline)
r = json.loads((a.output / 'run.json').read_text())
b = r['branches']['2']
s = b['kernel_stats']
if not (r['complete'] and b['returncode'] == 0 and b['search_exercised']):
    raise ValueError('validation failed')
if not (s['children'] > b['initial_children'] and s['block2_attempts'] > 0):
    raise ValueError('validation failed')
if not (s['cap_hits'] == s['single_fallbacks'] == 0 and s['injection_generation'] == -1):
    raise ValueError('validation failed')
if not (r['vertices'] == 150000 and (not r['injection']) and (not r['restart'])):
    raise ValueError('validation failed')
