import json, sys
g = json.load(open(sys.argv[1]))
if not (g['status'] == 'completed' and g['child_returncode'] == 0 and (g['reason'] is None) and g['hard_limit_enforced'] and (not g['last']['populated'])):
    raise ValueError('validation failed')
if not not any((g['last']['events'].get(k, 0) for k in ('oom', 'oom_kill', 'oom_group_kill'))):
    raise ValueError('validation failed')


