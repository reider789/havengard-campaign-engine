#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
import re
import fcntl
from pathlib import Path
from typing import Any

from campaign_model import (current_fact, integer, normalize_resource, player_visible,
                            transaction_hash, validate_v2)
from sync_time_dependent_state import synchronize
from knowledgegraph import validate_graph, render_scene_slice

SCHEMA_VERSION = 2
RULES_SCHEMA_VERSION = 1
RULES_RELATIVE_PATH = Path("rules") / "_campaign-rules.json"


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


def _relation_person_known(pid: str, state: dict[str, Any]) -> bool:
    return pid in state.get("characters", {}) or pid.startswith("npc:") or pid.startswith("group:")


def validate_relationships(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    relationships = state.get("relationships", {})
    if relationships is None:
        return errors
    if not isinstance(relationships, dict):
        return ["relationships должен быть объектом"]
    forbidden_numeric = {"affection", "trust", "warmth", "romance", "openness", "awkwardness", "attachment"}
    for rid, rel in relationships.items():
        if not isinstance(rel, dict):
            errors.append(f"{rid} должен быть объектом")
            continue
        participants = rel.get("participants", [])
        if not isinstance(participants, list) or len(participants) < 2:
            errors.append(f"{rid}.participants должен содержать минимум двух участников")
        else:
            for pid in participants:
                if not _relation_person_known(pid, state):
                    errors.append(f"{rid}.participants содержит неизвестного участника {pid}")
        if rel.get("status", "active") not in {"active", "inactive", "resolved", "historical"}:
            errors.append(f"{rid}.status имеет недопустимое значение")
        if rel.get("visibility", "party") not in {"party", "public", "gm"}:
            errors.append(f"{rid}.visibility имеет недопустимое значение")
        directional = rel.get("directional", {})
        if directional and not isinstance(directional, dict):
            errors.append(f"{rid}.directional должен быть объектом")
        elif isinstance(directional, dict):
            for pid, feelings in directional.items():
                if pid not in participants:
                    errors.append(f"{rid}.directional.{pid} не входит в participants")
                if not isinstance(feelings, dict):
                    errors.append(f"{rid}.directional.{pid} должен быть объектом")
                    continue
                for key, value in feelings.items():
                    if key in forbidden_numeric and isinstance(value, (int, float)) and not isinstance(value, bool):
                        errors.append(f"{rid}.directional.{pid}.{key} должен быть качественным, не числовым")
        evidence = rel.get("evidence", [])
        if evidence and not isinstance(evidence, list):
            errors.append(f"{rid}.evidence должен быть списком")
    return errors


def validate_state(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if state.get("schema_version") not in {1, SCHEMA_VERSION}:
        errors.append("schema_version должен быть 1 (архив) или 2")
    if not integer(state.get("state_revision")) or state["state_revision"] < 0:
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
    errors.extend(validate_relationships(state))
    errors.extend(validate_v2(state))
    if state.get("schema_version") == 2:
        errors.extend(validate_graph(state, state.get("knowledge_graph", {})))
    return errors


def read_campaign_rules(project: Path) -> dict[str, Any]:
    return read_json(project / RULES_RELATIVE_PATH)


def validate_rules(rules: dict[str, Any], state: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    if rules.get("schema_version") != RULES_SCHEMA_VERSION:
        errors.append(f"rules.schema_version должен быть {RULES_SCHEMA_VERSION}")
    required = (
        "campaign_id", "priority_order", "canon_policy", "narrative", "social_and_relationships",
        "character_anchors", "mechanics_and_rolls", "combat", "world_logic", "readiness_and_resources",
        "loot_inventory_and_assets", "travel", "city_and_population", "economy",
        "pacing_and_presentation", "continuity", "source_registry"
    )
    for key in required:
        if key not in rules:
            errors.append(f"В rule pack отсутствует обязательный раздел: {key}")
    if state:
        campaign_id = state.get("campaign", {}).get("id")
        if campaign_id and rules.get("campaign_id") != campaign_id:
            errors.append(f"rule pack относится к кампании {rules.get('campaign_id')}, а state — к {campaign_id}")
    return errors


def validate_project(state: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    errors = validate_state(state) + validate_rules(rules, state)
    if not errors and state.get("schema_version") == 2:
        derived = copy.deepcopy(state)
        if synchronize(derived):
            errors.append("Производные поля времени устарели; обновить через транзакцию")
    return errors


def _person_name(pid: str, state: dict[str, Any], rel: dict[str, Any] | None = None) -> str:
    if pid in state.get("characters", {}):
        return state["characters"][pid].get("name", pid)
    if rel:
        names = rel.get("participant_names", {})
        if pid in names:
            return names[pid]
    if pid.startswith("npc:"):
        return pid.split(":", 1)[1]
    return pid


def render_relationships_gm(state: dict[str, Any]) -> list[str]:
    rels = state.get("relationships", {})
    if not rels:
        return []
    lines = ["", "## Текущие отношения"]
    for rid, rel in rels.items():
        if rel.get("status", "active") not in {"active", "historical"}:
            continue
        label = rel.get("label") or " ↔ ".join(_person_name(p, state, rel) for p in rel.get("participants", []))
        lines.append(
            f"- {rid} — {label}: формально — {rel.get('formal_status','не указано')}; "
            f"эмоционально — {rel.get('emotional_stage','не указано')}; траектория — {rel.get('trajectory','не указано')}; "
            f"темп — {rel.get('pace','не указано')}."
        )
        summary = rel.get("gm_summary") or rel.get("player_summary")
        if summary:
            lines.append(f"  Сводка: {summary}")
        directional = rel.get("directional", {})
        for pid, feelings in directional.items():
            name = _person_name(pid, state, rel)
            desc = feelings.get("summary") if isinstance(feelings, dict) else None
            if desc:
                lines.append(f"  {name} → другой участник: {desc}")
        dynamics = rel.get("dynamics", [])
        if dynamics:
            lines.append("  Динамика: " + "; ".join(str(x) for x in dynamics) + ".")
        boundaries = rel.get("boundaries", [])
        if boundaries:
            lines.append("  Границы: " + "; ".join(str(x) for x in boundaries) + ".")
    return lines


def render_relationships_player(state: dict[str, Any]) -> list[str]:
    rels = state.get("relationships", {})
    visible = []
    for rid, rel in rels.items():
        if rel.get("status", "active") != "active" or rel.get("visibility", "party") not in {"party", "public"}:
            continue
        summary = rel.get("player_summary")
        if not summary:
            continue
        label = rel.get("label") or " ↔ ".join(_person_name(p, state, rel) for p in rel.get("participants", []))
        visible.append(f"- {label}: {summary}")
    if not visible:
        return []
    return ["", "## Отношения"] + visible


def render_gm_context(state: dict[str, Any], campaign_rules: dict[str, Any]) -> str:
    w = state["world"]
    lines = [
        "# GM Context", "", f"> state_revision: {state['state_revision']}",
        "> authoritative state = что происходит сейчас; rule pack = как вести кампанию", "",
        "## Где и когда",
        f"- Регион: {w.get('current_region', 'не указано')}",
        f"- Сцена: {w.get('current_scene', 'не указано')}",
        f"- Время: {w.get('time_label', 'не указано')}", "", "## Партия",
    ]
    for cid in state["party"].get("members", []):
        c = state["characters"][cid]
        lines.append(f"- {c['name']}: {c.get('state','')}; {c.get('time_summary', '')}; цель — {c.get('goal','')}")
    lines.extend(render_relationships_gm(state))
    lines += ["", "## Активные сюжетные линии"]
    for tid, t in state.get("threads", {}).items():
        if t.get("status") == "active":
            lines.append(f"- {tid} — {t.get('title')}: {t.get('summary')} | давление: {t.get('pressure','нет')}")
    lines += ["", "## Канонические факты"]
    for kid, fact in state.get("knowledge", {}).items():
        if current_fact(fact):
            lines.append(f"- {kid}: {fact.get('fact')}")
    lines += ["", "## Исторические факты — не текущее состояние"]
    for kid, fact in state.get("knowledge", {}).items():
        if fact.get("status") == "canonical" and not current_fact(fact):
            lines.append(f"- {kid}: {fact.get('fact')} | сменилось: {', '.join(fact.get('superseded_by', [])) or 'см. событие'}")
    lines += ["", "## Кандидатные идеи — НЕ КАНОН"]
    candidates = [(kid, f) for kid, f in state.get("knowledge", {}).items() if f.get("status") == "candidate"]
    if candidates:
        for kid, fact in candidates:
            lines.append(f"- {kid}: {fact.get('fact')}")
    else:
        lines.append("- Нет.")

    table_rules = state.get("play_rules", {})
    if table_rules:
        lines += ["", "## Правила текущего стола из state"]
        combat = table_rules.get("combat_control", {})
        controlled = combat.get("party_controlled_by_player", [])
        if controlled:
            names = [state["characters"].get(cid, {}).get("name", cid) for cid in controlled]
            lines.append(f"- В бою игрок управляет: {', '.join(names)}.")
        if combat.get("stop_before_each_player_character_turn"):
            lines.append("- Останавливаться перед ходом каждого персонажа игрока и не выбирать за него действия.")
        briefing = combat.get("turn_briefing", {})
        if briefing.get("principle"):
            lines.append(f"- Тактический брифинг: {briefing['principle']}")
        if combat.get("automatic_defensive_reactions", {}).get("daphne_shield"):
            lines.append("- Дафна автоматически применяет «Щит», если +5 КД превращает попадание в промах: сначала бесплатное применение Magic Initiate, затем минимальную доступную ячейку.")
        mage_hand = table_rules.get("combat_rulings", {}).get("mage_hand_soften_fall")
        if mage_hand:
            lines.append(f"- Трактовка Магической руки: {mage_hand}")
        narrative = table_rules.get("narrative_control", {})
        if narrative.get("player_words_are_woven_into_first_person_narrative"):
            lines.append("- Реплики и действия Яра от игрока вплетать в повествование от первого лица; не придумывать за Яра решения.")

    lines += ["", "## Постоянный rule pack кампании"]
    lines.append("- Это постоянные инструкции ведущему, а не факты мира; они не становятся знаниями персонажей.")
    priority = campaign_rules.get("priority_order", [])
    if priority:
        lines.append("- Приоритет источников: " + " → ".join(priority) + ".")
    categories = [
        ("canon_policy", "rules", "Канон"), ("narrative", "rules", "Повествование"),
        ("social_and_relationships", "rules", "Отношения"), ("mechanics_and_rolls", "rules", "Механика"),
        ("combat", "rules", "Бой"), ("world_logic", "rules", "Мир"),
        ("readiness_and_resources", "rules", "Ресурсы"), ("loot_inventory_and_assets", "rules", "Инвентарь"),
        ("travel", "rules", "Путешествия"), ("city_and_population", "rules", "Город"),
        ("economy", "always_on_rules", "Экономика"), ("pacing_and_presentation", "rules", "Темп"),
        ("continuity", "rules", "Непрерывность"),
    ]
    for section, field, prefix in categories:
        for rule in campaign_rules.get(section, {}).get(field, []):
            lines.append(f"- {prefix}: {rule}")
    anchors = campaign_rules.get("character_anchors", {})
    for cid in state.get("party", {}).get("members", []):
        if cid in anchors:
            name = state.get("characters", {}).get(cid, {}).get("name", cid)
            for anchor in anchors[cid]:
                lines.append(f"- {name}: {anchor}")
    lazy = campaign_rules.get("economy", {}).get("lazy_load_when", [])
    if lazy:
        lines.append("- Полный экономический промт загружать при: " + "; ".join(lazy) + ".")
    audit = campaign_rules.get("prompt_audit", {})
    if audit.get("status"):
        lines.append(f"- Аудит старых промтов: {audit['status']}")
    sources = campaign_rules.get("source_registry", [])
    if sources:
        lines += ["", "## Реестр полных источников — загружать по необходимости"]
        for source in sources:
            lines.append(f"- {source.get('key')}: {source.get('title')} | ID {source.get('drive_id') or source.get('library_file_id')} | роль: {source.get('role')} | режим: {source.get('load_policy')}")
    lines += ["", "## Последние события"]
    for event in state.get("recent_events", [])[-10:]:
        lines.append(f"- {event.get('id')}: {event.get('summary')}")
    return "\n".join(lines) + "\n"


def render_player_context(state: dict[str, Any]) -> str:
    w = state["world"]
    lines = ["# Player Context", "", f"> state_revision: {state['state_revision']}", "", "## Текущая сцена", f"- {w.get('current_scene')}", f"- {w.get('time_label')}"]
    lines.extend(render_relationships_player(state))
    lines += ["", "## Активные линии"]
    for t in state.get("threads", {}).values():
        if t.get("status") == "active" and player_visible(t, "gm" if state.get("schema_version") == 2 else "party"):
            lines.append(f"- {t.get('title')}: {t.get('summary')}")
    lines += ["", "## Последние события"]
    for event in state.get("recent_events", [])[-10:]:
        if player_visible(event, "gm" if state.get("schema_version") == 2 else "party"):
            lines.append(f"- {event.get('player_summary', event.get('summary'))}")
    return "\n".join(lines) + "\n"


def write_views(project: Path, state: dict[str, Any], campaign_rules: dict[str, Any] | None = None) -> None:
    if campaign_rules is None:
        campaign_rules = read_campaign_rules(project)
    errors = validate_rules(campaign_rules, state)
    if errors:
        raise CampaignError("Некорректный rule pack:\n" + "\n".join(errors))
    views = project / "views"
    views.mkdir(parents=True, exist_ok=True)
    for name, content in rendered_views(state, campaign_rules).items():
        atomic_write_text(views / name, content)
    if state.get("schema_version") == 2:
        atomic_write_json(project / "state" / "_knowledge-graph.json", state["knowledge_graph"])


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".view-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def rendered_views(state: dict, rules: dict) -> dict[str, str]:
    from scene_context import render_scene_context
    out = {"gm-context.md": render_gm_context(state, rules),
           "player-context.md": render_player_context(state),
           "scene-context.md": render_scene_context(state, rules)}
    if state.get("knowledge_graph"):
        out["scene-knowledge.md"] = render_scene_slice(state, state["knowledge_graph"])
    return out


def validate_transaction(tx: dict[str, Any], state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not integer(tx.get("expected_state_revision")):
        errors.append("expected_state_revision должен быть целым числом")
    if tx.get("expected_state_revision") != state.get("state_revision"):
        errors.append(f"stale transaction: expected {tx.get('expected_state_revision')}, current {state.get('state_revision')}")
    if not isinstance(tx.get("operations"), list):
        errors.append("operations должен быть списком")
    event = tx.get("event")
    if not isinstance(event, dict) or not event.get("id") or not event.get("summary"):
        errors.append("event должен содержать id и summary")
    elif not isinstance(event["id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,160}", event["id"]):
        errors.append("event.id: использовать безопасный постоянный идентификатор")
    if state.get("schema_version") == 2 and isinstance(event, dict) and event.get("visibility") not in {"party", "public", "gm"}:
        errors.append("event.visibility обязателен: party/public/gm")
    if tx.get("kind") == "month_close" and not str(tx.get("unique_key", "")).startswith("month:"):
        errors.append("Для month_close обязателен unique_key вида month:ГnМm")
    return errors


def apply_operation(state: dict[str, Any], op: dict[str, Any], event: dict | None = None) -> None:
    event = event or {}
    modern = state.get("schema_version") == 2
    t = op.get("type")
    if t == "advance_time":
        units = [key for key in ("seconds", "minutes", "hours") if key in op]
        if len(units) != 1 or not integer(op[units[0]]) or op[units[0]] < 0:
            raise CampaignError("advance_time: задать ровно одно неотрицательное целое seconds/minutes/hours")
        clock = state["world"]["timekeeping"]
        seconds = op[units[0]] * {"seconds": 1, "minutes": 60, "hours": 3600}[units[0]]
        clock["elapsed_seconds_from_anchor"] = clock.get("elapsed_seconds_from_anchor", clock["elapsed_hours_from_anchor"] * 3600) + seconds
        clock["elapsed_hours_from_anchor"] = clock["elapsed_seconds_from_anchor"] // 3600
        clock["elapsed_full_days_from_anchor"] = clock["elapsed_hours_from_anchor"] // 24
    elif t == "set_scene_context":
        state["scene_context"] = copy.deepcopy(op["value"])
    elif t in {"set_awareness", "upsert_knowledge_branch", "register_principal"}:
        graph = state["knowledge_graph"]
        if t == "set_awareness":
            graph.setdefault("awareness", {}).setdefault(op["fact_id"], {})[op["principal_id"]] = copy.deepcopy(op["value"])
        else:
            section = "branches" if t == "upsert_knowledge_branch" else "principals"
            graph.setdefault(section, {})[op["id"]] = copy.deepcopy(op["value"])
    elif t in {"supersede_knowledge", "correct_knowledge"}:
        fact = state["knowledge"][op["id"]]
        if not op.get("reason") or not op.get("replacement_ids"):
            raise CampaignError("Указать reason и replacement_ids для изменения канона")
        fact["temporal_status"] = "historical"
        fact["superseded_by"] = op["replacement_ids"]
        fact["valid_to_event"] = event.get("id")
        fact["transition_reason"] = op["reason"]
        if t == "correct_knowledge":
            fact["status"] = "disproven"
    elif t == "adjust_resource":
        resources = state["characters"][op["id"]]["resources"]
        key = op["resource"]
        value = resources[key]
        if not integer(op["delta"]):
            raise CampaignError("delta должен быть целым")
        if key == "spell_slots":
            value = value[str(op["level"])]
        if isinstance(value, dict):
            value["current"] += op["delta"]
        elif key.endswith("_money_cp"):
            resources[key] += op["delta"]
        else:
            raise CampaignError("adjust_resource поддерживает счётчики и деньги")
    elif t == "transfer_money":
        amount = op["amount_cp"]
        if not integer(amount) or amount <= 0 or op["from"] == op["to"]:
            raise CampaignError("Передача денег требует положительную сумму и разных участников")
        for who, delta in ((op["from"], -amount), (op["to"], amount)):
            resources = state["characters"][who]["resources"]
            if "personal_money_cp" not in resources:
                raise CampaignError(f"Баланс {who} не импортирован; неизвестное не равно нулю")
            resources["personal_money_cp"] += delta
    elif t == "set_world_field":
        if modern and op["field"] == "timekeeping":
            raise CampaignError("Для продвижения времени использовать advance_time; смена опоры требует миграции")
        state.setdefault("world", {})[op["field"]] = op.get("value")
    elif t == "set_party_field":
        state.setdefault("party", {})[op["field"]] = op.get("value")
    elif t == "set_scene_participants":
        state.setdefault("world", {})["scene_participants"] = op.get("value", [])
    elif t == "set_character_field":
        cid = op["id"]
        if cid not in state["characters"]:
            raise CampaignError(f"неизвестный персонаж {cid}")
        if modern and op["field"] in {"knowledge", "resources", "time_summary"}:
            raise CampaignError("Для ресурсов использовать ресурсные операции; знания и сводка времени производны")
        state["characters"][cid][op["field"]] = op.get("value")
    elif t == "set_character_resource":
        cid = op["id"]
        if cid not in state["characters"]:
            raise CampaignError(f"неизвестный персонаж {cid}")
        key, value = normalize_resource(op["resource"], op.get("value")) if modern else (op["resource"], op.get("value"))
        previous = state["characters"][cid].get("resources", {}).get(key)
        if modern and isinstance(previous, dict) and isinstance(value, dict):
            old_caps = {k: v.get("max") for k, v in previous.items()} if key == "spell_slots" else previous.get("max")
            new_caps = {k: v.get("max") if isinstance(v, dict) else None for k, v in value.items()} if key == "spell_slots" else value.get("max")
            if old_caps != new_caps and not op.get("capacity_reason"):
                raise CampaignError("Изменение максимума требует capacity_reason с основанием")
        state["characters"][cid].setdefault("resources", {})[key] = value
    elif t == "remove_character_item":
        cid = op["id"]
        item = op["item"]
        if cid not in state["characters"]:
            raise CampaignError(f"неизвестный персонаж {cid}")
        inv = state["characters"][cid].setdefault("inventory", [])
        if item not in inv:
            raise CampaignError(f"{item} отсутствует у {cid}")
        inv.remove(item)
    elif t == "set_knowledge_status":
        kid = op["id"]
        if kid not in state["knowledge"]:
            raise CampaignError(f"неизвестный факт {kid}")
        if modern:
            raise CampaignError("Статус канона менять через correct_knowledge/supersede_knowledge; новый факт добавлять отдельно")
        state["knowledge"][kid]["status"] = op["status"]
    elif t == "set_knowledge_field":
        kid = op["id"]
        if kid not in state["knowledge"]:
            raise CampaignError(f"неизвестный факт {kid}")
        if modern and op["field"] not in {"known_by", "hidden_from_party", "visibility"}:
            raise CampaignError("Не переписывать факт; создать замену и оформить исправление/смену состояния")
        state["knowledge"][kid][op["field"]] = op.get("value")
    elif t == "add_knowledge":
        kid = op["id"]
        if kid in state["knowledge"]:
            raise CampaignError(f"факт {kid} уже существует")
        state["knowledge"][kid] = {"fact": op["fact"], "status": op.get("status", "canonical"), "known_by": op.get("known_by", []), "hidden_from_party": op.get("hidden_from_party", False)}
        if op.get("source_event"):
            state["knowledge"][kid]["source_event"] = op["source_event"]
        if modern:
            state["knowledge"][kid]["source_event"] = op.get("source_event", event.get("id"))
            state["knowledge"][kid]["temporal_status"] = op.get("temporal_status", "current")
    elif t == "add_belief":
        bid = op["id"]
        state.setdefault("beliefs", {})[bid] = {"character": op["character"], "proposition": op["proposition"], "truth_relation": op.get("truth_relation", "unknown"), "confidence": op.get("confidence", "medium"), "status": "active"}
    elif t == "retire_belief":
        if op["id"] not in state.get("beliefs", {}):
            raise CampaignError(f"неизвестное убеждение {op['id']}")
        state["beliefs"][op["id"]]["status"] = "retired"
    elif t == "add_world_pressure":
        state.setdefault("world_pressures", {})[op["id"]] = {"title": op.get("title"), "status": "active", "visibility": op.get("visibility", "gm"), "condition": op.get("condition"), "consequence_if_ignored": op.get("consequence_if_ignored")}
    elif t == "resolve_world_pressure":
        if op["id"] not in state.get("world_pressures", {}):
            raise CampaignError(f"неизвестное давление мира {op['id']}")
        state["world_pressures"][op["id"]]["status"] = "resolved"
    elif t == "set_world_pressure_field":
        if op["id"] not in state.get("world_pressures", {}):
            raise CampaignError(f"неизвестное давление мира {op['id']}")
        state["world_pressures"][op["id"]][op["field"]] = op.get("value")
    elif t == "set_thread_status":
        if op["id"] not in state.get("threads", {}):
            raise CampaignError(f"неизвестная сюжетная линия {op['id']}")
        state["threads"][op["id"]]["status"] = op["status"]
    elif t == "set_thread_field":
        if op["id"] not in state.get("threads", {}):
            raise CampaignError(f"неизвестная сюжетная линия {op['id']}")
        state["threads"][op["id"]][op["field"]] = op.get("value")
    elif t == "set_project_field":
        projects = state.setdefault("projects", {})
        if op["id"] not in projects:
            raise CampaignError(f"неизвестный проект {op['id']}")
        projects[op["id"]][op["field"]] = op.get("value")
    elif t == "set_loot_bundle_field":
        bundles = state.setdefault("loot_bundles", {})
        if op["id"] not in bundles:
            raise CampaignError(f"неизвестный набор добычи {op['id']}")
        bundles[op["id"]][op["field"]] = op.get("value")
    elif t == "upsert_relationship":
        rid = op["id"]
        value = copy.deepcopy(op.get("value", {}))
        if not isinstance(value, dict):
            raise CampaignError("value отношения должен быть объектом")
        state.setdefault("relationships", {})[rid] = value
    elif t == "set_relationship_field":
        rid = op["id"]
        if rid not in state.setdefault("relationships", {}):
            raise CampaignError(f"неизвестное отношение {rid}")
        state["relationships"][rid][op["field"]] = op.get("value")
    elif t == "append_relationship_event":
        rid = op["id"]
        if rid not in state.setdefault("relationships", {}):
            raise CampaignError(f"неизвестное отношение {rid}")
        evidence = state["relationships"][rid].setdefault("evidence", [])
        evidence.append(copy.deepcopy(op["event"]))
        state["relationships"][rid]["evidence"] = evidence[-20:]
    elif t == "transfer_item":
        item = op["item"]
        if op["from"] not in state["characters"] or op["to"] not in state["characters"]:
            raise CampaignError("передача предмета ссылается на неизвестного персонажа")
        src = state["characters"][op["from"]].setdefault("inventory", [])
        dst = state["characters"][op["to"]].setdefault("inventory", [])
        if item not in src:
            raise CampaignError(f"{item} отсутствует у {op['from']}")
        if item in dst:
            raise CampaignError(f"{item} уже есть у получателя")
        src.remove(item)
        dst.append(item)
    else:
        raise CampaignError(f"Неизвестный тип операции: {t}")


def build_result(state: dict[str, Any], tx: dict[str, Any]) -> dict[str, Any]:
    eid = tx.get("event", {}).get("id")
    receipt = state.get("applied_events", {}).get(eid)
    if receipt:
        if receipt.get("payload_sha256") == transaction_hash(tx):
            return copy.deepcopy(state)
        raise CampaignError(f"event id уже существует: {eid}; другое содержание или старый импорт без полного payload")
    errors = validate_state(state) + validate_transaction(tx, state)
    if errors:
        raise CampaignError("\n".join(errors))
    if state.get("schema_version") == 2:
        operations = tx["operations"]
        if any(o.get("type") == "set_world_field" and o.get("field") == "current_scene" for o in operations):
            needed = {"set_scene_context", "set_scene_participants"}
            focus_set = any(o.get("type") == "set_world_field" and o.get("field") == "scene_knowledge_branches" for o in operations)
            if not needed.issubset({o.get("type") for o in operations}) or not focus_set:
                raise CampaignError("При смене сцены явно задать участников, scene_context и scene_knowledge_branches (можно [])")
    new_state = copy.deepcopy(state)
    for op in tx["operations"]:
        apply_operation(new_state, op, tx["event"])
    synchronize(new_state)
    if new_state.get("knowledge_graph") != state.get("knowledge_graph"):
        new_state["knowledge_graph"]["graph_revision"] = state["knowledge_graph"]["graph_revision"] + 1
    event = tx["event"]
    if any(e.get("id") == event["id"] for e in new_state.get("recent_events", [])):
        raise CampaignError(f"event id уже существует: {event['id']}")
    new_state.setdefault("recent_events", []).append(event)
    new_state["recent_events"] = new_state["recent_events"][-20:]
    next_revision = new_state["state_revision"] + 1
    new_state.setdefault("commit_history", []).append({"revision": next_revision, "event_id": event["id"], "summary": event["summary"]})
    new_state["commit_history"] = new_state["commit_history"][-50:]
    new_state["state_revision"] = next_revision
    if new_state.get("schema_version") == 2:
        new_state.setdefault("applied_events", {})[event["id"]] = {"revision": next_revision, "payload_sha256": transaction_hash(tx)}
        unique_key = tx.get("unique_key")
        if unique_key:
            keys = new_state.setdefault("event_unique_keys", {})
            if unique_key in keys:
                raise CampaignError(f"Уже выполнено: {unique_key}")
            keys[unique_key] = event["id"]
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
    rules = read_campaign_rules(project)
    errors = validate_project(state, rules)
    if errors:
        raise CampaignError("\n".join(errors))
    print(json.dumps({"status": "ok", "state_revision": state["state_revision"], "rules_schema_version": rules["schema_version"], "rules_loaded": True}, ensure_ascii=False))


def cmd_render(project: Path) -> None:
    state = read_json(project / "state" / "_campaign-state.json")
    rules = read_campaign_rules(project)
    errors = validate_project(state, rules)
    if errors:
        raise CampaignError("\n".join(errors))
    write_views(project, state, rules)
    print(json.dumps({"status": "rendered", "state_revision": state["state_revision"], "rules_loaded": True}, ensure_ascii=False))


def cmd_preview(project: Path, tx_path: Path) -> None:
    state = read_json(project / "state" / "_campaign-state.json")
    rules = read_campaign_rules(project)
    errors = validate_project(state, rules)
    if errors:
        raise CampaignError("\n".join(errors))
    tx = read_json(tx_path)
    new_state = build_result(state, tx)
    rendered_views(new_state, rules)
    changes = [c for c in diff(state, new_state) if c["path"] not in {"$.state_revision", "$.commit_history", "$.recent_events"}]
    print(json.dumps({"status": "preview", "current_revision": state["state_revision"], "next_revision": new_state["state_revision"], "event_id": tx["event"]["id"], "changes": changes}, ensure_ascii=False, indent=2))


def cmd_commit(project: Path, tx_path: Path) -> None:
    with (project / ".campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _commit_locked(project, tx_path)


def _commit_locked(project: Path, tx_path: Path) -> None:
    state_path = project / "state" / "_campaign-state.json"
    state = read_json(state_path)
    rules = read_campaign_rules(project)
    errors = validate_project(state, rules)
    if errors:
        raise CampaignError("\n".join(errors))
    tx = read_json(tx_path)
    new_state = build_result(state, tx)
    rendered_views(new_state, rules)  # Fail before changing authoritative state.
    if state.get("schema_version") == 2 and new_state != state:
        archive = project / "transactions" / "applied" / f"{tx['event']['id']}.json"
        if archive.exists() and transaction_hash(read_json(archive)) != transaction_hash(tx):
            raise CampaignError("Архивное событие нельзя перезаписывать другим содержимым")
        if not archive.exists():
            atomic_write_json(archive, tx)
    if new_state != state:
        atomic_write_json(state_path, new_state)
    write_views(project, new_state, rules)
    print(json.dumps({"status": "committed" if new_state != state else "already_applied", "previous_revision": state["state_revision"], "state_revision": new_state["state_revision"], "event_id": tx["event"]["id"]}, ensure_ascii=False))


def cmd_check_views(project: Path) -> None:
    state = read_json(project / "state" / "_campaign-state.json")
    rules = read_campaign_rules(project)
    errors = validate_project(state, rules)
    for name, content in rendered_views(state, rules).items():
        path = project / "views" / name
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            errors.append(f"Устарел views/{name}; выполнить render")
    if state.get("schema_version") == 2 and read_json(project / "state" / "_knowledge-graph.json") != state["knowledge_graph"]:
        errors.append("Производная копия knowledge graph устарела")
    if errors:
        raise CampaignError("\n".join(errors))
    print(json.dumps({"status": "ok", "views_current": True}))


def main() -> int:
    parser = argparse.ArgumentParser(description="D&D campaign state engine")
    parser.add_argument("--project", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("render")
    sub.add_parser("check-views")
    context = sub.add_parser("context")
    context.add_argument("--mode", choices=["social", "combat", "travel", "economy", "exploration"])
    p = sub.add_parser("preview"); p.add_argument("--transaction", required=True)
    c = sub.add_parser("commit"); c.add_argument("--transaction", required=True)
    args = parser.parse_args()
    project = Path(args.project).resolve()
    try:
        if args.command == "check": cmd_check(project)
        elif args.command == "render": cmd_render(project)
        elif args.command == "check-views": cmd_check_views(project)
        elif args.command == "context":
            from scene_context import render_scene_context
            state = read_json(project / "state" / "_campaign-state.json")
            rules = read_campaign_rules(project)
            errors = validate_project(state, rules)
            if errors: raise CampaignError("\n".join(errors))
            print(render_scene_context(state, rules, args.mode))
        elif args.command == "preview": cmd_preview(project, Path(args.transaction).resolve())
        elif args.command == "commit": cmd_commit(project, Path(args.transaction).resolve())
        return 0
    except (CampaignError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
