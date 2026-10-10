from playwright.sync_api import sync_playwright
from pathlib import Path
h=(Path(__file__).resolve().parents[1]/'engine-v19.html' if (Path(__file__).resolve().parents[1]/'engine-v19.html').exists() else Path('/mnt/data/havengard_chat_v19.html')).read_text()
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1360,'height':940});page.set_default_timeout(2100)
 errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
 page.evaluate('window.HAVENGARD_RUNTIME={source_state_revision:27,characters:{}};window.__HV_ENABLE_TEST_APIS=true;Math.random=()=>0.1')
 page.set_content(h)
 page.locator('[data-v19-mage]').click()
 page.locator('[data-v19-support]').click()
 print('after setup', page.locator('#inspector').inner_text()[-270:], page.locator('#journal').inner_text()[-450:], errs)
 page.locator('[data-action="fireball"]').click()
 page.locator('button[data-tile="5,5"]').click()
 page.locator('[data-op="apply"]').click()
 snap=page.evaluate('window.__HV_TEST_API.snapshot()')
 print('party spell counter',snap.get('spellStack'),snap.get('pending'),snap['units']['daphne']['slots'][3],snap['units']['mage']['slots'][3],snap['units']['mage2']['slots'][3]);print('errors',errs)
 assert snap['units']['daphne']['action']==0
 assert snap['units']['mage']['reaction']==0
 assert any('Контрзаклинание' in x for x in snap['history'])
 assert not errs
 # Nested enemy mage fireball -> Daphne Counterspell -> mage2 Counterspell -> expected original enemy spell triggers.
 page.locator('[data-op="reset"]').click()
 page.locator('[data-v19-mage]').click();page.locator('[data-v19-support]').click()
 page.evaluate('window.__HV_TEST_API.startSpell("mage")')
 page.locator('[data-v19-react="counterspell"]').click()
 snap=page.evaluate('window.__HV_TEST_API.snapshot()')
 print('nested counter result',snap.get('spellStack'),snap.get('pending'),snap['units']['daphne']['slots'][3],snap['units']['mage']['slots'][3],snap['units']['mage2']['slots'][3]);print('errors',errs)
 assert snap['units']['mage2']['reaction']==0
 assert any('Контрзаклинание' in x for x in snap['history'])
 assert not errs
 b.close()