#!/usr/bin/env python3
"""The data-backed adapter must preserve every published combat profile."""
import copy
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_party_combat_pack import build,BASE_RESOURCES
state=json.loads((ROOT/'state/_campaign-state.json').read_text(encoding='utf-8'))
published=json.loads((ROOT/'prototypes/shared-combat/party-pack.json').read_text(encoding='utf-8'))
extra=set().union(*(set(ch['resources']) for ch in published['characters'].values()))-BASE_RESOURCES
capabilities={'counters':sorted(extra)}
rebuilt=build(state,capabilities)
for id in ('yar','daphne','lyutobor','rada','raider'):
    assert rebuilt['profiles'][id]==published['profiles'][id],f'Mechanics drift: {id}'
for id in ('yar','daphne','lyutobor','rada'):
    assert rebuilt['characters'][id]==published['characters'][id],f'Inventory/resources drift: {id}'
assert rebuilt['encounters']==published['encounters']
assert rebuilt['source_state_sha256']==published['source_state_sha256']
assert rebuilt['continuity']==published['continuity']
# Adding a new combatant is declarative, not an if/elif class branch.
new=copy.deepcopy(state)
guest=copy.deepcopy(new['characters']['rada'])
guest['name']='Союзник'
guest['combat_profile']=copy.deepcopy(published['profiles']['rada'])
guest['inventory']=[];guest['inventory_catalog']={}
guest['resources']={'hp':{'current':30,'max':30}}
new['characters']['new-companion']=guest
pack=build(new,capabilities)
assert 'new-companion' in pack['profiles']
assert 'new-companion' in pack['characters']
assert 'new-companion' in pack['encounters']['party-training']['heroes']
cells=[p['cell'] for p in pack['encounters']['party-training']['heroes'].values()]
assert len(set(cells))==len(cells)
assert len(pack['profiles'])==len(published['profiles'])+1
print('DECLARATIVE PARTY OK: all four published cards identical, raider unchanged, extra heroes have valid cells')
