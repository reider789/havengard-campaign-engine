#!/usr/bin/env python3
"""City map HTML and import/export contract regression tests."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import copytree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import campaignctl as engine
from build_city_map import make_data, build
from map_layout_import import make_layout_transaction


def source_state():
    return json.loads((ROOT / "state/_campaign-state.json").read_text(encoding="utf-8"))


def source_layout():
    return json.loads((ROOT / "map/layout-base.json").read_text(encoding="utf-8"))


class CityMapTests(unittest.TestCase):
    def test_export_is_from_live_city_state_not_old_master_book(self):
        state = source_state()
        data = make_data()
        city = state["world"]["city"]
        self.assertEqual(data["revision"], state["state_revision"])
        self.assertEqual(data["population"], state["world"]["city_population"])
        self.assertEqual(data["ordinary_occupied"], int(next(
            x["current_occupants"] for x in city["housing"] if x["name"] == "Обычные жилые дома")))
        self.assertEqual(data["garrison"], int(next(
            x["resident_workers"] for x in city["worksites"] if x["name"] == "Гарнизон")))
        self.assertEqual(len(data["objects"]), len(source_layout()["objects"]))
        self.assertEqual(len({x["id"] for x in data["objects"]}), len(data["objects"]))
        self.assertNotIn("characters", data)
        self.assertNotIn("threads", data)

    def test_html_build_contains_same_snapshot_and_no_fetch_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "state").mkdir()
            (dest / "map").mkdir()
            for file in ("state/_campaign-state.json", "map/layout-base.json", "map/template.html"):
                (dest / file).write_bytes((ROOT / file).read_bytes())
            result = build(dest)
            html = result.read_text(encoding="utf-8")
            self.assertNotIn("/*CITY_JSON*/", html)
            self.assertIn('const DATA=', html)
            self.assertNotIn('ghp_', html)
            self.assertNotIn('"knowledge_graph"', html)
            self.assertIn(str(source_state()["state_revision"]), html)
            self.assertIn("heyvengard-map-layout", html)

    def test_layout_file_converts_to_a_safe_map_only_event(self):
        state, base = source_state(), source_layout()
        example = base["objects"][0]
        x = min(164 - example["w"], example["x"] + 0.5)
        payload = {"app": "heyvengard-map-layout", "version": 3,
                   "state_revision": state["state_revision"],
                   "positions": {example["id"]: {"x": x, "y": example["y"]}},
                   "extra": {"reyn": {"x": 114.5, "y": 84}}}
        transaction = make_layout_transaction(payload, state, base)
        self.assertEqual({o["type"] for o in transaction["operations"]}, {"city_map_place"})
        self.assertNotIn("city_adjust_treasury", str(transaction))
        self.assertIn("map-layout:", transaction["unique_key"])
        new_state = engine.build_result(state, transaction)
        self.assertIn(example["id"], new_state["world"]["city"]["layout"]["placements"])
        self.assertIn("reyn-home", new_state["world"]["city"]["layout"]["placements"])
        self.assertEqual(new_state["world"]["city_treasury_cp"], state["world"]["city_treasury_cp"])
        self.assertEqual(new_state["world"]["city_population"], state["world"]["city_population"])

    def test_reject_foreign_or_outside_map_positions(self):
        state, base = source_state(), source_layout()
        bad_examples = [
            {"positions": {"invented-building": {"x": 3, "y": 5}}},
            {"positions": {"garrison": {"x": -5, "y": 5}}},
            {"positions": {"garrison": {"x": 2.25, "y": 7}}},
        ]
        for data in bad_examples:
            payload = {"app": "heyvengard-map-layout", "version": 3, **data}
            with self.subTest(data=data), self.assertRaises(ValueError):
                make_layout_transaction(payload, state, base)


if __name__ == "__main__":
    unittest.main()
