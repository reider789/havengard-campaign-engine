#!/usr/bin/env python3
"""Turn explicit, confirmed narrative decisions into an auditable campaign transaction.

This tool NEVER mutates the canonical campaign. A Game Master must review the
transaction and use campaignctl commit separately. In particular, exhaustion
is awarded in the story, not by the tactical engine.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

from campaignctl import build_result

ROOT = Path(__file__).resolve().parents[1]
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")


def natural(value, label, *, maximum=10000):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"{label}: требуется целое число от 0 до {maximum}")
    return value


def changes_to_transaction(state: dict, request: dict) -> dict:
    if not isinstance(request, dict) or not isinstance(request.get("event"), dict):
        raise ValueError("Нужно подтверждённое сюжетное событие event")
    event = request["event"]
    if not event.get("id") or not event.get("summary") or not event.get("source"):
        raise ValueError("Нужны event.id, event.summary и ссылка на источник события")
    if not isinstance(request.get("characters"), dict) or not request["characters"]:
        raise ValueError("Нужна карта изменений персонажей")
    if any(k not in {"event", "characters", "advance_seconds"} for k in request):
        raise ValueError("Неизвестная операция сюжетной подготовки")
    operations = []
    for cid, update in request["characters"].items():
        if cid not in state["characters"]:
            raise ValueError(f"Неизвестный персонаж: {cid}")
        if not isinstance(update, dict) or any(k not in {
            "exhaustion", "prepared_spell_ids", "armor_class", "resources",
            "item_status", "item_quantity", "new_items",
        } for k in update):
            raise ValueError(f"Неизвестное изменение персонажа {cid}")
        character = state["characters"][cid]
        if "exhaustion" in update:
            level = natural(update["exhaustion"], "Уровень истощения", maximum=6)
            continuity = copy.deepcopy(character.get("combat_continuity", {}))
            continuity["exhaustion"] = level
            if level == 6:
                # The death itself is a confirmed narrative outcome, not an
                # automatic tactical penalty after a random combat.
                if update.get("resources", {}).get("hp", 0) != 0:
                    raise ValueError("При шестом уровне истощения ПЗ должны быть 0")
                continuity["life"] = dict(dead=True, stable=False,
                                           deathSuccesses=0, deathFailures=3)
                pool = copy.deepcopy(character["resources"]["hp"])
                pool["current"] = 0
                operations.append(dict(type="set_character_resource", id=cid,
                                       resource="hp", value=pool))
            operations.append(dict(type="set_character_field", id=cid,
                                   field="combat_continuity", value=continuity))
        if "prepared_spell_ids" in update or "armor_class" in update:
            sheet = copy.deepcopy(character["character_sheet"])
            if "prepared_spell_ids" in update:
                spells = update["prepared_spell_ids"]
                if not isinstance(spells, list) or len(spells) != len(set(spells)) or (
                    not all(isinstance(s, str) and SAFE_ID.fullmatch(s) for s in spells)
                ):
                    raise ValueError("Подготовленные заклинания должны быть уникальными ID")
                sheet["prepared_spell_ids"] = spells
            if "armor_class" in update:
                ac = update["armor_class"]
                if not isinstance(ac, str) or not re.match(r"^(?:[1-9]|[1-3][0-9]|40)(?:\b|\s)", ac):
                    raise ValueError("Текущий КД должен начинаться с числа 1–40")
                sheet["armor_class"] = ac
            operations.append(dict(type="set_character_field", id=cid,
                                   field="character_sheet", value=sheet))
        for resource, current in update.get("resources", {}).items():
            before = character["resources"].get(resource)
            if resource == "spell_slots":
                if not isinstance(current, dict):
                    raise ValueError("Ячейки требуется указывать по кругам")
                value = copy.deepcopy(before)
                for circle, amount in current.items():
                    if circle not in value:
                        raise ValueError(f"Неизвестный круг ячеек: {circle}")
                    value[circle]["current"] = natural(amount, "Текущие ячейки", maximum=value[circle]["max"])
            else:
                if not isinstance(before, dict) or "max" not in before:
                    raise ValueError(f"Неизвестный счётчик {resource}")
                value = copy.deepcopy(before)
                value["current"] = natural(current, resource, maximum=before["max"])
            operations.append(dict(type="set_character_resource", id=cid,
                                   resource=resource, value=value))
        statuses = update.get("item_status", {})
        amounts = update.get("item_quantity", {})
        additions = update.get("new_items", [])
        if statuses or amounts or additions:
            inventory = list(character.get("inventory", []))
            catalog = copy.deepcopy(character.get("inventory_catalog", {}))
            for item_id, status in statuses.items():
                if item_id not in inventory or item_id not in catalog:
                    raise ValueError("Нельзя экипировать неподтверждённый предмет: " + item_id)
                if not isinstance(status, str) or not 1 <= len(status) <= 200:
                    raise ValueError("Неверный статус экипировки")
                catalog[item_id]["status"] = status
            for item_id, quantity in amounts.items():
                if item_id not in inventory or item_id not in catalog:
                    raise ValueError("Нельзя изменять неизвестный предмет: " + item_id)
                catalog[item_id]["quantity"] = natural(quantity, "Количество предмета")
            for item in additions:
                if not isinstance(item, dict) or not set(item).issubset({
                    "id", "name", "quantity", "status", "description", "value_gp", "component_for",
                }):
                    raise ValueError("Недопустимые поля нового предмета")
                item_id = item.get("id")
                if not isinstance(item_id, str) or not SAFE_ID.fullmatch(item_id) or item_id in catalog:
                    raise ValueError("Неверный или повторный ID нового предмета")
                if not isinstance(item.get("name"), str) or not item["name"].strip():
                    raise ValueError("Нужно подтверждённое название предмета")
                quantity = natural(item.get("quantity"), "Количество предмета")
                if quantity == 0:
                    raise ValueError("Не добавлять нулевые предметы")
                record = {k: copy.deepcopy(v) for k, v in item.items() if k != "id"}
                if "value_gp" in item:
                    natural(item["value_gp"], "Стоимость компонента", maximum=1000000)
                record.setdefault("status", "При себе")
                catalog[item_id] = record
                inventory.append(item_id)
            operations.append(dict(type="set_character_field", id=cid,
                                   field="inventory_catalog", value=catalog))
            operations.append(dict(type="set_character_field", id=cid,
                                   field="inventory", value=inventory))
    if "advance_seconds" in request:
        seconds = natural(request["advance_seconds"], "Время сцены", maximum=86400 * 30)
        if seconds:
            operations.append(dict(type="advance_time", seconds=seconds))
    tx = {"event": {"id": event["id"], "source": event["source"],
                    "summary": event["summary"], "visibility": event.get("visibility", "party")},
          "expected_state_revision": state["state_revision"], "operations": operations}
    # This validates item quantities, exhaustion storage, canonical consistency and
    # transaction schema on a COPY. Never write state/_campaign-state.json here.
    build_result(state, tx)
    return tx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project", type=Path, default=ROOT)
    args = parser.parse_args()
    state = json.loads((args.project / "state/_campaign-state.json").read_text())
    request = json.loads(args.request.read_text())
    tx = changes_to_transaction(state, request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(tx, ensure_ascii=False, indent=2) + "\n")
    print(f"Предпросмотр подтверждённой сюжетной операции: {args.output}; "
          f"канон не изменён, правок: {len(tx['operations'])}")


if __name__ == "__main__":
    main()
