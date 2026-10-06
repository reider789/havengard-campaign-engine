#!/usr/bin/env python3
"""Explicit, idempotent storage migration. It never advances game time."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from campaign_model import normalize_resource, transaction_hash
from campaignctl import (CampaignError, atomic_write_json, read_json, read_campaign_rules,
                         validate_project, write_views)
from sync_time_dependent_state import synchronize

EVENT_ID = "ENGINE-SCHEMA-V2-001"


def migrate_state(original: dict, graph: dict, transactions: list[dict]) -> dict:
    if original.get("schema_version") == 2:
        return copy.deepcopy(original)
    state = copy.deepcopy(original)
    state["schema_version"] = 2
    state["knowledge_graph"] = copy.deepcopy(graph)
    ledger = {}
    for event in original.get("recent_events", []):
        ledger[event["id"]] = {"revision": 0, "payload_sha256": None, "origin": "legacy_event"}
    for entry in original.get("commit_history", []):
        ledger[entry["event_id"]] = {"revision": entry["revision"], "payload_sha256": None, "origin": "legacy_history"}
    for tx in transactions:
        eid = tx.get("event", {}).get("id")
        if eid in ledger:
            ledger[eid]["payload_sha256"] = transaction_hash(tx)
    state["applied_events"] = ledger
    state["event_unique_keys"] = {}
    clock = state.get("world", {}).get("timekeeping")
    if clock:
        clock["elapsed_seconds_from_anchor"] = clock["elapsed_hours_from_anchor"] * 3600
        clock["policy"] = "Продвигать реально прошедшие seconds/minutes/hours через advance_time. Секунды — основной счётчик; часы и дни производны. Время чата не продвигает игру."
    for cid, char in state["characters"].items():
        char["resources"] = dict(normalize_resource(k, v) for k, v in char.get("resources", {}).items())
        char.pop("knowledge", None)
        char["source_coverage"] = {
            part: {"status": "partial" if part == "sheet" or char.get("inventory") else "not_imported",
                   "source_key": "master_sheet", "source_version": None,
                   "note": "Перенесены только явно записанные поля. Отсутствующие значения читать из источника; версия мастер-книги не закреплена."}
            for part in ("inventory", "sheet")
        }
    # Historical claims remain word-for-word intact; only their temporal scope changes.
    replacements = {"K004": ["K008"], "K008": ["K012"], "K009": ["K010"], "K017": ["K018"]}
    historical = {"K004", "K005", "K006", "K007", "K008", "K009", "K010", "K011", "K012", "K017"}
    for kid, fact in state["knowledge"].items():
        fact["temporal_status"] = "historical" if kid in historical else "current"
        if kid in replacements and all(k in state["knowledge"] for k in replacements[kid]):
            fact["superseded_by"] = replacements[kid]
            fact["valid_to_event"] = state["knowledge"][replacements[kid][0]].get("source_event")
    for event in state.get("recent_events", []):
        event.setdefault("visibility", "party")  # Reviewed legacy played-event summaries.
    for thread in state.get("threads", {}).values():
        thread.setdefault("visibility", "party")

    if "K018" in state["knowledge"]:
        principals = state["knowledge_graph"].setdefault("principals", {})
        principals.update({"npc:mirel": {"name": "Мирэль", "kind": "npc"},
                           "npc:midwife_havengard": {"name": "Повитуха Хейвенгарда", "kind": "npc"}})
        state["knowledge_graph"]["branches"]["BR-DAPHNE-FAMILY"] = {
            "title": "Дафна — подтверждённая беременность и семейная жизнь", "status": "active",
            "knowledge_ids": ["K018"], "key_principals": ["yar", "daphne", "npc:mirel", "npc:midwife_havengard"]}
        state["knowledge_graph"].setdefault("awareness", {})["K018"] = {
            pid: {"state": "knows", "source": "DAPHNE-PREGNANCY-CONFIRMED-001: участие в осмотре и объявлении результата"}
            for pid in ("npc:mirel", "npc:midwife_havengard")}
        state["world"]["scene_knowledge_branches"] = ["BR-DAPHNE-FAMILY"]
        state["knowledge_graph"]["graph_revision"] += 1

    state["scene_context"] = {"mode": "social", "thread_ids": [], "fact_ids": [],
                              "handoff": {"player_intent": None, "last_player_input": None,
                                          "last_narrative_excerpt": None,
                                          "source_note": "Точная реплика пока не перенесена; не придумывать её."}}
    pregnancy = state.get("characters", {}).get("daphne", {}).get("health", {}).get("pregnancy")
    if pregnancy:
        # Keep the old text as history, not a second changing gestational-age counter.
        char = state["characters"]["daphne"]
        if char.get("state", "").startswith("беременность подтверждена; срок "):
            char["legacy_state_summary"] = {"text": char["state"], "as_of_revision": original["state_revision"]}
            char["state"] = "беременность подтверждена; наблюдается у Мирэль"
    synchronize(state)
    revision = original["state_revision"] + 1
    event = {"id": EVENT_ID, "visibility": "gm", "summary": "Техническая миграция: числовые ресурсы, реестр событий, актуальность фактов и контекст сцены. Игровое время не продвинуто."}
    state["state_revision"] = revision
    state["recent_events"] = (state.get("recent_events", []) + [event])[-20:]
    state["commit_history"] = (state.get("commit_history", []) + [{"revision": revision, "event_id": EVENT_ID, "summary": event["summary"]}])[-50:]
    state["applied_events"][EVENT_ID] = {"revision": revision, "payload_sha256": None, "origin": "schema_migration"}
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=".")
    parser.add_argument("--expected-revision", required=True, type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    old = read_json(project / "state" / "_campaign-state.json")
    if old.get("schema_version") == 2:
        print(json.dumps({"status": "already_migrated", "state_revision": old["state_revision"]}))
        return 0
    if old["state_revision"] != args.expected_revision:
        raise CampaignError("Состояние изменилось; повторить аудит миграции на свежей ревизии")
    archive = [read_json(p) for p in sorted((project / "transactions" / "applied").glob("*.json"))]
    new = migrate_state(old, read_json(project / "state" / "_knowledge-graph.json"), archive)
    rules = read_campaign_rules(project)
    errors = validate_project(new, rules)
    if errors:
        raise CampaignError("\n".join(errors))
    if args.apply:
        manifest = {"kind": "storage_migration", "event_id": EVENT_ID,
                    "from_schema": 1, "to_schema": 2, "from_revision": old["state_revision"],
                    "to_revision": new["state_revision"], "game_time_advanced": False,
                    "source_commit": "72bf6955568e4cb4b05e8c675e11793bbf3ea999",
                    "before_sha256": hashlib.sha256(json.dumps(old, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
        path = project / "migrations" / "002-state-format.json"
        if path.exists():
            raise CampaignError("Манифест миграции уже существует; проверить состояние")
        atomic_write_json(path, manifest)
        atomic_write_json(project / "state" / "_campaign-state.json", new)
        write_views(project, new, rules)
    print(json.dumps({"status": "migrated" if args.apply else "preview", "from_revision": old["state_revision"], "to_revision": new["state_revision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
