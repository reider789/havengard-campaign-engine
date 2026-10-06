#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sync_time_dependent_state import synchronize  # noqa: E402


STAGES = [
    {"weeks": "1–4", "label": "самое раннее начало", "guide": "обычно внешних изменений нет"},
    {"weeks": "5–12", "label": "I триместр", "guide": "возможны тошнота и утомляемость"},
    {"weeks": "13–17", "label": "начало II триместра", "guide": "живот постепенно становится заметным"},
    {"weeks": "18–22", "label": "II триместр", "guide": "могут начать ощущаться движения ребёнка"},
    {"weeks": "23–27", "label": "поздний II триместр", "guide": "движения становятся отчётливее"},
    {"weeks": "28–34", "label": "III триместр", "guide": "возрастают утомляемость и потребность в отдыхе"},
    {"weeks": "35–36", "label": "поздний III триместр", "guide": "нужен более щадящий темп"},
    {"weeks": "37–40+", "label": "доношенный срок", "guide": "роды могут начаться только как сыгранное событие"},
]


def make_state() -> dict:
    return {
        "state_revision": 15,
        "world": {"timekeeping": {"elapsed_full_days_from_anchor": 0}},
        "characters": {
            "daphne": {
                "state": "в целом стабильна; возможная очень ранняя беременность не подтверждена",
                "health": {
                    "pregnancy": {
                        "status": "suspected",
                        "confirmation": "pending",
                        "days_since_first_signs": 0,
                        "gestational_day_at_confirmation": None,
                        "gestational_day_current": None,
                        "gestational_week_current": None,
                        "trimester_current": None,
                        "stage_current": "подозрение на очень раннюю беременность; срок пока не установлен",
                        "current_symptoms": ["подташнивание", "лёгкая слабость"],
                        "automatic_gameplay_penalties": False,
                        "progression_model": {"name": "human_pregnancy_story_v1", "stages": copy.deepcopy(STAGES)},
                    }
                },
            }
        },
    }


def main() -> None:
    # Before confirmation only the elapsed-since-signs counter moves. No diagnosis,
    # gestational week, symptoms, or penalties may be invented by the synchronizer.
    pending = make_state()
    pending["world"]["timekeeping"]["elapsed_full_days_from_anchor"] = 6
    original_symptoms = copy.deepcopy(pending["characters"]["daphne"]["health"]["pregnancy"]["current_symptoms"])
    assert synchronize(pending) is True
    preg = pending["characters"]["daphne"]["health"]["pregnancy"]
    assert preg["days_since_first_signs"] == 6
    assert preg["confirmation"] == "pending"
    assert preg["gestational_day_current"] is None
    assert preg["gestational_week_current"] is None
    assert preg["current_symptoms"] == original_symptoms
    assert preg["automatic_gameplay_penalties"] is False

    # A played confirmation supplies an estimated gestational age. From then on,
    # only elapsed in-game days advance the derived age/stage.
    confirmed = make_state()
    confirmed["world"]["timekeeping"]["elapsed_full_days_from_anchor"] = 20
    cpreg = confirmed["characters"]["daphne"]["health"]["pregnancy"]
    cpreg["status"] = "confirmed"
    cpreg["confirmation"] = "confirmed"
    cpreg["confirmation_elapsed_day_from_first_signs"] = 3
    cpreg["gestational_day_at_confirmation"] = 39  # 5 нед. 4 д. на момент подтверждения
    assert synchronize(confirmed) is True
    assert cpreg["days_since_first_signs"] == 20
    assert cpreg["gestational_day_current"] == 56
    assert cpreg["gestational_week_current"] == 8
    assert cpreg["gestational_day_remainder"] == 0
    assert cpreg["gestational_age_label"] == "8 нед. 0 д."
    assert cpreg["trimester_current"] == "I"
    assert cpreg["stage_current"] == "I триместр"
    assert cpreg["expected_stage_guide"] == "возможны тошнота и утомляемость"
    assert confirmed["characters"]["daphne"]["time_summary"].startswith("беременность подтверждена; срок 8 нед. 0 д.")
    assert confirmed["characters"]["daphne"]["state"] == make_state()["characters"]["daphne"]["state"]

    # A late-stage pregnancy is still only time-derived: reaching term must not
    # automatically create labor, complications, penalties, or a child event.
    term = make_state()
    term["world"]["timekeeping"]["elapsed_full_days_from_anchor"] = 210
    tpreg = term["characters"]["daphne"]["health"]["pregnancy"]
    tpreg["status"] = "confirmed"
    tpreg["confirmation"] = "confirmed"
    tpreg["confirmation_elapsed_day_from_first_signs"] = 0
    tpreg["gestational_day_at_confirmation"] = 56
    symptoms_before = copy.deepcopy(tpreg["current_symptoms"])
    assert synchronize(term) is True
    assert tpreg["gestational_day_current"] == 266
    assert tpreg["gestational_week_current"] == 38
    assert tpreg["trimester_current"] == "III"
    assert tpreg["stage_current"] == "доношенный срок"
    assert tpreg["current_symptoms"] == symptoms_before
    assert "labor" not in tpreg
    assert "complication" not in tpreg
    assert tpreg["automatic_gameplay_penalties"] is False

    # Running twice at the same game time is idempotent.
    assert synchronize(term) is False

    print("Time-dependent state tests: OK")


if __name__ == "__main__":
    main()
