"""V25 efficiency regression: automatic art, DOM identity, coalesced saves and large-encounter timing.
All battles in this script are synthetic; no campaign resources are changed.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'current-chat-battle.html').read_text(encoding='utf-8')
DUMMY='data:image/webp;base64,UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA'
groups={'backgrounds':['meadow','forest','ruins','city'],
        'heroes':['yar','daphne','lyutobor','rada'],
        'enemies':['warrior','rogue','archer','mage','wolf','orc','undead','dragon'],
        'obstacles':['wall','rubble']}
ART={'schema':'havengard-combat-art-v1','version':1,'assets':{
    f'{group}.{name}':{'mime':'image/webp','data':DUMMY}
    for group,names in groups.items() for name in names
}}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1400,'height':1200})
    errors=[]
    requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    def serve_art(route):
        requests.append(route.request.url)
        route.fulfill(status=200,content_type='application/json',body=json.dumps(ART))
    page.route('**/hayvengard_art_v1.json',serve_art)
    page.evaluate('window.__HV_ENABLE_TEST_APIS=true;window.__bindings={setValue(v){window.__lastChatSave=v;window.__chatSaves=(window.__chatSaves||0)+1}};Math.random=()=>0.6')
    page.set_content(HTML)
    api='window.__HV_TEST_API'
    page.wait_for_function(f'{api} && {api}.artLoaded()',timeout=15000)
    assert len(requests)==1,requests
    assert page.locator('#hg-skin-file').count()==0
    assert page.locator('#board button[data-tile]').count()==88,errors
    assert page.locator('.unit').first.get_attribute('style') is not None
    # A save sends the SESSION only when the identical canonical reference is inside HTML.
    page.evaluate(f'{api}.flushSave()')
    bound=page.evaluate('window.__lastChatSave')
    assert 'session' in bound and 'source' not in bound, bound.keys()
    assert bound['session']['version']==12
    # Keep the same DOM elements when nothing changes, including their graphic skins.
    first=page.locator('[data-tile="0,0"]').element_handle()
    state_before=page.evaluate(f'{api}.snapshot()')
    p0=page.evaluate(f'{api}.persistenceStats()')
    stats0=page.evaluate(f'{api}.uiStats()')
    elapsed=page.evaluate('''async()=>{
      const start=performance.now();
      for(let i=0;i<15;i++)window.__HV_TEST_API.render();
      await Promise.resolve();
      return performance.now()-start;
    }''')
    p1=page.evaluate(f'{api}.persistenceStats()')
    stats1=page.evaluate(f'{api}.uiStats()')
    first_after=page.locator('[data-tile="0,0"]').element_handle()
    assert first.evaluate('(x,y)=>x===y',first_after), 'Unchanged tile was destroyed'
    assert stats1['tilesRetained']-stats0['tilesRetained']>=88*15-5,(stats0,stats1)
    assert p1['serializationCount']-p0['serializationCount']<=2,(p0,p1)
    assert p1['hostUpdates']==p0['hostUpdates'],(p0,p1)
    assert page.evaluate(f'{api}.snapshot().units.yar.hp')==state_before['units']['yar']['hp']
    # Real HP mutation must still be persisted exactly once, without resending reference source.
    page.evaluate(f'{api}.set(s=>{{s.units.yar.hp-=3;}})')
    page.wait_for_timeout(25)
    assert page.evaluate('window.__lastChatSave.session.units.yar.hp')==state_before['units']['yar']['hp']-3
    assert page.evaluate('window.__lastChatSave.source') is None
    # Scene stress: 20 enemies, same 88-cell area, retained board DOM and checkpoint import.
    used={'E6','B7','D6','C6'}
    cells=[chr(65+x)+str(y) for y in range(1,9) for x in range(11)
           if chr(65+x)+str(y) not in used]
    scene={
       'name':'Бенчмарк — 20 противников','kind':'training',
       'heroes':{'rada':{'cell':'E6','initiative':27},
                 'daphne':{'cell':'B7','initiative':17},
                 'lyutobor':{'cell':'D6','initiative':13},
                 'yar':{'cell':'C6','initiative':10}},
       'walls':[],'rubble':[],
       'enemies':[{'name':f'Солдат {n+1}','cell':cells[n+10],
                    'hp':30,'ac':14,'initiative':8,
                    'attack':{'bonus':5,'count':1,'die':6,'flat':3,'range':5},
                    'saves':{'STR':2,'DEX':1,'CON':2,'WIS':0},'abilities':[]}
                   for n in range(20)]
    }
    page.evaluate(f'(scene)=>{api}.newScenario(scene)',scene)
    assert page.locator('[data-tile]').count()==88
    assert page.evaluate(f'Object.keys({api}.snapshot().units).length')>=24
    large_ms=page.evaluate('''async()=>{
        const before=performance.now();
        for(let i=0;i<8;i++)window.__HV_TEST_API.render();
        await Promise.resolve();
        return performance.now()-before;
    }''')
    checkpoint=page.evaluate(f'{api}.checkpoint()')
    page.evaluate(f'(cp)=>{api}.load(cp)',checkpoint)
    assert page.evaluate(f'{api}.snapshot().battleName')==scene['name']
    assert not errors,errors
    print(json.dumps({'benchmark':'v25','empty_redraws':15,
         'no_op_render_ms':round(elapsed,2),'large_encounter_redraws':8,
         'large_render_ms':round(large_ms,2),
         'board_retained':stats1['tilesRetained']-stats0['tilesRetained'],
         'extra_serializations':p1['serializationCount']-p0['serializationCount'],
         'auto_art_requests':len(requests),
         'bundle_bytes':len(HTML.encode('utf-8'))},ensure_ascii=False))
    browser.close()
