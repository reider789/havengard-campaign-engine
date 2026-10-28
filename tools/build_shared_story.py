#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,subprocess
from build_shared_combat import ROOT,load_bundle,compile_pack
from build_party_combat_pack import build
p=argparse.ArgumentParser();p.add_argument('--engine-root',type=Path,required=True);p.add_argument('--scenario',type=Path,required=True);p.add_argument('--profiles',type=Path,help='Проверенные карточки новых врагов и союзников в JSON');p.add_argument('--output',type=Path,required=True);a=p.parse_args();engine=a.engine_root.resolve()
lock=json.loads((ROOT/'prototypes/shared-combat/engine-lock.json').read_text())
for name,sha in lock['files'].items():
 if hashlib.sha256((engine/name).read_bytes()).hexdigest()!=sha:raise SystemExit('Engine lock mismatch: '+name)
state=json.loads((ROOT/'state/_campaign-state.json').read_text());cap=json.loads(subprocess.check_output(['node',str(engine/'sdk/cli.js'),'capabilities'],text=True));pack=build(state,cap);scene=json.loads(a.scenario.read_text())
if scene.get('kind')!='story' or not scene.get('battle_id') or scene.get('source_revision')!=pack['revision'] or scene.get('source_state_sha256')!=pack['source_state_sha256']:raise SystemExit('Authored story must pin the current canonical revision and hash')
# The workbook may contain newly played resource use awaiting reconciliation in the
# canonical campaign ledger. Pin every such temporary change to the battle scene.
# Never silently reset a spent daily ability or ammunition to an older snapshot.
overrides=scene.get('resource_overrides',{})
if overrides:
 if not isinstance(overrides,dict) or not scene.get('resource_override_source'):raise SystemExit('Resource overrides require an explicit source')
 for char_id,pools in overrides.items():
  if char_id not in pack['characters'] or not isinstance(pools,dict):raise SystemExit('Unknown resource override character')
  existing=pack['characters'][char_id]['resources']
  for name,value in pools.items():
   if name not in existing or not isinstance(value,int) or not (0<=value<=existing[name]['max']):
    raise SystemExit('Invalid resource override '+char_id+'/'+name)
   existing[name]['current']=value
if a.profiles:
 extra=json.loads(a.profiles.read_text())
 if not isinstance(extra,dict) or set(extra)!={'profiles'} or not isinstance(extra['profiles'],dict):raise SystemExit('Expected {"profiles": {...}}')
 for key,profile in extra['profiles'].items():
  if not isinstance(key,str) or not key or key in pack['profiles'] or not isinstance(profile,dict):raise SystemExit('Duplicate/invalid additional creature: '+str(key))
  pack['profiles'][key]=profile
pack['default_encounter']='active-story';pack['encounters']={'active-story':scene};a.output.parent.mkdir(parents=True,exist_ok=True);data=compile_pack(engine,pack,a.output.with_suffix('.source.json'));bundle=load_bundle(engine);art=json.loads((ROOT/'prototypes/chat-combat/art/hayvengard_art_v1.json').read_text());a.output.write_text(bundle.render(data['runtime'],data['scene'],bundle.scene_art(data['runtime'],data['scene'],art),root=engine));print(a.output)
