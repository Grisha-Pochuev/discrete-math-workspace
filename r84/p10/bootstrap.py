"""Validate/extract the unchanged small source archive. No solver or network."""
import argparse,hashlib,json,tarfile
from pathlib import Path
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,m):
    if not x:raise ValueError(m)
def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    config=json.loads(Path(__file__).with_name('sources.json').read_text());need(sha(a.archive)==config['source_archive_sha256'],'source archive hash');need(not a.output.exists(),'output exists')
    with tarfile.open(a.archive,'r:xz') as t:
        members=t.getmembers();need(len(members)<=200 and sum(x.size for x in members)<=1024**3,'source limits');need(len({x.name for x in members})==len(members),'duplicate source')
        for x in members:need(x.isfile() and not Path(x.name).is_absolute() and '..' not in Path(x.name).parts,'source member')
        a.output.mkdir(parents=True)
        for x in members:
            out=a.output/x.name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(t.extractfile(x).read())
    (a.output/'SOURCE_ARCHIVE_SHA256').write_text(config['source_archive_sha256']+'\n')
if __name__=='__main__':main()

