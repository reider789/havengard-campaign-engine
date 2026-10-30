#!/usr/bin/env python3
"""Read-only integration gate; build outputs are disposable rehearsals."""
from pathlib import Path
import argparse, hashlib, json, os, subprocess
from build_prepared_encounter import ROOT,CATALOGUE,make_pack,render
def main():
    p=argparse.ArgumentParser();p.add_argument('--engine-root',type=Path,required=True);a=p.parse_args();engine=a.engine_root.resolve()
    protected=[ROOT/'state/_campaign-state.json',ROOT/'prototypes/chat-combat/story/active-scene.json',ROOT/'prototypes/chat-combat/story/enemy-profiles.json']
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    cat=json.loads(CATALOGUE.read_text());built=[]
    for room,t in cat['encounters'].items():
        if not t['population']:continue
        pack,c=make_pack(engine,room);render(engine,pack,c,ROOT/'.build'/f'{room}.html');built.append(room)
    env={**os.environ,'ENGINE_ROOT':str(engine)}
    for suite in ['test_prepared_encounters.js','test_prepared_runtime.js']:
        subprocess.run(['node','--test',str(ROOT/'tools'/suite)],check=True,env=env)
    # Actual story start pins the current state; preparation must not create one.
    for room in ['G5','T8']:
        try:make_pack(engine,room,{},True)
        except ValueError:pass
        else:raise AssertionError('Unverified story deployment was accepted')
    for name,sha in before.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==sha,name
    lock=json.loads((ROOT/'prototypes/shared-combat/engine-lock.json').read_text())
    for name,sha in lock['files'].items():assert hashlib.sha256((engine/name).read_bytes()).hexdigest()==sha,name
    result={'ok':True,'profiles':len(cat['profiles']),'room_templates':len(cat['encounters']),'built_rehearsals':built,'canonical_files_unchanged':True,'pinned_engine_55_files_unchanged':True,'mode':'prepared-runtime','full_3d_automation':False,'authored_encounter_automation':True}
    (ROOT/'.build/prepared-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
