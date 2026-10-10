#!/usr/bin/env python3
"""Build a read-only combat UI snapshot from canonical state. Never edits canonical files."""
from __future__ import annotations
import json, pathlib, re, datetime

ROOT=pathlib.Path(__file__).resolve().parents[2]
STATE=ROOT/"state/_campaign-state.json"
OUTPUT=ROOT/"prototypes/combat/runtime/latest.json"
PARTY=("yar","daphne","lyutobor","rada")
CONSUMABLES={
 "обычное лечебное зелье":"healing","улучшенное лечебное зелье":"greater_healing",
 "противоядие":"antitoxin","алхимический огонь":"fire","кислота":"acid",
 "дымовая бомба":"smoke","зелье скорости":"speed","зелье лазания":"climb",
 "зелье силы холмового великана":"giant","зелье сопротивления огню":"fire_resistance",
 "зелье роста":"growth","зелье героизма":"heroism",
 "яд быстрого хищника":"fast_poison","сигнальная ракета":"flare","металлическая ловушка":"trap"
}
HEADERS=("способности","атаки и боевые","заклинания","личный инвентарь")
SPELL_SECTION_MARKERS=("заклинания — боевая шпаргалка","заклинания — справка")
def identify(row, category):
    vals=row.get("cells") or []
    primary=next((str(v).strip() for v in vals if isinstance(v,str) and v.strip()),"")
    if not primary:return None
    lo=primary.lower()
    if any(x in lo for x in HEADERS):
        return ("heading",lo)
    if lo in ("способность","действие","предмет","заклинание","заклинания","ячейки и подготовка","стандартная подготовка — 15 из 15","книга заклинаний"):
        return None
    if category not in ("feature","spell","attack"):return None
    description=" · ".join(str(v) for v in vals[1:4] if v is not None and str(v).strip())
    if not description or (category=="attack" and primary in ("Инициатива","СЛ Хитрого удара")):return None
    return {"source_row":row.get("source_row"),"name":primary,"description":description[:900],
            "category":category,"available":"reference_only"}
def main():
    state=json.loads(STATE.read_text(encoding="utf-8"))
    payload={"schema_version":1,"kind":"Havengard battle UI read-only projection",
             "source_state_revision":state.get("state_revision"),"source_path":"state/_campaign-state.json",
             "policy":"Current canonical state is authoritative; this snapshot must never be written back as campaign truth",
             "characters":{}}
    for id in PARTY:
        c=state["characters"][id]
        sheet=c.get("character_sheet",{})
        rows=sheet.get("combat_reference",[])
        known=[]
        category=None
        for row in rows:
            first=str(next((v for v in row.get("cells",[]) if isinstance(v,str) and v.strip()),"")).lower()
            if "атаки и боевые действия" in first:category="attack";continue
            if "способности — описание" in first:category="feature";continue
            if "заклинания — боевая шпаргалка" in first:category="spell";continue
            if "личный инвентарь" in first:category=None
            item=identify(row,category)
            if item and item[0]!="heading" if isinstance(item,tuple) else bool(item):
                known.append(item)
        inventory=[]
        counters={}
        for source_key, item in c.get("inventory_catalog",{}).items():
            name=item.get("name","")
            kind=CONSUMABLES.get(name.strip().lower())
            count=item.get("quantity",0)
            inventory.append({"id":source_key,"name":name,"quantity":count,
                "status":item.get("status"),"description":item.get("description",""),
                "consumable_type":kind})
            if kind and isinstance(count,(int,float)) and count>0:
                counters[kind]=counters.get(kind,0)+int(count)
        payload["characters"][id]={"name":c.get("name",id),
            "class_and_level":sheet.get("class_and_level"),"level":sheet.get("level"),
            "armor_class":sheet.get("armor_class"),"stats":sheet.get("abilities",{}),
            "skills_attacks_spells":known,"inventory":inventory,
            "consumables":counters,"resources":c.get("resources",{}),
            "equipment_status":{x["id"]:x["status"] for x in inventory if any(w in x["name"].lower() for w in ("лат","брон","щит","меч","лук","метател","манти","плащ","фокус"))}}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=False)+"\n",encoding="utf-8")
    print("Wrote",OUTPUT,"state_rev",payload["source_state_revision"],"chars",len(payload["characters"]))
if __name__=="__main__": main()
