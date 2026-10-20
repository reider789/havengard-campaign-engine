"""Canonical expiry must agree with battle expiry; never touch live state."""
from pathlib import Path
import copy,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from sync_combat_effects import synchronize

def source(hp=15):
 return {'world':{'timekeeping':{'elapsed_seconds_from_anchor':0}},'characters':{
  'caster':{'resources':{'hp':{'current':30,'max':30}},'combat_continuity':{'effects':[dict(id='aid',kind='aid',owner='caster',targets=['ally'],amount=5,expires_at=6)]}},
  'ally':{'resources':{'hp':{'current':hp,'max':32}},'combat_continuity':{'effects':[]}},
  'untracked-npc':{'resources':{'hp':'не установлены'}}}}

for hp in (15,3,0):
 state=source(hp);synchronize(state);state['world']['timekeeping']['elapsed_seconds_from_anchor']=6
 assert synchronize(state);assert state['characters']['ally']['resources']['hp']==dict(current=max(0,hp-5),max=27)
 assert not synchronize(state)
 if hp==3:
  life=state['characters']['ally']['combat_continuity']['life'];assert life==dict(dead=False,stable=False,deathSuccesses=0,deathFailures=0)

state=source(3)
state['characters']['ally']['combat_continuity']['effects']=[dict(id='web',kind='web',owner='ally',targets=[],concentration=True,expires_at=60)]
state['characters']['caster']['combat_continuity']['statuses']=[dict(kind='restrained',effect='web',expires_at=60),dict(kind='grappled',source='ally')]
state['world']['timekeeping']['elapsed_seconds_from_anchor']=6
assert synchronize(state)
assert state['characters']['ally']['combat_continuity']['effects']==[]
assert state['characters']['caster']['combat_continuity']['statuses']==[]
assert not synchronize(state)

state=source();state['characters']['caster']['combat_continuity']['effects'][0]['targets']=['mount']
state['characters']['caster']['combat_continuity']['summons']=[dict(id='mount',hp=3,max=30)]
state['characters']['ally']['combat_continuity']['effects']=[dict(id='bless',kind='bless',owner='ally',targets=['mount'],expires_at=60)]
state['world']['timekeeping']['elapsed_seconds_from_anchor']=6
assert synchronize(state)
assert state['characters']['caster']['combat_continuity']['summons'][0]['hp']==0
assert not state['characters']['ally']['combat_continuity']['effects']
assert not synchronize(state)
print('CANONICAL EFFECTS OK: injured/zero HP Aid, collapse, concentration, linked conditions, mount loss, heterogeneous NPC resources, idempotence')

