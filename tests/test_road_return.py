#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "road-bridge-baseline.json"
LIVE_STATE = ROOT / "state" / "_campaign-state.json"


def run_engine(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python", str(project / "tools" / "campaignctl.py"), "--project", str(project), *args],
        capture_output=True,
        text=True,
    )


def read_state(project: Path) -> dict:
    return json.loads((project / "state" / "_campaign-state.json").read_text(encoding="utf-8"))


def commit_tx(project: Path, name: str, tx: dict) -> subprocess.CompletedProcess[str]:
    tx_path = project / "transactions" / f"test-{name}.json"
    tx_path.parent.mkdir(parents=True, exist_ok=True)
    tx_path.write_text(json.dumps(tx, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_engine(project, "commit", "--transaction", str(tx_path))


def assert_ok(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] in {"ok", "committed", "rendered", "preview"}, payload
    return payload


def main() -> None:
    live_before = LIVE_STATE.read_bytes()
    fixture_before = FIXTURE.read_bytes()

    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "campaign"
        shutil.copytree(ROOT, project)

        # Critical property of a regression fixture: the scenario begins from the
        # frozen state, never from today's live campaign state.
        (project / "state" / "_campaign-state.json").write_bytes(fixture_before)
        state = read_state(project)
        assert state["state_revision"] == 0
        assert state["party"]["location"].startswith("повреждённый мост")
        assert_ok(run_engine(project, "check"))

        # Rules/prompt pack must be injected into GM context, but not player context.
        assert_ok(run_engine(project, "render"))
        gm_context = (project / "views" / "gm-context.md").read_text(encoding="utf-8")
        player_context = (project / "views" / "player-context.md").read_text(encoding="utf-8")
        assert "Постоянный rule pack кампании" in gm_context
        assert "Хейвенгард — самостоятельный живой город" in gm_context
        assert "Дафна — выросший и компетентный боевой маг" in gm_context
        assert "Неутверждённая мастерская идея" in gm_context
        assert "Неутверждённая мастерская идея" not in player_context
        assert "Постоянный rule pack кампании" not in player_context

        # 1. Finish bridge rescue. Several fields/resources change atomically.
        bridge_tx = {
            "expected_state_revision": state["state_revision"],
            "event": {
                "id": "TEST-BRIDGE-COMPLETE",
                "summary": "Симуляция: спасение у моста завершено, ресурсы учтены.",
            },
            "operations": [
                {
                    "type": "set_character_resource",
                    "id": "daphne",
                    "resource": "spell_slots",
                    "value": "I 4/4; II 3/3; III 3/3; IV 3/3; V 0/2",
                },
                {
                    "type": "set_character_resource",
                    "id": "daphne",
                    "resource": "concentration",
                    "value": "нет",
                },
                {
                    "type": "set_character_resource",
                    "id": "lyutobor",
                    "resource": "lay_on_hands",
                    "value": "40/50",
                },
                {
                    "type": "set_world_field",
                    "field": "current_scene",
                    "value": "Спасение у моста завершено; партия готова продолжить путь.",
                },
                {
                    "type": "set_world_field",
                    "field": "travel_event",
                    "value": {
                        "check": "d20=18",
                        "status": "resolved",
                        "note": "Люди и лошади спасены; мост временно укреплён.",
                    },
                },
            ],
        }
        assert_ok(commit_tx(project, "bridge", bridge_tx))
        state = read_state(project)
        assert state["characters"]["daphne"]["resources"]["spell_slots"].endswith("V 0/2")
        assert state["characters"]["lyutobor"]["resources"]["lay_on_hands"] == "40/50"
        assert state["world"]["travel_event"]["status"] == "resolved"

        # 2. Atomicity. If a later operation fails, earlier changes in the same
        # transaction must not reach disk.
        before_bad = read_state(project)
        bad_tx = {
            "expected_state_revision": before_bad["state_revision"],
            "event": {"id": "TEST-ATOMIC-FAIL", "summary": "Должно полностью откатиться."},
            "operations": [
                {
                    "type": "set_character_resource",
                    "id": "daphne",
                    "resource": "hp",
                    "value": "1/62",
                },
                {
                    "type": "transfer_item",
                    "item": "definitely_missing_test_item",
                    "from": "yar",
                    "to": "daphne",
                },
            ],
        }
        failed = commit_tx(project, "atomic-fail", bad_tx)
        assert failed.returncode != 0, failed.stdout + failed.stderr
        assert read_state(project) == before_bad

        # 3. Short rest branch: Arcane Recovery returns one 5th-level slot.
        state = read_state(project)
        short_rest_tx = {
            "expected_state_revision": state["state_revision"],
            "event": {
                "id": "TEST-SHORT-REST",
                "summary": "Симуляция: Дафна использует Магическое восстановление.",
            },
            "operations": [
                {
                    "type": "set_character_resource",
                    "id": "daphne",
                    "resource": "spell_slots",
                    "value": "I 4/4; II 3/3; III 3/3; IV 3/3; V 1/2",
                },
                {
                    "type": "set_character_resource",
                    "id": "daphne",
                    "resource": "arcane_recovery",
                    "value": "0/1 до следующего длительного отдыха",
                },
                {"type": "set_world_field", "field": "time_label", "value": "после короткого отдыха"},
            ],
        }
        assert_ok(commit_tx(project, "short-rest", short_rest_tx))
        state = read_state(project)
        assert state["characters"]["daphne"]["resources"]["spell_slots"].endswith("V 1/2")
        assert state["characters"]["daphne"]["resources"]["arcane_recovery"].startswith("0/1")

        # 4. Long rest restores rest-based resources, never ammunition by itself.
        ammo_before = state["characters"]["yar"]["resources"]["storm_thrower_ammo"]
        long_rest_tx = {
            "expected_state_revision": state["state_revision"],
            "event": {"id": "TEST-LONG-REST", "summary": "Симуляция: длительный отдых завершён."},
            "operations": [
                {
                    "type": "set_character_resource",
                    "id": "daphne",
                    "resource": "spell_slots",
                    "value": "I 4/4; II 3/3; III 3/3; IV 3/3; V 2/2",
                },
                {
                    "type": "set_character_resource",
                    "id": "daphne",
                    "resource": "arcane_recovery",
                    "value": "1/1",
                },
                {
                    "type": "set_character_resource",
                    "id": "lyutobor",
                    "resource": "lay_on_hands",
                    "value": "50/50",
                },
                {"type": "set_world_field", "field": "time_label", "value": "утро"},
            ],
        }
        assert_ok(commit_tx(project, "long-rest", long_rest_tx))
        state = read_state(project)
        assert state["characters"]["daphne"]["resources"]["spell_slots"].endswith("V 2/2")
        assert state["characters"]["daphne"]["resources"]["arcane_recovery"] == "1/1"
        assert state["characters"]["lyutobor"]["resources"]["lay_on_hands"] == "50/50"
        assert state["characters"]["yar"]["resources"]["storm_thrower_ammo"] == ammo_before

        # 5. Arrival changes location, city counters and relevant threads together.
        arrival_tx = {
            "expected_state_revision": state["state_revision"],
            "event": {
                "id": "TEST-ARRIVAL-HAVENGARD",
                "summary": "Симуляция: обоз прибыл в Хейвенгард; Рейны переселились, еда доставлена.",
            },
            "operations": [
                {"type": "set_party_field", "field": "location", "value": "Хейвенгард"},
                {"type": "set_character_field", "id": "yar", "field": "location", "value": "Хейвенгард"},
                {"type": "set_character_field", "id": "daphne", "field": "location", "value": "Хейвенгард"},
                {"type": "set_character_field", "id": "lyutobor", "field": "location", "value": "Хейвенгард"},
                {"type": "set_character_field", "id": "rada", "field": "location", "value": "Хейвенгард"},
                {"type": "set_world_field", "field": "current_region", "value": "Хейвенгард"},
                {
                    "type": "set_world_field",
                    "field": "current_scene",
                    "value": "Отряд и семья Рейн прибыли через ворота Хейвенгарда.",
                },
                {"type": "set_world_field", "field": "city_population", "value": 221},
                {"type": "set_world_field", "field": "city_food_reserve_pe", "value": 426.43},
                {"type": "set_world_field", "field": "city_food_target_pe", "value": 442.0},
                {"type": "set_thread_status", "id": "T001", "status": "resolved"},
                {
                    "type": "set_thread_field",
                    "id": "T002",
                    "field": "summary",
                    "value": "Дом родителей Дафны строится; переселение Рейнов состоялось.",
                },
            ],
        }
        assert_ok(commit_tx(project, "arrival", arrival_tx))
        state = read_state(project)
        assert state["party"]["location"] == "Хейвенгард"
        assert state["world"]["city_population"] == 221
        assert state["world"]["city_food_reserve_pe"] == 426.43
        assert state["world"]["city_food_target_pe"] == 442.0
        assert state["threads"]["T001"]["status"] == "resolved"
        assert state["state_revision"] == 4
        assert state["commit_history"][-1]["event_id"] == "TEST-ARRIVAL-HAVENGARD"

        # 6. Reload and rendered views still work after the entire chain.
        assert_ok(run_engine(project, "check"))
        assert_ok(run_engine(project, "render"))
        final_gm = (project / "views" / "gm-context.md").read_text(encoding="utf-8")
        final_player = (project / "views" / "player-context.md").read_text(encoding="utf-8")
        assert "Хейвенгард" in final_gm
        assert "Хейвенгард" in final_player
        assert "Неутверждённая мастерская идея" in final_gm
        assert "Неутверждённая мастерская идея" not in final_player

    # Neither the live campaign nor the frozen fixture is mutated by simulation.
    assert LIVE_STATE.read_bytes() == live_before
    assert FIXTURE.read_bytes() == fixture_before
    print("Road return fixture scenario: OK")


if __name__ == "__main__":
    main()
