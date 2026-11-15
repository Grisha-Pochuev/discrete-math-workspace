"""Local package entry."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile


def extract(archive, target, expected):
    archive, target = Path(archive), Path(target)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError('package checksum')
    if target.exists():
        raise ValueError('output exists')
    with tarfile.open(archive, 'r:xz') as f:
        members = f.getmembers()
        if sum(m.size for m in members) > 1024**3 or len(members) > 200:
            raise ValueError('package size')
        for m in members:
            p = Path(m.name)
            if p.is_absolute() or '..' in p.parts or not m.isfile():
                raise ValueError('package member')
        target.mkdir(parents=True)
        for m in members:
            p = target/m.name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(f.extractfile(m).read())


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); root = Path(__file__).resolve().parent
    m = json.loads((root/'m.json').read_text())
    extract(root/'s.bin', a.output/'s', m['s'])
    extract(root/'b.bin', a.output/'b', m['b'])
    subprocess.run([sys.executable, str(a.output/'s/engine/build_kernel.py'), '--output', str(a.output/'k'), '--compact', '--wide', '--objective64'], check=True)


if __name__ == '__main__':
    main()
