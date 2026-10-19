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
 assert (ROOT/'state/_campaign-state.json').read_bytes()==original
 # Expiry of temporary HP maximum and armor follows real game seconds, not wall-clock time.
 c=copy.deepcopy(state);clock=c['world']['timekeeping']['elapsed_seconds_from_anchor'];hp=c['characters']['rada']['resources']['hp'];hp['max']+=5;hp['current']+=5
 c['characters']['lyutobor']['combat_continuity']={'effects':[{'id':'aid','kind':'aid','owner':'lyutobor','targets':['rada'],'amount':5,'expires_at':clock+6}]}
 assert not synchronize(c);c['world']['timekeeping']['elapsed_seconds_from_anchor']+=6;assert synchronize(c);assert c['characters']['rada']['resources']['hp']==state['characters']['rada']['resources']['hp']
 print('FULL PARTY HANDOFF OK: three completed story copies, serialized decisions, canonical bounds, exact replay, conflicting replay rejection, expiry; live canon unchanged')
