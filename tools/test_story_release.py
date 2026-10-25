#!/usr/bin/env python3
"""Final end-to-end story battle regression after mechanics, AI and terrain changes.

All changes are carried out against a copied state. The real campaign is never
advanced by technical QA, and the test report is not accepted as game canon.
"""
from __future__ import annotations
import copy, json, subprocess, sys, tempfile
from pathlib import Path
from campaignctl import build_result
from prepare_combat_event import changes_to_transaction
from build_party_combat_pack import build
from import_shared_combat_result import prepare

ROOT=Path(__file__).resolve().parents[1]
def verify(engine):
    engine=Path(engine).resolve()
    canonical=ROOT/'state/_campaign-state.json'
    original_bytes=canonical.read_bytes()
    state=json.loads(original_bytes)
    assert state['state_revision']>=32, 'The required level-11 party has not been published'
    narrative_event={
      "event":{"id":"QA-STORY-EXHAUSTION-REHEARSAL",
               "source":"Только проверка на копии канона, НЕ событие кампании",
               "summary":"Репетиция: Яр вступает в поход с одним уровнем истощения",
               "visibility":"gm"},
      "characters":{"yar":{"exhaustion":1}}
    }
    tx=changes_to_transaction(state,narrative_event)
    prepped=build_result(state,tx)
    assert prepped['state_revision']==state['state_revision']+1
    assert prepped['characters']['yar']['combat_continuity']['exhaustion']==1
    assert state==json.loads(original_bytes)
    caps=json.loads(subprocess.check_output(['node',str(engine/'sdk/cli.js'),'capabilities'],text=True))
    package=build(prepped,caps)
    assert package['continuity']['exhaustion']['yar']==1
    scene=package['encounters'][package['default_encounter']]
    # Authored 5-foot surface tiers; no unsupported flying or stacked floors.
    scene['elevation']={'C4':5,'D4':5,'E4':10,'F4':20}
    with tempfile.TemporaryDirectory(prefix='havengard-final-story-') as tmp:
        tmp=Path(tmp)
        source=tmp/'story-pack.json'
        source.write_text(json.dumps(package,ensure_ascii=False),encoding='utf-8')
        reports=tmp/'reports'
        subprocess.run(['node',str(ROOT/'tools/test_shared_party.js'),
                        str(engine),str(source),str(reports)],check=True)
        result_files=sorted(reports.glob('result-*.json'))
        assert len(result_files)==3, 'Need three complete deterministic story simulations'
        for report_file in result_files:
            report=json.loads(report_file.read_text())
            assert report['session_kind']=='story'
            assert report['phase']=='ended'
            assert report['source_revision']==prepped['state_revision']
            assert report['continuity']['exhaustion']['yar']==1
            operation=prepare(report,prepped,engine)
            updated=build_result(prepped,operation)
            assert updated['state_revision']==prepped['state_revision']+1
            assert updated['characters']['yar']['combat_continuity']['exhaustion']==1
            assert build_result(updated,prepare(report,updated,engine))==updated
            next_pack=build(updated,caps)
            assert next_pack['continuity']['exhaustion']['yar']==1
            next_path=tmp/'next-pack.json'
            next_path.write_text(json.dumps(next_pack,ensure_ascii=False))
            subprocess.run(['node',str(engine/'sdk/cli.js'),'validate',str(next_path)],
                           check=True,capture_output=True)
            assert state==json.loads(original_bytes)
    assert canonical.read_bytes()==original_bytes
    print('FINAL STORY BATTLE OK: 3 full deterministic fights with height + exhaustion,'
          ' replay-safe canonical import on copies; live campaign unchanged')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: test_story_release.py ENGINE_ROOT')
    verify(sys.argv[1])
