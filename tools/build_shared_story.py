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
# The canonical master workbook can be newer than the last exported GitHub
# campaign snapshot. A story-specific, sourced defensive profile correction must
# be applied BEFORE compiling; otherwise AC/armor are silently reset.
combat_overrides=scene.get('combat_profile_overrides',{})
if combat_overrides:
 if not isinstance(combat_overrides,dict) or not scene.get('combat_profile_override_source'):
  raise SystemExit('Combat profile overrides require a source')
 for char_id,delta in combat_overrides.items():
  if char_id not in pack['characters'] or not isinstance(delta,dict) or set(delta)-{'ac','features'}:
   raise SystemExit('Unknown or invalid combat profile override '+str(char_id))
  profile=pack['profiles'][char_id]
  if 'ac' in delta:
   value=delta['ac']
   if not isinstance(value,int) or not 1<=value<=40:raise SystemExit('Invalid AC correction')
   profile['ac']=value
  if 'features' in delta:
   new_features=delta['features']
   if not isinstance(new_features,dict) or set(new_features)-{'heavyArmor','heavyArmorReduction'}:
    raise SystemExit('Only documented heavy-armor features may be corrected')
   if 'heavyArmor' in new_features and not isinstance(new_features['heavyArmor'],bool):
    raise SystemExit('Invalid heavy armor flag')
   if 'heavyArmorReduction' in new_features and (not isinstance(new_features['heavyArmorReduction'],int) or not 1<=new_features['heavyArmorReduction']<=10):
    raise SystemExit('Invalid heavy armor reduction')
   profile['features'].update(new_features)
  if char_id in pack.get('profiles',{}):
   pack['profiles'][char_id]['ac']=profile['ac']
   pack['profiles'][char_id]['features']=dict(profile['features'])
if a.profiles:
 extra=json.loads(a.profiles.read_text())
 if not isinstance(extra,dict) or set(extra)!={'profiles'} or not isinstance(extra['profiles'],dict):raise SystemExit('Expected {"profiles": {...}}')
 for key,profile in extra['profiles'].items():
  if not isinstance(key,str) or not key or key in pack['profiles'] or not isinstance(profile,dict):raise SystemExit('Duplicate/invalid additional creature: '+str(key))
  pack['profiles'][key]=profile
pack['default_encounter']='active-story';pack['encounters']={'active-story':scene};a.output.parent.mkdir(parents=True,exist_ok=True);data=compile_pack(engine,pack,a.output.with_suffix('.source.json'));bundle=load_bundle(engine);art=json.loads((ROOT/'prototypes/chat-combat/art/hayvengard_art_v1.json').read_text());a.output.write_text(bundle.render(data['runtime'],data['scene'],bundle.scene_art(data['runtime'],data['scene'],art),root=engine));print(a.output)
