import sys,subprocess,shutil
from pathlib import Path
from common import *
source_gate();p=Path('wd/s');need(sha(p/'run_experiment.py')==read('sources.json')['original_runner_sha256'],'original runner');shutil.copyfile(ROOT/'run_experiment.py',p/'run_experiment.py')
subprocess.run([sys.executable,str(p/'engine/build_kernel.py'),'--output',str(Path('wd/k').resolve()),'--compact','--wide','--objective64'],check=True)
