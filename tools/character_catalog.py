"""Validate character equipment catalogs in the authoritative campaign state."""
from __future__ import annotations

from typing import Any


def validate_character_catalogs(state: dict[str, Any]) -> list[str]:
    errors = []
    for char_id, char in state.get("characters", {}).items():
        catalog = char.get("inventory_catalog")
        if catalog is None:
            continue
        inventory = char.get("inventory")
        if not isinstance(inventory, list) or any(not isinstance(i, str) for i in inventory):
            errors.append(f"{char_id}.inventory: нужны идентификаторы предметов")
            continue
        if len(set(inventory)) != len(inventory):
            errors.append(f"{char_id}.inventory: повторный идентификатор предмета")
        if not isinstance(catalog, dict) or set(inventory) != set(catalog):
            errors.append(f"{char_id}.inventory_catalog: идентификаторы не совпадают с inventory")
            continue
        for item_id, record in catalog.items():
            if not isinstance(record, dict) or not record.get("name"):
                errors.append(f"{char_id}.inventory_catalog.{item_id}: нет наименования")
                continue
            amount = record.get("quantity")
            if amount is not None and (not isinstance(amount, int) or isinstance(amount, bool) or amount < 0):
                errors.append(f"{char_id}.inventory_catalog.{item_id}: количество должно быть целым >=0 либо неизвестным")
    return errors
