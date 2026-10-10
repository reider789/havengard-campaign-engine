from playwright.sync_api import sync_playwright
from pathlib import Path
import json
HTML=(Path(__file__).resolve().parents[1]/'engine-v19.html' if (Path(__file__).resolve().parents[1]/'engine-v19.html').exists() else Path('/mnt/data/havengard_chat_v19.html')).read_text()

def setup(p, random=0.5):
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox']); page=b.new_page(viewport={'width':1320,'height':1000}); page.set_default_timeout(2200)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.evaluate(f'window.HAVENGARD_RUNTIME={{source_state_revision:27,characters:{{}}}};window.__HV_ENABLE_TEST_APIS=true;Math.random=()=>{random}')
 page.set_content(HTML);page.wait_for_timeout(60)
 return b,page,errors

with sync_playwright() as p:
 b,pg,err=setup(p)
 assert pg.locator('button[data-tile]').count()==88
 # forced crit on Rada: paladin adjacent. Mark prevents critical, then Uncanny halves remaining damage.
 pg.evaluate('window.__HV_TEST_API.attack("guard","rada",25,false)')
 print('crit pending 1:',pg.locator('#response').inner_text()[:190])
 assert pg.locator('[data-v19-react="mark"]').count()==1
 before=pg.evaluate('window.__HV_TEST_API.snapshot()')
 pg.locator('[data-v19-react="mark"]').click()
 afterMark=pg.evaluate('window.__HV_TEST_API.snapshot()')
 assert afterMark['units']['lyutobor']['reaction']==0 and afterMark['units']['lyutobor']['mark']==2
 assert pg.locator('[data-v19-react="uncanny"]').count()==1
 pg.locator('[data-v19-react="uncanny"]').click()
 after=pg.evaluate('window.__HV_TEST_API.snapshot()')
 assert after['attackFrame'] is None and after['pending'] is None
 assert after['units']['rada']['hp']<before['units']['rada']['hp']
 assert after['units']['rada']['reaction']==0
 print('crit defense chain passed',before['units']['rada']['hp'],after['units']['rada']['hp'], 'errors',err)
 b.close()

 b,pg,err=setup(p,0.05)
 pg.locator('[data-v19-mage]').click()
 # Start a spell with reaction window; mage has counterspell prepared.
 pg.evaluate('window.__HV_TEST_API.startSpell("mage")')
 assert pg.locator('[data-v19-react="counterspell"]').count()==1
 old=pg.evaluate('window.__HV_TEST_API.snapshot()')
 assert old['units']['daphne']['slots'][3]==3
 pg.locator('[data-v19-react="counterspell"]').click()
 end=pg.evaluate('window.__HV_TEST_API.snapshot()')
 print('counter chain:',end['units']['daphne']['slots'][3],end['units']['mage']['slots'][3],end.get('pending'), 'round',end['round'])
 assert end['units']['daphne']['reaction']==0
 assert any('Контрзаклинание' in x for x in end['history'])
 assert any('ТЕЛ' in x for x in end['history'])
 assert not err,err
 print('nested counterspells passed')
 b.close()

 b,pg,err=setup(p,0.5)
 pg.locator('[data-v18="bigby"]').click()
 pg.locator('button[data-tile="5,5"]').click()
 pg.locator('select[data-v19-hand="mode"]').select_option('move')
 pg.locator('[data-v19-hand-apply]').click()
 snap=pg.evaluate('window.__HV_TEST_API.snapshot()')
 assert snap['bigby']['hp']==62 and snap['bigby']['createdRound']==1
 assert snap['units']['daphne']['slots'][5]==1
 pg.locator('[data-v18="bigbyStrike"]').click()
 assert not pg.locator('[data-v19-hand-apply]').is_enabled()
 assert 'последующих ходах' in pg.locator('#preview').inner_text()
 # simulated following turn, bonus action available
 pg.evaluate('window.__HV_TEST_API.set(s=>{s.round=2;s.units.daphne.bonus=1})')
 # at H5 hand is adjacent to guard at H4
 pg.locator('input[data-v19-hand="position"]').check()
 pg.locator('button[data-tile="7,4"]').click()
 pg.locator('input[data-v19-hand="position"]').uncheck()
 pg.locator('button[data-tile="7,3"]').click()
 print('bigby preview',pg.locator('#preview').inner_text()[-220:])
 assert pg.locator('[data-v19-hand-apply]').is_enabled()
 pg.locator('[data-v19-hand-apply]').click()
 snap=pg.evaluate('window.__HV_TEST_API.snapshot()')
 assert snap['units']['daphne']['bonus']==0
 assert snap['bigby']['evocationUsed']
 print('bigby strike',snap['units']['guard']['hp'],snap['bigby']['hp'], 'errors',err)
 assert not err,err
 b.close()

 b,pg,err=setup(p,0.5)
 pg.evaluate('window.__HV_TEST_API.set(s=>{s.index=0;s.units.rada.action=1;s.units.rada.bonus=1;s.units.rada.move=30})')
 pg.locator('button[data-tab="consumable"]').click()
 print('manual item selectors',pg.locator('button[data-item="flare"]').count(),pg.locator('button[data-item="trap"]').count())
 pg.locator('button[data-item="flare"]').click()
 assert pg.locator('[data-v19-rule-save]').count()==1
 assert not pg.locator('[data-v19-item-apply]').is_enabled()
 pg.locator('[data-v19-rule="range"]').fill('30')
 pg.locator('[data-v19-rule="duration"]').fill('60')
 pg.locator('[data-v19-rule="approved"]').check()
 pg.locator('[data-v19-rule-save]').click()
 print('after item approval',pg.locator('#preview').inner_text()[-200:]);assert pg.locator('[data-v19-item-apply]').is_enabled()
 pg.locator('[data-v19-item-apply]').click()
 end=pg.evaluate('window.__HV_TEST_API.snapshot()');assert end['units']['rada']['action']==0 and end['inv']['rada']['flare']==1
 print('item used',end.get('worldItems'))
 assert not err,err
 b.close()
print('ALL CHECKS PASSED')