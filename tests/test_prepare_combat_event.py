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
try:
    changes_to_transaction(state,{"event":request["event"],
      "characters":{"yar":{"exhaustion":6}}})
except ValueError:
    pass
else:
    raise AssertionError("6 levels must require explicit death adjudication")
try:
    changes_to_transaction(state,{"event":request["event"],
      "characters":{"daphne":{"item_quantity":{"invented-item":1}}}})
except ValueError:
    pass
else:
    raise AssertionError("unknown items cannot be conjured by quantity edit")
print("STORY PREPARATION OK: transaction, confirmed components, exhaustion, rollback")
