#!/usr/bin/env python3
"""Reproducible, noncanonical preparation from the reviewed 3.2 source.

The source is supplied explicitly, never fetched or silently replaced by this tool.
"""
from pathlib import Path
import argparse, copy, hashlib, json, re

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'prototypes/prepared-encounters/perelomye'
IDS='C03 C04 C05 C09 C10 C11 C12 C14 C18 C23 C24 C26 C29 C32 C33 C34 C36 C37'.split()
STATS=['STR','DEX','CON','INT','WIS','CHA']
def attack(key,name,bonus,count,die,flat,damage='piercing',reach=5,normal=None,kind=None):
    a=dict(id=key,name=name,bonus=bonus,count=count,die=die,flat=flat,damageType=damage,
           range=reach,kind=kind or ('ranged' if normal else 'melee'))
    if normal:a['normalRange']=normal
    return a
def generate(src):
    data=json.loads(src.read_text());assert data['version']=='3.2'
    rooms={r['id']:r for m in data['modules'] for r in m['rooms']}
    cards={k:copy.deepcopy(data['creatures'][k]) for k in IDS}
    profiles={}
    for key,c in cards.items():
        p=dict(name=c['name'],hp=c['hp'],ac=c['ac'],speed=int(re.match(r'\d+',c['speed'])[0]),
          proficiency=3,scores={s:max(1,10+2*v) for s,v in zip(STATS,c['abilities'])},
          saves=dict(zip(STATS,c['abilities'])),skills={'perception':c['perception']-10},
          senses={},features={},attacks=[],reference=['prepared:'+key]+[
           label+': '+c[field] for label,field in [('Действия','action'),('Бонусное действие','bonus'),
            ('Реакция','reaction'),('Особенности','extra'),('Защита','defenses'),('Чувства','senses'),
            ('Языки','language'),('Навыки','skills'),('Поведение','behavior'),('Имущество','gear')]],
          tokenKey='enemies.prepared_'+key,creatureType='humanoid',
          tactics={'role':'guardian','canFlee':False,'hold':True})
        if key in ['C09','C14','C18','C29','C32','C34']:p.update(size=3,footprint=2)
        if key=='C33':p.update(size=4,footprint=3)
        profiles[key]=p
    def attacks(k,*args,n=1):
        profiles[k]['attacks']=list(args)
        if n>1:profiles[k]['features']['extraAttack']=n
    attacks('C03',attack('tool','Инструмент',2,1,4,0,'bludgeoning'))
    attacks('C04',attack('hammer','Молоток',3,1,4,1,'bludgeoning'),attack('crossbow','Арбалет',4,1,8,2,reach=320,normal=80))
    attacks('C05',attack('spear','Копьё',5,1,6,3),attack('spear-thrown','Бросок копья',5,1,6,3,reach=60,normal=20),n=2)
    # Existing live G5 profile remains byte-for-byte the source of this reusable card.
    live=json.loads((ROOT/'prototypes/chat-combat/story/enemy-profiles.json').read_text())['profiles']['garden_thread_strangler']
    profiles['C09']={**copy.deepcopy(live),'reference':profiles['C09']['reference'],'tokenKey':'enemies.prepared_C09'}
    # The stock contract requires range >=5. The extension enforces shared space;
    # this profile must NEVER be loaded without the required extension.
    attacks('C10',attack('sting','Ужаления: только общее пространство',6,4,4,0))
    attacks('C11',attack('sickle','Серп',5,1,6,3,'slashing'),attack('shortbow','Короткий лук',5,1,6,3,reach=320,normal=80))
    attacks('C12',attack('bite','Укус',6,1,8,3),n=2)
    attacks('C14',attack('sting','Жало',7,2,8,4,reach=10))
    attacks('C18',attack('arm','Захватный рычаг',8,2,8,5,'bludgeoning',10),n=2)
    attacks('C23',attack('sword','Меч',8,1,8,4,'slashing'),attack('crossbow','Лёгкий арбалет',6,1,8,2,reach=320,normal=80),n=3)
    attacks('C24',attack('dagger','Кинжал',4,1,4,2))
    attacks('C26',attack('rapier','Рапира',5,1,8,3))
    attacks('C29',attack('pseudopod','Ложноножка',7,2,6,4,'bludgeoning',10),n=2)
    attacks('C32',attack('voice','Режущий глас',10,3,8,4,'psychic',90,kind='rangedSpell'),attack('hand','Удар рукой',6,1,6,2,'bludgeoning'),n=2)
    attacks('C33',attack('claw','Когти',12,2,10,7,'slashing',10),attack('beak','Клюв',12,3,10,7,reach=15),attack('tail','Хвост',12,2,10,7,'bludgeoning',15),n=3)
    attacks('C34',attack('arm','Манипулятор',10,2,8,6,'bludgeoning',10),attack('impulse','Силовой импульс',10,3,8,4,'force',180,90),n=3)
    attacks('C36',attack('blade','Клинок оболочки',7,2,6,3,'slashing'))
    attacks('C37',attack('halberd','Алебарда',7,2,8,3,'slashing',10),attack('crossbow','Арбалет',7,1,10,3,reach=320,normal=80))
    for key,kind in {'C09':'plant','C10':'beast','C12':'monstrosity','C14':'monstrosity','C18':'construct','C29':'ooze','C32':'undead','C33':'monstrosity','C34':'construct','C36':'construct','C37':'construct'}.items():profiles[key]['creatureType']=kind
    for key,typ in [('C10',['bludgeoning','piercing','slashing']),('C14',['lightning']),('C32',['necrotic']),('C33',['lightning'])]:profiles[key]['resistances']=typ
    for key in ['C18','C32','C34','C36','C37']:profiles[key]['immunities']=['poison'];profiles[key]['conditionImmunities']=['poisoned']
    profiles['C10']['conditionImmunities']=['prone','restrained']
    profiles['C29']['conditionImmunities']=['charmed','frightened','prone']
    for key,vision in [('C12',60),('C18',60),('C32',120),('C33',90),('C34',90),('C36',60),('C37',60)]:profiles[key]['senses']['darkvision']=vision
    profiles['C29']['senses']={'blindsight':30,'blindBeyondBlindsight':True}
    for key in ['C32','C33','C34']:
        profiles[key]['saves']=dict(zip(STATS,{'C32':[2,7,7,8,7,10],'C33':[12,7,11,-2,8,0],'C34':[10,0,9,7,8,1]}[key]))
        profiles[key]['proficiency']=4 if key!='C33' else 5
    for key,skills in {'C04':{'artisanTools':6,'investigation':5,'perception':4},'C11':{'nature':5,'survival':5,'perception':5},'C23':{'perception':5},'C24':{'investigation':6,'insight':5,'persuasion':5},'C26':{'deception':7,'persuasion':7,'insight':5},'C32':{'perception':7,'insight':7,'arcana':8},'C34':{'perception':8,'insight':8,'investigation':7}}.items():profiles[key]['skills']=skills
    for key,prof in {'C03':2,'C04':2,'C05':2,'C10':2,'C11':2,'C23':4,'C24':2,'C26':2,'C36':4,'C37':4}.items():profiles[key]['proficiency']=prof
    profiles['C32']['casting']=dict(ability='CHA',attack=10,dc=18,level=11,prepared=['mistyStep','counterspell'],cantrips=[],components=True)
    rules={key:{'movement':{'walk':p['speed']},'ammo':{},'uses':{},'actions':{}} for key,p in profiles.items()}
    for key,c in cards.items():rules[key]['noReaction']=c['reaction'].strip()=='Нет.'
    def action(k,id,name,cost,op,**kw):rules[k]['actions'][id]=dict(name=name,cost=cost,op=op,**kw)
    def save(k,id,name,stat,dc,dice,typ,**kw):action(k,id,name,kw.pop('cost','action'),'saveDamage',stat=stat,dc=dc,dice=dice,damageType=typ,half=kw.pop('half',True),**kw)
    for k,speeds in {'C09':{},'C10':{'fly':40},'C11':{'climb':20},'C12':{'climb':30},'C14':{'fly':50,'swim':40},'C29':{'climb':20},'C33':{'fly':80,'swim':40}}.items():rules[k]['movement'].update(speeds)
    for k,r in rules.items():
        if 'climb' in r['movement']:profiles[k]['features']['climbSpeed']=r['movement']['climb']
    for k,ammo in {'C04':{'crossbow':10},'C05':{'spear-thrown':2},'C11':{'shortbow':12},'C23':{'crossbow':20},'C37':{'crossbow':12}}.items():rules[k]['ammo']=ammo
    rules['C10'].update(sharedSpace=True,onHit={'sting':{'stat':'CON','dc':13,'condition':'poisoned','duration':'target-next-end'}},halfHPAttack={'attack':'sting','threshold':18,'count':2})
    rules['C12']['uses']={'dust':1};action('C12','dust','Пылевое облако: радиус 10 фт','action','obscure',radius=10,resource='dust',duration='source-next-start')
    rules['C14']['uses']={'discharge':1};save('C14','discharge','Разряд: линия 30×5 фт','DEX',15,[4,6,0],'lightning',resource='discharge',shape='line',length=30,width=5)
    rules['C14']['riders']={'sting':[[1,6,0,'lightning']]};rules['C14']['recharge']={'resource':'discharge','min':6,'max':1}
    action('C05','push','Вместо второй атаки: толчок 5 фт','attack','pushSave',stats=['STR','DEX'],dc=13,distance=5,range=5,attackIndex=2)
    action('C18','grapple','Вместо рычага: захват','attack','grappleSave',stats=['STR','DEX'],dc=16,range=10,maxSize=2,maxTargets=2)
    action('C18','power-off','Аварийное отключение линии','action','adjudication',reference=cards['C18']['action'])
    rules['C29']['riders']={'pseudopod':[[1,6,0,'acid']]};action('C29','grapple','Захват при попадании','onHit','grappleSave',stats=['STR','DEX'],dc=15,range=10,maxTargets=1)
    rules['C29']['squeezeGapFeet']=1
    action('C23','parry','Парирование +3 КД на одно попадание','reaction','parry',amount=3)
    rules['C23']['attackAlternatives']={'sword':3,'crossbow':1}
    for k,limit,threshold,hpcost,obj in [('C32',2,175,10,True),('C33',3,210,15,False),('C34',3,195,0,True)]:
        rules[k].update(legendary={'max':3},resistance={'max':limit,'hpCost':hpcost,'objectCost':obj},phase={'threshold':threshold},uses={**rules[k]['uses'],'resistance':limit})
        action(k,'legend-move','Легендарное движение','legendary','move',points=1,distance=15 if k!='C33' else 0,halfFly=k=='C33',provokes=True)
        action(k,'resistance','Легендарная устойчивость','failedSave','resistance',resource='resistance',hpCost=hpcost,objectCost=obj)
    rules['C32']['uses'].update(chord=3,pause=2)
    save('C32','chord','Раскалывающий аккорд, III круг В/С','CON',18,[6,8,0],'thunder',resource='chord',spell=True,shape='cone',length=30)
    action('C32','pause','Пауза, III круг В/С','action','saveStatus',stat='WIS',dc=18,condition='incapacitated',rooted=True,resource='pause',range=90,hearing=True,spell=True,duration='source-next-start-or-damage')
    action('C32','legend-voice','Легендарный глас','legendary','attack',points=2,attack='voice')
    action('C32','activate','Настройка хора: существующая оболочка','legendary','activate',points=2,once=True,profile='C36')
    for k,slave in [('C32','C36'),('C34','C37')]:action(k,'command','Приказ: реакция активного подчинённого','legendary','command',points=1,once=True,profile=slave,range=60,distance=15)
    rules['C32']['phase'].update(objectsOff=2,riders={'voice':[[1,6,0,'thunder']]},loseSpell='counterspell')
    rules['C32']['hearingAttacks']=['voice'];rules['C32']['singleAttackAlternatives']=['hand']
    rules['C33']['uses']['breath']=3
    save('C33','breath','Заранее объявленное дыхание: конус 60 фт','DEX',18,[10,6,0],'lightning',resource='breath',shape='cone',length=60,requiresTelegraph=True)
    action('C33','prepare-breath','Объявить дыхание в конце своего хода','endOwnTurn','telegraph',length=60)
    action('C33','legend-tail','Легендарный хвост','legendary','attack',points=2,attack='tail')
    save('C33','wings','Удар крыльями: все остальные в 10 фт','STR',18,[1,8,0],'bludgeoning',cost='legendary',points=2,once=True,half=False,push=10,radius=10)
    rules['C33']['phase'].update(ac=17,fly=100,riders={'claw':[[1,6,0,'lightning']]})
    rules['C33']['recharge']={'resource':'breath','min':5,'max':3,'requiresUngroundedRod':True,'range':60}
    rules['C33']['attackSequence']=['claw','claw','beak'];rules['C33']['singleAttackAlternatives']=['tail']
    rules['C34']['riders']={'arm':[[1,6,0,'force']]}
    rules['C34']['phase'].update(objectsOff=3,ac=17,walk=40,riders={'arm':[[1,6,0,'force']]})
    rules['C34']['attackAlternatives']={'arm':3,'impulse':2}
    action('C34','grapple','Манипулятор: заменить весь урон попадания захватом','onHit','grappleSave',stats=['STR','DEX'],dc=18,range=10,maxSize=3,maxTargets=1,replaceDamage=True)
    action('C34','legend-arm','Легендарный манипулятор','legendary','attack',points=2,attack='arm')
    rules['C34']['shield']={'reduce':12,'requiresWorkingObject':True}
    # An explicitly authored preparation variant, not an additional person.
    # The two company guards reuse C05 combat numbers, but speak Common and
    # protect their contracted workers rather than a Shore settlement.
    company='C05_company';cards[company]=copy.deepcopy(cards['C05']);cards[company].update(id=company,name='Охранник компании «Мерная цепь»',language='Общий.',
      behavior='Профессиональная охрана работников по ограниченному договору. Проверяет приказ Ровена; не начинает бой за неудобный разговор. При незаконном приказе требует оснований. При половине отряда выведенной из боя прикрывает отход работников; сдаётся при обеспеченной безопасности.',
      gear='КД 16: щит и чешуйчатая броня; два копья, свисток. Подготовленный обычный комплект двух охранников, не новый гарнизон.')
    profiles[company]=copy.deepcopy(profiles['C05']);profiles[company].update(name=cards[company]['name'],tokenKey='enemies.prepared_'+company,
      reference=['prepared:'+company]+[f+': '+str(v) for f,v in cards[company].items() if isinstance(v,str)])
    rules[company]=copy.deepcopy(rules['C05'])
    scoped=['G1','G3','G4','G5','T3','T5','T8','L1','L3','L5','P9','B8','V4']
    encounters={}
    for rid in scoped:
        r=copy.deepcopy(rooms[rid]);enemies=r['spawns']
        # Positions for the two alternate-shift guards are not invented.
        policy='preserve-active-scene' if rid=='G5' else 'conditional' if rid in ['G1','G3','G4','L1','L3','L5','P9'] else 'story-trigger'
        encounters[rid]={'room':r,'triggerPolicy':'deployment-only-conditional-faction' if rid=='V4' else policy,'population':[{'id':s['id'],'profile':s['profile'],'x':s['x'],'y':s['y'],'condition':s['condition'],'active':not(rid=='T8' and s['profile']=='C36' and s['x']==4)} for s in enemies],
          'loot':{k:data['loot'][k] for k in r['loot'].split(',') if k},
          'hazards':{k:data['hazards'][k] for k in r['haz'].split(',') if k},'resetOnReturn':False}
    out=dict(kind='havengard-prepared-encounters',schema_version=1,version='1.0.0',preparation_only=True,
      source={'driveFileId':'1dvDee86foyIMMC55LvSmXck359hXVjvu','version':'3.2','sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'preparedOn':'2026-10-28'},
      engine={'repository':'reider789/rin_dnd','commit':'153b8447b0d77f700f006eb40b9725f1ac943e33','version':'30.7.1','requiredExtension':'perelomye-gm-assist-v1'},
      scope={'unvisited':['T','L','P8-P9','B7-B8'],'inProgress':'G','reuseOnly':['C14','C18'],'conditionalFaction':['C23','C24','C26','C05'],
       'excluded':['S','K','N','X','B1-B6 played','Gray adit independent'],
       'populationRules':['C36: четыре всего; две восточные активны, две западные неактивны.','C37: два всего.','C14: уже существующая пара B5, не новые противники B7/B8.','L: четыре C05 всего: два L1, два других посменно L5.','V: шесть городских стражей всего; усиление — перемещение, не спавн.','Именные NPC, рабочие и садовники нейтральны, пока реальные события не дают причину боя.']},
      profiles=profiles,rules=rules,cards=cards,encounters=encounters,
      bosses={k:data['bosses'][k] for k in ['BT','BB','BP']},
      npc_bindings=data['preparation_addendum'].get('npc_bindings',{}),
      reward_policy={'autoAward':False,'bossXP':'profile_xp/creature xp относится к самому боссу; boss.xp — сумма с конечной свитой, не добавлять оба значения.','noReset':True},
      faction_roster={'source':'Мастерская библия, §11.3; §9.8','presentOnlyIfPlayed':True,'company':{'C23':1,'C24':1,'workers_C03_C04_total':6,'guards_C05_company':2,'carts':2,'budget_gp':900},'C26':'Только при фактическом присутствии; не телепортируется к отряду.','guards_note':'Два охранника компании и шесть городских стражей — разные конечные составы. C05_company — явно подготовленный вариант C05: те же боевые числа, Общий язык, служебная мотивация и конечный обычный комплект; перед фактическим вводом сверить со сыгранной сценой.'},
      travelConstraints=['T5–T3: 4 минуты, не подкрепление за два раунда.','T4–T7: 20 минут; часовню из T4 не слышно.','C36 бросает личную инициативу d20+2 в начале боя; активация разрешает ход только со следующего раунда.'],
      adjudication={'mode':'gm-assisted','geometry':'Ведущий подтверждает состав целей, слышимость, полное укрытие, высоту, полёт и путь. Основное ядро имеет 2D поле; 3D физика не заявляется.',
       'canonicalState':'При подготовке не меняются время, ПЗ, ресурсы, награды или факт посещения. При старте требуется актуальный снимок и подтверждение размещения.',
       'scores':'В исходнике даны модификаторы. scores — представитель с тем же модификатором; точные saves/skills сохранены отдельно; -5 представлен значением 1.'})
    DEST.mkdir(parents=True,exist_ok=True)
    (DEST/'catalog.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);a=p.parse_args();d=generate(a.source)
    print(f"{len(d['profiles'])} profiles; {len(d['encounters'])} room templates; no canonical writes")
