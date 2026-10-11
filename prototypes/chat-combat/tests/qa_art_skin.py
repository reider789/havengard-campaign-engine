"""Visual regression of offline assets, board control and story theme (no canon changes)."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML=(Path(__file__).resolve().parents[1]/'current-chat-battle.html').read_text(encoding='utf-8')
DUMMY='data:image/webp;base64,UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA'
THEMES=('meadow','forest','ruins','city')
HEROES=('yar','daphne','lyutobor','rada')
ENEMIES=('warrior','rogue','archer','mage','wolf','orc','undead','dragon')
OBSTACLES=('wall','broken_wall','rubble','barricade','log','boulder','bush','pillar')
assets={'backgrounds.'+x:{'mime':'image/webp','data':DUMMY} for x in THEMES}
assets.update({'heroes.'+x:{'mime':'image/webp','data':DUMMY} for x in HEROES})
assets.update({'enemies.'+x:{'mime':'image/webp','data':DUMMY} for x in ENEMIES})
assets.update({'obstacles.'+x:{'mime':'image/webp','data':DUMMY} for x in OBSTACLES})
pack={'schema':'havengard-combat-art-v1','version':1,'assets':assets}
assert 'const HG_SKIN_THEME=' in HTML, 'Visual skin is not compiled into current chat battle'
# Offline art must be painted on the INITIAL rendering pass when the pack
# has been inserted into the game root before the engine script executes.
art_tag='<script type="application/json" data-hg-artpack>'+json.dumps(pack,separators=(',',':'))+'</script>'
embedded=HTML.replace('<div id="hv12">','<div id="hv12">'+art_tag,1)
assert embedded!=HTML
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 first=browser.new_page(viewport={'width':1250,'height':1100})
 bootstrap_errors=[]
 first.on('pageerror',lambda e:bootstrap_errors.append(str(e)))
 first.evaluate('window.__HV_ENABLE_TEST_APIS=true')
 first.set_content(embedded)
 first.wait_for_timeout(150)
 assert not bootstrap_errors,bootstrap_errors
 assert first.locator('#board button[data-tile]').count()==88
 assert first.locator('#hv12').evaluate("(e)=>e.classList.contains('hg-skin-on')")
 assert 'data:image/webp;base64' in first.locator('.boardframe').get_attribute('style')
 assert first.evaluate('window.__HV_TEST_API.artLoaded()')
 first.close()
 page=browser.new_page(viewport={'width':1250,'height':1100})
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('**/hayvengard_art_v1.json',lambda route: route.abort())
 page.evaluate('window.__HV_ENABLE_TEST_APIS=true')
 page.set_content(HTML)
 page.wait_for_timeout(120)
 api='window.__HV_TEST_API'
 before=page.evaluate(f'{api}.snapshot()')
 assert page.locator('#board button[data-tile]').count()==88
 assert page.locator('#hg-skin-settings').count()==1
 assert not page.evaluate(f'{api}.artLoaded()')
 # The offline fallback remains playable; simulated installation only tests the renderer.
 page.evaluate(f'(p)=>{api}.artInstall(p)',pack)
 assert page.evaluate(f'{api}.artLoaded()')
 assert page.locator('#hv12').evaluate("(e)=>e.classList.contains('hg-skin-on')")
 assert 'data:image/webp;base64' in page.locator('.boardframe').get_attribute('style')
 assert 'data:image/webp;base64' in page.locator('.unit').first.get_attribute('style')
 assert 'data:image/webp;base64' in page.locator('.tile.wall').first.get_attribute('style')
 assert page.locator('.unit').first.evaluate("(e)=>getComputedStyle(e).borderRadius")=='50%'
 # Selecting new graphics must change state only by the theme field.
 page.locator('#hg-skin-theme').select_option('ruins')
 assert page.evaluate(f'{api}.artTheme()')=='ruins'
 after=page.evaluate(f'{api}.snapshot()')
 for hero in HEROES:
  assert after['units'][hero]['hp']==before['units'][hero]['hp']
  assert after['units'][hero]['action']==before['units'][hero]['action']
 assert after['round']==before['round']
 assert after['sourceRevision']==before['sourceRevision']
 assert after['visualTheme']=='ruins'
 # The selected background survives a checkpoint restore.
 saved=page.evaluate(f'{api}.checkpoint()')
 page.locator('#hg-skin-theme').select_option('forest')
 page.evaluate(f'(x)=>{api}.load(x)',saved)
 assert page.evaluate(f'{api}.artTheme()')=='ruins'
 assert not errors,errors
 browser.close()
print('ART SKIN: all checks passed')
