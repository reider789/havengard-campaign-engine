#!/usr/bin/env python3
"""Check one pinned engine; audit live sheets without modifying the campaign."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--engine-root',type=Path,required=True);p.add_argument('--project',type=Path,default=ROOT);p.add_argument('--output',type=Path);p.add_argument('--require-ready',action='store_true');a=p.parse_args()
lock=json.loads((ROOT/'prototypes/shared-combat/engine-lock.json').read_text(encoding='utf-8'));engine=a.engine_root.resolve();project=a.project.resolve()
for name,expected in lock['files'].items():
    if hashlib.sha256((engine/name).read_bytes()).hexdigest()!=expected:raise SystemExit('Shared engine lock mismatch: '+name)
cap=json.loads(subprocess.check_output(['node',str(engine/'sdk/cli.js'),'capabilities'],text=True))
if cap['engine']!=lock['engine_version'] or cap['api']!=lock['content_api']:raise SystemExit('Shared API/version mismatch')
state=project/'state/_campaign-state.json';before=state.read_bytes()
def run(*args):subprocess.run(args,cwd=engine,check=True)
run('node','sdk/cli.js','validate','examples/portable/border-watch.json')
run('node','--test','tests/test_content_packs.js','tests/test_class_features.js','tests/test_defenses.js','tests/test_martial_features.js')
run('node','sdk/cli.js','validate','examples/portable/class-defense-lab.json')
with tempfile.TemporaryDirectory(prefix='shared-combat-check-') as tmp:
    run(sys.executable,'tools/build_combat.py','--pack','examples/portable/border-watch.json','--output',str(Path(tmp)/'battle.html'))
    run(sys.executable,'tools/build_combat.py','--pack','examples/portable/class-defense-lab.json','--output',str(Path(tmp)/'class-lab.html'))
    output=a.output.resolve() if a.output else Path(tmp)/'audit.json'
    run(sys.executable,'tools/audit_havengard.py','--state',str(state),'--registry',str(project/'prototypes/combat/character-capability-registry-g1m8-v1.json'),'--output',str(output))
    report=json.loads(output.read_text(encoding='utf-8'))
if state.read_bytes()!=before:raise SystemExit('Canonical state changed during a read-only check')
print('Shared engine verified:',lock['engine_version'],'from',lock['repository']+'@'+lock['commit'])
print('Canonical revision:',report['source_state_revision'],'/ full character migration ready:',report['ready_for_full_migration'])
if a.require_ready and not report['ready_for_full_migration']:raise SystemExit('Migration blocked: verified profiles and handlers are missing')
