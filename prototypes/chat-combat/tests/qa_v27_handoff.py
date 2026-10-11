"""V27: player-click report transfer, reaction safety and exact battle facts."""
from pathlib import Path
from playwright.sync_api import sync_playwright
HTML=(Path(__file__).resolve().parents[1]/'current-chat-battle.html').read_text(encoding='utf-8')
assert 'class CombatNarrativeHandoff' in HTML
assert 'Завершить бой и передать мастеру' in HTML
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1250,'height':1100})
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('**/hayvengard_art_v1.json',lambda r:r.abort())
 page.evaluate("""window.__HV_ENABLE_TEST_APIS=true;
 window.__handoffs=[];
 window.__bindings={setValue:v=>window.__handoffs.push(v)};""")
 page.set_content(HTML)
 page.wait_for_selector('#hg-narrative-handoff')
 api='window.__HV_TEST_API'
 snapshot=page.evaluate(api+'.snapshot()')
 assert snapshot['phase']=='active'
 assert page.evaluate("window.__handoffs.filter(x=>x.kind==='havengard-battle-handoff-v1').length")==0
 # Reaction windows must be finished before a report can be delivered.
 page.evaluate(api+".set(s=>{s.pending={kind:'sneak',target:'guard',raw:5}})")
 page.locator('#hg-narrative-handoff').click()
 assert page.evaluate("window.__handoffs.filter(x=>x.kind==='havengard-battle-handoff-v1').length")==0
 assert page.evaluate(api+".snapshot().phase")=='active'
 assert 'реакцию' in page.locator('#hg-narrative-status').inner_text()
 page.evaluate(api+".set(s=>{s.pending=null})")
 page.locator('#hg-narrative-handoff').click()
 reports=page.evaluate("window.__handoffs.filter(x=>x.kind==='havengard-battle-handoff-v1')")
 assert len(reports)==1
 assert reports[0]['report']['kind']=='havengard-battle-report-v1'
 assert reports[0]['report']['battle']['source_revision']==27
 assert reports[0]['report']['battle']['mode']=='training'
 assert reports[0]['report']['battle']['result']=='stopped'
 assert len(reports[0]['report']['allies'])==4
 assert len(reports[0]['report']['foes'])==2
 assert reports[0]['report']['journal']['all_entries']>=2
 assert reports[0]['report']['outcome']['canonical_unchanged'] is True
 assert 'Отчёт подготовлен' in page.locator('#hg-narrative-status').inner_text()
 assert 'Нажмите' in page.locator('#hg-narrative-status').inner_text()
 assert page.evaluate(api+".snapshot().phase")=='ended'
 assert page.locator('#board button[data-tile]').count()==88
 checkpoint=page.evaluate(api+'.checkpoint()')
 assert checkpoint['session']['version']==12
 # Repeated click does not rewrite battle or undo resources. Explicit repeat is allowed.
 page.locator('#hg-narrative-handoff').click()
 assert page.evaluate("window.__handoffs.filter(x=>x.kind==='havengard-battle-handoff-v1').length")==2
 assert page.evaluate(api+'.snapshot().history')==checkpoint['session']['history']
 assert not errors,errors
 # Very long stories must disclose partial coverage, never claim exhaustive evidence.
 page.evaluate(api+""".set(s=>{s.history=Array.from({length:550},(_,i)=>
 'Р'+(i%15+1)+' · '+i+' Рада атакует противника, Дафна удерживает проход, Яр защищает Лютобора, '+('подробное описание '.repeat(6)))})""")
 report=page.evaluate(api+'.handoffReport()')
 assert report['journal']['coverage']=='partial'
 assert report['journal']['transferred']<550
 assert report['journal']['events'][0].startswith('Р1')
 assert report['journal']['events'][-1].startswith('Р10')
 assert not errors,errors
 # No host binding: do not mistakenly mark battle as ended or claim submission.
 unbound=browser.new_page()
 unbound.route('**/hayvengard_art_v1.json',lambda r:r.abort())
 unbound.evaluate('window.__HV_ENABLE_TEST_APIS=true')
 unbound.set_content(HTML)
 unbound.wait_for_selector('#hg-narrative-handoff')
 assert unbound.evaluate('window.__HV_TEST_API.snapshot().phase')=='active'
 unbound.locator('#hg-narrative-handoff').click()
 assert unbound.evaluate('window.__HV_TEST_API.snapshot().phase')=='active'
 assert 'Связь с чатом недоступна' in unbound.locator('#hg-narrative-status').inner_text()
 unbound.close()
 print('V27 REPORT OK: direct click, reaction guard, saved battle, explicit journal coverage, four heroes')
 browser.close()
