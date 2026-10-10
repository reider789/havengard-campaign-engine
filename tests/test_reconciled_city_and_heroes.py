#!/usr/bin/env python3
"""Check invariants that must remain true as the story moves forward.

Historical totals belong to transaction receipts and migration snapshots, not
to regression assertions against the current campaign state.
"""
import copy
import json
import re
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


def transaction(state, ops, event_id="TEST-DYNAMIC-CONSISTENCY"):
    return {"expected_state_revision": state["state_revision"],
            "event": {"id": event_id, "summary": "Изолированная проверка.", "visibility": "gm"},
            "operations": ops}


class LiveConsistencyTests(unittest.TestCase):
    def test_population_and_housing_agree_in_current_state(self):
        state = current()
        city = state["world"]["city"]
        active = [r for r in city["residents"] if not any(
            word in str(r.get("status", "")).lower() for word in ("погиб", "умер", "выбыл"))]
        self.assertEqual(len(active), state["world"]["city_population"])
        self.assertEqual(validate_city_registry(state), [])

    def test_worksite_assignments_and_qualifications(self):
        city = current()["world"]["city"]
        roster = {r["name"]: r for r in city["residents"]}
        training = {t["worker"]: t for t in city["training"]}
        for name, item in training.items():
            if name in roster:
                self.assertEqual(roster[name]["qualification"], item["current_grade"])
        # No need to freeze the number of schools, workers or residents.
        self.assertEqual(len({s["id"] for s in city["worksites"]}), len(city["worksites"]))

    def test_animals_do_not_contain_aggregate_rows(self):
        city = current()["world"]["city"]
        for animal in city["animals"]:
            self.assertNotEqual(animal["category"], "Показатель")
            self.assertNotRegex(str(animal["name_or_group"]), r"^\d+$")

    def test_hero_catalogs_and_consumable_bounds(self):
        state = current()
        self.assertEqual(validate_character_catalogs(state), [])
        for hero in state["characters"].values():
            for name, value in hero.get("resources", {}).items():
                if isinstance(value, dict) and "current" in value:
                    self.assertGreaterEqual(value["current"], 0, name)
                    self.assertLessEqual(value["current"], value["max"], name)
        for hero in state["characters"].values():
            for item in hero.get("inventory_catalog", {}).values():
                amount = item.get("quantity")
                if amount is not None:
                    self.assertGreaterEqual(amount, 0)

    def test_shooting_one_arrow_does_not_fail_when_count_changes(self):
        state = current()
        arrows = state["characters"]["rada"]["resources"]["arrows"]["current"]
        if arrows <= 0:
            self.skipTest("Рада сейчас без стрел")
        shot = engine.build_result(state, transaction(state, [
            {"type": "adjust_resource", "id": "rada", "resource": "arrows", "delta": -1}
        ], "TEST-NEXT-ARROW"))
        self.assertEqual(shot["characters"]["rada"]["resources"]["arrows"]["current"], arrows - 1)
        self.assertFalse(validate_character_catalogs(shot))
        self.assertEqual(state["characters"]["rada"]["resources"]["arrows"]["current"], arrows)

    def test_legal_treasury_change_is_not_blocked_by_old_snapshot(self):
        state = current()
        before = state["world"]["city_treasury_cp"]
        plus = engine.build_result(state, transaction(state, [
            {"type": "city_adjust_treasury", "delta_cp": 100}
        ], "TEST-FUTURE-TREASURY"))
        self.assertEqual(plus["world"]["city_treasury_cp"], before + 100)
        self.assertEqual(state["world"]["city_treasury_cp"], before)

    def test_reject_population_staff_and_housing_inconsistency(self):
        state = current()
        original = copy.deepcopy(state)
        homes = next(x for x in state["world"]["city"]["housing"] if x["name"] == "Обычные жилые дома")
        staff = next(x for x in state["world"]["city"]["worksites"] if x["name"] == "Администрация")
        for op in [
            {"type": "set_world_field", "field": "city_population", "value": state["world"]["city_population"] + 1},
            {"type": "city_patch_record", "section": "housing", "record_id": homes["name"],
             "patch": {"current_occupants": str(int(homes["current_occupants"]) + 1)}},
            {"type": "city_patch_record", "section": "worksites", "record_id": staff["id"],
             "patch": {"resident_workers": str(int(staff["resident_workers"]) + 1)}},
        ]:
            with self.subTest(op=op), self.assertRaises((engine.CampaignError, ValueError)):
                engine.build_result(state, transaction(state, [op]))
            self.assertEqual(state, original)

    def test_transfer_moves_metadata(self):
        state = current()
        state["characters"]["yar"]["inventory"].append("TEST-FUTURE-ITEM")
        state["characters"]["yar"]["inventory_catalog"]["TEST-FUTURE-ITEM"] = {
            "name": "Тестовый предмет", "quantity": 1, "status": "У Яра"}
        moved = engine.build_result(state, transaction(state, [
            {"type": "transfer_item", "from": "yar", "to": "daphne", "item": "TEST-FUTURE-ITEM"}
        ], "TEST-TRANSFER-CATALOG"))
        self.assertNotIn("TEST-FUTURE-ITEM", moved["characters"]["yar"]["inventory_catalog"])
        self.assertIn("TEST-FUTURE-ITEM", moved["characters"]["daphne"]["inventory_catalog"])
        self.assertEqual(validate_character_catalogs(moved), [])


if __name__ == "__main__":
    unittest.main()
