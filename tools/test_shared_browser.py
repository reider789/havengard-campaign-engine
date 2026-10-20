#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
API='window.__RIN_TEST_API'
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage']);page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.add_init_script('window.__HV_ENABLE_TEST_APIS=true')
 page.goto((ROOT/'prototypes/chat-combat/desktop-battle.html').as_uri());page.wait_for_function(f'Boolean({API})');page.evaluate(f'{API}.stop()')
 # A controlled turn, with real UI target selection and no fabricated resource pools.
 page.evaluate(f'''{API}.set(s=>{{s.pending=null;s.queue=[];s.index=s.order.indexOf('daphne');s.turnSerial++;Object.assign(s.units.daphne,{{action:1,bonus:1,move:30}});s.random.tape=Array(30).fill(2);}})''')
 assert page.locator('#magic-spell').locator('option').count()==22
 page.locator('#magic-spell').select_option('fireball');assert page.locator('#magic-level').input_value()=='3'
 page.locator('[data-op="magicPoint"]').click();page.locator('[data-tile="9,4"]').click();assert page.locator('#magic-point').input_value()=='J5'
 page.locator('#magic-sculpt').select_option(['yar','lyutobor','rada']);before=page.evaluate(f'{API}.snapshot().units.daphne.slots[3].current');assert page.locator('[data-op="cast"]').is_enabled();page.locator('[data-op="cast"]').click();assert page.evaluate(f'{API}.snapshot().units.daphne.slots[3].current')==before-1
 assert page.evaluate(f'{API}.visuals().counts.area')>0
 assert page.evaluate(f'{API}.visuals().failure') is None
 saved=page.evaluate(f'JSON.parse(JSON.stringify({API}.snapshot()))');page.reload();page.wait_for_function(f'Boolean({API})');page.evaluate(f'{API}.stop()');assert page.evaluate(f'JSON.parse(JSON.stringify({API}.snapshot()))')==saved
 assert page.evaluate(f'{API}.visuals().created')==0
 # A nested reaction is rendered and reloads without spending either slot twice.
 page.evaluate(f'''{API}.set(s=>{{s.pending=null;s.queue=[];s.index=s.order.indexOf('daphne');s.turnSerial++;Object.assign(s.units.daphne,{{action:1,bonus:1}});delete s.units.daphne.slotTurn;Object.assign(s.units.raider1,{{x:8,y:4,hp:42,max:42,controlled:true,reaction:1,slots:{{3:{{current:2,max:2}}}},casting:structuredClone(s.units.daphne.casting)}});s.units.raider1.casting.prepared=['counterspell'];s.random.tape=[1];}})''')
 page.locator('#magic-spell').select_option('fireball');page.locator('#magic-point').fill('J5');page.locator('#magic-point').dispatch_event('change');page.locator('[data-op="cast"]').click();assert page.evaluate(f'{API}.snapshot().pending.choice')=='counterspell';saved=page.evaluate(f'JSON.parse(JSON.stringify({API}.snapshot()))');page.reload();page.wait_for_function(f'Boolean({API})');page.evaluate(f'{API}.stop()');assert page.evaluate(f'JSON.parse(JSON.stringify({API}.snapshot()))')==saved
 page.locator('#decision [data-decision="yes"]').click();assert page.evaluate(f'{API}.snapshot().units.raider1.slots[3].current')==1;assert page.evaluate(f'{API}.snapshot().units.daphne.slots[3].current')==before-1
 for width,height in [(1366,768),(1440,900),(1920,1080)]:
  page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(50);boxes=page.evaluate("Object.fromEntries(['board','turn-controls'].map(id=>[id,document.getElementById(id).getBoundingClientRect().toJSON()]))");assert boxes['board']['bottom']<height;assert boxes['turn-controls']['bottom']<=height+1
 assert page.evaluate(f'{API}.visuals().failure') is None
 assert not errors,errors
 page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path='/tmp/havengard-shared-desktop.png');browser.close()
print('SHARED DESKTOP BROWSER OK: illustrated arena, all current wizard choices, map point/sculpt controls, cast costs, reload, Counterspell reaction, 3 desktop sizes; no JS errors')
