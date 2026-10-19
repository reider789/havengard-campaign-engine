#!/usr/bin/env python3
"""Verify the pin, compile the full canonical party and audit reviewed mechanics."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,tempfile
from build_shared_combat import generate
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--engine-root',type=Path,required=True);p.add_argument('--project',type=Path,default=ROOT);p.add_argument('--output',type=Path);p.add_argument('--require-ready',action='store_true');a=p.parse_args();engine=a.engine_root.resolve();project=a.project.resolve();state=project/'state/_campaign-state.json';before=state.read_bytes()
with tempfile.TemporaryDirectory(prefix='shared-combat-check-') as tmp:
    tmp=Path(tmp);manifest=generate(engine,project,tmp)
    report=json.loads((tmp/'prototypes/shared-combat/migration-audit.json').read_text())
    if a.output:a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
subprocess.run(['node','--test',*[str(f) for f in sorted((engine/'tests').glob('test_*.js'))]],cwd=engine,check=True)
if state.read_bytes()!=before:raise SystemExit('Canonical state changed during a read-only check')
if not report['ready_for_full_migration']:raise SystemExit('Full party migration is blocked: '+str(report.get('errors')))
print('SHARED ENGINE VERIFIED:',manifest['engine_version'],'/ canonical revision',report['source_state_revision'],'/ all four profiles ready')
