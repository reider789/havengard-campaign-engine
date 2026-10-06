#!/usr/bin/env python3
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import campaignctl as engine
import knowledgegraph as graph
from campaign_model import normalize_resource
from migrate_v2 import migrate_state
from scene_context import render_scene_context
from sync_time_dependent_state import synchronize
from apply_live import apply_pending


def baseline():
    old = json.loads((ROOT / "tests/fixtures/road-bridge-baseline.json").read_text())
    g = {"schema_version": 1, "campaign_id": "yar-warrior", "graph_revision": 1,
         "principals": {}, "branches": {}, "awareness": {}}
    s = migrate_state(old, g, [])
    s["world"]["timekeeping"] = {"anchor_event": "TEST-ANCHOR", "elapsed_seconds_from_anchor": 0, "elapsed_hours_from_anchor": 0, "elapsed_full_days_from_anchor": 0}
    s["world"]["scene_participants"] = ["yar", "daphne"]
    s["world"]["scene_knowledge_branches"] = []
    return s


def transaction(s, ops, eid="TEST-V2"):
    return {"expected_state_revision": s["state_revision"],
            "event": {"id": eid, "summary": "Изолированная проверка.", "visibility": "party"}, "operations": ops}


class IntegrityTests(unittest.TestCase):
    def test_typed_migration_preserves_values_and_unknown_inventory(self):
        s = baseline()
        self.assertEqual(engine.validate_state(s), [])
        self.assertEqual(s["characters"]["yar"]["resources"]["personal_money_cp"], 1870389)
        self.assertEqual(s["characters"]["daphne"]["resources"]["spell_slots"]["5"], {"current": 1, "max": 2})
        self.assertEqual(s["characters"]["daphne"]["source_coverage"]["inventory"]["status"], "not_imported")
        self.assertEqual(migrate_state(s, {}, []), s)

    def test_bounds_and_whole_transaction_rollback(self):
        s = baseline(); original = copy.deepcopy(s)
        for key, value in [("hp", "999/62"), ("arrows", "-3/60"), ("spell_slots", "I 9/4; V 7/2"), ("hp", {"current": True, "max": 62}), ("personal_money_cp", -1)]:
            tx = transaction(s, [{"type": "set_character_field", "id": "yar", "field": "state", "value": "bad earlier write"},
                                 {"type": "set_character_resource", "id": "daphne", "resource": key, "value": value}])
            with self.subTest(key=key, value=value), self.assertRaises((engine.CampaignError, ValueError)):
                engine.build_result(s, tx)
            self.assertEqual(s, original)

    def test_replay_after_history_rotation_and_changed_payload(self):
        s = baseline(); tx = transaction(s, [{"type": "adjust_resource", "id": "yar", "resource": "personal_money_cp", "delta": -10}])
        s = engine.build_result(s, tx)
        for i in range(65):
            s = engine.build_result(s, transaction(s, [], f"FILL-{i}"))
        self.assertEqual(engine.build_result(s, tx), s)
        tx["expected_state_revision"] = s["state_revision"]
        self.assertEqual(engine.build_result(s, tx), s)
        tx["operations"][0]["delta"] = -11
        with self.assertRaises(engine.CampaignError): engine.build_result(s, tx)

    def test_month_key_and_money_conservation(self):
        s = baseline(); s["characters"]["daphne"]["resources"]["personal_money_cp"] = 5
        missing_key = transaction(s, []); missing_key["kind"] = "month_close"
        with self.assertRaises(engine.CampaignError): engine.build_result(s, missing_key)
        before = sum(c["resources"].get("personal_money_cp", 0) for c in s["characters"].values())
        tx = transaction(s, [{"type": "transfer_money", "from": "yar", "to": "daphne", "amount_cp": 100}]);tx["unique_key"] = "month:test"
        out = engine.build_result(s, tx)
        self.assertEqual(sum(c["resources"].get("personal_money_cp", 0) for c in out["characters"].values()), before)
        tx2 = transaction(out, [], "SECOND-MONTH"); tx2["unique_key"] = "month:test"
        with self.assertRaises(engine.CampaignError): engine.build_result(out, tx2)

    def test_capacity_change_needs_explicit_cause(self):
        s = baseline()
        op = {"type": "set_character_resource", "id": "yar", "resource": "hp", "value": {"current": 114, "max": 120}}
        with self.assertRaises(engine.CampaignError): engine.build_result(s, transaction(s, [op]))
        op["capacity_reason"] = "Согласованное повышение уровня; тест"
        self.assertEqual(engine.build_result(s, transaction(s, [op]))["characters"]["yar"]["resources"]["hp"]["max"], 120)

    def test_clock_preview_and_state_description(self):
        s = baseline(); char = s["characters"]["daphne"]
        char["state"] = "ранена и истощена"
        char["health"] = {"pregnancy": {"status": "confirmed", "confirmation": "confirmed", "confirmation_elapsed_day_from_first_signs": 0, "gestational_day_at_confirmation": 39}}
        synchronize(s)
        out = engine.build_result(s, transaction(s, [{"type": "advance_time", "hours": 49}]))
        self.assertEqual(out["world"]["timekeeping"]["elapsed_full_days_from_anchor"], 2)
        self.assertEqual(out["characters"]["daphne"]["health"]["pregnancy"]["gestational_day_current"], 41)
        self.assertEqual(out["characters"]["daphne"]["state"], "ранена и истощена")
        self.assertFalse(synchronize(out))
        s["world"]["timekeeping"]["elapsed_full_days_from_anchor"] = 7
        self.assertTrue(engine.validate_state(s))

    def test_subhour_time_accumulates_without_rounding(self):
        s = baseline()
        s = engine.build_result(s, transaction(s, [{"type": "advance_time", "seconds": 6}], "ROUND-1"))
        self.assertEqual(s["world"]["timekeeping"]["elapsed_hours_from_anchor"], 0)
        s = engine.build_result(s, transaction(s, [{"type": "advance_time", "seconds": 3594}], "ROUND-END"))
        self.assertEqual(s["world"]["timekeeping"]["elapsed_seconds_from_anchor"], 3600)
        self.assertEqual(s["world"]["timekeeping"]["elapsed_hours_from_anchor"], 1)
        with self.assertRaises(engine.CampaignError):
            engine.build_result(s, transaction(s, [{"type": "advance_time", "hours": 1, "minutes": 1}]))

    def test_historical_fact_and_correction_keep_old_text(self):
        s = baseline(); old = s["knowledge"]["KTEST-CANON"]["fact"]
        out = engine.build_result(s, transaction(s, [
            {"type": "add_knowledge", "id": "NEW", "fact": "Переход завершён", "known_by": ["yar"]},
            {"type": "supersede_knowledge", "id": "KTEST-CANON", "replacement_ids": ["NEW"], "reason": "Сыграно прибытие"}]))
        self.assertEqual(out["knowledge"]["KTEST-CANON"]["fact"], old)
        self.assertEqual(out["knowledge"]["KTEST-CANON"]["status"], "canonical")
        self.assertEqual(out["knowledge"]["KTEST-CANON"]["temporal_status"], "historical")
        with self.assertRaises(engine.CampaignError):
            engine.build_result(s, transaction(s, [{"type": "set_knowledge_field", "id": "KTEST-CANON", "field": "fact", "value": "silently changed"}]))

    def test_player_visibility_and_candidate_awareness(self):
        s = baseline()
        s["threads"]["HIDDEN"] = {"status": "active", "title": "SECRET_THREAD", "summary": "secret", "visibility": "gm"}
        s["recent_events"].append({"id": "SECRET", "summary": "SECRET_EVENT", "visibility": "gm"})
        view = engine.render_player_context(s)
        self.assertNotIn("SECRET", view)
        s["knowledge_graph"]["awareness"] = {"KTEST-CANDIDATE": {"yar": {"state": "knows", "source": "prep"}}}
        self.assertTrue(graph.validate_graph(s, s["knowledge_graph"]))

    def test_disproven_does_not_render_as_true_knowledge(self):
        s = baseline(); kid = "KTEST-CANON"
        s["knowledge"][kid]["status"] = "disproven"
        s["knowledge_graph"]["branches"] = {"B": {"status": "active", "title": "Test", "knowledge_ids": [kid], "key_principals": ["yar"]}}
        s["world"]["scene_knowledge_branches"] = ["B"]
        text = graph.render_scene_slice(s, s["knowledge_graph"])
        self.assertNotIn(kid + ": knows", text)
        self.assertIn("ОПРОВЕРГНУТО", text)
        s["world"]["scene_knowledge_branches"] = []
        self.assertEqual(graph.selected_branches(s, s["knowledge_graph"]), [])

    def test_scene_change_requires_refreshed_context(self):
        s = baseline()
        with self.assertRaises(engine.CampaignError):
            engine.build_result(s, transaction(s, [{"type": "set_world_field", "field": "current_scene", "value": "new place"}]))
        rules = json.loads((ROOT / "rules/_campaign-rules.json").read_text())
        s["scene_context"]["handoff"] = {"last_narrative_excerpt": "Последняя точная реплика.", "source": "fixture"}
        text = render_scene_context(s, rules)
        self.assertIn("Последняя точная реплика.", text)
        self.assertNotIn("непрерывную летопись", text)  # Full report is not automatically injected.

    def test_two_writers_and_recoverable_views(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "campaign"
            shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(".git", "__pycache__", ".campaign.lock", "live"))
            s = baseline(); engine.atomic_write_json(project / "state/_campaign-state.json", s)
            paths=[]
            for i in range(2):
                p = project / f"tx{i}.json"
                p.write_text(json.dumps(transaction(s, [{"type": "adjust_resource", "id": "yar", "resource": "personal_money_cp", "delta": -10}], f"RACE-{i}")))
                paths.append(p)
            processes=[subprocess.Popen([sys.executable, str(project / "tools/campaignctl.py"), "--project", str(project), "commit", "--transaction", str(p)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for p in paths]
            for proc in processes: proc.communicate(timeout=20)
            self.assertEqual(sorted(p.returncode for p in processes), [0, 2])
            after=json.loads((project / "state/_campaign-state.json").read_text())
            self.assertEqual(after["characters"]["yar"]["resources"]["personal_money_cp"], 1870379)
            winner=next(p for p in paths if json.loads(p.read_text())["event"]["id"] in after["applied_events"])
            (project / "views/scene-context.md").unlink()
            engine.cmd_commit(project, winner)
            engine.cmd_check_views(project)
            self.assertEqual(json.loads((project / "state/_campaign-state.json").read_text()), after)

    def test_live_queue_orders_revisions_and_retries_safely(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "campaign"
            shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(".git", "__pycache__", ".campaign.lock", "live"))
            s = baseline(); engine.atomic_write_json(project / "state/_campaign-state.json", s)
            first = transaction(s, [{"type": "adjust_resource", "id": "yar", "resource": "personal_money_cp", "delta": -10}], "QUEUE-1")
            second = transaction(engine.build_result(s, first), [{"type": "adjust_resource", "id": "yar", "resource": "personal_money_cp", "delta": -20}], "QUEUE-2")
            queue = project / "transactions/live"; queue.mkdir(exist_ok=True)
            (queue / "z-first.json").write_text(json.dumps(first))
            (queue / "a-second.json").write_text(json.dumps(second))
            self.assertEqual(apply_pending(project), 2)
            after = json.loads((project / "state/_campaign-state.json").read_text())
            self.assertEqual(after["characters"]["yar"]["resources"]["personal_money_cp"], 1870359)
            self.assertEqual(list(queue.glob("*.json")), [])
            self.assertTrue((project / "transactions/applied/QUEUE-1.json").exists())
            (queue / "retry.json").write_text(json.dumps(first))
            apply_pending(project)
            self.assertEqual(json.loads((project / "state/_campaign-state.json").read_text()), after)

    def test_preview_contains_derived_fields_before_commit(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "campaign"
            shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(".git", "__pycache__", ".campaign.lock", "live"))
            s = baseline()
            s["characters"]["daphne"]["health"] = {"pregnancy": {"status": "confirmed", "confirmation": "confirmed", "confirmation_elapsed_day_from_first_signs": 0, "gestational_day_at_confirmation": 39}}
            synchronize(s)
            engine.atomic_write_json(project / "state/_campaign-state.json", s)
            tx = transaction(s, [{"type": "advance_time", "hours": 48}], "PREVIEW-TIME")
            path = project / "tx.json"; path.write_text(json.dumps(tx))
            result = subprocess.run([sys.executable, str(project / "tools/campaignctl.py"), "--project", str(project), "preview", "--transaction", str(path)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            paths = [item["path"] for item in json.loads(result.stdout)["changes"]]
            self.assertIn("$.characters.daphne.health.pregnancy.gestational_day_current", paths)
            self.assertEqual(json.loads((project / "state/_campaign-state.json").read_text()), s)
            engine.cmd_commit(project, path)
            self.assertEqual(json.loads((project / "state/_campaign-state.json").read_text()), engine.build_result(s, tx))


if __name__ == "__main__":
    unittest.main()
