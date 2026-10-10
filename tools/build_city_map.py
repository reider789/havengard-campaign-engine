#!/usr/bin/env python3
"""Build a private, standalone city map from authoritative Campaign Engine state.

This produces a browser-readable snapshot inside the private repository.
It deliberately does not expose the full GM state, and it does not require a
personal access token in the browser. Map position edits remain local until a
confirmed transaction imports the exported layout into the campaign state.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Stable, verified map IDs from the original v3 city-map prototype.
# They link only to existing worksite IDs, not to a second staff database.
WORKSITE_MAP_IDS = {
    "garrison": 2, "admin": 1, "research": 28, "school": 3,
    "notary": 31, "market": 8, "clinic": 4, "bath": 13,
    "weave": 37, "potter": 38, "alchemy": 32, "smith": 9,
    "helga": 10, "tarvek": 14, "nira": 15, "leather": 30,
    "kitchen": 5, "bakery": 6, "inn": 7, "wood": 11,
    "sewing": 12, "stone": 16, "stables": 18, "dragons": 17,
    "runes": 33, "elfbows": 34, "range": 35, "fields": 20,
    "herbs": 21, "pastures": 22, "yard": 23, "mill": 24,
    "hives": 25, "forest": 19, "grove": 36, "quarry": 29,
}
HOUSING_IDS = {
    "estate": "Усадьба Яра — основной дом",
    "guardhouse": "Жилой караульный дом усадьбы",
    "harrik-home": "Дом семьи Харрика",
    "family-aster": "Флигель семьи Астэр",
    "research-residence": "Жилое крыло Исследовательского центра",
    "mirelle-home": "Дом Мирэль в Роще Иллариэль",
}


def _decimal(value: object) -> str:
    return str(value).replace(".", ",")


def _gps(cp: int) -> str:
    gp = Decimal(cp) / Decimal(100)
    return f"{gp:,.2f}".replace(",", " ").replace(".", ",")


def make_data(project: Path = ROOT) -> dict:
    state = json.loads((project / "state/_campaign-state.json").read_text(encoding="utf-8"))
    layout = json.loads((project / "map/layout-base.json").read_text(encoding="utf-8"))
    world = state["world"]
    city = world["city"]
    sites = {int(item["id"]): item for item in city["worksites"]}
    houses = {item["name"]: item for item in city["housing"]}
    if len(layout["objects"]) < 101 or len({o["id"] for o in layout["objects"]}) != len(layout["objects"]):
        raise ValueError("Map baseline must retain 101 original v3 objects with unique IDs")
    objects = []
    for shape in layout["objects"]:
        item = dict(shape)
        site_id = WORKSITE_MAP_IDS.get(item["id"])
        if site_id is not None:
            site = sites[site_id]
            item["worksite_id"] = site_id
            item["name"] = site["name"]
            item["assigned"] = int(site.get("resident_workers") or 0)
            item["external_workers"] = int(site.get("external_workers") or 0)
            item["staff_names"] = site.get("staff_names", "")
            item["equipment_status"] = site.get("equipment_status", "")
            item["notes"] = site.get("notes", "")
            m = re.search(r"(?:^|\s)(I{1,3}|IV|V)(?:\s+уровень|\s+ур\.|\s*/)", site.get("status", ""))
            if m:
                item["level"] = m.group(1)
        home_name = HOUSING_IDS.get(item["id"])
        if home_name is not None and home_name in houses:
            item["notes"] = houses[home_name].get("notes", "")
        objects.append(item)
    house = houses["Обычные жилые дома"]
    rein = next(p for p in city["projects"] if p["name"].startswith("Новый дом Мелании"))
    walls = next(p for p in city["projects"] if p["name"] == "Усиление существующей стены I → II")
    garrison = sites[2]
    layout_positions = city.get("layout", {}).get("placements", {})
    authoritative_positions = {}
    for key, rect in layout_positions.items():
        if not isinstance(rect, dict):
            continue
        x, y = rect.get("x_m"), rect.get("y_m")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            authoritative_positions[key] = {"x": x / 10, "y": y / 10}
    active = [r for r in city["residents"] if not any(
        mark in str(r.get("status", "")).lower() for mark in ("погиб", "умер", "выбыл"))]
    if len(active) != world["city_population"]:
        raise ValueError("City population and live resident roster disagree")
    # City facts must reconcile with the current census, not with frozen G1M8 figures.
    from city_registry import validate_city_registry
    problems = validate_city_registry(state)
    if problems:
        raise ValueError("City consistency failed: " + "; ".join(problems))
    target = world["city_food_target_pe"]
    reserve = world["city_food_reserve_pe"]
    if abs((target - reserve) - world["city_food_shortfall_pe"]) > 0.01:
        raise ValueError("Food shortfall does not match authoritative reserve and target")
    cap_match = re.search(r"\d+", house.get("capacity", ""))
    if not cap_match:
        raise ValueError("Ordinary housing comfortable capacity is unknown")
    month_row = next((r for r in city.get("financial_current_sheet", []) if r.get("source_row") == 6), None)
    month = str(month_row["cells"][1]) if month_row else str(world.get("date_label", "Не указан"))
    return {
        "schema": "hayvengard.map.snapshot.v1",
        "revision": state["state_revision"],
        "month": month,
        "source": "state/_campaign-state.json",
        "objects": objects,
        "saved_positions": authoritative_positions,
        "population": world["city_population"],
        "ordinary_occupied": int(house["current_occupants"]),
        "comfortable_capacity": int(cap_match.group(0)),
        "separate_residents": len(active) - int(house["current_occupants"]),
        "treasury_gp": _gps(world["city_treasury_cp"]),
        "food_reserve_pe": _decimal(reserve),
        "food_target_pe": _decimal(target),
        "food_shortfall_pe": _decimal(world["city_food_shortfall_pe"]),
        "worksites_count": len(sites),
        "garrison": int(garrison["resident_workers"]),
        "rein_project": {"status": rein.get("status"), "next_step": rein.get("next_step")},
        "wall_project": {"status": walls.get("status")},
    }


def build(project: Path = ROOT) -> Path:
    data = make_data(project)
    template = (project / "map/template.html").read_text(encoding="utf-8")
    marker = "/*CITY_JSON*/"
    if template.count(marker) != 1:
        raise ValueError("Template must contain one CITY_JSON marker")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    result = template.replace(marker, payload)
    path = project / "map/offline.html"
    path.write_text(result, encoding="utf-8")
    return path


if __name__ == "__main__":
    output = build()
    print(f"Generated {output} from private campaign state")
