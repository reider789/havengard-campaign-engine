#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("knowledgegraph", ROOT / "tools" / "knowledgegraph.py")
assert SPEC and SPEC.loader
kg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kg)


def minimal_state() -> dict:
    return {
        "campaign": {"id": "yar-warrior"},
        "state_revision": 7,
        "characters": {"yar": {"name": "Яр"}, "daphne": {"name": "Дафна"}},
        "world": {
            "scene_participants": ["yar", "npc:test_npc"],
            "scene_knowledge_branches": ["BR-TEST"]
        },
        "threads": {"T-TEST": {"title": "Тест", "status": "active"}},
        "knowledge": {
            "K1": {"fact": "Яр лично видел арку.", "status": "canonical", "known_by": ["yar"], "source_event": "EV1"},
            "K2": {"fact": "У арки есть маршрутный ключ.", "status": "canonical", "known_by": []}
        }
    }


def minimal_graph() -> dict:
    return {
        "schema_version": 1,
        "campaign_id": "yar-warrior",
        "graph_revision": 1,
        "principals": {
            "npc:test_npc": {"name": "Тестовый NPC", "kind": "npc"},
            "npc:offscene": {"name": "Внесценовый NPC", "kind": "npc"}
        },
        "branches": {
            "BR-TEST": {
                "title": "Тестовая ветка",
                "status": "active",
                "linked_thread_id": "T-TEST",
                "knowledge_ids": ["K1", "K2"],
                "key_principals": ["yar", "npc:test_npc", "npc:offscene"]
            },
            "BR-OTHER": {
                "title": "Другая ветка",
                "status": "active",
                "linked_thread_id": None,
                "knowledge_ids": [],
                "key_principals": ["daphne"]
            }
        },
        "awareness": {
            "K1": {
                "npc:test_npc": {"state": "heard_of", "source": "рассказ Яра"},
                "npc:offscene": {"state": "knows", "source": "личное наблюдение"}
            },
            "K2": {
                "npc:test_npc": {
                    "state": "misinformed",
                    "source": "ошибочный слух",
                    "version": "NPC думает, что ключ одноразовый"
                }
            }
        }
    }


def main() -> None:
    state = minimal_state()
    graph = minimal_graph()
    assert kg.validate_graph(state, graph) == []

    text = kg.render_scene_slice(state, graph)
    assert "Тестовая ветка" in text
    assert "Другая ветка" not in text
    assert "**Яр**" in text
    assert "K1: knows" in text
    assert "**Тестовый NPC**" in text
    assert "K1: heard_of" in text
    assert "K2: misinformed" in text
    assert "NPC думает, что ключ одноразовый" in text
    assert "Внесценовый NPC — K1:knows" in text

    bad_principal = copy.deepcopy(graph)
    bad_principal["branches"]["BR-TEST"]["key_principals"].append("unregistered_person")
    assert any("неизвестного участника" in e for e in kg.validate_graph(state, bad_principal))

    bad_fact = copy.deepcopy(graph)
    bad_fact["branches"]["BR-TEST"]["knowledge_ids"].append("K404")
    assert any("неизвестный факт K404" in e for e in kg.validate_graph(state, bad_fact))

    bad_awareness = copy.deepcopy(graph)
    bad_awareness["awareness"]["K1"]["npc:test_npc"] = {"state": "invalid_state", "source": "test"}
    assert any("недопустимое значение" in e for e in kg.validate_graph(state, bad_awareness))

    live_state = json.loads((ROOT / "state" / "_campaign-state.json").read_text(encoding="utf-8"))
    live_graph = json.loads((ROOT / "state" / "_knowledge-graph.json").read_text(encoding="utf-8"))
    assert kg.validate_graph(live_state, live_graph) == []
    assert live_graph["awareness"]["K013"]["npc:melania_rein"]["state"] == "knows"
    assert live_graph["awareness"]["K014"]["npc:serit"]["state"] == "knows"

    print("Knowledge graph tests: OK")


if __name__ == "__main__":
    main()
