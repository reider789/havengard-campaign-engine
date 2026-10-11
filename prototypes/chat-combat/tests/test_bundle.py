"""Offline unit test: changing canon changes the next chat bundle, never a running save."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_chat_bundle import build, validate_scene

class ChatBundleTest(unittest.TestCase):
    def test_live_inventory_and_features(self):
        with tempfile.TemporaryDirectory() as work:
            root=Path(work)
            (root/'state').mkdir()
            (root/'prototypes/chat-combat').mkdir(parents=True)
            shutil.copy(Path(__file__).resolve().parents[1]/'engine-v23.html',root/'prototypes/chat-combat/engine-v23.html')
            shutil.copytree(Path(__file__).resolve().parents[1]/'core',root/'prototypes/chat-combat/core')
            state={'state_revision':38,'characters':{}}
            for h in ('yar','daphne','lyutobor','rada'):
                state['characters'][h]={
                    'name':h,'inventory_catalog':{'potion':{'name':'Обычное лечебное зелье','quantity':4}},
                    'resources':{'hp':{'current':17,'max':50}},
                    'character_sheet':{'class_and_level':'уровень 10','armor_class':'КД 17',
                        'combat_reference':[{'source_row':42,'cells':['Новое умение','новый эффект']}]}}
            (root/'state/_campaign-state.json').write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
            manifest=build(root)
            txt=(root/'prototypes/chat-combat/current-chat-battle.html').read_text(encoding='utf-8')
            self.assertEqual(manifest['source_revision'],38)
            self.assertIn('Новое умение',txt)
            self.assertIn('"healing":4',txt)
            self.assertIn('"current":17',txt)
            self.assertIn('data-hg-runtime',txt)
            for core_class in ('CombatDiceRoller','CombatJournal','CombatConditions','CombatBattlefield','CombatSpellResolver','CombatReactionResolver'):
                self.assertIn('class '+core_class,txt)
            self.assertNotIn('/*__HV_COMBAT_CORE_MODULES__*/',txt)
            self.assertNotIn('/*__HV_SPELL_RESOLVER__*/',txt)
            self.assertNotIn('/*__HV_REACTION_RESOLVER__*/',txt)
            self.assertIn('combatSpellResolver.execute(d)',txt)
            self.assertIn('combatReactionResolver.reactChoice(choice)',txt)
            self.assertIn('"version": "v23"',json.dumps(manifest))
            self.assertNotIn('<script src=',txt)
            state['state_revision']=39
            state['characters']['yar']['inventory_catalog']['potion']['quantity']=6
            (root/'state/_campaign-state.json').write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
            nxt=build(root)
            txt2=(root/'prototypes/chat-combat/current-chat-battle.html').read_text(encoding='utf-8')
            self.assertEqual(nxt['source_revision'],39)
            self.assertIn('"healing":6',txt2)
            self.assertNotEqual(txt,txt2)


class StoryEncounterTest(unittest.TestCase):
    @staticmethod
    def scene(rev):
        return {
            'schema_version': 1,
            'kind': 'story', 'battle_id':'test_story_001',
            'source_revision':rev, 'name':'Тестовая засада',
            'narrative_context':'Только автоматическая проверка. Не канонический эпизод.',
            'chronicle_anchor':'QA / искусственный сценарий, НЕ летопись',
            'heroes':{
                'rada':{'cell':'B5','initiative':19},
                'daphne':{'cell':'B6','initiative':13},
                'lyutobor':{'cell':'C5','initiative':12},
                'yar':{'cell':'C6','initiative':11},
            },
            'walls':['G2','G3'],'rubble':['E4'],
            'enemies':[{
                'name':'Тестовый страж','cell':'H5','hp':26,'ac':15,'initiative':17,
                'attack':{'bonus':5,'count':1,'die':8,'flat':3,'range':5},
                'saves':{'STR':2,'DEX':1,'CON':2,'INT':0,'WIS':0,'CHA':0},
                'abilities':[]
            }]
        }

    def test_fails_closed_and_does_not_mutate_canon(self):
        import copy
        good=self.scene(38)
        checked=validate_scene(good,38)
        self.assertEqual(checked['battle_id'],'test_story_001')
        for mutation in (
            lambda s: s.update(source_revision=37),
            lambda s: s.update(kind='training'),
            lambda s: s['heroes']['yar'].update(cell='B5'),
            lambda s: s['enemies'][0]['attack'].pop('die'),
            lambda s: s['enemies'][0]['saves'].pop('CON'),
            lambda s: s['walls'].append('B6'),
            lambda s: s['enemies'][0].update(cell='H9'),
        ):
            changed=copy.deepcopy(good)
            mutation(changed)
            with self.assertRaises(ValueError):
                validate_scene(changed,38)

    def test_story_package_is_separate_from_training(self):
        with tempfile.TemporaryDirectory() as work:
            root=Path(work)
            (root/'state').mkdir()
            chat=root/'prototypes/chat-combat'
            chat.mkdir(parents=True)
            shutil.copy(Path(__file__).resolve().parents[1]/'engine-v23.html',chat/'engine-v23.html')
            shutil.copytree(Path(__file__).resolve().parents[1]/'core',chat/'core')
            state={'state_revision':38,'characters':{}}
            for h in ('yar','daphne','lyutobor','rada'):
                state['characters'][h]={
                    'name':h,'inventory_catalog':{},
                    'resources':{'hp':{'current':37,'max':50}},
                    'character_sheet':{'armor_class':'17','speed':'30','combat_reference':[]}}
            source=root/'state/_campaign-state.json'
            source.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
            scene=chat/'story-input.json'
            scene.write_text(json.dumps(self.scene(38),ensure_ascii=False),encoding='utf-8')
            ordinary=build(root)
            training=(chat/'current-chat-battle.html').read_bytes()
            story=build(root,scene)
            content=(chat/'story-chat-battle.html').read_text(encoding='utf-8')
            self.assertEqual(story['mode'],'story')
            self.assertEqual(story['battle_id'],'test_story_001')
            self.assertEqual(story['source_revision'],38)
            self.assertIn('data-hg-scene',content)
            self.assertIn('test_story_001',content)
            self.assertIn('Тестовая засада',content)
            self.assertEqual((chat/'current-chat-battle.html').read_bytes(),training)
            self.assertEqual(json.loads(source.read_text(encoding='utf-8')),state)
            self.assertNotIn('<script type="application/json" data-hg-scene>',(chat/'current-chat-battle.html').read_text(encoding='utf-8'))
            self.assertEqual(json.loads((chat/'story-manifest.json').read_text(encoding='utf-8'))['battle_id'],'test_story_001')
            self.assertEqual(json.loads((chat/'current-manifest.json').read_text(encoding='utf-8'))['mode'],'training')
            state['state_revision']=39
            source.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
            before=(chat/'story-chat-battle.html').read_bytes()
            with self.assertRaisesRegex(ValueError,'Stale scene'):
                build(root,scene)
            self.assertEqual((chat/'story-chat-battle.html').read_bytes(),before)


if __name__=='__main__':unittest.main()