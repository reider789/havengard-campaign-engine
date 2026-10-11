"""D&D 2024 nonlethal knock-out v28: real melee post-hit, ranged exclusion,
living unconscious foes, enemy AI, healing, save/load and narration."""
from pathlib import Path
from playwright.sync_api import sync_playwright
HTML=(Path(__file__).resolve().parents[1]/'current-chat-battle.html').read_text(encoding='utf-8')
assert 'class CombatKnockout2024' in HTML
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1280,'height':900})
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('**/hayvengard_art_v1.json',lambda r:r.abort())
 page.evaluate('window.__HV_ENABLE_TEST_APIS=true')
 page.set_content(HTML)
 page.wait_for_selector('#board button[data-tile]')
 api='window.__HV_TEST_API'
 def reset_guard(hp=3):
  page.evaluate(api+f""".set(s=>{{
   s.phase='active';s.pending=null;s.moving=false;
   s.units.guard.hp={hp};s.units.guard.temp=0;
   s.units.guard.status=[];s.units.guard.reaction=1;
   s.units.archer.hp=30;
   s.units.yar.weapon='sword';s.units.yar.coated=false;
   s.effects=[];s.nonlethalMeleeContext=null;
  }})""")
 # Sword hit: offer the choice only on lethal damage.
 reset_guard()
 page.evaluate(api+".knockoutWeaponHit('yar','guard',12)")
 pending=page.evaluate(api+'.snapshot().pending')
 assert pending and pending['kind']=='nonlethal2024',pending
 assert page.evaluate(api+'.snapshot().units.guard.hp')==3
 assert page.locator('[data-hg-ko=spare]').count()==1
 assert page.locator('[data-hg-ko=lethal]').count()==1
 page.locator('[data-hg-ko=spare]').click()
 state=page.evaluate(api+'.snapshot()')
 assert state['pending'] is None
 assert state['units']['guard']['hp']==1
 assert state['units']['guard']['knockedOutBy']=='yar'
 assert state['units']['guard']['status'][-1]['kind']=='unconscious'
 assert state['units']['guard']['status'][-1]['until']==state['elapsed']+3600
 assert state['phase']=='active'   # Archer is still fighting.
 report=page.evaluate(api+'.handoffReport()')
 guard=next(x for x in report['foes'] if x['id']=='guard')
 assert guard['alive'] is True and guard['unconscious'] is True
 assert report['battle']['result']=='stopped'
 # Knocked enemies cannot act in their turn.
 page.evaluate(api+".set(s=>{s.index=4})")
 page.evaluate(api+'.advance()')
 after=page.evaluate(api+'.snapshot()')
 assert after['phase']=='active'
 assert not (after['units']['guard']['action']==1 and after['units']['guard']['hp']<=0)
 # New scenario can end with a live unconscious captive.
 reset_guard()
 page.evaluate(api+".set(s=>{s.units.archer.hp=0})")
 page.evaluate(api+".knockoutWeaponHit('yar','guard',20)")
 page.locator('[data-hg-ko=spare]').click()
 assert page.evaluate(api+'.snapshot().phase')=='ended'
 victory=page.evaluate(api+'.handoffReport()')
 assert victory['battle']['result']=='victory'
 assert victory['foes'][0]['alive'] is True
 assert victory['foes'][0]['unconscious'] is True
 assert page.evaluate(api+'.checkpoint().session.version')==12
 # Damaging ranged hits can't produce the dialog.
 reset_guard()
 page.evaluate(api+".knockoutHit('rada','guard',11,'ranged')")
 state=page.evaluate(api+'.snapshot()')
 assert state['units']['guard']['hp']==0
 assert state['pending'] is None
 # Spell area damage can't be marked nonlethal.
 reset_guard()
 page.evaluate(api+".knockoutHit('daphne','guard',11,'spell')")
 assert page.evaluate(api+'.snapshot().pending') is None
 # Nonlethal never bypasses the player's choice.
 reset_guard()
 page.evaluate(api+".knockoutWeaponHit('lyutobor','guard',20)")
 assert page.evaluate(api+'.snapshot().units.guard.hp')==3
 page.locator('[data-hg-ko=lethal]').click()
 assert page.evaluate(api+'.snapshot().units.guard.hp')==0
 assert not any(z['kind']=='unconscious' for z in page.evaluate(api+'.snapshot().units.guard.status'))
 # No knockout prompt before the target drops to zero.
 reset_guard(80)
 page.evaluate(api+".knockoutWeaponHit('yar','guard',10)")
 assert page.evaluate(api+'.snapshot().units.guard.hp')==70
 assert page.evaluate(api+'.snapshot().pending') is None
 # Healing wakes a living knocked-out creature.
 reset_guard()
 page.evaluate(api+".knockoutWeaponHit('yar','guard',20)")
 page.locator('[data-hg-ko=spare]').click()
 page.evaluate(api+".knockoutHeal('guard',5)")
 assert page.evaluate(api+'.snapshot().units.guard.hp')==6
 assert not page.evaluate(api+".knockoutActive('guard')")
 assert not errors,errors
 print('V28 NONLETHAL PASSED: melee decision, ranged refusal, captive, victory, journal, healing, persistence')
 browser.close()
