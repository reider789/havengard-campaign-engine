#!/usr/bin/env python3
"""Build an offline, GM-assisted battle from data; never change live state.

Default output is a clearly labelled rehearsal. Story start requires an explicit
deployment, verified finite populations, and the current canonical hash.
"""
from pathlib import Path
import argparse, base64, copy, hashlib, json, subprocess, uuid
from build_shared_combat import ROOT, load_bundle
from build_party_combat_pack import build

CATALOGUE=ROOT/'prototypes/prepared-encounters/perelomye/catalog.json'
def cell(x,y):
    out='';x+=1
    while x:x,d=divmod(x-1,26);out=chr(65+d)+out
    return out+str(y+1)
def terrain(room):
    walls=set();rubble=set();cover={};elevation={}
    width,height=room['w']//5,room['h']//5
    for raw in room.get('terrain','').split(';'):
        if not raw:continue
        kind,coords=raw.split(':');x,y,w,h=map(int,coords.split(','))
        for xx in range(x,min(x+w,width)):
            for yy in range(y,min(y+h,height)):
                c=cell(xx,yy)
                if kind in ['wall','pillar']:walls.add(c)
                elif kind in ['rubble','plants']:rubble.add(c)
                elif kind=='crate':cover[c]=2
                elif kind=='ledge' and room['id']=='T8':elevation[c]=10
    # Lightning rods are interactive, destructible arena objects, not solid
    # unbreakable map walls. Their collision is adjudicated by the GM.
    for o in room.get('objects',[]):walls.discard(cell(o['x'],o['y']))
    return dict(width=width,height=height,walls=sorted(walls),rubble=sorted(rubble),cover=cover,elevation=elevation)
def make_pack(engine,room_id,deployment=None,story=False):
    cat=json.loads(CATALOGUE.read_text());template=cat['encounters'][room_id];room=template['room']
    lock=json.loads((ROOT/'prototypes/shared-combat/engine-lock.json').read_text())
    for name,sha in lock['files'].items():
        if hashlib.sha256((engine/name).read_bytes()).hexdigest()!=sha:raise ValueError('Engine lock mismatch: '+name)
    caps=json.loads(subprocess.check_output(['node',str(engine/'sdk/cli.js'),'capabilities'],text=True))
    state=json.loads((ROOT/'state/_campaign-state.json').read_text());pack=build(state,caps)
    if story:
        if not deployment or deployment.get('source_revision')!=pack['revision'] or deployment.get('source_state_sha256')!=pack['source_state_sha256']:
            raise ValueError('Story deployment must pin the CURRENT canonical revision/hash')
        if deployment.get('population_verified') is not True or not deployment.get('source'):
            raise ValueError('Confirm actual survivors, hostility, location, clock and finite population with a source')
        if not deployment.get('heroes') or 'enemies' not in deployment:raise ValueError('Explicit current hero/enemy positions required')
        if deployment.get('initial_deployment') is not True:raise ValueError('For a return encounter resume the actual saved session; this builder only creates an explicitly confirmed first deployment')
        if room_id=='G5':raise ValueError('G5 is already in preparation elsewhere: resume its actual save; never reset it with this builder')
    scene=dict(name=('РЕПЕТИЦИЯ · ' if not story else '')+room['title'],kind='story' if story else 'training',
       scene_id=room_id,battle_id=('prepared-' if story else 'rehearsal-')+room_id+'-'+str(uuid.uuid4()),theme='ruins',
       source_revision=pack['revision'],source_state_sha256=pack['source_state_sha256'],**terrain(room))
    population=template['population']
    if deployment:
        scene['heroes']=copy.deepcopy(deployment['heroes']);scene['enemies']=copy.deepcopy(deployment['enemies'])
        allowed={p['id']:p['profile'] for p in population}
        # L5 positions are intentionally unspecified in the source, so its two
        # OTHER shift guards require an explicit, nonduplicating deployment.
        if room_id=='L5':allowed={'L5-C05-3':'C05','L5-C05-4':'C05'}
        if room_id=='V4':allowed={'faction-roven':'C23','faction-itta':'C24','faction-demar':'C26',**{f'faction-guard-{i}':'C05_company' for i in [1,2]},**{f'faction-worker-{i}':['C03','C04'] for i in range(1,7)}}
        for e in scene['enemies']:
            expected=allowed.get(e['id']);valid=e['profile'] in expected if isinstance(expected,list) else expected==e['profile']
            if not valid:raise ValueError('Unknown/additional population: '+e['id'])
        if len({e['id'] for e in scene['enemies']})!=len(scene['enemies']):raise ValueError('Duplicate population ID')
        if deployment.get('battlefield'):
            override=deployment['battlefield']
            if not set(override)<=set(['width','height','walls','rubble','cover','elevation','name']):raise ValueError('Unsupported battlefield override')
            if room_id!='V4':raise ValueError('Source arenas cannot be silently replaced')
            scene.update(copy.deepcopy(override))
    else:
        if not population:raise ValueError('This room needs explicit real positions; no population is invented')
        scene['enemies']=[dict(id=p['id'],profile=p['profile'],cell=cell(p['x'],p['y'])) for p in population]
        # Demonstration positions only. Never use these as an authored story.
        occupied={(p['x']+dx,p['y']+dy) for p in population for dx in range(cat['profiles'][p['profile']].get('footprint',1)) for dy in range(cat['profiles'][p['profile']].get('footprint',1))}
        candidates=[cell(x,y) for y in range(scene['height']-1,-1,-1) for x in range(scene['width']) if (x,y) not in occupied and cell(x,y) not in scene['walls']]
        scene['heroes']={k:{'cell':candidates[i*2]} for i,k in enumerate(pack['characters'])}
    if set(scene['heroes'])!=set(pack['characters']):raise ValueError('All four canonical heroes must be present and player controlled')
    if deployment and deployment.get('resource_overrides'):
        if not deployment.get('resource_override_source'):raise ValueError('Resource overrides need a played source')
        for cid,pools in deployment['resource_overrides'].items():
            if cid not in pack['characters']:raise ValueError('Unknown hero')
            for name,value in pools.items():
                pool=pack['characters'][cid]['resources'].get(name)
                if not pool or type(value) is not int or not 0<=value<=pool['max']:raise ValueError('Invalid resource override')
                pool['current']=value
    for enemy in scene['enemies']:
        enemy['tokenKey']=cat['profiles'][enemy['profile']]['tokenKey']
        if enemy['profile']=='C32':enemy['resources']={'spell_slots':{'2':{'current':2,'max':2},'3':{'current':2,'max':2}}}
    overlap=set(pack['profiles'])&set(cat['profiles'])
    if overlap:raise ValueError('Profile collision '+str(overlap))
    pack['profiles'].update(copy.deepcopy(cat['profiles']))
    pack['requires']=list(dict.fromkeys(pack.get('requires',[])+[cat['engine']['requiredExtension'],'perelomye-runtime-v1']))
    pack['encounters']={room_id:scene};pack['default_encounter']=room_id
    pack['notes']=['GM-assisted: полная карточка, геометрия и специальные решения ведущего.','Подготовка не является сыгранным событием.']
    return pack,cat
def render(engine,pack,cat,output):
    output.parent.mkdir(parents=True,exist_ok=True)
    source=output.with_suffix('.pack.json');source.write_text(json.dumps(pack,ensure_ascii=False,indent=2)+'\n')
    data=json.loads(subprocess.check_output(['node',str(ROOT/'tools/prepared_combat_cli.js'),str(engine),str(CATALOGUE),str(source)],text=True))
    bundle=load_bundle(engine)
    artpath=ROOT/'prototypes/chat-combat/art/hayvengard_art_v1.json'
    art=json.loads(artpath.read_text()) if artpath.exists() else {'assets':{}}
    for key,c in cat['cards'].items():
        # Code-generated SVG tokens are deterministic, offline and distinct;
        # silhouette/ID does not pretend to be an undisclosed portrait.
        color={'C09':'#3b6650','C10':'#ba9d44','C12':'#8a7662','C29':'#62538b','C32':'#9d709f','C33':'#657f9e','C34':'#9d8152','C36':'#867194','C37':'#99845d'}.get(key,'#5e7c88')
        glyph={'C09':'❧','C10':'⬡','C12':'◆','C29':'●','C32':'♬','C33':'ϟ','C34':'⚙','C36':'♩','C37':'♜'}.get(key,'♟')
        label='C05 · МЦ' if key=='C05_company' else key
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128"><circle cx="64" cy="64" r="59" fill="{color}" stroke="#eadcba" stroke-width="5"/><text x="64" y="78" font-size="65" text-anchor="middle" fill="#fff4d4">{glyph}</text><text x="64" y="111" font-size="18" text-anchor="middle" fill="white">{label}</text></svg>'
        art.setdefault('assets',{})['enemies.prepared_'+key]={'mime':'image/svg+xml','data':base64.b64encode(svg.encode()).decode(),'bytes':len(svg.encode())}
    html=bundle.render(data['runtime'],data['scene'],bundle.scene_art(data['runtime'],data['scene'],art),root=engine)
    core=(engine/'web/combat_app.js').read_text()
    install=(ROOT/'prototypes/prepared-encounters/gm-assist.js').read_text()+'\nconst PreparedCatalogue='+bundle.encoded(cat)+';\ninstallPreparedGM({CombatContentPack,CombatCampaignAdapter,CombatRulesEngine,CombatMagic},PreparedCatalogue);\n'+(ROOT/'prototypes/prepared-encounters/prepared-runtime.js').read_text()+'\ninstallPreparedRuntime({CombatContentPack,CombatCampaignAdapter,CombatRulesEngine,CombatMagic,CombatActivities},PreparedCatalogue);\n'
    # A small, explicit integration seam; fail closed if upstream changes it.
    assert html.count(core)==1
    ui=core.replace('function schedule() {','function schedule() {\n    if(engine?.s.prepared) return;')
    assert ui!=core
    marker='  function download(name, value) {'
    assert ui.count(marker)==1
    ui=ui.replace('Object.values(engine.s.objects).find((o) => o.owner === id)', 'Object.values(engine.s.objects).find((o) => o.owner === id && !o.preparedObject)')
    ui=ui.replace('Рука Бигби · ', 'Предмет · ')
    ui=ui.replace(marker,'  globalThis.PreparedGMPort = {getEngine:()=>engine, act, save, render};\n'+marker)
    html=html.replace(core,install+ui)
    panel=(ROOT/'prototypes/prepared-encounters/gm-panel.js').read_text()+'\n'+(ROOT/'prototypes/prepared-encounters/runtime-panel.js').read_text()
    html=html.replace('</body>','<script>'+panel+'</script></body>')
    output.write_text(html)
    return {'room':data['scene']['scene_id'],'mode':data['scene']['kind'],'source_revision':pack['revision'],
      'source_state_sha256':pack['source_state_sha256'],'html_sha256':hashlib.sha256(html.encode()).hexdigest(),
      'requiredExtension':cat['engine']['requiredExtension'],'execution':'gm-assisted','preparation_only':True}
def main():
    p=argparse.ArgumentParser();p.add_argument('--engine-root',type=Path,required=True);p.add_argument('--room',required=True)
    p.add_argument('--deployment',type=Path);p.add_argument('--story',action='store_true');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();deployment=json.loads(a.deployment.read_text()) if a.deployment else None
    pack,cat=make_pack(a.engine_root.resolve(),a.room,deployment,a.story)
    result=render(a.engine_root.resolve(),pack,cat,a.output)
    a.output.with_suffix('.manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(a.output)
if __name__=='__main__':main()
