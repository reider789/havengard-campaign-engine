#!/usr/bin/env python3
"""One canonical adapter, one pinned shared engine, two desktop delivery paths."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,subprocess,sys
from build_party_combat_pack import build
ROOT=Path(__file__).resolve().parents[1]
def load_bundle(engine):
    spec=importlib.util.spec_from_file_location('shared_bundle',engine/'tools/combat_bundle.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def compile_pack(engine,pack,output):
    output.write_text(json.dumps(pack,ensure_ascii=False,indent=2)+'\n');return json.loads(subprocess.check_output(['node',str(engine/'sdk/cli.js'),'compile',str(output)],text=True))
def generate(engine,project=ROOT,output_root=None,check_lock=True):
    engine=Path(engine).resolve();project=Path(project).resolve();out=Path(output_root or project)
    lock=json.loads((project/'prototypes/shared-combat/engine-lock.json').read_text())
    if check_lock:
        for name,sha in lock['files'].items():
            if hashlib.sha256((engine/name).read_bytes()).hexdigest()!=sha:raise ValueError('Shared engine lock mismatch: '+name)
    cap=json.loads(subprocess.check_output(['node',str(engine/'sdk/cli.js'),'capabilities'],text=True));state=json.loads((project/'state/_campaign-state.json').read_text());pack=build(state,cap)
    dest=out/'prototypes/shared-combat';dest.mkdir(parents=True,exist_ok=True);data=compile_pack(engine,pack,dest/'party-pack.json');bundle=load_bundle(engine)
    subprocess.run([sys.executable,str(engine/'tools/audit_havengard.py'),'--state',str(project/'state/_campaign-state.json'),'--pack',str(dest/'party-pack.json'),'--coverage',str(project/'prototypes/shared-combat/reviewed-profiles.json'),'--output',str(dest/'migration-audit.json'),'--require-ready'],check=True)
    art=json.loads((project/'prototypes/chat-combat/art/hayvengard_art_v1.json').read_text());art=bundle.scene_art(data['runtime'],data['scene'],art);html=bundle.render(data['runtime'],data['scene'],art,root=engine)
    target=out/'prototypes/chat-combat';target.mkdir(parents=True,exist_ok=True)
    for name in ['desktop-battle.html','current-chat-battle.html']:(target/name).write_text(html,encoding='utf-8')
    entry={'schema_version':3,'engine':'shared dnd combat','version':cap['engine'],'current_ui_path':'prototypes/chat-combat/desktop-battle.html','chat_embed_path':'prototypes/chat-combat/current-chat-battle.html','content_pack':'prototypes/shared-combat/party-pack.json','engine_lock':'prototypes/shared-combat/engine-lock.json','verified_source_revision':state['state_revision'],'source_state_sha256':pack['source_state_sha256'],'desktop_only':True,'noncanonical':True,'mode':'standalone desktop HTML file preview','status':'Full current party profiles, prepared spells, classes and attuned combat items use the shared tested core.','legacy_session_policy':'v29 sessions stay in the v29 archive; never reinterpret an active legacy save as v30.','result_import':'tools/import_shared_combat_result.py','architecture':{'core_modules':bundle.MODULES,'source_repository':lock['repository'],'source_commit':lock['commit'],'offline':True}}
    (target/'entrypoint.json').write_text(json.dumps(entry,ensure_ascii=False,indent=2)+'\n')
    manifest={'schema_version':3,'engine_version':cap['engine'],'source_revision':state['state_revision'],'source_state_sha256':pack['source_state_sha256'],'canonical_migration_complete':True,'sha256':hashlib.sha256(html.encode()).hexdigest(),'html_bytes':len(html.encode()),'art_bytes':sum(len(str(v)) for v in art['assets'].values())}
    (target/'current-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--engine-root',type=Path,required=True);p.add_argument('--project',type=Path,default=ROOT);p.add_argument('--output-root',type=Path);p.add_argument('--development',action='store_true');a=p.parse_args();print(json.dumps(generate(a.engine_root,a.project,a.output_root,not a.development),ensure_ascii=False))
