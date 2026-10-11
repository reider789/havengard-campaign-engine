"""End-to-end plot-battle bootstrap. All scenes here are synthetic, never canonical events."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from playwright.sync_api import sync_playwright

CHAT = Path(__file__).resolve().parents[1]
REPO = CHAT.parents[1]
sys.path.insert(0, str(CHAT))
from build_chat_bundle import build

canon = json.loads((REPO/'state/_campaign-state.json').read_text(encoding='utf-8'))
rev = canon['state_revision']
scene = {
    'schema_version':1,'kind':'story','battle_id':'qa_story_0001',
    'source_revision':rev,'name':'Учебная проверка сценария',
    'narrative_context':'Синтетическая проверка инициализации. Не событие Хейвенгарда.',
    'chronicle_anchor':'QA ONLY — вне сюжетной летописи',
    'heroes':{
        'rada':{'cell':'B5','initiative':22},
        'daphne':{'cell':'B6','initiative':16},
        'lyutobor':{'cell':'C5','initiative':14},
        'yar':{'cell':'C6','initiative':11}
    },
    'walls':['F3','F4'], 'rubble':['E4'],
    'enemies':[{
        'name':'Условный дозорный','cell':'H5','hp':33,'ac':15,'initiative':13,
        'attack':{'bonus':5,'count':1,'die':8,'flat':3,'range':5},
        'saves':{'STR':2,'DEX':1,'CON':2,'INT':0,'WIS':0,'CHA':0},'abilities':[]
    }]
}
def source_with_saved(html, saved):
    marker='const received=globalThis.__bindings?.value;'
    replacement='const received='+json.dumps({'session':saved},ensure_ascii=False,separators=(',',':'))+';'
    assert marker in html
    return html.replace(marker,replacement,1)

with TemporaryDirectory() as work:
    scene_path=Path(work)/'scene.json'
    output=Path(work)/'story-battle.html'
    scene_path.write_text(json.dumps(scene,ensure_ascii=False),encoding='utf-8')
    manifest=build(REPO,scene_path,output)
    assert manifest['battle_id']==scene['battle_id'] and manifest['source_revision']==rev
    html=output.read_text(encoding='utf-8')
    assert html.count('data-hg-scene')==2  # opening tag and JS selector
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1360,'height':1100})
        errors=[]
        page.on('pageerror',lambda exc:errors.append(str(exc)))
        page.evaluate('window.__HV_ENABLE_TEST_APIS=true')
        page.set_content(html)
        page.wait_for_timeout(150)
        api='window.__HV_TEST_API'
        assert not errors,errors
        assert page.locator('#board button[data-tile]').count()==88
        state=page.evaluate(f'{api}.snapshot()')
        assert state['sessionKind']=='story'
        assert state['battleId']==scene['battle_id']
        assert state['chronicleAnchor']==scene['chronicle_anchor']
        assert state['sourceRevision']==rev
        assert state['battleName']==scene['name']
        assert state['units']['guard']['hp']==0 and state['units']['archer']['hp']==0
        assert state['units']['yar']['hp']==canon['characters']['yar']['resources']['hp']['current']
        assert state['units']['daphne']['hp']==canon['characters']['daphne']['resources']['hp']['current']
        assert state['index']==0 and page.locator('#actor').inner_text().startswith('Ход: Рада')
        assert 'Рада: выстрел по стражу' not in '\n'.join(state['history'])
        assert scene['chronicle_anchor'] in page.locator('#v21story-context').inner_text()
        assert page.locator('[data-v21-new]').count()==0
        report=page.evaluate(f'{api}.outcome()')
        assert report['battle_id']==scene['battle_id']
        assert report['chronicle_anchor']==scene['chronicle_anchor']
        assert report['canonical_state_unchanged'] is True
        assert report['outcome_can_be_applied_automatically'] is False
        # Persist a distinctive noncanonical session and verify it is resumed, not rebuilt.
        page.evaluate(f'{api}.set(s=>{{s.units.yar.hp-=7;s.round=3;}})')
        active=page.evaluate(f'{api}.snapshot()')
        resumed=browser.new_page()
        resume_errors=[]
        resumed.on('pageerror',lambda exc:resume_errors.append(str(exc)))
        resumed.set_content(source_with_saved(html,active))
        resumed.wait_for_timeout(120)
        assert not resume_errors,resume_errors
        got=resumed.locator('#v21story-context').inner_text()
        assert scene['chronicle_anchor'] in got
        assert resumed.locator('#actor').count()==1
        # Page error would occur if a demo or a stale effect dictionary overwrote the saved state.
        resumed_page=page.evaluate('()=>null')  # client remains separate
        assert resumed.locator('#round').inner_text()=='Раунд 3'
        resumed.close()
        # An unrelated saved battle must never be resumed in the narrative scene.
        old=json.loads(json.dumps(active));old['battleId']='other_story';old['units']['yar']['hp']=1
        unrelated=browser.new_page()
        unrelated_errors=[]
        unrelated.on('pageerror',lambda exc:unrelated_errors.append(str(exc)))
        unrelated.evaluate('window.__HV_ENABLE_TEST_APIS=true')
        unrelated.set_content(source_with_saved(html,old))
        unrelated.wait_for_timeout(120)
        assert not unrelated_errors,unrelated_errors
        fresh=unrelated.evaluate(f'{api}.snapshot()')
        assert fresh['battleId']==scene['battle_id'] and fresh['round']==1
        assert fresh['units']['yar']['hp']==canon['characters']['yar']['resources']['hp']['current']
        unrelated.close()
        # Import of another story must be rejected before changing any current counters.
        bad=page.evaluate(f'{api}.checkpoint()')
        bad['session']['battleId']='other_story'
        try:
            page.evaluate(f'(x)=>{api}.load(x)',bad)
            raise AssertionError('Unrelated battle checkpoint was accepted')
        except Exception as exc:
            if 'was accepted' in str(exc):raise
        assert page.evaluate(f'{api}.snapshot().battleId')==scene['battle_id']
        # Plot reset must show confirmation and not silently load Old Bridge.
        page.locator('[data-op="reset"]').click()
        assert page.locator('[data-v21-story-reset-cancel]').count()==1
        assert page.evaluate(f'{api}.snapshot().round')==3
        page.locator('[data-v21-story-reset-cancel]').click()
        assert page.evaluate(f'{api}.snapshot().round')==3
        page.locator('[data-op="reset"]').click()
        page.locator('[data-v21-story-reset-confirm]').click()
        reset=page.evaluate(f'{api}.snapshot()')
        assert reset['round']==1 and reset['battleId']==scene['battle_id']
        assert reset['units']['guard']['hp']==0
        assert not errors,errors
        browser.close()
    print('V21 STORY BATTLE AUTOBOOT QA PASSED')
