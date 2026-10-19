"""Standalone desktop delivery keeps the field and end-turn control in view."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
entry=json.loads((root/'entrypoint.json').read_text())
manifest=json.loads((root/'current-manifest.json').read_text())
assert entry['desktop_only'] is True
assert entry['verified_source_revision']==manifest['source_revision']
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1366,'height':768})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('window.__HV_ENABLE_TEST_APIS=true')
 page.route('**/hayvengard_art_v1.json',lambda r:r.abort())
 page.goto((root/'desktop-battle.html').as_uri())
 page.wait_for_selector('#board [data-tile]')
 assert page.locator('#board [data-tile]').count()==88
 boxes=page.evaluate("({board:document.querySelector('#board').getBoundingClientRect().toJSON(),side:document.querySelector('aside').getBoundingClientRect().toJSON(),end:document.querySelector('#endturn').getBoundingClientRect().toJSON()})")
 assert boxes['board']['right']<=boxes['side']['left']
 assert boxes['board']['bottom']<=768,boxes
 assert boxes['end']['bottom']<=768,boxes
 assert not errors,errors
 browser.close()
 print('HAVENGARD DESKTOP OK: standalone document, source revision, 88 cells, field/sidebar/end-turn visible, no mobile gate')
