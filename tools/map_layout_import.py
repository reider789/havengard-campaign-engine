#!/usr/bin/env python3
"""Preview a v3/v4 browser map export as a normal Campaign Engine transaction.

Nothing is committed by this program. It prints a JSON transaction that can
be reviewed and queued through transactions/live/ by a connected ChatGPT or
an authorized local operator. Never put a personal access token in HTML.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def make_layout_transaction(payload: dict, state: dict, baseline: dict) -> dict:
    if payload.get("app") != "heyvengard-map-layout" or payload.get("version") != 3:
        raise ValueError("Expected heyvengard-map-layout JSON version 3")
    declared_revision = payload.get("state_revision")
    if declared_revision is not None and (
        not isinstance(declared_revision, int) or declared_revision > state["state_revision"]
    ):
        raise ValueError("Map file has unknown or future source revision")
    changes = payload.get("positions")
    if not isinstance(changes, dict):
        raise ValueError("Map export must contain positions object")
    ids = {o["id"]: o for o in baseline["objects"]}
    if len(ids) != len(baseline["objects"]):
        raise ValueError("Duplicate base map object IDs")
    updates = []
    def add(item_id: str, value: dict, footprint: dict) -> None:
        if not isinstance(value, dict):
            raise ValueError("Invalid object position")
        x, y = value.get("x"), value.get("y")
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError(f"{item_id}: x and y must be numeric")
        w, h = footprint["w"], footprint["h"]
        if not (0 <= x <= 164 - w and 0 <= y <= 116 - h):
            raise ValueError(f"{item_id}: object is outside the schematic")
        if any(round(v * 2) != v * 2 for v in (x, y)):
            raise ValueError("Coordinates must snap to half-cell grid")
        coords = {"x_m": int(x * 10), "y_m": int(y * 10),
                  "width_m": int(w * 10), "height_m": int(h * 10)}
        live = state["world"]["city"].get("layout", {}).get("placements", {}).get(item_id)
        if live != coords:
            updates.append({"type": "city_map_place", "object_id": item_id, **coords})
    for item_id, rect in sorted(changes.items()):
        if item_id not in ids:
            raise ValueError(f"Unknown map object ID {item_id}; cannot write unsourced objects")
        add(item_id, rect, ids[item_id])
    rein = (payload.get("extra") or {}).get("reyn")
    if rein is not None:
        add("reyn-home", rein, {"w": 3, "h": 2})
    if not updates:
        raise ValueError("Nothing to change on the authoritative GitHub map")
    compact = json.dumps(updates, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(compact.encode("utf-8")).hexdigest()[:20]
    return {
        "expected_state_revision": state["state_revision"],
        "unique_key": "map-layout:" + digest,
        "event": {
            "id": "MAP-LAYOUT-" + digest.upper(),
            "summary": "Подтверждённые игроком изменения расположения объектов на условной карте. Постройки, жители, экономика и время игры не меняются.",
            "visibility": "gm"
        },
        "operations": updates
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create reviewable map position transaction")
    parser.add_argument("export", type=Path, help="JSON exported from the map UI")
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, help="Optional reviewed transaction output")
    args = parser.parse_args()
    payload = json.loads(args.export.read_text(encoding="utf-8"))
    state = json.loads((args.project / "state/_campaign-state.json").read_text(encoding="utf-8"))
    base = json.loads((args.project / "map/layout-base.json").read_text(encoding="utf-8"))
    tx = make_layout_transaction(payload, state, base)
    data = json.dumps(tx, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
