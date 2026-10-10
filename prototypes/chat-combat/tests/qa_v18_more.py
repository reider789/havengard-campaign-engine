from playwright.sync_api import sync_playwright
from pathlib import Path
from contextlib import suppress

def check(case,condition):
 assert condition,case
 print('PASS:',case,flush=True)

with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1200,'height':900});page.set_default_timeout(1200)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.evaluate('window.HAVENGARD_RUNTIME={source_state_revision:27,characters:{}}')
 page.set_content(Path('/mnt/data/havengard_chat_v18.html').read_text(),wait_until='domcontentloaded')
 page.wait_for_timeout(250)
 check('88-cell board',page.locator('button[data-tile]').count()==88)
 check('Daphne starts', 'Дафн' in page.locator('#actor').inner_text())
 # Block on not in range and do not consume
 page.locator('button[data-v18="thunder"]').click()
 check('invalid thunder blocked',page.locator('button[data-v18-confirm]').is_disabled())
 page.locator('button[data-op="cancel"]').click()
 # Fireball + sculpt
 page.locator('button[data-action="fireball"]').click();page.locator('button[data-tile="5,5"]').click()
 check('3 automatically protected',page.locator('input[data-sculpt]:checked').count()==3)
 page.locator('button[data-op="apply"]').click()
 journal=page.locator('#journal').inner_text()
 check('Fireball resolved', 'Огненный шар, центр F6' in journal)
 check('Sculpt prevents ally damage',all('Скульптура: '+h for h in ['Яр','Лютобор','Рада']))
 page.locator('button[data-op="next"]').click()
 check('Paladin turn','Лютобор' in page.locator('#actor').inner_text())
 page.locator('button[data-v18="sacred"]').click()
 check('Sacred weapon ready',not page.locator('button[data-v18-confirm]').is_disabled())
 page.locator('button[data-v18-confirm]').click()
 check('Sacred weapon state','sacred' in page.locator('#journal').inner_text())
 # Fighter
 page.locator('button[data-op="next"]').click()
 check('Fighter turn','Яр' in page.locator('#actor').inner_text())
 page.locator('button[data-v18="bait"]').click()
 page.locator('button[data-tile="3,5"]').click()
 check('Bait available',not page.locator('button[data-v18-confirm]').is_disabled())
 page.locator('button[data-v18-confirm]').click()
 check('Bait swapped positions','Приманка и смена' in page.locator('#journal').inner_text())
 check('No runtime errors',not errors)
 print('ERRORS',errors,flush=True)
 browser.close()