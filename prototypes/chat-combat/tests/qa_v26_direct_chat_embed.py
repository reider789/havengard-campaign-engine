"""Full v26 in-chat bootstrap: same DOM, no iframe, no crypto, no stubbed mechanics."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
CANON=json.loads((ROOT.parents[1]/'state/_campaign-state.json').read_text(encoding='utf-8'))
LOADER=(ROOT/'chat_embed_loader_v29.html').read_text(encoding='utf-8')
BUNDLE=(ROOT/'current-chat-battle.html').read_text(encoding='utf-8')
assert LOADER.count('</script>')==1, 'Literal closing-script tag would break bootstrap HTML parsing'
assert 'iframe' not in LOADER.lower()
assert 'crypto.subtle' not in LOADER.lower()
assert 'class CombatVisualFX' in BUNDLE
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1280,'height':1024})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    requests=[]
    def route_bundle(route):
        requests.append(route.request.url)
        route.fulfill(status=200,content_type='text/html; charset=utf-8',body=BUNDLE)
    page.route('**/current-chat-battle.html',route_bundle)
    page.route('**/hayvengard_art_v1.json',lambda route:route.abort())
    page.evaluate('window.__HV_ENABLE_TEST_APIS=true')
    page.set_content(LOADER)
    page.wait_for_timeout(4500)
    current_status=page.locator('#hg-embed-status').inner_text()
    print('BOOT DIAGNOSTICS',repr({'status':current_status,'errors':errors,
          'requests':requests,'battle_count':page.locator('#hv12').count(),
          'board_tiles':page.locator('#hv12 #board button').count(),
          'initialized':page.locator('#hv12').get_attribute('data-init') if page.locator('#hv12').count() else None}),flush=True)
    assert 'Полный v29 запущен' in current_status,current_status
    assert len(requests)==1,requests
    assert page.locator('#hv12 #board button[data-tile]').count()==88
    assert page.locator('#hv12 .hvfx-layer').count()==1
    assert page.locator('#hv12 #hvfx-quality option').count()==3
    assert page.locator('iframe').count()==0
    assert page.locator('#hv12').evaluate("e=>e.classList.contains('hv-fantasy')")
    assert 'gradient' in page.locator('#hv12').evaluate("e=>getComputedStyle(e).backgroundImage")
    snapshot=page.evaluate('window.__HV_TEST_API.snapshot()')
    assert snapshot['sourceRevision']==CANON['state_revision'], (snapshot['sourceRevision'],CANON['state_revision'])
    assert snapshot['units']['rada']['hp']>0
    assert snapshot['units']['daphne']['hp']>0
    assert snapshot['units']['lyutobor']['hp']>0
    assert snapshot['units']['yar']['hp']>0
    checkpoint=page.evaluate('window.__HV_TEST_API.checkpoint()')
    assert checkpoint['session']['version']==12
    assert page.locator('#hv12 #choices button').count()>0
    assert not errors,errors
    page.close()
    # No connection must show honest error rather than silently display a fake game.
    blocked=browser.new_page()
    blocked.route('**/current-chat-battle.html',lambda route:route.abort())
    blocked.set_content(LOADER)
    blocked.wait_for_function("document.querySelector('#hg-embed-status').textContent.includes('Не удалось запустить')",timeout=15000)
    assert blocked.locator('#hv12').count()==0
    assert blocked.locator('iframe').count()==0
    blocked.close()
    browser.close()
print('DIRECT CHAT V27 LOADER: full engine started, 88 cells, saved session, network fallback checked')
