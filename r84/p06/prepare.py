"""Pure source-bound preparation inside the existing memory guard, no solver."""
import argparse,hashlib,json,resource,shutil,subprocess,sys,time
from pathlib import Path
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,m):
    if not x:raise ValueError(m)
def main():
    p=argparse.ArgumentParser()
    for x in ('source-root','g24','builder','parent','coordinates','reference','output'):p.add_argument('--'+x,type=Path,required=True)
    p.add_argument('--index',type=int,required=True);a=p.parse_args();start=time.monotonic();root=Path(__file__).resolve().parent;config=json.loads((root/'sources.json').read_text());parents=json.loads((root/'parents.json').read_text())
    import numpy,scipy
    need(numpy.__version__==config['numpy'] and scipy.__version__==config['scipy'],'numerical versions')
    for f,h in config['text_sources'].items():need(sha(root/f)==h,'text source hash '+f)
    need((a.source_root/'SOURCE_ARCHIVE_SHA256').read_text().strip()==config['source_archive_sha256'],'source identity')
    need(sha(a.g24)==config['g24_sha256'] and sha(a.builder)==config['builder_sha256'],'geometry source bytes')
    need(not a.output.exists(),'new output required');a.output.mkdir(parents=True)
    # The helper imports the unchanged engine below this same source root.
    target=a.source_root/'region_tools.py';need(not target.exists(),'constructor already exists');shutil.copyfile(root/'region_tools.py',target)
    geometry=a.output/'g25.bin'
    subprocess.run([sys.executable,str(a.builder),'--coords',str(a.coordinates),'--g24',str(a.g24),'--out',str(geometry),'--expected-sha',parents['geometry_sha256']],check=True)
    scorer=a.output/'exact.so';subprocess.run(['g++','-O2','-shared','-fPIC',str(root/'exact.cpp'),'-o',str(scorer)],check=True)
    command=[sys.executable,str(root/'materialize.py'),'--manifest',str(root/'parents.json'),'--index',str(a.index),'--parent',str(a.parent),'--geometry',str(geometry),'--coordinates',str(a.coordinates),'--reference',str(a.reference),'--tools',str(a.source_root),'--exact',str(scorer),'--output',str(a.output/'materialized')]
    subprocess.run(command,check=True)
    subprocess.run([sys.executable,str(a.source_root/'engine/build_kernel.py'),'--output',str(a.output/'k'),'--compact','--wide','--objective64'],check=True)
    receipt={'status':'SOURCE_GEOMETRY_AND_PARENT_PASS_NOT_SEARCH_ADMISSION','seconds':time.monotonic()-start,'child_peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'source_archive_sha256':config['source_archive_sha256'],'geometry_sha256':sha(geometry),'scorer_source_sha256':sha(root/'exact.cpp'),'search_started':False}
    (a.output/'PREPARATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
