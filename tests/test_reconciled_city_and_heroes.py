#!/usr/bin/env python3
"""Regression checks for the G1M8 documented reconciliation."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import campaignctl as engine
from city_registry import validate_city_registry
from character_catalog import validate_character_catalogs


def current():
    return json.loads((ROOT / "state/_campaign-state.json").read_text(encoding="utf-8"))


def transaction(state, ops, event_id="TEST-G1M8-CONSISTENCY"):
    return {"expected_state_revision": state["state_revision"],
            "event": {"id": event_id, "summary": "Проверка без сохранения", "visibility": "gm"},
            "operations": ops}


class G1M8Reconciliation(unittest.TestCase):
    def test_census_and_housing_match_chronicle(self):
        s = current()
        city = s["world"]["city"]
        live = [r for r in city["residents"] if "погиб" not in r.get("status", "").lower()]
        self.assertEqual(len(live), 221)
        self.assertEqual(len(city["residents"]), 222)  # deceased resident stays as archived record
        self.assertEqual(s["world"]["city_population"], 221)
        rein = [r for r in live if r["name"] in {"Мелания Рейн", "Теодор Рейн"}]
        self.assertEqual(len(rein), 2)
        self.assertTrue(all(r["worksite"] == "—" for r in rein))
        homes = {r["name"]: r for r in city["housing"]}
        self.assertEqual(homes["Обычные жилые дома"]["current_occupants"], "205")
        self.assertEqual(homes["Обычные жилые дома"]["available"], "35 комфортно / 95 максимум")
        self.assertEqual(homes["Усадьба Яра — основной дом"]["current_occupants"], "8")
        self.assertEqual(validate_city_registry(s), [])

    def test_worksite_and_qualifications(self):
        s = current()
        city = s["world"]["city"]
        roster = {r["name"]: r for r in city["residents"]}
        training = {t["worker"]: t for t in city["training"]}
        self.assertEqual(sum(int(w.get("resident_workers", 0)) for w in city["worksites"]), 200)
        self.assertEqual(len(city["worksites"]), 38)
        self.assertEqual(len(city["training"]), 200)
        self.assertTrue(all(roster[n]["qualification"] == t["current_grade"]
                            for n, t in training.items() if n in roster))
        self.assertNotIn("Житель 158", training)  # 14-year-old school pupil, not professional trainee
        self.assertIn("Житель 12", training)      # archived deceased, never silently removed

    def test_animals_are_not_double_counted(self):
        city = current()["world"]["city"]
        self.assertEqual(len(city["animals"]), 22)
        self.assertEqual(sum(int(a["quantity"]) for a in city["animals"] if a["category"].startswith("Драк")), 12)
        self.assertEqual(next(a["quantity"] for a in city["animals"] if a["name_or_group"] == "Городской конюшенный парк"), "28")
        horses = next(a for a in city["animals"] if a["name_or_group"] == "Вельмар — награда за «Медный Ключ»")
        self.assertEqual(horses["quantity"], "4")
        self.assertIn("не являются собственностью города", horses["status"])

    def test_hero_inventory_priority_and_uniqueness(self):
        s = current()
        self.assertFalse(validate_character_catalogs(s))
        self.assertEqual(s["characters"]["yar"]["resources"]["storm_thrower_ammo"]["current"], 20)
        self.assertEqual(s["characters"]["rada"]["resources"]["arrows"]["current"], 57)
        def item(who, name):
            return next(v for v in s["characters"][who]["inventory_catalog"].values()
                        if v["name"] == name)
        self.assertEqual(item("rada", "Стрелы")["quantity"], 57)
        self.assertEqual(item("yar", "Обычное лечебное зелье")["quantity"], 3)
        self.assertEqual(item("yar", "Противоядие")["quantity"], 3)
        self.assertEqual(item("yar", "Алхимический огонь")["quantity"], 2)
        self.assertIn("Сложена", item("lyutobor", "Мгновенная крепость Даэрна")["status"])
        self.assertIn("При Яре", item("yar", "Звёздная мантия")["status"])
        self.assertFalse(any(v["name"] == "Звёздная мантия"
                             for v in s["characters"]["daphne"]["inventory_catalog"].values()))
        self.assertEqual(s["characters"]["daphne"]["resources"]["shield_magic_initiate"]["current"], 1)
        yar = s["characters"]["yar"]
        self.assertTrue(yar["character_sheet"]["portable_hole_policy"]["packed_after_last_road_camp"])
        self.assertEqual(len(yar["character_sheet"]["portable_hole_policy"]["delivered_expansion_modules"]), 3)
        self.assertNotIn("paid_but_delivery_not_confirmed", yar["character_sheet"]["portable_hole_policy"])
        for row_id in (74, 75, 76):
            self.assertIn(f"yar-source-row-{row_id}", yar["inventory_catalog"])
            self.assertIn("Получен", yar["inventory_catalog"][f"yar-source-row-{row_id}"]["status"])

    def test_reject_broken_derived_census_or_housing(self):
        s = current()
        original = copy.deepcopy(s)
        for op in [
            {"type": "set_world_field", "field": "city_population", "value": 222},
            {"type": "city_patch_record", "section": "housing", "record_id": "Обычные жилые дома",
             "patch": {"current_occupants": "207"}},
            {"type": "city_patch_record", "section": "worksites", "record_id": "1",
             "patch": {"resident_workers": "8"}},
        ]:
            with self.subTest(op=op), self.assertRaises(engine.CampaignError):
                engine.build_result(s, transaction(s, [op]))
            self.assertEqual(s, original)

    def test_transfer_item_moves_catalog_reference(self):
        s = current()
        item = "yar-star-mantle"
        transferred = engine.build_result(s, transaction(s, [
            {"type": "transfer_item", "from": "yar", "to": "daphne", "item": item}
        ], event_id="TEST-CATALOG-TRANSFER"))
        self.assertNotIn(item, transferred["characters"]["yar"]["inventory"])
        self.assertNotIn(item, transferred["characters"]["yar"]["inventory_catalog"])
        self.assertIn(item, transferred["characters"]["daphne"]["inventory"])
        self.assertIn(item, transferred["characters"]["daphne"]["inventory_catalog"])
        self.assertFalse(validate_character_catalogs(transferred))


if __name__ == "__main__":
    unittest.main()
