"""V26 browser QA: Heroes-inspired style, limited VFX, quality controls, accessibility, and battle safety."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json

HTML=(Path(__file__).resolve().parents[1]/'current-chat-battle.html').read_text(encoding='utf-8')
assert 'class CombatVisualFX' in HTML
assert 'hv-fantasy' in HTML
assert 'hvfx-quality' in HTML

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1300,'height':1050})
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/hayvengard_art_v1.json',lambda r:r.abort())
    page.evaluate('window.__HV_ENABLE_TEST_APIS=true')
    page.set_content(HTML)
    api='window.__HV_TEST_API'
    page.wait_for_function(f'{api} && {api}.fxMode()',timeout=10000)
    assert page.locator('#hv12').evaluate('(el)=>el.classList.contains("hv-fantasy")')
    assert page.locator('#board button[data-tile]').count()==88
    assert page.locator('#hvfx-quality option').count()==3
    assert page.locator('.hvfx-layer').count()==1
    assert page.evaluate(f'{api}.fxMode()')=='standard'
    before=page.evaluate(f'{api}.snapshot()')
    # Standard: ephemeral glyphs, damage numbers, no projectile cost.
    page.evaluate(f'''{api}.fxEmit({{kind:'hit',source:'yar',target:'guard',school:'arcane'}})''')
    page.evaluate(f'''{api}.fxEmit({{kind:'damage',target:'guard',amount:14,school:'fire'}})''')
    page.wait_for_timeout(50)
    assert page.locator('.hvfx-spark').count()==1
    assert page.locator('.hvfx-damage').count()==1
    assert page.locator('.hvfx-projectile').count()==0
    assert '−14' in page.locator('.hvfx-damage').first.inner_text()
    assert page.evaluate(f'{api}.snapshot()')==before
    # Animate spell cast and area effect in rich mode; max 16 transient elements.
    page.locator('#hvfx-quality').select_option('rich')
    page.evaluate(f'''{api}.fxEmit({{kind:'cast',source:'daphne',target:'guard',
      point:{{x:7,y:3}},school:'fire'}})''')
    page.wait_for_timeout(40)
    assert page.locator('.hvfx-rune').count()>=1
    assert page.locator('.hvfx-projectile').count()>=1
    assert page.locator('.hvfx-area').count()>=1
    for n in range(60):
        page.evaluate(f'''{api}.fxEmit({{kind:'damage',target:'guard',amount:1,school:'storm'}})''')
    page.wait_for_timeout(40)
    stats=page.evaluate(f'{api}.fxStats()')
    assert stats['peak']<=16,stats
    assert stats['dropped']>0,stats
    assert page.locator('.hvfx-mark').count()<=16
    page.locator('#hvfx-quality').select_option('off')
    assert page.locator('.hvfx-mark').count()==0
    assert page.evaluate(f'{api}.fxMode()')=='off'
    assert page.evaluate(f'{api}.snapshot()')==before
    # Status visualization is read-only, added/removed with current state.
    page.locator('#hvfx-quality').select_option('standard')
    page.evaluate(f'''{api}.set(s=>{{s.units.yar.status.push({{kind:'burn',until:null}})}})''')
    assert page.locator('[data-tile="2,5"] .unit.hvfx-state-burn').count()==1
    page.evaluate(f'''{api}.set(s=>{{s.units.yar.status=s.units.yar.status.filter(x=>x.kind!=='burn')}})''')
    assert page.locator('[data-tile="2,5"] .unit.hvfx-state-burn').count()==0
    # Save excludes cosmetic/ephemeral data; scenario schema and HP stay intact.
    checkpoint=page.evaluate(f'{api}.checkpoint()')
    assert checkpoint['session']['version']==12
    assert 'fx' not in checkpoint['session']
    assert 'visualFX' not in checkpoint['session']
    assert not errors,errors
    context.close()
    # Small viewport: no missing board or controls.
    mobile=browser.new_context(viewport={'width':390,'height':844})
    small=mobile.new_page()
    small.on('pageerror',lambda e:errors.append(str(e)))
    small.route('**/hayvengard_art_v1.json',lambda r:r.abort())
    small.set_content(HTML)
    small.wait_for_selector('#hvfx-quality')
    assert small.locator('#board button[data-tile]').count()==88
    assert small.locator('#hvfx-quality').is_visible()
    mobile.close()
    # Respect OS reduced-motion default for users without stored choice.
    reduced=browser.new_context(reduced_motion='reduce')
    quiet=reduced.new_page()
    quiet.route('**/hayvengard_art_v1.json',lambda r:r.abort())
    quiet.set_content(HTML)
    quiet.wait_for_selector('#hvfx-quality')
    assert quiet.locator('#hvfx-quality').input_value()=='off'
    reduced.close()
    assert not errors,errors
    print(json.dumps({'version':'v26','tested':'desktop, mobile, reduced-motion, limited VFX',
                      'quality_modes':3,'fx_max':stats['peak'],'dropped':stats['dropped'],
                      'save_schema':checkpoint['session']['version'],
                      'source_revision':before['sourceRevision']},ensure_ascii=False))
    browser.close()
