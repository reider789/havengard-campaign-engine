#!/usr/bin/env python3
"""Use the pinned SDK's pure validator with this campaign's transactional store."""
from pathlib import Path
import argparse,hashlib,json,sys
from campaignctl import build_result
ROOT=Path(__file__).resolve().parents[1]
def prepare(report,state,engine_root):
    sys.path.insert(0,str(Path(engine_root)/'tools'))
    from combat_handoff import prepare_report
    def state_hash(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return prepare_report(report,state,build_result,state_hash)
if __name__=='__main__':
    import subprocess,tempfile
    p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('--engine-root',type=Path,required=True);p.add_argument('--project',type=Path,default=ROOT);p.add_argument('--output',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args()
    state=json.loads((a.project/'state/_campaign-state.json').read_text());report=json.loads(a.report.read_text());tx=prepare(report,state,a.engine_root);value=json.dumps(tx,ensure_ascii=False,indent=2)+'\n'
    if a.output:a.output.write_text(value)
    if a.apply:
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'result.json';f.write_text(value);subprocess.run([sys.executable,str(a.project/'tools/campaignctl.py'),'--project',str(a.project),'commit','--transaction',str(f)],check=True)
    else:print(value,end='')
