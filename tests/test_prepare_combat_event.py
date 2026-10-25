#!/usr/bin/env python3
"""Narrative decisions never mutate canonical state without reviewed transactions."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from prepare_combat_event import changes_to_transaction
from campaignctl import build_result

state=json.loads((ROOT/"state/_campaign-state.json").read_text())
original=copy.deepcopy(state)
request={
  "event":{"id":"STORY-TEST-PREPARATION","source":"Проверяемое учебное сюжетное решение",
           "summary":"Вне боя: восстановлено снаряжение, учтены компоненты и истощение"},
  "characters":{
    "yar":{"exhaustion":2,"armor_class":"19 в надетых латах",
           "item_status":{"yar-source-row-47":"Экипированы"}},
    "daphne":{"new_items":[{
       "id":"narrative-test-ladle","name":"Позолоченный половник",
       "quantity":1,"value_gp":500,"component_for":"tashasBubblingCauldron",
       "status":"При себе"
    }]},
    "lyutobor":{"new_items":[{
       "id":"narrative-test-diamond","name":"Алмаз",
       "quantity":1,"value_gp":300,"component_for":"revivify",
       "status":"При себе"
    }]}
  }
}
tx=changes_to_transaction(state,request)
assert state==original, "creation must never mutate canonical data"
assert tx["expected_state_revision"]==32
assert tx["event"]["id"]=="STORY-TEST-PREPARATION"
after=build_result(state,tx)
assert after["characters"]["yar"]["combat_continuity"]["exhaustion"]==2
assert after["characters"]["yar"]["character_sheet"]["armor_class"]=="19 в надетых латах"
assert after["characters"]["daphne"]["inventory_catalog"]["narrative-test-ladle"]["value_gp"]==500
assert after["characters"]["lyutobor"]["inventory_catalog"]["narrative-test-diamond"]["value_gp"]==300
assert state==original, "preview must not mutate canonical data"
from build_party_combat_pack import build
sample_cap={"counters":[]}
updated_pack=build(after,sample_cap)
assert updated_pack["continuity"]["exhaustion"]["yar"]==2
assert updated_pack["profiles"]["daphne"]["casting"]["components"]["tashasBubblingCauldron"]=={
    "itemId":"narrative-test-ladle","valueGp":500
}
assert updated_pack["profiles"]["lyutobor"]["casting"]["components"]["revivify"]=={
    "itemId":"narrative-test-diamond","valueGp":300
}
# A previously unknown character can join with a verified portable data profile.
guest_state=copy.deepcopy(state)
guest=copy.deepcopy(guest_state["characters"]["rada"])
guest["name"]="Учебный союзник"
guest["combat_profile"]=copy.deepcopy(build(state,sample_cap)["profiles"]["rada"])
guest["inventory"]=[]
guest["inventory_catalog"]={}
guest["resources"]={"hp":{"current":30,"max":30}}
guest_state["characters"]["guest"]=guest
guest_pack=build(guest_state,sample_cap)
assert "guest" in guest_pack["characters"] and "guest" in guest_pack["profiles"]

fatal=changes_to_transaction(state,{"event":{"id":"STORY-TEST-FATAL-EXHAUSTION",
       "summary":"Учебная смерть от шестого истощения","source":"Подтверждённое сюжетное решение"},
    "characters":{"yar":{"exhaustion":6}}})
fallen=build_result(state,fatal)["characters"]["yar"]
assert fallen["resources"]["hp"]["current"]==0
assert fallen["combat_continuity"]["exhaustion"]==6
assert fallen["combat_continuity"]["life"]["dead"] is True
try:
    changes_to_transaction(state,{"event":request["event"],
      "characters":{"daphne":{"item_quantity":{"invented-item":1}}}})
except ValueError:
    pass
else:
    raise AssertionError("unknown items cannot be conjured by quantity edit")
print("STORY PREPARATION OK: transaction, confirmed components, exhaustion, rollback")
