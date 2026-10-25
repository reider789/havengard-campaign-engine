#!/usr/bin/env python3
"""Canonical party adapter. Levels and prepared spell IDs come from authoritative state.

Level-11 abilities that are not registered by the pinned shared core MUST fail
pack validation, not silently disappear. See docs/LEVEL_11_SYNC_2026-10-25.md.
"""
from pathlib import Path
import argparse,hashlib,json,re
BASE_RESOURCES={"hp","focus","luck","heroic","arrows","unusual_metabolism","spell_slots"}
STATS=dict(zip(['СИЛ','ЛОВ','ТЕЛ','ИНТ','МДР','ХАР'],['STR','DEX','CON','INT','WIS','CHA']))
def attack(id,name,bonus,count,die,flat,kind='melee',damageType='slashing',range=5,**kw):return dict(id=id,name=name,bonus=bonus,count=count,die=die,flat=flat,kind=kind,damageType=damageType,range=range,**kw)
def build(state,capabilities):
    RESOURCES=BASE_RESOURCES|set(capabilities["counters"])
    cid=state['campaign']['id'];profiles={};characters={}
    spell_wizard=['mageArmor','magicMissile','thunderwave','fogCloud','scorchingRay','mistyStep','fireball','slow','counterspell','dimensionDoor','greaterInvisibility','coneCold','seeming','holdMonster','bigbyHand']
    spell_paladin=['bless','cureWounds','heroism','command','compelledDuel','protectionEvil','shieldFaith','aid','lesserRestoration','zoneTruth','wardingBond','beaconHope','dispelMagic','crusaderMantle','auraVitality','divineSmite','findSteed']
    for key in ['yar','daphne','lyutobor','rada']:
        c=state['characters'][key];sh=c['character_sheet'];r={k:v for k,v in c['resources'].items() if k in RESOURCES}
        inv=c['inventory_catalog']; scores={STATS[k]:int(re.match(r'\d+',v)[0]) for k,v in sh['abilities'].items()}
        p=dict(name=c['name'],hp=r['hp']['max'],ac=int(re.match(r'\d+',sh['armor_class'])[0]),speed=30,scores=scores,proficiency=4,features={},attacks=[],deathSaves=True,equipment={},reference=[])
        for row in sh.get('combat_reference',[]):
            cells=row.get('cells',[])
            if cells and cells[0]:p['reference'].append({'name':str(cells[0]),'text':' · '.join(str(x) for x in cells[1:5] if x),'source_row':row.get('source_row')})
        p['reference'] += [{'name':i['name'],'text':i.get('description',''),'status':i.get('status',''),'inventory_id':iid} for iid,i in inv.items()]
        inventory=[];consumables={}
        kinds={'Противоядие':'antitoxin','Алхимический огонь':'alchemistFire','Кислота':'acid','Дымовая бомба':'smoke','Зелье скорости':'speedPotion','Зелье героизма':'heroismPotion','Зелье сопротивления огню':'fireResistance','Зелье роста':'growthPotion','Зелье силы холмового великана':'giantStrength','Зелье лазания':'climbingPotion','Яд быстрого хищника':'poison'}
        for iid,i in inv.items():
            qty=i.get('quantity')
            if not isinstance(qty,int):continue
            available=not any(s in i.get('status','').lower() for s in ['личная собственность','личный резерв','в переносной дыре','не надеты'])
            z=dict(id=iid,name=i['name'],quantity=qty,combat_available=available)
            if 'лечебное зелье' in i['name'].lower():z['consumable_type']='healing';z['healing_dice']=4 if 'Улучшенное' in i['name'] else 2;z['healing_flat']=4 if 'Улучшенное' in i['name'] else 2
            if i['name'] in kinds:consumables[iid]=kinds[i['name']]
            inventory.append(z)
        p['equipment']['consumables']=consumables
        if key=='yar':
            p['saves']=dict(STR=10,DEX=2,CON=8,INT=0,WIS=2,CHA=0)
            p['skills']=dict(athletics=9,acrobatics=5,perception=5,insight=5,survival=5,intimidation=3)
            p['features']=dict(fighterLevel=sh['level'],secondWind=True,actionSurge=True,tacticalMind=True,tacticalShift=True,indomitable=True,knowEnemy=True,extraAttack=3 if sh['level'] >= 11 else 2,greatWeaponFighting=True,greatWeaponMaster=4,savageAttacker=True,tacticalMaster=True,superiorityDie=10,maneuverDC=17,maneuvers=['precision','trip','push','goad','maneuvering','riposte','bait'],masteries=['graze','sap'],acReaction=3,heavyArmorReduction=4,heavyArmor=False)
            p['attacks']=[attack('accurateSword','Меч Меткого Удара',12,2,6,6,ability='STR',mastery='graze',heavy=True,twoHanded=True,inventoryId='yar-source-row-45'),attack('stormThrower','Грозовой метатель',8,2,8,2,'ranged','lightning',240,normalRange=90,ammoCounter='storm_thrower_ammo'),attack('forgeMaul','Молот Великой Кузни',9,2,6,5,damageType='bludgeoning',ability='STR',heavy=True,twoHanded=True,inventoryId='yar-source-row-52'),attack('flail','Цеп',9,1,8,5,damageType='bludgeoning',ability='STR',mastery='sap',inventoryId='yar-source-row-46')]
            p['equipment'].update(rootPartner='daphne',forgeAttuned=False)
        elif key=='daphne':
            p['saveProficiencies']=['INT','WIS'];p['features']=dict(sculptSpells=True,potentCantrip=True,empoweredEvocation=True,shieldSpell=True,autoShield=True,alert=True)
            p['attacks']=[attack('staff','Посох',3,1,6,-1,damageType='bludgeoning',ability='STR')]
            p['casting']=dict(ability='INT',attack=11,dc=19,level=sh['level'],prepared=sh.get('prepared_spell_ids',spell_wizard),cantrips=['fireBolt','rayFrost','mindSliver','mageHand','prestidigitation'],book=['burningHands','web','dispelMagic','fly','wallFire','polymorph','resilientSphere','wallForce',*sh.get('new_spellbook_ids',[])],components={'tashasBubblingCauldron':False},recoveryLevels=(sh['level']+1)//2)
            p['equipment'].update(stormBracers=True,vaeltirFocus=True,leafPartner='yar')
        elif key=='lyutobor':
            p['saves']=dict(STR=4,DEX=0,CON=2,INT=-1,WIS=5,CHA=6)
            p['features']=dict(extraAttack=2,radiantStrikes=sh['level'] >= 11,masteries=['sap'],auraProtection=2,auraRadius=10,auraDevotion=True,auraCourage=True,guardianSaveBonus=1,critNegation=True,protection=True,shieldEquipped=True,heavyArmor=True,heavyArmorReduction=4,layOnHands=True,sacredWeapon=True,abjureFoes=True,shieldMaster=True,divineSmite=True)
            p['attacks']=[attack('longsword','Длинный меч',8,1,8,4,ability='STR',mastery='sap',inventoryId='lyutobor-source-row-57')]
            p['casting']=dict(ability='CHA',attack=6,dc=14,level=sh['level'],prepared=sh.get('prepared_spell_ids',spell_paladin),cantrips=[],components={'wardingBond':False,'protectionEvil':False,'revivify':False})
            p['equipment']['armor']=True
        else:
            p['saveProficiencies']=['DEX','INT'];p['skills']=dict(stealth=13,sleight=13,intimidation=10,perception=10,acrobatics=9,insight=6,investigation=4)
            p['skillProficiencies']={k:['DEX' if k in ['stealth','sleight','acrobatics'] else 'CHA' if k=='intimidation' else 'INT' if k=='investigation' else 'WIS',1] for k in p['skills']}
            p['features']=dict(sneakDice=6 if sh['level'] >= 11 else 5,improvedCunningStrike=sh['level'] >= 11,cunningAction=True,steadyAim=True,uncannyDodge=True,evasion=True,reliableTalent=True,sharpshooter=True,masteries=['vex','nick'],cunningStrike=True,cunningDC=17,stealthAttack=True,thiefHands=True,climbSpeed=30,poisonerKit=True,silentShadow=True,alert=True)
            p['attacks']=[attack('leafBow','Лук Последнего Листа',11,1,6,7,'ranged','piercing',320,normalRange=80,ability='DEX',mastery='vex',sneakEligible=True,ammo='arrows',ammoInventoryId='rada-source-row-43',inventoryId='rada-source-row-42'),attack('scimitar','Скимитар',9,1,6,5,ability='DEX',light=True,mastery='nick',sneakEligible=True,inventoryId='rada-source-row-44'),attack('shortsword','Короткий меч',9,1,6,5,damageType='piercing',ability='DEX',light=True,sneakEligible=True,inventoryId='rada-source-row-45'),attack('dagger','Кинжал',9,1,4,5,damageType='piercing',ability='DEX',light=True,sneakEligible=True,inventoryId='rada-source-row-46')]
        p['tokenKey']='heroes.'+key
        profiles[key]=p;characters[key]=dict(name=c['name'],profile=key,resources=r,inventory=inventory)
    profiles['raider']=dict(name='Налётчик',hp=42,ac=14,speed=30,scores=dict(STR=14,DEX=14,CON=12,INT=10,WIS=10,CHA=8),proficiency=2,features={},attacks=[attack('sword','Клинок',5,1,8,2)])
    pack=dict(kind='dnd-combat-pack',version=1,api=1,id=cid,revision=state['state_revision'],name='Хейвенгард · полная партия',rules_version='dnd-2024-2026-10',requires=['spellcasting','magicItems','advancedClasses'],abilities={},profiles=profiles,characters=characters,default_encounter='party-training',encounters={
      'party-training':dict(name='Хейвенгард · учебная встреча',kind='training',width=14,height=10,theme='forest',heroes={k:dict(cell=cell) for k,cell in zip(characters,['C4','B6','D5','C7'])},enemies=[dict(id='raider'+str(i+1),profile='raider',cell=cell) for i,cell in enumerate(['J3','K5','J7','L4','L8'])],walls=['G2','G3','G8','G9'],rubble=['G5','H5'],cover={'C4':5,'C7':5})},source_state_sha256=hashlib.sha256(json.dumps(state,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),notes=['Учебная встреча не является сыгранным событием. Все четыре героя управляются игроком. Текущий КД Яра 11: латы не надеты. Неподготовленные заклинания доступны в справочнике книги.'])
    clock=state.get('world',{}).get('timekeeping',{}).get('elapsed_seconds_from_anchor',0)
    continuity={'effects':[],'temporary_hp':{},'temp_sources':{},'statuses':{},'objects':[],'zones':[],'life':{}}
    for key in characters:
        saved=state['characters'][key].get('combat_continuity',{})
        continuity['temporary_hp'][key]=saved.get('temporary_hp',0)
        continuity['temp_sources'][key]=saved.get('temp_source')
        if saved.get('life'):continuity['life'][key]=saved['life']
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
