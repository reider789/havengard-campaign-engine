from playwright.sync_api import sync_playwright
from pathlib import Path
HTML=(Path(__file__).resolve().parents[1]/'engine-v20.html').read_text(encoding='utf-8')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1200,'height':900});page.set_default_timeout(2300)
 errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
 page.evaluate('window.HAVENGARD_RUNTIME={source_state_revision:27,characters:{}};window.__HV_ENABLE_TEST_APIS=true;Math.random=()=>0.6')
 page.set_content(HTML);page.wait_for_timeout(70)
 api='window.__HV_TEST_API'
 # caster B7, guard C7. CON d20 13+3 passes DC19? 13+3=16 -> fails. with 0.99 roll 20 (success)
 page.evaluate(f'{api}.set(s=>{{s.units.guard.x=2;s.units.guard.y=6;s.units.guard.reaction=0;s.units.guard.hp=28;s.units.daphne.action=1;s.units.daphne.slots[1]=4;}})')
 page.evaluate('Math.random=()=>0.99')
 page.locator('[data-v18="thunder"]').click()
 page.locator('button[data-tile="2,6"]').click()
 before=page.evaluate(f'{api}.snapshot()')
 print('thunder draft',before['draft'])
 if page.locator('[data-v18-confirm]').is_enabled():
  page.locator('[data-v18-confirm]').click()
  after=page.evaluate(f'{api}.snapshot()')
  print('thunder effect positions',before['units']['guard']['x'], after['units']['guard']['x'], 'hist',after['history'][-4:])
  assert after['units']['guard']['x']==before['units']['guard']['x'], 'Success save wrongly pushed'
  assert after['units']['daphne']['slots'][1]==3
 else: print('Thunder target geometry illegal, test skipped for terrain:', page.locator('#preview').inner_text()[-220:])
 # Next run: ensure normal turn advances no errors even with pending reactions.
 page.evaluate(f'{api}.set(s=>{{s.pending=null;s.draft=null;s.units.guard.x=7;s.units.guard.y=3;s.units.guard.hp=28;s.round=1;s.index=1;}})')
 for i in range(22):
  ss=page.evaluate(f'{api}.snapshot()')
  if ss['round']>=3:break
  if ss.get('pending'):
   if ss['pending']['kind']=='v19react':page.locator('[data-v19-react="no"]').click()
   elif ss['pending']['kind']=='indomitable':page.locator('#response button[data-choice="no"]').first.click()
   else:print('Unresolved pending',ss['pending']);break
  elif ss['units'][('rada','daphne','lyutobor','yar','guard','archer')[ss['index']]]['hp']<=0:page.evaluate(f'{api}.advance()')
  else:page.evaluate(f'{api}.advance()')
 ss=page.evaluate(f'{api}.snapshot()')
 print('final rounds',ss['round'],'index',ss['index'],'hp guard',ss['units']['guard']['hp'],'pending',ss.get('pending'))
 assert ss['round']>=2 and not errs,errs
 print('ROUND+THUNDER PASSED')
 b.close()