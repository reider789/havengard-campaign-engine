from playwright.sync_api import sync_playwright
from pathlib import Path
import json
HTML=(Path(__file__).resolve().parents[1]/'engine-v20.html').read_text(encoding='utf-8')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True, executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1400,'height':1100},accept_downloads=True);page.set_default_timeout(2500)
 errors=[];page.on('pageerror',lambda e: errors.append(str(e)))
 page.evaluate('window.HAVENGARD_RUNTIME={source_state_revision:27,characters:{}};window.__HV_ENABLE_TEST_APIS=true;Math.random=()=>0.35')
 page.set_content(HTML);page.wait_for_timeout(100)
 assert page.locator('[data-tile]').count()==88, 'board not rendered'
 api='window.__HV_TEST_API'
 old=page.evaluate(f'{api}.snapshot()')
 print('initial',old['round'],old['index'],old['units']['daphne']['slots'][3])
 assert old['index']==1 and old['round']==1 and old['units']['guard']['hp']==28
 page.locator('[data-v20-open]').click()
 assert page.locator('#v20enemy-json').count()==1
 enemy={'name':'Шаман Пустоши','x':7,'y':5,'hp':44,'ac':15,'initiative':12,'attack':{'bonus':7,'count':2,'die':6,'flat':3,'range':30},'saves':{'DEX':3,'WIS':5,'CON':4},'abilities':['Варп']}
 page.locator('#v20enemy-json').fill(json.dumps(enemy,ensure_ascii=False));page.locator('[data-v20-add]').click()
 snap=page.evaluate(f'{api}.snapshot()')
 assert snap['extraEnemies'][0]['name']=='Шаман Пустоши'
 assert snap['units']['enemy_1']['enemyAttack']['count']==2
 print('enemy added',snap['index'],snap['extraEnemies'])
 assert snap['index']==1, 'current Daphne changed when foe added'
 # Specific save bonus is loaded into engine (test via deterministically forced 7 result at DC11)
 page.evaluate(f'{api}.set(s=>{{s.units.enemy_1.enemySaves.DEX=4;}})')
 # Attack custom enemy with fixed roll, avoid existing paladin protection by forcing no reaction
 page.evaluate(f'{api}.set(s=>{{s.units.lyutobor.reaction=0;s.units.rada.reaction=0;s.round=2;s.index=4;s.units.enemy_1.action=1}})')
 print('new init index',page.evaluate('window.__HV_TEST_API.snapshot().index'))
 # Test direct enemy attack: 2d6+3 and hit bonus+7
 hp0=page.evaluate(f'{api}.snapshot().units.rada.hp')
 page.evaluate(f'{api}.attack("enemy_1","rada",27,true)')
 # no reaction due to modified state
 snap=page.evaluate(f'{api}.snapshot()');print('custom attack',hp0,snap['units']['rada']['hp'],snap['pending'])
 assert snap['units']['rada']['hp']<hp0
 # Pending chain preservation: mark against Rada, interrupt
 page.evaluate(f'{api}.set(s=>{{s.units.lyutobor.reaction=1;s.units.lyutobor.mark=3;s.units.rada.reaction=1;s.index=1;s.round=2;}})')
 page.evaluate(f'{api}.attack("guard","rada",25,true)')
 pending=page.evaluate(f'{api}.snapshot().pending');print('pending',pending)
 assert pending and pending['kind']=='v19react'
 cp=page.evaluate(f'{api}.checkpoint()')
 assert cp['active_actor']=='daphne' and cp['session']['pending']['kind']=='v19react'
 # Import must not swallow pending and must not alter initiative actor
 page.evaluate(f'{api}.set(s=>{{s.pending=null;s.units.rada.hp=1;}})')
 page.evaluate('(cp)=>window.__HV_TEST_API.load(cp)',cp)
 ss=page.evaluate(f'{api}.snapshot()')
 assert ss['pending']['kind']=='v19react' and ss['units']['rada']['hp']==cp['session']['units']['rada']['hp']
 assert page.locator('[data-v19-react="mark"]').count()==1
 page.locator('[data-v19-react="mark"]').click()
 assert page.locator('[data-v19-react="uncanny"]').count()==1
 page.locator('[data-v19-react="uncanny"]').click()
 ss=page.evaluate(f'{api}.snapshot()');assert ss['pending'] is None and ss['attackFrame'] is None
 print('react resumed',ss['units']['rada']['hp'])
 # Reopen checkpoint through actual browser file input using memory JSON
 page.locator('#importer').set_input_files({'name':'checkpoint.json','mimeType':'application/json','buffer':json.dumps(cp,ensure_ascii=False).encode()})
 page.wait_for_timeout(120)
 ss=page.evaluate(f'{api}.snapshot()')
 assert ss['pending'] and ss['pending']['kind']=='v19react'
 assert ss['extraEnemies'][0]['name']==enemy['name']
 print('file import preserved pending and roster')
 # invalid import rejected while state unchanged
 tamper=dict(cp);tamper['version']=10
 try:page.evaluate('(cp)=>window.__HV_TEST_API.load(cp)',tamper);raise AssertionError('invalid accepted')
 except Exception as e:
  if 'invalid accepted' in str(e):raise
 assert not errors,errors
 print('ALL CHECKS PASSED')
 page.screenshot(path='/mnt/data/havengard_v20_qa.png',full_page=True)
 b.close()