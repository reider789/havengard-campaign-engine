#!/usr/bin/env python3
"""Create SDK combat packs from versioned declarative hero and NPC templates.

Canonical sheets, inventory, resources and story continuity remain authoritative.
Mechanical templates register reviewed handlers; no special hero-name code paths.
"""
from pathlib import Path
import argparse, copy, hashlib, json, re

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "prototypes/shared-combat/party-profile-templates.json"
BASE_RESOURCES = {"hp", "focus", "luck", "heroic", "arrows", "unusual_metabolism", "spell_slots"}
STATS = dict(zip(["СИЛ", "ЛОВ", "ТЕЛ", "ИНТ", "МДР", "ХАР"],
                 ["STR", "DEX", "CON", "INT", "WIS", "CHA"]))
CONSUMABLES = {
    "Противоядие":"antitoxin", "Алхимический огонь":"alchemistFire",
    "Кислота":"acid", "Дымовая бомба":"smoke",
    "Зелье скорости":"speedPotion", "Зелье героизма":"heroismPotion",
    "Зелье сопротивления огню":"fireResistance", "Зелье роста":"growthPotion",
    "Зелье силы холмового великана":"giantStrength",
    "Зелье лазания":"climbingPotion", "Яд быстрого хищника":"poison",
}

def prepared_component(catalog, spell, spec):
    word=spec["name_contains"].lower()
    minimum=spec["minimum_gp"]
    for item_id,item in catalog.items():
        value=item.get("value_gp")
        status=item.get("status","").lower()
        if (type(item.get("quantity")) is not int or item["quantity"]<1
            or any(x in status for x in ("личный резерв","в переносной дыре","не при себе"))
            or word not in item.get("name","").lower()
            or item.get("component_for") not in (None,spell)
            or type(value) is not int or value<minimum):
            continue
        return {"itemId":item_id,"valueGp":value}
    return False

def level_feature(formula, level):
    known={
        "level":lambda:level,
        "halfLevelUp":lambda:(level+1)//2,
        "levelAtLeast11":lambda:level>=11,
        "fighterAttacks":lambda:4 if level>=20 else 3 if level>=11 else 2 if level>=5 else 1
    }
    if formula not in known:raise ValueError("Неизвестная формула уровня: "+formula)
    return known[formula]()

def equipped(catalog, spec):
    name=spec["name_contains"].lower()
    required=spec.get("must_have","").lower()
    excluded=spec.get("must_not_have","").lower()
    return any(
        type(item.get("quantity")) is int and item["quantity"]>0 and
        name in item.get("name","").lower() and
        required in item.get("status","").lower() and
        (not excluded or excluded not in item.get("status","").lower()) and
        not any(x in item.get("status","").lower() for x in
                ("личный резерв","в переносной дыре","не при себе"))
        for item in catalog.values()
    )

def combat_inventory(catalog):
    inventory=[]
    consumables={}
    for item_id,item in catalog.items():
        quantity=item.get("quantity")
        if type(quantity) is not int:continue
        name=item.get("name",item_id)
        available=not any(x in item.get("status","").lower() for x in
                          ("личная собственность","личный резерв","в переносной дыре","не надеты"))
        record={"id":item_id,"name":name,"quantity":quantity,"combat_available":available}
        if "лечебное зелье" in name.lower():
            bigger="Улучшенное" in name
            record.update(consumable_type="healing",healing_dice=4 if bigger else 2,
                          healing_flat=4 if bigger else 2)
        if name in CONSUMABLES:consumables[item_id]=CONSUMABLES[name]
        inventory.append(record)
    return inventory,consumables

def build(state, capabilities):
    templates=json.loads(TEMPLATES.read_text(encoding="utf-8"))
    if templates.get("schema_version")!=1:raise ValueError("Несовместимые шаблоны боевых карточек")
    resource_names=BASE_RESOURCES|set(capabilities["counters"])
    profiles={}
    characters={}
    for char_id,hero in state["characters"].items():
        definition=templates["heroes"].get(char_id)
        if definition:
            sheet=hero["character_sheet"]
            p=copy.deepcopy(definition["profile"])
            binds=definition.get("bindings",{})
            level=sheet["level"]
            source=hero["resources"]
            resource={key:copy.deepcopy(value) for key,value in source.items() if key in resource_names}
            catalog=hero["inventory_catalog"]
            p["name"]=hero["name"]
            p["hp"]=resource["hp"]["max"]
            p["ac"]=int(re.match(r"\d+",sheet["armor_class"])[0])
            p["scores"]={STATS[key]:int(re.match(r"\d+",value)[0])
                         for key,value in sheet["abilities"].items()}
            p["proficiency"]=2+(level-1)//4
            for feature,formula in binds.get("level_features",{}).items():
                p.setdefault("features",{})[feature]=level_feature(formula,level)
            for key,rule in binds.get("equipment_status",{}).items():
                section=p["features"] if key in p.get("features",{}) else p.setdefault("equipment",{})
                active=equipped(catalog,rule)
                if "value" in rule:
                    if active:section[key]=rule["value"]
                    else:section.pop(key,None)
                else:section[key]=active
            if p.get("casting"):
                p["casting"]["level"]=level
                p["casting"]["prepared"]=copy.deepcopy(sheet.get("prepared_spell_ids",p["casting"]["prepared"]))
                if binds.get("spellbook_extensions"):
                    extras=sheet.get(binds["spellbook_extensions"],[])
                    p["casting"]["book"]=list(dict.fromkeys(p["casting"].get("book",[])+extras))
                if binds.get("recovery_levels"):
                    p["casting"]["recoveryLevels"]=level_feature(binds["recovery_levels"],level)
                for spell,spec in binds.get("component_spells",{}).items():
                    p["casting"].setdefault("components",{})[spell]=prepared_component(catalog,spell,spec)
            p["reference"]=[]
            for row in sheet.get("combat_reference",[]):
                cells=row.get("cells",[])
                if cells and cells[0]:
                    p["reference"].append({"name":str(cells[0]),
                      "text":" · ".join(str(x) for x in cells[1:5] if x),
                      "source_row":row.get("source_row")})
            p["reference"] += [{"name":item["name"],"text":item.get("description",""),
                                "status":item.get("status",""),"inventory_id":item_id}
                               for item_id,item in catalog.items()]
            p["tokenKey"]="heroes."+char_id
        elif isinstance(hero.get("combat_profile"),dict):
            p=copy.deepcopy(hero["combat_profile"])
            resource=copy.deepcopy(hero["resources"])
            catalog=hero.get("inventory_catalog",{})
        else:
            continue
        inventory,consumables=combat_inventory(catalog)
        if definition:p.setdefault("equipment",{})["consumables"]=consumables
        profiles[char_id]=p
        characters[char_id]={"name":hero["name"],"profile":char_id,
                             "resources":resource,"inventory":inventory}
    for npc_id,p in templates.get("npc_profiles",{}).items():
        if npc_id in profiles:raise ValueError("Конфликт ID профиля: "+npc_id)
        profiles[npc_id]=copy.deepcopy(p)
    arena=copy.deepcopy(templates["training_encounter"])
    for hero_id in arena["heroes"]:
        if hero_id not in characters:raise ValueError("Нет героя для учебного поля: "+hero_id)
    occupied={x["cell"] for x in arena["heroes"].values()} | {x["cell"] for x in arena["enemies"]}
    occupied.update(arena.get("walls",[]))
    for hero_id in characters:
        if hero_id not in arena["heroes"]:
            cell=next((chr(65+x)+str(y+1) for y in range(arena["height"])
                       for x in range(arena["width"])
                       if chr(65+x)+str(y+1) not in occupied),None)
            if not cell:raise ValueError("Нет свободной позиции для дополнительного героя")
            arena["heroes"][hero_id]={"cell":cell}
            occupied.add(cell)
    cid=state["campaign"]["id"]
    pack={
        "kind":"dnd-combat-pack", "version":1, "api":1, "id":cid,
        "revision":state["state_revision"],"name":"Хейвенгард · полная партия",
        "rules_version":"dnd-2024-2026-10",
        "requires":["spellcasting","magicItems","advancedClasses"],
        "abilities":{},"profiles":profiles,"characters":characters,
        "default_encounter":"party-training",
        "encounters":{"party-training":arena},
        "source_state_sha256":hashlib.sha256(json.dumps(state,ensure_ascii=False,sort_keys=True,
                          separators=(",",":")).encode()).hexdigest(),
        "notes":["Учебная встреча не является сыгранным событием. Все герои управляются игроком.",
                 "КД, компоненты, готовые заклинания и доступные предметы проверяются по текущему состоянию."]
    }
    clock=state.get('world',{}).get('timekeeping',{}).get('elapsed_seconds_from_anchor',0)
    continuity={'effects':[],'temporary_hp':{},'temp_sources':{},'statuses':{},'objects':[],'zones':[],'life':{},'cauldron_vials':[]}
    for key in characters:
        saved=state['characters'][key].get('combat_continuity',{})
        if saved.get('exhaustion',0):
            continuity.setdefault('exhaustion',{})[key]=saved['exhaustion']
        continuity['temporary_hp'][key]=saved.get('temporary_hp',0)
        continuity['temp_sources'][key]=saved.get('temp_source')
        if saved.get('life'):continuity['life'][key]=saved['life']
        # These phials are distinct spell-created inventory, not ordinary loot.
        # Preserve source, owner and current holder, without merging quantities.
        for vial in saved.get('cauldron_vials',[]):
            if vial.get('owner')!=key or vial.get('holder') not in characters:
                raise ValueError('Некорректный владелец или держатель зелья котла')
            continuity['cauldron_vials'].append(vial)
        continuity['statuses'][key]=[{**z,**({'until':z['expires_at']-clock} if 'expires_at' in z else {})} for z in saved.get('statuses',[]) if 'expires_at' not in z or z['expires_at']>clock]
        for x in saved.get('effects',[]):
            remaining=x['expires_at']-clock
            if remaining>0:continuity['effects'].append({**x,'until':remaining})
    live={x['id'] for x in continuity['effects']}
    # Spatial magic stays on its original field. Restore that field verbatim;
    # moving it to another scene requires an explicit new placement/ending.
    spatial_owners=[c.get('combat_continuity',{}) for c in state['characters'].values()
                    if any(o['id'] in live and o.get('hp',0)>0 for o in c.get('combat_continuity',{}).get('objects',[]))
                    or any(z.get('effect') in live and z.get('expires_at',0)>clock for z in c.get('combat_continuity',{}).get('zones',[]))]
    scenes=[c.get('scene') for c in spatial_owners if c.get('scene')]
    spatial=bool(spatial_owners)
    arena=pack['encounters']['party-training']
    if scenes and spatial:
        spatial_owners.sort(key=lambda c:c.get('recorded_at',0))
        scenes=[c['scene'] for c in spatial_owners if c.get('scene')]
        scene=scenes[-1]
        geometry=('id','width','height','walls','rubble','cover')
        if any(any(s[k]!=scene[k] for k in geometry) for s in scenes):raise ValueError('Продолжение содержит разные поля боя')
        positions={uid:p for s in scenes for uid,p in s['positions'].items()}
        summon_ids={u['id'] for key in characters for u in state['characters'][key].get('combat_continuity',{}).get('summons',[]) if u.get('hp',0)>0}
        # Absent heroes' old, empty scenes are history, not live spatial magic.
        scene={**scene,'positions':{uid:p for uid,p in positions.items() if uid in characters or uid in summon_ids}}
        continuity['scene']=scene
        arena.update({k:scene[k] for k in ('width','height')})
        arena['scene_id']=scene['id']
        arena['walls']=[chr(65+int(p.split(',')[0]))+str(1+int(p.split(',')[1])) for p in scene['walls']]
        arena['rubble']=[chr(65+int(p.split(',')[0]))+str(1+int(p.split(',')[1])) for p in scene['rubble']]
        arena['cover']={chr(65+int(p.split(',')[0]))+str(1+int(p.split(',')[1])):v for p,v in scene['cover'].items()}
        if scene.get('elevation'):
            arena['elevation']={chr(65+int(p.split(',')[0]))+str(1+int(p.split(',')[1])):v for p,v in scene['elevation'].items()}
        for uid,p in scene['positions'].items():
            if uid in arena['heroes']:arena['heroes'][uid]['cell']=chr(65+p['x'])+str(1+p['y'])
        taken={chr(65+p['x'])+str(1+p['y']) for p in scene['positions'].values()}|set(arena['walls'])
        # Heroes absent from the preceding fight need a free entry position;
        # their default training cell can collide with the restored field.
        for uid,hero in arena['heroes'].items():
            if uid in scene['positions']:continue
            cell=hero['cell']
            if cell in taken or ord(cell[0])-65>=arena['width'] or int(cell[1:])>arena['height']:
                cell=next(chr(65+x)+str(y+1) for y in range(arena['height']) for x in range(arena['width']) if chr(65+x)+str(y+1) not in taken)
                hero['cell']=cell
            taken.add(cell)
        for enemy in arena['enemies']:
            cell=enemy['cell']
            if cell in taken or ord(cell[0])-65>=arena['width'] or int(cell[1:])>arena['height']:
                cell=next(chr(65+x)+str(y+1) for y in range(arena['height']) for x in range(arena['width']) if chr(65+x)+str(y+1) not in taken)
                enemy['cell']=cell
            taken.add(cell)
    occupied={v['cell'] for v in pack['encounters']['party-training']['heroes'].values()}
    for key in characters:
        saved=state['characters'][key].get('combat_continuity',{})
        continuity['objects'] += [o for o in saved.get('objects',[]) if o['id'] in live and o.get('hp',0)>0]
        continuity['zones'] += [{**z,'until':z['expires_at']-clock} for z in saved.get('zones',[]) if z.get('effect') in live and z.get('expires_at',0)>clock]
        for u in saved.get('summons',[]):
            if u.get('hp',0)<=0:continue
            uid=u['id'];profile=dict(name=u['name'],hp=u['max'],initialHP=u['hp'],ac=u['ac'],speed=u['speed'],size=u['size'],scores={k:10+2*v for k,v in u['stats'].items()},saves=u['saves'],proficiency=u['proficiency'],features=u['features'],attacks=u['attacks'],summoner=key,summonLevel=u['summonLevel'],summonDC=u['summonDC'],creatureType=u['creatureType'],powerAvailable=u['powerAvailable'])
            continuity['temporary_hp'][uid]=u.get('persistent_temp',u.get('temp',0))
            continuity['temp_sources'][uid]=u.get('persistent_temp_source',u.get('tempSource'))
            continuity['statuses'][uid]=[{**z,**({'until':z['expires_at']-clock} if 'expires_at' in z else {})} for z in u.get('persistent_statuses',[]) if 'expires_at' not in z or z['expires_at']>clock]
            if u.get('persistent_life'):continuity['life'][uid]=u['persistent_life']
            profiles[uid]=profile
            position=continuity.get('scene',{}).get('positions',{}).get(uid)
            free=(chr(65+position['x'])+str(1+position['y'])) if position else next(chr(65+x)+str(y+1) for y in range(arena['height']) for x in range(arena['width']) if chr(65+x)+str(y+1) not in occupied and chr(65+x)+str(y+1) not in arena['walls'] and chr(65+x)+str(y+1) not in {v['cell'] for v in arena['enemies']})
            occupied.add(free);pack['encounters']['party-training']['heroes'][uid]=dict(profile=uid,cell=free,controlled=True)
    pack['campaign_clock']=clock
    pack['continuity']=continuity
    return pack
if __name__=='__main__':
    import subprocess
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True);p.add_argument('--engine-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    cap=json.loads(subprocess.check_output(['node',str(a.engine_root/'sdk/cli.js'),'capabilities'],text=True));pack=build(json.loads(a.state.read_text()),cap);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(pack,ensure_ascii=False,indent=2)+'\n');print(a.output)
