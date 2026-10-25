"""Explicit, evidence-based material components from campaign inventory.

A component is eligible only when the canonical inventory confirms its name,
value, quantity and that it is physically accessible for combat. Never infer
the value of a gem, never purchase items automatically.
"""
from __future__ import annotations
import re

def _accessible(item):
    text = str(item.get("status", "")).lower()
    return (type(item.get("quantity")) is int and item["quantity"] > 0 and
            not any(x in text for x in (
                "личный резерв", "в переносной дыре", "не надет",
                "не при себе", "на складе", "передан", "утрачен"
            )))

def component_records(catalog):
    found = {}
    for item_id, item in catalog.items():
        if not isinstance(item, dict) or not _accessible(item):
            continue
        name = str(item.get("name", "")).lower()
        gp = item.get("value_gp")
        if type(gp) is not int or gp <= 0:
            continue
        if re.search(r"\bалмаз\b", name) and gp >= 300:
            found.setdefault("revivify", {"itemId": item_id, "valueGp": gp})
        if "позолоченн" in name and "половник" in name and gp >= 500:
            found.setdefault("tashasBubblingCauldron", {"itemId": item_id, "valueGp": gp})
    return found
