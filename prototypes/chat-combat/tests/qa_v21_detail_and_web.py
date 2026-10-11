"""End-to-end QA: combat narration, localized statuses, canonical Web, randomized training map."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
HTML=(Path(__file__).resolve().parents[1]/'current-chat-battle.html').read_text(encoding='utf-8')
assert 'function v21WebInside' in HTML
assert 'v21RandomTrainingTerrain' in HTML
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1400,'height':1200})
    errors=[]
    page.on('pageerror',lambda exc:errors.append(str(exc)))
    page.evaluate('window.__HV_ENABLE_TEST_APIS=true;Math.random=()=>0.12')
    page.set_content(HTML)
    page.wait_for_timeout(150)
    api='window.__HV_TEST_API'
    start=page.evaluate(f'{api}.snapshot()')
    assert start['trainingTerrain']['walls']
    assert start['trainingTerrain']['rubble']
    assert not any(start['trainingTerrain']['walls'][0]==x for x in start['trainingTerrain']['rubble'])
    page.locator('[data-action="rayfrost"]').evaluate('(e)=>e.click()')
    guide=page.locator('#v21guide').inner_text()
    assert 'Луч холода' in guide and 'История' not in guide,guide
    page.locator('[data-action="mindsliver"]').evaluate('(e)=>e.click()')
    guide=page.locator('#v21guide').inner_text()
    assert 'Расщепление разума' in guide and 'Расследование' not in guide,guide
    page.locator('[data-action="attack"]').evaluate('(e)=>e.click()')
    guide=page.locator('#v21guide').inner_text()
    assert 'Яр и Лютобор' not in guide and 'Фокус Ваэльтира' not in guide,guide
    # Web: level-II, concentration, no fake immediate damage.
    page.evaluate(f'{api}.set(s=>{{s.index=1;s.units.daphne.action=1;s.units.daphne.slots[2]=3;s.draft=null;s.pending=null;}})')
    page.locator('[data-v18="web"]').evaluate('(e)=>e.click()')
    assert 'Паутина' in page.locator('#v21guide').inner_text()
    page.evaluate(f'{api}.set(s=>{{s.draft.point={{x:3,y:4}};}})')
    page.locator('[data-v18-confirm]').click()
    state=page.evaluate(f'{api}.snapshot()')
    assert state['web']['x']==2 and state['web']['y']==3
    assert state['units']['daphne']['slots'][2]==2
    assert any(x['kind']=='web' and x['concentration'] for x in state['effects'])
    assert len(page.locator('#board .tile.web').all())==16
    # A non-hero walks into the Web and fails a save.
    page.evaluate(f'{api}.set(s=>{{s.units.guard.x=2;s.units.guard.y=3;s.units.guard.hp=28;s.units.guard.move=20;}})')
    page.evaluate(f'{api}.webSave("guard")')
    state=page.evaluate(f'{api}.snapshot()')
    assert any(x['kind']=='restrained' for x in state['units']['guard']['status'])
    assert state['units']['guard']['move']==20, 'Web must not permanently erase unspent movement after escape'
    assert any('спасбросок Ловкости' in x for x in state['history'])
    assert any('ПРОВАЛ' in x for x in state['history'])
    assert any('Опутан' in x for x in state['history'])
    # Restrained imposes disadvantage on Dexterity saves (D&D 2024).
    page.evaluate('window.__qaD20=[0.95,0.05];Math.random=()=>window.__qaD20.shift()??0.05')
    assert page.evaluate(f'{api}.save("guard","DEX",19)') is False
    assert any('ПОМЕХА: к20 [20, 2] → 2' in line for line in page.evaluate(f'{api}.snapshot().history')), page.evaluate(f'{api}.snapshot().history')[-8:]
    # Advantage against restrained targets, full d20 rolls, modifiers, target AC.
    page.evaluate('Math.random=()=>0.90')
    page.evaluate(f'{api}.set(s=>{{s.index=3;s.units.yar.action=1;s.units.yar.superiority=0;s.units.yar.weapon="sword";s.target="guard";s.units.guard.x=2;s.units.guard.y=4;}})')
    page.locator('[data-action="attack"]').evaluate('(e)=>e.click()')
    page.locator('[data-op="apply"]').click()
    history=page.evaluate(f'{api}.snapshot().history')
    assert any('ПРЕИМУЩЕСТВО' in x and 'к20 [' in x and 'против КД' in x for x in history),history[-12:]
    assert any('Кости ' in x and '[' in x for x in history),history[-12:]
    assert page.locator('#v21-journal-toggle').count()==1
    page.locator('#v21-journal-toggle').click()
    assert page.evaluate(f'{api}.snapshot().showFullJournal') is True
    # A new training encounter randomizes map, and resumes the same map after checkpoint.
    page.locator('[data-op="reset"]').click()
    terrain1=page.evaluate(f'{api}.snapshot().trainingTerrain')
    page.evaluate('Math.random=()=>0.79')
    page.locator('[data-op="reset"]').click()
    terrain2=page.evaluate(f'{api}.snapshot().trainingTerrain')
    assert terrain1!=terrain2, 'Every new training battle must get a new obstacle layout'
    checkpoint=page.evaluate(f'{api}.checkpoint()')
    page.evaluate(f'(cp)=>{api}.load(cp)',checkpoint)
    assert page.evaluate(f'{api}.snapshot().trainingTerrain')==terrain2
    assert not errors,errors
    browser.close()
print('V21 DETAIL, WEB AND TRAINING MAP QA PASSED')
