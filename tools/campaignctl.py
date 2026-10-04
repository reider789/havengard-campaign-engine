#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


class CampaignError(Exception):
    pass


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CampaignError(f"Файл не найден: {path}")
    except json.JSONDecodeError as exc:
        raise CampaignError(f"Некорректный JSON в {path}: {exc}")


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def validate_state(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version должен быть {SCHEMA_VERSION}")
    if not isinstance(state.get("state_revision"), int) or state["state_revision"] < 0:
        errors.append("state_revision должен быть неотрицательным целым")
    for key in ("world", "party", "characters", "knowledge", "beliefs", "threads", "world_pressures", "recent_events", "commit_history"):
        if key not in state:
            errors.append(f"Отсутствует обязательный раздел: {key}")
    chars = state.get("characters", {})
    for cid in state.get("party", {}).get("members", []):
        if cid not in chars:
            errors.append(f"Участник партии {cid} отсутствует в characters")
    for kid, fact in state.get("knowledge", {}).items():
        if fact.get("status") not in {"canonical", "candidate", "disproven"}:
            errors.append(f"{kid}.status имеет недопустимое значение")
        for cid in fact.get("known_by", []):
            if cid not in chars:
                errors.append(f"{kid}.known_by ссылается на неизвестного персонажа {cid}")
    history = state.get("commit_history", [])
    if history and history[-1].get("revision") != state.get("state_revision"):
        errors.append("последняя revision в commit_history должна совпадать со state_revision")
    return errors


def render_gm_context(state: dict[str, Any]) -> str:
    w = state["world"]
    lines = [
        "# GM Context", "", f"> state_revision: {state['state_revision']}", "",
        "## Где и когда",
        f"- Регион: {w.get('current_region', 'не указано')}",
        f"- Сцена: {w.get('current_scene', 'не указано')}",
        f"- Время: {w.get('time_label', 'не указано')}", "",
        "## Партия",
    ]
    for cid in state["party"].get("members", []):
        c = state["characters"][cid]
        lines.append(f"- {c['name']}: {c.get('state','')}; цель — {c.get('goal','')}")
    lines += ["", "## Активные сюжетные линии"]
    for tid, t in state.get("threads", {}).items():
        if t.get("status") == "active":
            lines.append(f"- {tid} — {t.get('title')}: {t.get('summary')} | давление: {t.get('pressure','нет')}")
    lines += ["", "## Канонические факты"]
    for kid, fact in state.get("knowledge", {}).items():
        if fact.get("status") == "canonical":
            lines.append(f"- {kid}: {fact.get('fact')}")
    lines += ["", "## Кандидатные идеи — НЕ КАНОН"]
    candidates = [(kid, f) for kid, f in state.get("knowledge", {}).items() if f.get("status") == "candidate"]
    if candidates:
        for kid, fact in candidates:
            lines.append(f"- {kid}: {fact.get('fact')}")
    else:
        lines.append("- Нет.")
    rules = state.get("play_rules", {})
    if rules:
        lines += ["", "## Постоянные правила ведения"]
        combat = rules.get("combat_control", {})
        controlled = combat.get("party_controlled_by_player", [])
        if controlled:
            names = [state["characters"].get(cid, {}).get("name", cid) for cid in controlled]
            lines.append(f"- В бою игрок управляет: {', '.join(names)}.")
        if combat.get("stop_before_each_player_character_turn"):
            lines.append("- Останавливаться перед ходом каждого персонажа игрока и не выбирать за него действия.")
        briefing = combat.get("turn_briefing", {})
        if briefing.get("principle"):
            lines.append(f"- Тактический брифинг: {briefing['principle']}")
        shield = combat.get("automatic_defensive_reactions", {}).get("daphne_shield")
        if shield:
            lines.append("- Дафна автоматически применяет «Щит», если +5 КД превращает попадание в промах: сначала бесплатное применение Magic Initiate, затем минимальную доступную ячейку.")
        mage_hand = rules.get("combat_rulings", {}).get("mage_hand_soften_fall")
        if mage_hand:
            lines.append(f"- Трактовка Магической руки: {mage_hand}")
        narrative = rules.get("narrative_control", {})
        if narrative.get("player_words_are_woven_into_first_person_narrative"):
            lines.append("- Реплики и действия Яра от игрока вплетать в повествование от первого лица; не придумывать за Яра решения.")
    lines += ["", "## Последние события"]
    for event in state.get("recent_events", [])[-10:]:
        lines.append(f"- {event.get('id')}: {event.get('summary')}")
    return "\n".join(lines) + "\n"


def render_player_context(state: dict[str, Any]) -> str:
    w = state["world"]
    lines = ["# Player Context", "", f"> state_revision: {state['state_revision']}", "", "## Текущая сцена", f"- {w.get('current_scene')}", f"- {w.get('time_label')}", "", "## Активные линии"]
    for t in state.get("threads", {}).values():
        if t.get("status") == "active":
            lines.append(f"- {t.get('title')}: {t.get('summary')}")
    lines += ["", "## Последние события"]
    for event in state.get("recent_events", [])[-10:]:
        lines.append(f"- {event.get('summary')}")
    return "\n".join(lines) + "\n"


def write_views(project: Path, state: dict[str, Any]) -> None:
    views = project / "views"
    views.mkdir(parents=True, exist_ok=True)
    (views / "gm-context.md").write_text(render_gm_context(state), encoding="utf-8")
    (views / "player-context.md").write_text(render_player_context(state), encoding="utf-8")


def validate_transaction(tx: dict[str, Any], state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if tx.get("expected_state_revision") != state.get("state_revision"):
        errors.append(f"stale transaction: expected {tx.get('expected_state_revision')}, current {state.get('state_revision')}")
    if not isinstance(tx.get("operations"), list):
        errors.append("operations должен быть списком")
    event = tx.get("event")
    if not isinstance(event, dict) or not event.get("id") or not event.get("summary"):
        errors.append("event должен содержать id и summary")
    return errors


def apply_operation(state: dict[str, Any], op: dict[str, Any]) -> None:
    t = op.get("type")
    if t == "set_world_field":
        state.setdefault("world", {})[op["field"]] = op.get("value")
    elif t == "set_party_field":
        state.setdefault("party", {})[op["field"]] = op.get("value")
    elif t == "set_character_field":
        cid = op["id"]
        if cid not in state["characters"]:
            raise CampaignError(f"неизвестный персонаж {cid}")
        state["characters"][cid][op["field"]] = op.get("value")
    elif t == "set_character_resource":
        cid = op["id"]
        state["characters"][cid].setdefault("resources", {})[op["resource"]] = op.get("value")
    elif t == "set_knowledge_status":
        kid = op["id"]
        state["knowledge"][kid]["status"] = op["status"]
    elif t == "add_knowledge":
        kid = op["id"]
        if kid in state["knowledge"]:
            raise CampaignError(f"факт {kid} уже существует")
        state["knowledge"][kid] = {
            "fact": op["fact"], "status": op.get("status", "canonical"),
            "known_by": op.get("known_by", []), "hidden_from_party": op.get("hidden_from_party", False)
        }
    elif t == "add_belief":
        bid = op["id"]
        state.setdefault("beliefs", {})[bid] = {
            "character": op["character"], "proposition": op["proposition"],
            "truth_relation": op.get("truth_relation", "unknown"),
            "confidence": op.get("confidence", "medium"), "status": "active"
        }
    elif t == "retire_belief":
        state["beliefs"][op["id"]]["status"] = "retired"
    elif t == "add_world_pressure":
        state.setdefault("world_pressures", {})[op["id"]] = {
            "title": op.get("title"), "status": "active", "visibility": op.get("visibility", "gm"),
            "condition": op.get("condition"), "consequence_if_ignored": op.get("consequence_if_ignored")
        }
    elif t == "resolve_world_pressure":
        state["world_pressures"][op["id"]]["status"] = "resolved"
    elif t == "set_thread_status":
        state["threads"][op["id"]]["status"] = op["status"]
    elif t == "set_thread_field":
        state["threads"][op["id"]][op["field"]] = op.get("value")
    elif t == "transfer_item":
        item = op["item"]
        src = state["characters"][op["from"]].setdefault("inventory", [])
        dst = state["characters"][op["to"]].setdefault("inventory", [])
        if item not in src:
            raise CampaignError(f"{item} отсутствует у {op['from']}")
        src.remove(item)
        dst.append(item)
    else:
        raise CampaignError(f"Неизвестный тип операции: {t}")


def build_result(state: dict[str, Any], tx: dict[str, Any]) -> dict[str, Any]:
    errors = validate_state(state) + validate_transaction(tx, state)
    if errors:
        raise CampaignError("\n".join(errors))
    new_state = copy.deepcopy(state)
    for op in tx["operations"]:
        apply_operation(new_state, op)
    event = tx["event"]
    if any(e.get("id") == event["id"] for e in new_state.get("recent_events", [])):
        raise CampaignError(f"event id уже существует: {event['id']}")
    new_state.setdefault("recent_events", []).append(event)
    new_state["recent_events"] = new_state["recent_events"][-20:]
    next_revision = new_state["state_revision"] + 1
    new_state.setdefault("commit_history", []).append({"revision": next_revision, "event_id": event["id"], "summary": event["summary"]})
    new_state["commit_history"] = new_state["commit_history"][-50:]
    new_state["state_revision"] = next_revision
    errors = validate_state(new_state)
    if errors:
        raise CampaignError("После применения транзакции состояние невалидно:\n" + "\n".join(errors))
    return new_state


def diff(before: Any, after: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        out: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            p = f"{path}.{key}"
            if key not in before:
                out.append({"path": p, "before": None, "after": after[key]})
            elif key not in after:
                out.append({"path": p, "before": before[key], "after": None})
            else:
                out.extend(diff(before[key], after[key], p))
        return out
    if before != after:
        return [{"path": path, "before": before, "after": after}]
    return []


def cmd_check(project: Path) -> None:
    state = read_json(project / "state" / "_campaign-state.json")
    errors = validate_state(state)
    if errors:
        raise CampaignError("\n".join(errors))
    print(json.dumps({"status": "ok", "state_revision": state["state_revision"]}, ensure_ascii=False))


def cmd_render(project: Path) -> None:
    state = read_json(project / "state" / "_campaign-state.json")
    errors = validate_state(state)
    if errors:
        raise CampaignError("\n".join(errors))
    write_views(project, state)
    print(json.dumps({"status": "rendered", "state_revision": state["state_revision"]}, ensure_ascii=False))


def cmd_preview(project: Path, tx_path: Path) -> None:
    state = read_json(project / "state" / "_campaign-state.json")
    tx = read_json(tx_path)
    new_state = build_result(state, tx)
    changes = [c for c in diff(state, new_state) if c["path"] not in {"$.state_revision", "$.commit_history", "$.recent_events"}]
    print(json.dumps({"status": "preview", "current_revision": state["state_revision"], "next_revision": new_state["state_revision"], "event_id": tx["event"]["id"], "changes": changes}, ensure_ascii=False, indent=2))


def cmd_commit(project: Path, tx_path: Path) -> None:
    state_path = project / "state" / "_campaign-state.json"
    state = read_json(state_path)
    tx = read_json(tx_path)
    new_state = build_result(state, tx)
    atomic_write_json(state_path, new_state)
    write_views(project, new_state)
    print(json.dumps({"status": "committed", "previous_revision": state["state_revision"], "state_revision": new_state["state_revision"], "event_id": tx["event"]["id"]}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="D&D campaign state engine")
    parser.add_argument("--project", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("render")
    p = sub.add_parser("preview"); p.add_argument("--transaction", required=True)
    c = sub.add_parser("commit"); c.add_argument("--transaction", required=True)
    args = parser.parse_args()
    project = Path(args.project).resolve()
    try:
        if args.command == "check": cmd_check(project)
        elif args.command == "render": cmd_render(project)
        elif args.command == "preview": cmd_preview(project, Path(args.transaction).resolve())
        elif args.command == "commit": cmd_commit(project, Path(args.transaction).resolve())
        return 0
    except CampaignError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
