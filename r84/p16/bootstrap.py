import argparse,hashlib,json,tarfile
from pathlib import Path
def need(v,m):
 if not v:raise ValueError(m)
def main():
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();cfg=json.loads(Path(__file__).with_name('sources.json').read_text());need(hashlib.sha256(a.archive.read_bytes()).hexdigest()==cfg['source_archive_sha256'],'archive SHA');need(not a.output.exists(),'output exists')
 with tarfile.open(a.archive,'r:xz') as t:
  mm=t.getmembers();need(len(mm)<=200 and sum(m.size for m in mm)<1024**3 and len({m.name for m in mm})==len(mm),'archive bounds')
  for m in mm:need(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts,'unsafe member')
  a.output.mkdir(parents=True)
  for m in mm:
   q=a.output/m.name;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(t.extractfile(m).read())
 (a.output/'SOURCE_ARCHIVE_SHA256').write_text(cfg['source_archive_sha256']+'\n')
if __name__=='__main__':main()
