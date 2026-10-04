#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "tools" / "campaignctl.py"
STATE = ROOT / "state" / "_campaign-state.json"


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
    result = run_engine(project, "commit", "--transaction", str(tx_path))
    return result


def assert_ok(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] in {"ok", "committed", "rendered", "preview"}, payload
    return payload


def main() -> None:
    # Baseline itself must already be valid.
    check = subprocess.run(
        ["python", str(ENGINE), "--project", str(ROOT), "check"],
        capture_output=True,
        text=True,
    )
    assert_ok(check)
    original = json.loads(STATE.read_text(encoding="utf-8"))
    original_revision = original["state_revision"]

    # Everything below happens only on a temporary copy of the real campaign.
    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "campaign"
        shutil.copytree(ROOT, project)
        state = read_state(project)
        assert state["state_revision"] == original_revision

        # 1. Finish the bridge rescue: several resources and world fields change atomically.
        bridge_tx = {
            "expected_state_revision": state["state_revision"],
            "event": {
                "id": "TEST-BRIDGE-COMPLETE",
                "summary": "Симуляция: спасение у моста завершено, ресурсы после двух применений Руки Бигби и лечения лошадей учтены.",
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
                    "value": "Событие у повреждённого моста завершено; партия готова продолжить путь.",
                },
                {
                    "type": "set_world_field",
                    "field": "travel_event",
                    "value": {
                        "check": "d20=18",
                        "status": "resolved",
                        "note": "Девочка, обе лошади и повозка спасены; мост временно укреплён.",
                    },
                },
            ],
        }
        assert_ok(commit_tx(project, "bridge", bridge_tx))
        state = read_state(project)
        assert state["characters"]["daphne"]["resources"]["spell_slots"].endswith("V 0/2")
        assert state["characters"]["lyutobor"]["resources"]["lay_on_hands"] == "40/50"
        assert state["world"]["travel_event"]["status"] == "resolved"

        # 2. Atomicity: a later invalid operation must prevent every earlier operation
        # in the same transaction from reaching disk.
        before_bad = read_state(project)
        bad_tx = {
            "expected_state_revision": before_bad["state_revision"],
            "event": {
                "id": "TEST-ATOMIC-FAIL",
                "summary": "Эта транзакция обязана полностью откатиться.",
            },
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
        after_bad = read_state(project)
        assert after_bad == before_bad, "Неудачная транзакция частично изменила authoritative state"

        # 3. Short rest branch: Arcane Recovery restores one 5th-level slot and is spent.
        short_rest_tx = {
            "expected_state_revision": state["state_revision"],
            "event": {
                "id": "TEST-SHORT-REST",
                "summary": "Симуляция: короткий отдых, Дафна использует Магическое восстановление на одну ячейку V круга.",
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

        # 4. Long rest restores rest-based resources, but not ammunition.
        ammo_before = state["characters"]["yar"]["resources"]["storm_thrower_ammo"]
        long_rest_tx = {
            "expected_state_revision": state["state_revision"],
            "event": {
                "id": "TEST-LONG-REST",
                "summary": "Симуляция: ночной длительный отдых на дороге полностью завершён.",
            },
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

        # 5. Arrival changes location, city counters and the return-home thread together.
        arrival_tx = {
            "expected_state_revision": state["state_revision"],
            "event": {
                "id": "TEST-ARRIVAL-HAVENGARD",
                "summary": "Симуляция: обоз прибыл в Хейвенгард; Рейны переселились, привезённая еда поступила в резерв.",
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
                    "value": "Дом родителей Дафны продолжает строиться; переселение Рейнов уже состоялось.",
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

        # 6. Reload/check from disk must still work after the whole chain.
        final_check = run_engine(project, "check")
        assert_ok(final_check)

        # 7. Derived contexts must rebuild from authoritative state and keep candidate
        # GM-only material out of player context.
        render = run_engine(project, "render")
        assert_ok(render)
        gm_context = (project / "views" / "gm-context.md").read_text(encoding="utf-8")
        player_context = (project / "views" / "player-context.md").read_text(encoding="utf-8")
        assert "Хейвенгард" in gm_context
        assert "Хейвенгард" in player_context
        assert "Кандидатные идеи" in gm_context
        assert "Неутверждённая мастерская идея" in gm_context
        assert "Неутверждённая мастерская идея" not in player_context

        expected_revision = original_revision + 4
        assert state["state_revision"] == expected_revision
        assert state["commit_history"][-1]["event_id"] == "TEST-ARRIVAL-HAVENGARD"

    # The real campaign must remain untouched by the simulation.
    real_after = json.loads(STATE.read_text(encoding="utf-8"))
    assert real_after["state_revision"] == original_revision
    assert real_after == original

    print("Real scenario tests: OK")


if __name__ == "__main__":
    main()
