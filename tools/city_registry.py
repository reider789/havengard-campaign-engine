"""Small, deterministic operations for the G1M8 city registry.

City records live in world.city inside the single Campaign Engine state.
The G1M8 Google Sheet snapshot is an audit archive, not an operational database.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any

RECORD_KEYS = {
    "residents": "name",
    "worksites": "id",
    "housing": "name",
    "inventory": "source_row",
    "animals": "source_row",
    "training": "worker",
    "projects": "source_row",
    "chronicle_people_index": "index",
}


def _city(state: dict[str, Any]) -> dict[str, Any]:
    city = state.get("world", {}).get("city")
    if not isinstance(city, dict) or city.get("schema_version") != 1:
        raise ValueError("Городской реестр ещё не импортирован")
    return city


def _identity(section: str, row: dict[str, Any]) -> str:
    key = RECORD_KEYS[section]
    value = row.get(key)
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        raise ValueError(f"Нет идентификатора {section}.{key}")
    return str(value)


def validate_city_registry(state: dict[str, Any]) -> list[str]:
    world = state.get("world", {})
    city = world.get("city")
    if city is None:
        return []
    errors: list[str] = []
    if not isinstance(city, dict) or city.get("schema_version") != 1:
        return ["world.city: требуется городской реестр schema_version=1"]
    for section, id_field in RECORD_KEYS.items():
        entries = city.get(section)
        if not isinstance(entries, list):
            errors.append(f"city.{section}: требуется список")
            continue
        seen: set[str] = set()
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"city.{section}[{index}]: требуется объект")
                continue
            try:
                key = _identity(section, entry)
                if key in seen:
                    errors.append(f"city.{section}: повтор ключа {id_field}={key}")
                seen.add(key)
            except ValueError as exc:
                errors.append(str(exc))
    treasury = world.get("city_treasury_cp")
    if not isinstance(treasury, int) or isinstance(treasury, bool) or treasury < 0:
        errors.append("world.city_treasury_cp: неотрицательное целое число медных")
    layout = city.get("layout")
    if layout is not None:
        if not isinstance(layout, dict) or not isinstance(layout.get("placements"), dict):
            errors.append("city.layout.placements: требуется объект")
        else:
            for obj_id, position in layout["placements"].items():
                if not isinstance(obj_id, str) or not obj_id.strip() or not isinstance(position, dict):
                    errors.append("city.layout: некорректный идентификатор/положение")
                    continue
                for field in ("x_m", "y_m", "width_m", "height_m"):
                    val = position.get(field)
                    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                        errors.append(f"city.layout.{obj_id}.{field}: требуется конечное число")
                    elif field in ("width_m", "height_m") and val <= 0:
                        errors.append(f"city.layout.{obj_id}.{field}: размер должен быть положительным")
    if city.get("reconciliation", {}).get("status") == "census_housing_staff_verified":
        # Cross-check independent ledgers. Archived casualties still exist as records.
        active = [r for r in city["residents"] if not any(
            marker in str(r.get("status", "")).lower() for marker in ("погиб", "умер", "выбыл"))]
        if len(active) != world.get("city_population"):
            errors.append(f"city.population: действующих записей {len(active)} != world.city_population {world.get('city_population')}")
        by_site: dict[str, int] = {}
        for resident in active:
            age = resident.get("age")
            adult = (isinstance(age, str) and age.isdigit() and int(age) >= 14) or resident.get("age_group") == "взрослый"
            if adult and resident.get("worksite") not in {None, "", "—"}:
                name = resident["worksite"]
                by_site[name] = by_site.get(name, 0) + 1
        for site in city.get("worksites", []):
            try:
                expected = int(site.get("resident_workers", 0))
            except (ValueError, TypeError):
                errors.append(f"city.worksites.{site.get('id')}: некорректная численность")
                continue
            actual = by_site.pop(site.get("name"), 0)
            if actual != expected:
                errors.append(f"city.worksites.{site.get('id')}: по реестру {actual}, штатная строка {expected}")
        if by_site:
            errors.append(f"city.residents: рабочие точки без реестра {by_site}")
        homes = {home.get("name"): home for home in city.get("housing", [])}
        ordinary = homes.get("Обычные жилые дома", {})
        occupied = None
        if ordinary:
            try:
                occupied = int(ordinary["current_occupants"])
                capacity = [int(n) for n in re.findall(r"\d+", ordinary["capacity"])]
                free = [int(n) for n in re.findall(r"\d+", ordinary["available"])]
                if len(capacity) < 2 or free[:2] != [capacity[0] - occupied, capacity[1] - occupied]:
                    errors.append("city.housing: резерв не соответствует вместимости и заселению")
            except (ValueError, KeyError, TypeError):
                errors.append("city.housing: неизвестная вместимость типовых домов")
        known_separate = 0
        for name, house in homes.items():
            if name == "Обычные жилые дома":
                continue
            included = str(house.get("counted_in_population", "")).strip()
            occupants = str(house.get("current_occupants", "")).strip()
            if not included:
                # A construction project has no residents yet. Once it is
                # occupied, its city-population membership must be explicit.
                if occupants not in {"Не заселён", "Не заселен", "0"}:
                    errors.append(f"city.housing.{name}: не задан учёт жителей")
                continue
            if included.startswith("Нет"):
                continue
            if included.startswith("Частично"):
                counted = re.search(r"(\d+)\s+из\s+(\d+)", included)
                if not counted or int(counted.group(2)) != int(occupants):
                    errors.append(f"city.housing.{name}: не совпадает состав жильцов")
                    continue
                known_separate += int(counted.group(1))
            elif included == "Да":
                try:
                    known_separate += int(occupants)
                except ValueError:
                    errors.append(f"city.housing.{name}: требуется число жильцов")
            else:
                errors.append(f"city.housing.{name}: неизвестный способ подсчёта жильцов")
        if ordinary and occupied is not None and occupied + known_separate != len(active):
            errors.append(f"city.housing: {occupied} + {known_separate} != {len(active)} жителей")
        for animal in city.get("animals", []):
            if animal.get("category") == "Показатель" or animal.get("name_or_group") in {"28", "20", "6", "12", "0", "8"}:
                errors.append("city.animals: строка итоговой таблицы попала в реестр животных")
    return errors


def apply_city_operation(state: dict[str, Any], operation: dict[str, Any]) -> None:
    city = _city(state)
    op = operation.get("type")
    if op == "city_patch_record":
        section = operation.get("section")
        if section not in RECORD_KEYS:
            raise ValueError("Неизвестный реестр города")
        key = str(operation.get("record_id", ""))
        if not key:
            raise ValueError("Не указан record_id")
        patch = operation.get("patch")
        if not isinstance(patch, dict) or not patch:
            raise ValueError("Указать непустой patch")
        identity_field = RECORD_KEYS[section]
        if identity_field in patch or "source_row" in patch:
            raise ValueError("Идентификатор/источник нельзя изменять через patch")
        found = [entry for entry in city[section] if _identity(section, entry) == key]
        if len(found) != 1:
            raise ValueError(f"Запись {section}:{key} не найдена либо не уникальна")
        found[0].update(copy.deepcopy(patch))
    elif op == "city_map_place":
        obj_id = operation.get("object_id")
        if not isinstance(obj_id, str) or not obj_id.strip() or len(obj_id) > 160:
            raise ValueError("Не указан допустимый object_id")
        rect = {k: operation.get(k) for k in ("x_m", "y_m", "width_m", "height_m")}
        for k, v in rect.items():
            if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v):
                raise ValueError(f"{k}: требуется конечное число метров")
            if k in ("width_m", "height_m") and v <= 0:
                raise ValueError(f"{k}: размер должен быть положительным")
        layout = city.setdefault("layout", {"units": "meters", "grid_primary_m": 10,
                                             "grid_edit_m": 5, "placements": {}})
        layout["placements"][obj_id] = copy.deepcopy(rect)
    elif op == "city_map_unplace":
        obj_id = operation.get("object_id")
        layout = city.get("layout", {})
        if obj_id not in layout.get("placements", {}):
            raise ValueError("Нет размещения с таким object_id")
        del layout["placements"][obj_id]
    elif op == "city_adjust_treasury":
        delta = operation.get("delta_cp")
        if not isinstance(delta, int) or isinstance(delta, bool):
            raise ValueError("delta_cp должно быть целым числом медных")
        new_value = state["world"]["city_treasury_cp"] + delta
        if new_value < 0:
            raise ValueError("Недостаточно средств в городской казне")
        state["world"]["city_treasury_cp"] = new_value
    else:
        raise ValueError(f"Неизвестная городская операция: {op}")
