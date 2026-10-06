"""Small, deterministic rules for storage; this is not a D&D rules simulator."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

COUNTERS = {"hp", "temp_hp", "arrows", "storm_thrower_ammo", "action_surge",
            "arcane_recovery", "lay_on_hands", "shield_magic_initiate", "prepared_spells"}
ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6",
         "VII": "7", "VIII": "8", "IX": "9"}
VISIBILITIES = {"party", "public", "gm"}
SCENE_MODES = {"social", "combat", "travel", "economy", "exploration"}


def integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def counter(value: Any) -> dict:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        raise ValueError("Ресурс должен содержать current/max")
    match = re.fullmatch(r"\s*(-?\d+)\s*/\s*(-?\d+)(.*)", value)
    if not match:
        raise ValueError(f"Непонятный счётчик: {value}")
    out = {"current": int(match[1]), "max": int(match[2])}
    if match[3].strip(" ;"):
        out["note"] = match[3].strip(" ;")
    return out


def normalize_resource(key: str, value: Any) -> tuple[str, Any]:
    if key == "personal_money_gp":
        try:
            amount = Decimal(str(value)) * 100
            if not amount.is_finite() or amount != amount.to_integral_value():
                raise ValueError("Деньги должны быть точны до медной монеты")
            return "personal_money_cp", int(amount)
        except InvalidOperation as exc:
            raise ValueError("Некорректные деньги") from exc
    if key in COUNTERS:
        return key, counter(value)
    if key == "spell_slots":
        if isinstance(value, dict):
            return key, copy.deepcopy(value)
        if not isinstance(value, str):
            raise ValueError("Ячейки должны быть объектом по кругам")
        out = {}
        for part in value.split(";"):
            match = re.fullmatch(r"\s*([IVX]+)\s+(-?\d+)\s*/\s*(-?\d+)\s*", part)
            if not match or match[1] not in ROMAN or ROMAN[match[1]] in out:
                raise ValueError(f"Непонятные ячейки: {value}")
            out[ROMAN[match[1]]] = {"current": int(match[2]), "max": int(match[3])}
        return key, out
    return key, copy.deepcopy(value)


def validate_counter(value: Any, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label}: требуется объект current/max"]
    current, maximum = value.get("current"), value.get("max")
    if not integer(current) or not integer(maximum) or not 0 <= current <= maximum:
        return [f"{label}: требуется 0 <= current <= max, целые значения"]
    return []


def validate_resources(state: dict) -> list[str]:
    errors = []
    modern = state.get("schema_version") == 2
    for cid, char in state.get("characters", {}).items():
        resources = char.get("resources", {})
        if not isinstance(resources, dict):
            errors.append(f"{cid}.resources должен быть объектом")
            continue
        for key, original in resources.items():
            label = f"{cid}.resources.{key}"
            try:
                normalized_key, value = normalize_resource(key, original)
                if modern and (key != normalized_key or value != original):
                    errors.append(f"{label}: в schema v2 требуется числовая структура")
                if normalized_key.endswith("_money_cp"):
                    if not integer(value) or value < 0:
                        errors.append(f"{label}: деньги — неотрицательное целое число медных монет")
                elif key == "spell_slots":
                    if not value or any(k not in set(ROMAN.values()) for k in value):
                        errors.append(f"{label}: круги должны быть от 1 до 9")
                    for level, slot in value.items():
                        errors.extend(validate_counter(slot, f"{label}.{level}"))
                elif key in COUNTERS or isinstance(value, dict) and ("current" in value or "max" in value):
                    errors.extend(validate_counter(value, label))
            except (ValueError, TypeError) as exc:
                errors.append(f"{label}: {exc}")
    return errors


def validate_clock(state: dict) -> list[str]:
    clock = state.get("world", {}).get("timekeeping")
    if clock is None:
        return []
    if not isinstance(clock, dict):
        return ["timekeeping должен быть объектом"]
    hours = clock.get("elapsed_hours_from_anchor")
    days = clock.get("elapsed_full_days_from_anchor")
    if hours is None and state.get("schema_version") == 1:
        return []
    seconds = clock.get("elapsed_seconds_from_anchor")
    if state.get("schema_version") == 2:
        if not integer(seconds) or seconds < 0:
            return ["elapsed_seconds_from_anchor должен быть неотрицательным целым"]
        if not integer(hours) or hours != seconds // 3600:
            return ["elapsed_hours_from_anchor должен равняться elapsed_seconds_from_anchor // 3600"]
    if not integer(hours) or hours < 0:
        return ["elapsed_hours_from_anchor должен быть неотрицательным целым"]
    if not integer(days) or days != hours // 24:
        return ["elapsed_full_days_from_anchor должен равняться elapsed_hours_from_anchor // 24"]
    return []


def current_fact(fact: dict) -> bool:
    return fact.get("status") == "canonical" and fact.get("temporal_status", "current") == "current"


def player_visible(record: dict, default: str = "party") -> bool:
    return record.get("visibility", default) in {"party", "public"} and not record.get("hidden_from_party", False)


def transaction_hash(tx: dict) -> str:
    # Revision is an optimistic-lock precondition, not part of the played event.
    payload = {k: v for k, v in tx.items() if k != "expected_state_revision"}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def validate_v2(state: dict) -> list[str]:
    errors = validate_resources(state) + validate_clock(state)
    modern = state.get("schema_version") == 2
    for kid, fact in state.get("knowledge", {}).items():
        if fact.get("temporal_status", "current") not in {"current", "historical"}:
            errors.append(f"{kid}: неизвестная актуальность факта")
        for replacement in fact.get("superseded_by", []):
            if replacement not in state["knowledge"] or replacement == kid:
                errors.append(f"{kid}: некорректная ссылка superseded_by")
        if fact.get("status") == "candidate" and fact.get("known_by"):
            errors.append(f"{kid}: подготовительная идея не может быть знанием персонажа")
    for records in (state.get("threads", {}).values(), state.get("recent_events", [])):
        for rec in records:
            if rec.get("visibility", "party") not in VISIBILITIES:
                errors.append("Неизвестная видимость события/линии")
    if not modern:
        return errors
    for cid, char in state.get("characters", {}).items():
        if "knowledge" in char:
            errors.append(f"{cid}.knowledge: ручной дубль запрещён; использовать knowledge/awareness")
        coverage = char.get("source_coverage", {})
        for part in ("inventory", "sheet"):
            item = coverage.get(part, {})
            if item.get("status") not in {"complete", "partial", "not_imported"} or not item.get("source_key"):
                errors.append(f"{cid}.source_coverage.{part}: указать полноту и источник")
    ledger = state.get("applied_events")
    if not isinstance(ledger, dict):
        errors.append("applied_events должен быть постоянным реестром событий")
    else:
        for eid, receipt in ledger.items():
            if not isinstance(receipt, dict) or not integer(receipt.get("revision")):
                errors.append(f"Некорректная квитанция события {eid}")
        if state.get("commit_history") and state["commit_history"][-1].get("event_id") not in ledger:
            errors.append("Последнее событие отсутствует в applied_events")
    scene = state.get("scene_context", {})
    if scene.get("mode") not in SCENE_MODES:
        errors.append("scene_context.mode: неизвестный режим")
    for tid in scene.get("thread_ids", []):
        if tid not in state.get("threads", {}):
            errors.append(f"scene_context: неизвестная линия {tid}")
    for kid in scene.get("fact_ids", []):
        if kid not in state.get("knowledge", {}):
            errors.append(f"scene_context: неизвестный факт {kid}")
    handoff = scene.get("handoff", {})
    if any(handoff.get(k) for k in ("last_player_input", "last_narrative_excerpt")) and not handoff.get("source"):
        errors.append("Точная реплика/проза в handoff требует source")
    if len(handoff.get("last_narrative_excerpt") or "") > 6000:
        errors.append("handoff: сохранить короткий точный фрагмент до 6000 знаков")
    return errors
