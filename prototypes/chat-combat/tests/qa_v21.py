"""Regression: the packaged in-chat v21 engine, not a separate website."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML=(Path(__file__).resolve().parents[1]/'current-chat-battle.html').read_text(encoding='utf-8')
sample={
    'name':'Проверочная засада', 'kind':'story',
    'heroes':{'rada':{'cell':'E6','initiative':20},'daphne':{'cell':'B7','initiative':16},
              'lyutobor':{'cell':'D6','initiative':14},'yar':{'cell':'C6','initiative':12}},
    'walls':['G2','F4'], 'rubble':['E4'],
    'enemies':[{'name':'Шаман','cell':'H4','hp':44,'ac':15,'initiative':10,
                'attack':{'bonus':7,'count':2,'die':6,'flat':3,'range':30},
                'saves':{'STR':3,'DEX':2,'CON':4,'WIS':5},'abilities':['Проклятие']}],
}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1400,'height':1200})
    errors=[]
    page.on('pageerror', lambda e:errors.append(str(e)))
    page.evaluate('window.__HV_ENABLE_TEST_APIS=true;Math.random=()=>0.60')
    page.set_content(HTML)
    page.wait_for_timeout(120)
    api='window.__HV_TEST_API'
    assert page.locator('[data-tile]').count()==88
    initial=page.evaluate(f'{api}.snapshot()')
    assert initial['sourceRevision']==27, initial['sourceRevision']
    assert initial['units']['yar']['storm']==20
    assert initial['units']['daphne']['shieldFree']==1
    # Boot a second panel from a saved chat state containing active effects.
    # This previously threw: Cannot access 'v21EffectTitles' before initialization.
    restored=json.loads(json.dumps(initial))
    restored['effects']=[
        {'kind':'bless','owner':'lyutobor','targets':['yar'],'until':120,'concentration':True},
        {'kind':'mage','owner':'daphne','targets':['daphne'],'until':28800,'concentration':False},
    ]
    restored['inspected']='daphne'
    restored_html=HTML.replace(
        'const received=globalThis.__bindings?.value;',
        'const received={session:'+json.dumps(restored,ensure_ascii=False,separators=(',',':'))+'};',
        1,
    )
    assert restored_html!=HTML, 'Saved-state injection point is missing'
    resumed=browser.new_page()
    resume_errors=[]
    resumed.on('pageerror',lambda e:resume_errors.append(str(e)))
    resumed.set_content(restored_html)
    resumed.wait_for_timeout(120)
    assert resumed.locator('[data-tile]').count()==88, resume_errors
    assert 'Доспехи мага' in resumed.locator('#inspector').inner_text(), resume_errors
    resumed.locator('[data-inspect="yar"]').click()
    assert 'Благословение' in resumed.locator('#inspector').inner_text(), resume_errors
    assert not resume_errors, resume_errors
    resumed.close()
    # UX: no more than 9 visible buttons in the long Actions/All lists.
    visible=lambda: page.locator('#choices button.choice:visible').count()
    assert visible()<=9 and visible()>=1, ('actions page',visible())
    assert page.locator('#v21pager').count()==1
    first_page=[x.inner_text() for x in page.locator('#choices button.choice:visible').all()]
    if page.locator('[data-v21-page="1"]').is_enabled():
        page.locator('[data-v21-page="1"]').click()
        assert visible()<=9 and visible()>0
        assert [x.inner_text() for x in page.locator('#choices button.choice:visible').all()]!=first_page
        page.locator('[data-v21-page="-1"]').click()
        assert [x.inner_text() for x in page.locator('#choices button.choice:visible').all()]==first_page
    page.locator('#choices button[data-action="fireball"]').evaluate('(e)=>e.click()')
    assert 'Огненный шар' in page.locator('#v21guide').inner_text()
    assert 'ЛОВ СЛ 19' in page.locator('#v21guide').inner_text()
    # Active effects must be in Russian with readable meaning.
    page.evaluate(f'{api}.set(s=>{{s.effects.push({{kind:"bless",owner:"lyutobor",targets:["yar"],until:120,concentration:true}});s.effects.push({{kind:"mage",owner:"daphne",targets:["daphne"],until:28000,concentration:false}});s.inspected="yar";}})')
    assert 'Благословение' in page.locator('#inspector').inner_text()
    assert 'bless' not in page.locator('#inspector').inner_text()
    page.locator('[data-inspect="daphne"]').click()
    assert 'Доспехи мага' in page.locator('#inspector').inner_text()
    assert 'mage ·' not in page.locator('#inspector').inner_text()
    # Full reference has a preview and no silent expenditure of resources.
    page.locator('[data-tab="all"]').click()
    assert visible()<=9
    old=page.evaluate(f'{api}.snapshot().units.daphne.slots[5]')
    page.locator('[data-reference="Рука Бигби"]').evaluate('(e)=>e.click()')
    assert 'Рука Бигби' in page.locator('#v21guide').inner_text()
    assert len(page.locator('#v21guide').inner_text())>80
    assert page.evaluate(f'{api}.snapshot().units.daphne.slots[5]')==old
    page.locator('[data-tab="actions"]').click()
    assert visible()<=9
    # A 15 total vs AC 12 is a hit but Shield would raise AC to 17.
    page.evaluate(f'{api}.set(s=>{{s.units.lyutobor.reaction=0;s.units.daphne.reaction=1;s.units.daphne.shieldFree=1;}})')
    hp=page.evaluate(f'{api}.snapshot().units.daphne.hp')
    page.evaluate(f'{api}.attack("guard","daphne",15,true)')
    prompt=page.evaluate(f'{api}.snapshot()')
    assert prompt['pending'] and prompt['pending']['kind']=='v19react'
    assert prompt['units']['daphne']['shieldFree']==1, 'Shield was spent without consent'
    assert page.locator('[data-v19-react="shield"]').count()==1
    page.locator('[data-v19-react="shield"]').click()
    after=page.evaluate(f'{api}.snapshot()')
    assert after['pending'] is None
    assert after['units']['daphne']['shieldFree']==0
    assert after['units']['daphne']['hp']==hp
    # Invalid arena must not discard the original encounter.
    invalid=json.loads(json.dumps(sample));invalid['heroes']['yar']['cell']='E6'
    try:
        page.evaluate(f'(d)=>{api}.newScenario(d)',invalid)
        raise AssertionError('Overlapping actor positions were accepted')
    except Exception as exc:
        if 'were accepted' in str(exc):raise
    assert page.evaluate(f'{api}.snapshot().units.guard.hp')==28
    # Fully new encounter: arbitrary opponent and custom terrain, with correct initiative.
    page.locator('[data-v21-new]').click()
    assert page.locator('#v21json').count()==1
    page.locator('#v21json').fill(json.dumps(sample,ensure_ascii=False))
    page.locator('[data-v21-create]').click()
    state=page.evaluate(f'{api}.snapshot()')
    assert state['battleName']==sample['name']
    assert state['units']['guard']['hp']==0 and state['units']['archer']['hp']==0
    assert state['units']['enemy_1']['enemyAttack']['count']==2
    assert state['units']['enemy_1']['enemySaves']['CON']==4
    assert state['index']==0
    assert page.locator('[data-tile]').count()==88
    # Noncanonical result draft; source resources remain unchanged.
    page.evaluate(f'{api}.set(s=>{{s.units.yar.hp-=4;s.units.yar.storm-=1;s.inv.yar.healing-=1;}})')
    report=page.evaluate(f'{api}.outcome()')
    assert report['canonical_state_unchanged'] is True
    assert report['requires_player_confirmation'] is True
    assert {'type':'adjust_resource','id':'yar','resource':'hp','delta':-4} in report['operations']
    assert {'type':'adjust_resource','id':'yar','resource':'storm_thrower_ammo','delta':-1} in report['operations']
    # JSON checkpoint and restoration retain scenario and opponent attacks.
    cp=page.evaluate(f'{api}.checkpoint()')
    page.evaluate(f'{api}.set(s=>{{s.units.yar.hp=1;s.units.enemy_1.enemyAttack.count=1;}})')
    page.evaluate(f'(x)=>{api}.load(x)',cp)
    state=page.evaluate(f'{api}.snapshot()')
    assert state['units']['yar']['hp']==110
    assert state['units']['enemy_1']['enemyAttack']['count']==2
    assert state['battleName']==sample['name']
    tamper=json.loads(json.dumps(cp))
    tamper['session']['scenario']['terrain']['walls']=['99,5']
    try:
        page.evaluate(f'(x)=>{api}.load(x)',tamper)
        raise AssertionError('Tampered scene accepted')
    except Exception as exc:
        if 'Tampered scene accepted' in str(exc):raise
    assert page.evaluate(f'{api}.snapshot().units.yar.hp')==110, 'Bad import mutated the battle'
    assert 'wall' in page.locator('[data-tile="6,1"]').get_attribute('class'), 'Custom wall not loaded'
    page.locator('[data-op="reset"]').click()
    state=page.evaluate(f'{api}.snapshot()')
    assert state['units']['guard']['hp']==28
    assert state.get('battleName') is None
    assert 'wall' not in page.locator('[data-tile="6,1"]').get_attribute('class'), 'Custom terrain leaked into reset'
    assert 'wall' in page.locator('[data-tile="5,2"]').get_attribute('class'), 'Original terrain lost'
    # Maximum supported enemy roster: skipping dead enemies must cross to round 2.
    extra=json.loads(json.dumps(sample))
    extra['name']='Большое сражение'
    reserved={'E6','B7','D6','C6','G2','F4'}
    cells=[chr(ord('A')+x)+str(y) for y in range(1,9) for x in range(11)
           if chr(ord('A')+x)+str(y) not in reserved]
    extra['enemies']=[dict(sample['enemies'][0],name='Враг '+str(i+1),cell=cells[i]) for i in range(20)]
    page.evaluate(f'(d)=>{api}.newScenario(d)',extra)
    page.evaluate(f'{api}.set(s=>{{s.index=3;for(const id of Object.keys(s.units))if(id.startsWith("enemy_"))s.units[id].hp=0;}})')
    page.evaluate(f'{api}.advance()')
    long_round=page.evaluate(f'{api}.snapshot()')
    assert long_round['round']==2 and long_round['index']==0, 'Dead enemy turns interrupted round transition'
    assert not errors, errors
    print('V21 PACKAGED CHAT ENGINE QA PASSED')
    browser.close()
