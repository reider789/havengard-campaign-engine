"""V23 end-to-end: refactored spell and reaction classes, no separate website."""
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML=(Path(__file__).resolve().parents[1]/'current-chat-battle.html').read_text(encoding='utf-8')
assert 'class CombatSpellResolver' in HTML
assert 'class CombatReactionResolver' in HTML
assert '/*__HV_SPELL_RESOLVER__*/' not in HTML
assert '/*__HV_REACTION_RESOLVER__*/' not in HTML
assert '<script src=' not in HTML

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1400,'height':1200})
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.evaluate('window.__HV_ENABLE_TEST_APIS=true;Math.random=()=>0.6')
    page.set_content(HTML)
    page.wait_for_timeout(100)
    api='window.__HV_TEST_API'
    assert page.locator('[data-tile]').count()==88,errors

    # Bigby's Hand: validate an empty creation cell, pay one level-5 slot, persist it.
    page.evaluate(f'''{api}.set(s=>{{
      s.index=1;s.pending=null;s.draft=null;s.bigby=null;
      s.units.daphne.action=1;s.units.daphne.slots[5]=2;
      s.units.daphne.spellSlotThisTurn=false;
    }})''')
    before=page.evaluate(f'{api}.snapshot().units.daphne.slots[5]')
    assert page.evaluate(f'''{api}.activateBigby({{
        type:'advanced',key:'bigby',target:'guard',point:{{x:1,y:7}},handMode:'move'
    }})''') is True
    created=page.evaluate(f'{api}.snapshot()')
    assert created['bigby'] is not None, created.get('info')
    assert created['bigby']['x']==1 and created['bigby']['y']==7
    assert created['units']['daphne']['slots'][5]==before-1
    assert any(e['kind']=='bigby' for e in created['effects'])
    saved=page.evaluate(f'{api}.checkpoint()')
    page.evaluate(f'(cp)=>{api}.load(cp)',saved)
    assert page.evaluate(f'{api}.snapshot().bigby.x')==1

    # Enemy Fireball interrupts for an honest, serialized Counterspell reaction.
    assert page.locator('[data-v19-mage]').count()==1
    page.locator('[data-v19-mage]').click()
    page.locator('[data-v19-support]').click()
    page.evaluate(f'''{api}.set(s=>{{
       s.index=1;s.units.daphne.reaction=1;s.units.daphne.slots[3]=3;
       s.units.daphne.spellSlotThisTurn=false;
       s.units.mage.action=1;s.units.mage.slots[3]=2;
       s.units.mage2.reaction=1;s.units.mage2.slots[3]=3;
       s.pending=null;s.spellStack=[];
    }})''')
    result=page.evaluate(f'{api}.startSpell("mage")')
    suspended=page.evaluate(f'{api}.snapshot()')
    assert result is True
    assert suspended['pending'] and suspended['pending']['kind']=='v19react', suspended.get('pending')
    assert suspended['pending']['phase']=='spell'
    assert len(suspended['spellStack'])==1
    assert suspended['units']['mage']['slots'][3]==1
    saved=page.evaluate(f'{api}.checkpoint()')
    page.evaluate(f'(cp)=>{api}.load(cp)',saved)
    recovered=page.evaluate(f'{api}.snapshot()')
    assert len(recovered['spellStack'])==1
    assert recovered['pending']['phase']=='spell'
    page.evaluate(f'{api}.react("counterspell")')
    after=page.evaluate(f'{api}.snapshot()')
    assert after['units']['daphne']['reaction']==0,after
    assert after['units']['daphne']['slots'][3]==2
    # The enemy mage can answer her Counterspell with its own reaction:
    # this is a genuine nested cast, not merely a single reaction prompt.
    assert after['units']['mage']['reaction']==0,after['history'][-15:]
    assert any('Маг применяет Контрзаклинание' in h for h in after['history']),after['history'][-15:]
    assert any('Контрзаклинание' in h for h in after['history']),after['history'][-15:]
    assert not errors,errors
    browser.close()
print('V23 SPELL AND REACTION OBJECT DISPATCH QA PASSED')
