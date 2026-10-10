from playwright.sync_api import sync_playwright
from pathlib import Path
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 pg=b.new_page(viewport={'width':1200,'height':850});pg.set_default_timeout(1800)
 errors=[];pg.on('pageerror',lambda e:errors.append(str(e)))
 pg.evaluate('window.HAVENGARD_RUNTIME={source_state_revision:27,characters:{}};Math.random=()=>0')
 pg.set_content(Path('/mnt/data/havengard_chat_v18.html').read_text(),wait_until='domcontentloaded')
 pg.locator('button[data-action="fireball"]').click();pg.locator('button[data-tile="5,5"]').click()
 pg.locator('input[data-sculpt="yar"]').uncheck()
 pg.locator('button[data-op="apply"]').click()
 print('pending:',pg.locator('#response').inner_text()[:250]);assert 'Несгибаемость' in pg.locator('#response').inner_text()
 before=pg.locator('#inspector').inner_text();print('before decision',before[:200]);assert '114' in pg.locator('button[data-inspect="yar"]').inner_text()
 pg.locator('button[data-choice="no"]').click()
 after=pg.locator('#journal').inner_text()
 print('after decision:',after[:360]);assert 'Яр: −' in after
 print('errors:',errors);assert not errors
 b.close()