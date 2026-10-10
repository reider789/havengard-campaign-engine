#!/usr/bin/env python3
"""Build a non-canonical combat UI manifest from *current* Campaign Engine data.

Runs under GitHub Actions when state or character-source files change. Requires
only Python stdlib; does not embed API tokens or write canonical game files.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

CHARACTERS = ("yar", "daphne", "lyutobor", "rada")
ALIASES = {
    "healing": "healing", "greater_healing": "greater", "antitoxin": "antitoxin",
    "alchemist_fire": "fire", "acid": "acid", "smoke_bomb": "smoke",
    "potion_speed": "speed", "potion_climbing": "climb",
    "hill_giant_strength": "giant", "potion_fire_resistance": "fireRes",
    "potion_growth": "growth", "potion_heroism": "heroism",
    "fast_predator_poison": "poison", "flare": "flare", "trap": "trap",
}
SPECIAL = re.compile("зель|бомб|кислот|яд |яда|настой|реактив|эликсир|ракета|ловушка|противояд", re.I)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build(root: Path) -> dict:
    state = load(root / "state/_campaign-state.json")
    ref = load(root / "prototypes/combat/character-capability-registry-g1m8-v1.json")
    inv = load(root / "prototypes/combat/inventory-interactions-g1m8-v1.json")
    manifest = {
        "schema_version": 1,
        "source_state_revision": state["state_revision"],
        "source": "campaign-engine-current-state",
        "is_canonical": False,
        "about": "Generated source data for tactical UI; changing the UI does not update canonical state.",
        "characters": {},
    }
    for hero in CHARACTERS:
        character = state["characters"][hero]
        sheet = character["character_sheet"]
        cached = ref["characters"][hero]
        old_inv = inv.get("source_inventory_keys", {}).get(hero, {})
        by_key = {value["key"]: ALIASES.get(kind, kind) for kind, value in old_inv.items()}
        # Use *current* inventory quantities, not the initial historical count.
        items, counts = [], {}
        for catalog_key, item in (character.get("inventory_catalog") or {}).items():
            name = str(item.get("name") or catalog_key)
            category = by_key.get(catalog_key)
            quantity = item.get("quantity")
            if category and isinstance(quantity, (int, float)) and quantity > 0:
                counts[category] = counts.get(category, 0) + int(quantity)
            items.append({
                "id": catalog_key,
                "name": name,
                "quantity": quantity,
                "status": item.get("status"),
                "description": item.get("description"),
                "consumable_type": category,
                "requires_manual_rule": category is None and bool(SPECIAL.search(name)),
            })
        sections = []
        for group in ("attacks", "class_species_feats", "spell_reference"):
            for row in cached.get(group, []):
                columns = row.get("columns", [])
                title = str(columns[0]) if columns and columns[0] else ""
                if not title or title in {"Способность", "Атака", "Действие", "Заклинание"}:
                    continue
                sections.append({
                    "id": f"{hero}-{row.get('category',group)}-{row.get('source_row')}",
                    "name": title,
                    "category": row.get("category", group),
                    "source_row": row.get("source_row"),
                    "description": " · ".join(str(c) for c in columns[1:] if c is not None and c != "")[:900],
                    "execution_status": "reference_only_unless_combat_handler_verified",
                })
        # Current character_sheet combat_reference overrides stale snapshot details.
        authoritative = []
        for row in sheet.get("combat_reference", []):
            columns = row.get("cells") or []
            if columns and isinstance(columns[0], str) and columns[0] not in {"Действие", "Атака", "Способность", "Заклинание"}:
                authoritative.append({"source_row": row.get("source_row"), "columns": columns[:8]})
        manifest["characters"][hero] = {
            "name": character.get("name", hero),
            "class_and_level": sheet.get("class_and_level"),
            "ac_description": sheet.get("armor_class"),
            "speed": sheet.get("speed"),
            "resources": character.get("resources", {}),
            "consumables": counts,
            "inventory": items,
            "skills_attacks_spells": sections,
            "current_combat_reference": authoritative,
        }
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    data = build(args.root.resolve())
    out = args.root / "prototypes/combat/app/runtime/latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Combat manifest updated: state revision {data['source_state_revision']}, {len(data['characters'])} heroes, {out}")


if __name__ == "__main__":
    main()