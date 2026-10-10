from playwright.sync_api import sync_playwright
from pathlib import Path
HTML=(Path(__file__).resolve().parents[1]/'engine-v19.html' if (Path(__file__).resolve().parents[1]/'engine-v19.html').exists() else Path('/mnt/data/havengard_chat_v19.html')).read_text()
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1200,'height':840});page.set_default_timeout(1700)
 err=[];page.on('pageerror',lambda e:err.append(str(e)))
 page.evaluate('window.HAVENGARD_RUNTIME={source_state_revision:27,characters:{}};window.__HV_ENABLE_TEST_APIS=true;Math.random=()=>0.1')
 page.set_content(HTML)
 page.evaluate('window.__HV_TEST_API.set(s=>{s.bigby={x:7,y:4,owner:"daphne",hp:62,max:62,ac:20,grappled:null,createdRound:1};s.effects.push({owner:"daphne",kind:"bigby",targets:["daphne"],until:60,concentration:true});s.round=2;s.units.daphne.bonus=1;})')
 base=page.evaluate('window.__HV_TEST_API.snapshot()')
 d={'type':'advanced','owner':'daphne','key':'bigbyGrasp','target':'guard','point':{'x':7,'y':4},'handMode':'grasp'}
 assert page.evaluate('(d)=>window.__HV_TEST_API.activateBigby(d)',d)
 ss=page.evaluate('window.__HV_TEST_API.snapshot()');print('grasp',ss['bigby']['grappled'],ss['units']['daphne']['bonus']);assert ss['bigby']['grappled']=='guard'
 page.evaluate('window.__HV_TEST_API.set(s=>{s.round=3;s.units.daphne.bonus=1})')
 d['key']='bigbyCrush';d['handMode']='crush';assert page.evaluate('(d)=>window.__HV_TEST_API.activateBigby(d)',d)
 ss=page.evaluate('window.__HV_TEST_API.snapshot()');print('crush',ss['units']['guard']['hp']);assert ss['units']['guard']['hp']<28
 page.evaluate('window.__HV_TEST_API.set(s=>{s.round=4;s.units.daphne.bonus=1})')
 d['key']='bigbyInterpose';d['handMode']='interpose';d['point']={'x':4,'y':4};assert page.evaluate('(d)=>window.__HV_TEST_API.activateBigby(d)',d)
 ss=page.evaluate('window.__HV_TEST_API.snapshot()');assert ss['bigby']['interposing']
 page.evaluate('window.__HV_TEST_API.set(s=>{s.index=0;s.units.rada.action=1;s.units.rada.bonus=1;s.units.rada.move=30})')
 page.locator('button[data-tab="consumable"]').click()
 page.locator('button[data-item="trap"]').click()
 page.locator('button[data-tile="5,5"]').click()
 page.locator('[data-v19-rule="range"]').fill('5');page.locator('[data-v19-rule="duration"]').fill('600');page.locator('[data-v19-rule="dc"]').fill('14');page.locator('[data-v19-rule="damageDice"]').fill('1d4+1');page.locator('[data-v19-rule="approved"]').check();page.locator('[data-v19-rule-save]').click()
 assert page.locator('[data-v19-item-apply]').is_enabled();page.locator('[data-v19-item-apply]').click()
 ss=page.evaluate('window.__HV_TEST_API.snapshot()');assert ss['inv']['rada']['trap']==4 and ss['worldItems'][-1]['armed']
 page.evaluate('window.__HV_TEST_API.set(s=>{s.units.guard.x=5;s.units.guard.y=5})');page.evaluate('window.__HV_TEST_API.trap("guard")')
 ss=page.evaluate('window.__HV_TEST_API.snapshot()');print('trap',ss['worldItems'][-1], 'guard',ss['units']['guard']['hp']);assert ss['worldItems'][-1]['armed'] is False
 assert not err,err
 print('BIGBY+ITEM MODES PASSED')
 b.close()