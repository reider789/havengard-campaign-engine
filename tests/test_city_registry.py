#!/usr/bin/env python3
"""City registry integrity, mutation and transaction rollbacks."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import campaignctl as engine
from city_registry import validate_city_registry


def current():
    return json.loads((ROOT / "state/_campaign-state.json").read_text(encoding="utf-8"))


def tx(state, operations, eid):
    return {"expected_state_revision": state["state_revision"],
            "event": {"id": eid, "summary": "Проверка городского реестра", "visibility": "gm"},
            "operations": operations}


class CityRegistryTests(unittest.TestCase):
    def test_city_import_and_main_ledger_are_valid(self):
        state = current()
        self.assertFalse(validate_city_registry(state))
        self.assertEqual(len(state["world"]["city"]["worksites"]), 38)
        self.assertEqual(state["world"]["city_treasury_cp"], 1312633)

    def test_patch_one_worksite_without_rewriting_entire_register(self):
        state = current()
        original = copy.deepcopy(state)
        out = engine.build_result(state, tx(state, [
            {"type": "city_patch_record", "section": "worksites", "record_id": "1",
             "patch": {"equipment_status": "Проверено в тесте"}},
        ], "TEST-CITY-PATCH"))
        self.assertEqual(out["world"]["city"]["worksites"][0]["equipment_status"], "Проверено в тесте")
        self.assertEqual(state, original)

    def test_move_building_more_than_once(self):
        state = current()
        first = engine.build_result(state, tx(state, [
            {"type": "city_map_place", "object_id": "rein-house", "x_m": 20,
             "y_m": 40, "width_m": 10, "height_m": 10}], "TEST-CITY-PLACE1"))
        second = engine.build_result(first, tx(first, [
            {"type": "city_map_place", "object_id": "rein-house", "x_m": 50,
             "y_m": 70, "width_m": 10, "height_m": 10}], "TEST-CITY-PLACE2"))
        self.assertEqual(second["world"]["city"]["layout"]["placements"]["rein-house"]["x_m"], 50)
        self.assertEqual(len(second["world"]["city"]["layout"]["placements"]), 1)

    def test_negative_treasury_change_rolls_back(self):
        state = current()
        with self.assertRaises(ValueError):
            engine.build_result(state, tx(state, [
                {"type": "city_adjust_treasury", "delta_cp": -(state["world"]["city_treasury_cp"]+1)},
            ], "TEST-CITY-DEBT"))
        self.assertEqual(state["world"]["city_treasury_cp"], 1312633)

    def test_refuse_invalid_or_missing_city_entries(self):
        state = current()
        for op in [
            {"type": "city_patch_record", "section": "residents", "record_id": "Нет такого",
             "patch": {"status": "Работает"}},
            {"type": "city_patch_record", "section": "worksites", "record_id": "1",
             "patch": {"id": "100"}},
            {"type": "city_map_place", "object_id": "rein-house", "x_m": True,
             "y_m": 4, "width_m": 8, "height_m": 8},
        ]:
            with self.subTest(op=op), self.assertRaises(ValueError):
                engine.build_result(state, tx(state, [op], "TEST-CITY-BAD"))


if __name__ == "__main__":
    unittest.main()
