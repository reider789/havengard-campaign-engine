"""Regression: the packaged in-chat v21 engine, not a separate website."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML=(Path(__file__).resolve().parents[1]/'current-chat-battle.html').read_text(encoding='utf-8')
sample={
    'name':'Проверочная засада', 'kind':'story',
    'heroes':{'rada':{'cell':'E6','initiative':20},'daphne':{'cell':'B7','initiative':16},
              'lyutobor':{'cell':'D6','initiative':14},'yar':{'cell':'C6','initiative':12}},
    'walls':['F3','F4'], 'rubble':['E4'],
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
    page.evaluate(f'(d)=>{api}.newScenario(d)',sample)
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
    assert not errors, errors
    print('V21 PACKAGED CHAT ENGINE QA PASSED')
    browser.close()
