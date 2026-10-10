"""Offline unit test: changing canon changes the next chat bundle, never a running save."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_chat_bundle import build

class ChatBundleTest(unittest.TestCase):
    def test_live_inventory_and_features(self):
        with tempfile.TemporaryDirectory() as work:
            root=Path(work)
            (root/'state').mkdir()
            (root/'prototypes/chat-combat').mkdir(parents=True)
            shutil.copy(Path(__file__).resolve().parents[1]/'engine-v20.html',root/'prototypes/chat-combat/engine-v20.html')
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
            self.assertNotIn('<script src=',txt)
            state['state_revision']=39
            state['characters']['yar']['inventory_catalog']['potion']['quantity']=6
            (root/'state/_campaign-state.json').write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
            nxt=build(root)
            txt2=(root/'prototypes/chat-combat/current-chat-battle.html').read_text(encoding='utf-8')
            self.assertEqual(nxt['source_revision'],39)
            self.assertIn('"healing":6',txt2)
            self.assertNotEqual(txt,txt2)

if __name__=='__main__':unittest.main()