#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any


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


def _require_nonnegative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} должен быть неотрицательным целым")
    return value


def _stage_index_for_week(week: int) -> int:
    if week <= 4:
        return 0
    if week <= 12:
        return 1
    if week <= 17:
        return 2
    if week <= 22:
        return 3
    if week <= 27:
        return 4
    if week <= 34:
        return 5
    if week <= 36:
        return 6
    return 7


def synchronize(state: dict[str, Any]) -> bool:
    """Synchronize derived time-dependent fields without inventing story events.

    This function never confirms a pregnancy, changes symptoms, creates complications,
    starts labor, or applies gameplay penalties. It only derives counters/stages from
    already-canonical time and an already-played confirmation when one exists.
    """
    world = state.get("world", {})
    timekeeping = world.get("timekeeping")
    if not isinstance(timekeeping, dict):
        return False

    daphne = state.get("characters", {}).get("daphne")
    if not isinstance(daphne, dict):
        return False
    health = daphne.get("health")
    if not isinstance(health, dict):
        return False
    pregnancy = health.get("pregnancy")
    if not isinstance(pregnancy, dict):
        return False

    elapsed_days = _require_nonnegative_int(
        timekeeping.get("elapsed_full_days_from_anchor", 0),
        "world.timekeeping.elapsed_full_days_from_anchor",
    )

    changed = False

    if pregnancy.get("days_since_first_signs") != elapsed_days:
        pregnancy["days_since_first_signs"] = elapsed_days
        changed = True

    confirmation = pregnancy.get("confirmation", "pending")
    if confirmation != "confirmed":
        # Suspicion is not a diagnosis. Do not derive a gestational age until a
        # played confirmation supplies an estimated age at that moment.
        expected_stage = "подозрение на очень раннюю беременность; срок пока не установлен"
        if pregnancy.get("stage_current") != expected_stage:
            pregnancy["stage_current"] = expected_stage
            changed = True
        return changed

    confirmation_elapsed = _require_nonnegative_int(
        pregnancy.get("confirmation_elapsed_day_from_first_signs"),
        "characters.daphne.health.pregnancy.confirmation_elapsed_day_from_first_signs",
    )
    gestational_day_at_confirmation = _require_nonnegative_int(
        pregnancy.get("gestational_day_at_confirmation"),
        "characters.daphne.health.pregnancy.gestational_day_at_confirmation",
    )
    if elapsed_days < confirmation_elapsed:
        raise ValueError("Текущее игровое время не может быть раньше сыгранного подтверждения беременности")

    gestational_day = gestational_day_at_confirmation + (elapsed_days - confirmation_elapsed)
    gestational_week = gestational_day // 7
    day_remainder = gestational_day % 7

    if gestational_week <= 12:
        trimester = "I"
    elif gestational_week <= 27:
        trimester = "II"
    else:
        trimester = "III"

    stages = pregnancy.get("progression_model", {}).get("stages", [])
    stage_index = _stage_index_for_week(gestational_week)
    if isinstance(stages, list) and len(stages) > stage_index and isinstance(stages[stage_index], dict):
        stage = stages[stage_index]
        stage_label = stage.get("label") or f"{gestational_week}-я неделя"
        stage_guide = stage.get("guide")
    else:
        stage_label = f"{gestational_week}-я неделя"
        stage_guide = None

    derived = {
        "gestational_age_status": "estimated_confirmed",
        "gestational_day_current": gestational_day,
        "gestational_week_current": gestational_week,
        "gestational_day_remainder": day_remainder,
        "trimester_current": trimester,
        "stage_current": stage_label,
        "gestational_age_label": f"{gestational_week} нед. {day_remainder} д.",
    }
    if stage_guide is not None:
        derived["expected_stage_guide"] = stage_guide

    for key, value in derived.items():
        if pregnancy.get(key) != value:
            pregnancy[key] = value
            changed = True

    state_label = f"беременность подтверждена; срок {gestational_week} нед. {day_remainder} д.; стадия — {stage_label}"
    if daphne.get("state") != state_label:
        daphne["state"] = state_label
        changed = True

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize derived time-dependent campaign state")
    parser.add_argument("--project", default=".")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    state_path = project / "state" / "_campaign-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    changed = synchronize(state)
    if changed:
        atomic_write_json(state_path, state)
    print(json.dumps({"status": "updated" if changed else "unchanged", "state_revision": state.get("state_revision")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
