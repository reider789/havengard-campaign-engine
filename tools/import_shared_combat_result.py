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
    tx=prepare_report(report,state,build_result,state_hash)
    # Validate the actual next launch before confirming the transaction.
    import subprocess,tempfile
    from build_party_combat_pack import build
    updated=build_result(state,tx)
    cap=json.loads(subprocess.check_output(['node',str(Path(engine_root)/'sdk/cli.js'),'capabilities'],text=True))
    pack=build(updated,cap)
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'next-pack.json';path.write_text(json.dumps(pack,ensure_ascii=False))
        result=subprocess.run(['node',str(Path(engine_root)/'sdk/cli.js'),'validate',str(path)],capture_output=True,text=True)
        if result.returncode:raise ValueError('Следующий бой не запускается: '+result.stderr.strip())
    return tx
if __name__=='__main__':
    import subprocess,tempfile
    p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('--engine-root',type=Path,required=True);p.add_argument('--project',type=Path,default=ROOT);p.add_argument('--output',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args()
    state=json.loads((a.project/'state/_campaign-state.json').read_text());report=json.loads(a.report.read_text());tx=prepare(report,state,a.engine_root);value=json.dumps(tx,ensure_ascii=False,indent=2)+'\n'
    if a.output:a.output.write_text(value)
    if a.apply:
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'result.json';f.write_text(value);subprocess.run([sys.executable,str(a.project/'tools/campaignctl.py'),'--project',str(a.project),'commit','--transaction',str(f)],check=True)
    else:print(value,end='')
