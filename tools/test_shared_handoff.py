#!/usr/bin/env python3
from pathlib import Path
import copy,hashlib,json,subprocess,sys,tempfile
from build_shared_combat import generate
from build_party_combat_pack import build
from import_shared_combat_result import prepare
from campaignctl import build_result
from sync_combat_effects import synchronize
ROOT=Path(__file__).resolve().parents[1]
engine=Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as d:
 d=Path(d);original=(ROOT/'state/_campaign-state.json').read_bytes();state=json.loads(original)
 generate(engine,ROOT,d,check_lock=False)
 subprocess.run(['node',str(ROOT/'tools/test_shared_party.js'),str(engine),str(d/'prototypes/shared-combat/party-pack.json'),str(d/'reports')],check=True)
 for file in sorted((d/'reports').glob('result-*.json')):
  report=json.loads(file.read_text());tx=prepare(report,state,engine);new=build_result(state,tx);assert new['state_revision']==state['state_revision']+1
  replay=prepare(report,new,engine);assert replay==tx;assert build_result(new,replay)==new
  tampered=copy.deepcopy(report);tampered['after']['yar']['hp']['current']-=1
  try:prepare(tampered,new,engine)
  except Exception:pass
  else:raise AssertionError('Conflicting replay accepted')
  assert new['characters']['daphne']['resources']['spell_slots']['3']['current']==report['after']['daphne']['spell_slots']['3']['current']
 # Persistent spells and summons survive the canonical bridge and a new battle.
 source=d/'prototypes/shared-combat/party-pack.json';report_file=d/'continuity-result.json'
 subprocess.run(['node',str(ROOT/'tools/test_shared_continuity.js'),str(engine),str(source),str(report_file)],check=True)
 result=json.loads(report_file.read_text());updated=build_result(state,prepare(result,state,engine));assert build_result(updated,prepare(result,updated,engine))==updated
 cap=json.loads(subprocess.check_output(['node',str(engine/'sdk/cli.js'),'capabilities'],text=True));next_pack=d/'next-pack.json';next_pack.write_text(json.dumps(build(updated,cap),ensure_ascii=False))
 subprocess.run(['node',str(ROOT/'tools/test_shared_continuity.js'),str(engine),str(next_pack),'check'],check=True)
 # Source-tagged cauldron vials must survive a true transactional handoff,
 # remain with their holder, and never enter ordinary purchased inventory.
 vial=dict(id='vial-9999',sourceSpellId='effect-9999',owner='daphne',
           holder='yar',potionKind='healing')
 potion_result=copy.deepcopy(result)
 potion_result['continuity']['cauldron_vials']=[vial]
 potion_tx=prepare(potion_result,state,engine)
 potion_state=build_result(state,potion_tx)
 assert potion_state['characters']['daphne']['combat_continuity']['cauldron_vials']==[vial]
 assert potion_state['characters']['yar']['inventory_catalog']==state['characters']['yar']['inventory_catalog']
 potion_pack=build(potion_state,cap)
 assert potion_pack['continuity']['cauldron_vials']==[vial]
 assert build_result(potion_state,prepare(potion_result,potion_state,engine))==potion_state
 next_pack.write_text(json.dumps(potion_pack,ensure_ascii=False))
 subprocess.run(['node',str(engine/'sdk/cli.js'),'validate',str(next_pack)],check=True,capture_output=True)
 # Life state must survive SDK export -> canonical transaction -> rebuilt pack -> turn.
 for life in [dict(dead=False,stable=True,deathSuccesses=0,deathFailures=0),
              dict(dead=True,stable=False,deathSuccesses=0,deathFailures=3),
              dict(dead=False,stable=False,deathSuccesses=1,deathFailures=2)]:
  subprocess.run(['node',str(ROOT/'tools/test_shared_continuity.js'),str(engine),str(source),str(report_file),json.dumps(life)],check=True)
  r=json.loads(report_file.read_text());assert r['continuity']['life']['yar']==life
  new=build_result(state,prepare(r,state,engine));assert new['characters']['yar']['combat_continuity']['life']==life
  next_pack.write_text(json.dumps(build(new,cap),ensure_ascii=False))
  subprocess.run(['node','-e',r'''
const fs=require('node:fs'),assert=require('node:assert/strict'),{createBattle}=require(process.argv[1]+'/sdk');
const {engine:e}=createBattle(JSON.parse(fs.readFileSync(process.argv[2]))),life=JSON.parse(process.argv[3]);
for(const [k,v] of Object.entries(life))assert.equal(e.unit('yar')[k],v);
e.s.started=true;e.s.queue=[];e.s.pending=null;e.s.index=e.s.order.indexOf('yar');e.s.random.tape=[10];e.enqueue({kind:'startTurn'});e.run();
assert.equal(e.unit('yar').deathSuccesses,life.deathSuccesses+(life.dead||life.stable?0:1));
assert.equal(e.unit('yar').dead,life.dead);assert.equal(e.unit('yar').stable,life.stable);
''',str(engine),str(next_pack),json.dumps(life)],check=True)
  if life['stable']:
   healed=copy.deepcopy(new);healed['characters']['yar']['resources']['hp']['current']=5;synchronize(healed)
   assert healed['characters']['yar']['combat_continuity']['life']==dict(dead=False,stable=False,deathSuccesses=0,deathFailures=0)
 # Reject corrupt continuity before any canonical mutation.
 for mutate in [lambda r:r['continuity']['effects'][0].update(kind='unknown'),
                lambda r:r['continuity']['units'].append(dict(summoner='daphne',hp=10)),
                lambda r:r['continuity']['statuses']['yar'].append(dict(kind='invented'))]:
  bad=copy.deepcopy(result);mutate(bad);before=copy.deepcopy(state)
  try:prepare(bad,state,engine)
  except (ValueError,RuntimeError):pass
  else:raise AssertionError('Corrupt continuity accepted')
  assert state==before
 assert (ROOT/'state/_campaign-state.json').read_bytes()==original
 # Expiry of temporary HP maximum and armor follows real game seconds, not wall-clock time.
 c=copy.deepcopy(state);clock=c['world']['timekeeping']['elapsed_seconds_from_anchor'];hp=c['characters']['rada']['resources']['hp'];hp['max']+=5;hp['current']+=5
 c['characters']['lyutobor']['combat_continuity']={'effects':[{'id':'aid','kind':'aid','owner':'lyutobor','targets':['rada'],'amount':5,'expires_at':clock+6}]}
 synchronize(c);assert not synchronize(c);c['world']['timekeeping']['elapsed_seconds_from_anchor']+=6;assert synchronize(c);assert c['characters']['rada']['resources']['hp']==state['characters']['rada']['resources']['hp']
 # Aid/Heroism on a retained mount expire through the same clock without party lookups.
 c=copy.deepcopy(state);clock=c['world']['timekeeping']['elapsed_seconds_from_anchor']
 c['characters']['lyutobor']['combat_continuity']={'effects':[
  dict(id='aid-steed',kind='aid',owner='lyutobor',targets=['lyutobor-steed'],amount=5,expires_at=clock+6),
  dict(id='hero-steed',kind='heroism',owner='lyutobor',targets=['lyutobor-steed'],expires_at=clock+6)],
  'summons':[dict(id='lyutobor-steed',hp=29,max=30,persistent_temp=4,persistent_temp_source='hero-steed',persistent_statuses=[dict(kind='poisoned',expires_at=clock+6)])]}
 synchronize(c);assert not synchronize(c);c['world']['timekeeping']['elapsed_seconds_from_anchor']+=6;assert synchronize(c)
 mount=c['characters']['lyutobor']['combat_continuity']['summons'][0];assert (mount['hp'],mount['max'],mount['persistent_temp'],mount['persistent_statuses'])==(24,25,0,[])
 # B01-B03: final-clock normalization and the actual next field are validated before commit.
 for mode in ('goad','cast-aid','imported-aid','heroism','large-field'):
  source_state=copy.deepcopy(state)
  if mode=='imported-aid':
   hp=source_state['characters']['yar']['resources']['hp'];hp['max']+=5;hp['current']+=5
   now=source_state['world']['timekeeping']['elapsed_seconds_from_anchor']
   source_state['characters']['lyutobor']['combat_continuity']={'effects':[dict(id='effect-900',kind='aid',owner='lyutobor',targets=['yar'],level=2,dc=14,concentration=False,amount=5,expires_at=now+6)]}
  pack=build(source_state,cap)
  raw=subprocess.check_output(['node',str(ROOT/'tools/test_shared_boundary.js'),str(engine),mode],input=json.dumps(pack),text=True)
  r=json.loads(raw);tx=prepare(r,source_state,engine);new=build_result(source_state,tx)
  assert build_result(new,prepare(r,new,engine))==new
  assert new['characters']['yar']['resources']['hp']['max']==state['characters']['yar']['resources']['hp']['max']
  assert new['characters']['yar']['combat_continuity']['temporary_hp']==0
  assert not any(z['kind']=='goaded' for z in new['characters']['yar']['combat_continuity']['statuses'])
  next_pack.write_text(json.dumps(build(new,cap),ensure_ascii=False))
  subprocess.run(['node',str(engine/'sdk/cli.js'),'validate',str(next_pack)],check=True,capture_output=True)
  if mode=='large-field':
   restored=json.loads(next_pack.read_text());arena=restored['encounters'][restored['default_encounter']]
   assert (arena['width'],arena['height'])==(20,12)
   assert (restored['continuity']['objects'][0]['x'],restored['continuity']['objects'][0]['y'])==(18,10)
   assert arena['heroes']['lyutobor-steed']['cell']=='J3'
   assert all(x['cell']!='J3' for x in arena['enemies'])
   bad=copy.deepcopy(r);bad['continuity']['scene']['positions']['yar']=bad['continuity']['scene']['positions']['daphne']
   before=copy.deepcopy(source_state)
   try:prepare(bad,source_state,engine)
   except ValueError as error:assert 'Следующий бой не запускается' in str(error)
   else:raise AssertionError('Unlaunchable next battle accepted')
   assert source_state==before
 # C02-C03: native zonal statuses and partial parties restore through the
 # actual transaction, rebuild, validation and initialized next battle.
 def audit_scene(source_state,mode):
  return json.loads(subprocess.check_output(['node',str(ROOT/'tools/test_shared_audit_3053.js'),str(engine),mode],input=json.dumps(build(source_state,cap)),text=True))
 first=audit_scene(copy.deepcopy(state),'first')
 previous=build_result(state,prepare(first,state,engine))
 for mode,source_state in [('partial',previous),('web',state)]:
  r=audit_scene(copy.deepcopy(source_state),mode)
  updated=build_result(source_state,prepare(r,source_state,engine))
  restored=build(updated,cap)
  subprocess.run(['node',str(ROOT/'tools/test_shared_audit_3053.js'),str(engine),'check-'+mode],input=json.dumps(restored),text=True,check=True)
  assert build_result(updated,prepare(r,updated,engine))==updated
  if mode=='partial':
   bad=copy.deepcopy(updated)
   other=copy.deepcopy(bad['characters']['daphne']['combat_continuity'])
   other['scene']['id']='actual-different-live-field'
   bad['characters']['lyutobor']['combat_continuity']=other
   try:build(bad,cap)
   except ValueError as error:assert 'разные поля боя' in str(error)
   else:raise AssertionError('Conflicting live spatial fields accepted')
 assert (ROOT/'state/_campaign-state.json').read_bytes()==original
 print('FULL PARTY HANDOFF OK: three full fights, partial-party field, native Web restraint, exact replay, expiry and initialized next battle; live canon unchanged')
