import importlib.util, json, tempfile, unittest
from pathlib import Path
BUILDER=Path(__file__).resolve().parents[1]/"scripts"/"build_runtime.py"
spec=importlib.util.spec_from_file_location("havengard_builder",BUILDER)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class RuntimeProjectionTests(unittest.TestCase):
    def test_new_skill_and_consumable_are_discovered(self):
        hero={"name":"Тест","resources":{"hp":{"current":11,"max":15}},
              "character_sheet":{"class_and_level":"Тест 10","level":10,"armor_class":"17",
              "abilities":{"ЛОВ":"18 (+4)"},"combat_reference":[
               {"source_row":23,"cells":["Способности — описание для боя"]},
               {"source_row":24,"cells":["Способность","Описание"]},
               {"source_row":25,"cells":["Новая способность","Урон 3к6"]}]},
              "inventory_catalog":{"inv-1":{"name":"Зелье скорости","quantity":3,
                "status":"При себе","description":"Для проверки"}}}
        data={"state_revision":998,"characters":{p:hero for p in mod.PARTY}}
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/"state.json";dest=Path(temp)/"latest.json"
            source.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
            before,after=mod.STATE,mod.OUTPUT
            try:
                mod.STATE,mod.OUTPUT=source,dest;mod.main()
            finally:
                mod.STATE,mod.OUTPUT=before,after
            output=json.loads(dest.read_text(encoding="utf-8"))
            self.assertEqual(output["source_state_revision"],998)
            self.assertEqual(output["characters"]["yar"]["consumables"]["speed"],3)
            self.assertIn("Новая способность",[x["name"] for x in output["characters"]["yar"]["skills_attacks_spells"]])
            self.assertEqual(data["characters"]["yar"]["resources"]["hp"]["current"],11)
if __name__=="__main__":unittest.main()
