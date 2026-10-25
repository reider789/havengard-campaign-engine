#!/usr/bin/env python3
"""Level 11 source-of-truth regression; never resolve a combat action by guesswork."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Level11SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = json.loads((ROOT / "state/_campaign-state.json").read_text(encoding="utf-8"))
        cls.chars = cls.state["characters"]

    def test_approved_party_levels_and_hit_points(self):
        expected = {"yar": 125, "daphne": 68, "lyutobor": 114, "rada": 69}
        for cid, hp in expected.items():
            with self.subTest(hero=cid):
                char = self.chars[cid]
                self.assertEqual(char["character_sheet"]["level"], 11)
                self.assertEqual(char["resources"]["hp"], {"current": hp, "max": hp})
                self.assertIn(" 11 /", char["character_sheet"]["class_and_level"])

    def test_resources_stay_consistent(self):
        c = self.chars
        self.assertEqual(c["yar"]["resources"]["second_wind"]["max"], 4)
        self.assertEqual(c["daphne"]["resources"]["prepared_spells"]["max"], 16)
        self.assertEqual(c["daphne"]["resources"]["spell_slots"]["6"], {"current": 1, "max": 1})
        self.assertEqual(c["lyutobor"]["resources"]["lay_on_hands"], {"current": 55, "max": 55})
        self.assertEqual(c["lyutobor"]["resources"]["channel_divinity"], {"current": 3, "max": 3})
        self.assertEqual(c["lyutobor"]["resources"]["spell_slots"]["3"], {"current": 3, "max": 3})

    def test_new_and_pending_spells_are_explicit(self):
        d = self.chars["daphne"]["character_sheet"]["combat_reference"]
        texts = " ".join(" ".join(str(x or "") for x in row["cells"]) for row in d)
        for spell in ("Цепная молния", "Сфера неуязвимости", "Кипящий котёл Таши"):
            self.assertIn(spell, texts)
        self.assertIn("Громовая волна", texts)
        self.assertIn("Палящий луч", texts)
        l = self.chars["lyutobor"]["character_sheet"]["combat_reference"]
        self.assertTrue(any("Возрождение" in str(row["cells"][0]) for row in l))
        self.assertNotIn("Возрождение", json.dumps(self.chars["lyutobor"].get("inventory_catalog", {}), ensure_ascii=False))

    def test_levels_are_not_time_advance_or_treasury_operation(self):
        events = [e for e in self.state.get("recent_events", []) if e.get("id") == "HAVENGARD-LEVEL11-20261025"]
        self.assertEqual(len(events), 1)
        self.assertEqual(self.state["commit_history"][-1]["revision"], self.state["state_revision"])
        # A level-up event must never make a synthetic item appear.
        for cid in ("yar", "daphne", "lyutobor", "rada"):
            self.assertNotIn("позолоченный половник", json.dumps(self.chars[cid].get("inventory_catalog", {}), ensure_ascii=False).lower())


if __name__ == "__main__":
    unittest.main()
