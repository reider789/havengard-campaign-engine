#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "road-bridge-baseline.json"


def run_engine(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["python", str(project / "tools" / "campaignctl.py"), "--project", str(project), *args], capture_output=True, text=True)


def read_state(project: Path) -> dict:
    return json.loads((project / "state" / "_campaign-state.json").read_text(encoding="utf-8"))


def commit_tx(project: Path, name: str, tx: dict) -> subprocess.CompletedProcess[str]:
    path = project / "transactions" / f"test-rel-{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tx, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_engine(project, "commit", "--transaction", str(path))


def assert_ok(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def main() -> None:
    rules = json.loads((ROOT / "rules" / "_campaign-rules.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "rules" / "_prompt-audit.json").read_text(encoding="utf-8"))
    universal = next(s for s in audit["sources"] if s["key"] == "universal_master_prompt")
    assert universal["coverage"] == "53/53 numbered sections"
    assert rules["social_and_relationships"]["relationship_state_policy"]["never_numeric_affection"] is True
    assert any(s["key"] == "economy_prompt" for s in rules["source_registry"])
    assert any(s["key"] == "relationship_baseline_g1m5" for s in rules["source_registry"])

    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "campaign"
        shutil.copytree(ROOT, project)
        (project / "state" / "_campaign-state.json").write_bytes(FIXTURE.read_bytes())
        state = read_state(project)

        rel_yar_daphne = {
            "label": "Яр ↔ Дафна", "participants": ["yar", "daphne"], "kind": "romantic",
            "formal_status": "помолвлены; свадьба ещё не сыграна",
            "emotional_stage": "очень близкая устойчивая пара; эмоционально и бытово почти как молодожёны",
            "player_summary": "Очень близкая и тёплая пара; помолвлены и строят совместную жизнь.",
            "gm_summary": "Дафна заметно привязана и тепла к Яру, но способна резко возражать его безрассудству.",
            "directional": {
                "yar": {"trust": "очень высокое", "attachment": "очень сильная", "summary": "глубоко доверяет Дафне, любит её и видит с ней будущую семью"},
                "daphne": {"trust": "очень высокое", "attachment": "очень сильная и заметная", "summary": "очень тепло и привязанно относится к Яру; хочет делить с ним риск, а не смотреть, как он принимает всё на себя"}
            },
            "trajectory": "устойчивая положительная", "pace": "сложившаяся близкая пара",
            "dynamics": ["тёплая бытовая близость", "шутки", "забота", "споры о безрассудстве Яра"],
            "boundaries": ["беременность не установлена", "свадьба ещё не сыграна"],
            "evidence": [], "visibility": "party", "status": "active"
        }
        rel_lut_rada = {
            "label": "Лютобор ↔ Рада", "participants": ["lyutobor", "rada"], "kind": "romantic_emerging",
            "formal_status": "официально не пара",
            "emotional_stage": "чуть больше чем друзья; взаимная романтическая симпатия заметна и частично проговорена",
            "player_summary": "Между ними уже больше, чем дружба, но оба стесняются и развивают отношения медленно.",
            "directional": {
                "lyutobor": {"trust": "очень высокое", "romance": "явная симпатия", "openness": "осторожная", "summary": "думает о Раде романтически, но стесняется и редко делает прямой шаг"},
                "rada": {"trust": "очень высокое", "romance": "явная симпатия", "openness": "осторожная", "summary": "серьёзно воспринимает их близость; чаще допускает небольшую физическую близость и поддразнивание"}
            },
            "trajectory": "медленное положительное сближение", "pace": "медленный и стеснительный",
            "dynamics": ["сидят рядом", "поддразнивают друг друга", "маленькие проявления телесной близости"],
            "boundaries": ["не форсировать поцелуй", "не объявлять парой без сыгранного шага", "не форсировать признание или свадьбу"],
            "evidence": [], "visibility": "party", "status": "active"
        }
        hidden = {
            "label": "Яр ↔ Вера Ренк", "participants": ["yar", "npc:vera_renk"],
            "participant_names": {"npc:vera_renk": "Вера Ренк"}, "kind": "professional",
            "formal_status": "союзники по отдельным делам", "emotional_stage": "взаимное профессиональное уважение",
            "player_summary": "Уважительные рабочие отношения.", "gm_summary": "GM-only тест видимости.",
            "trajectory": "стабильная", "pace": "по событиям", "directional": {}, "dynamics": [], "boundaries": [],
            "evidence": [], "visibility": "gm", "status": "active"
        }
        tx = {"expected_state_revision": state["state_revision"], "event": {"id": "TEST-REL-SEED", "summary": "Симуляция: создан качественный граф отношений."}, "operations": [
            {"type": "upsert_relationship", "id": "REL-YAR-DAPHNE", "value": rel_yar_daphne},
            {"type": "upsert_relationship", "id": "REL-LYUTOBOR-RADA", "value": rel_lut_rada},
            {"type": "upsert_relationship", "id": "REL-YAR-VERA", "value": hidden}
        ]}
        assert_ok(commit_tx(project, "seed", tx))
        state = read_state(project)
        assert state["relationships"]["REL-YAR-DAPHNE"]["formal_status"].startswith("помолвлены")
        assert state["relationships"]["REL-LYUTOBOR-RADA"]["pace"] == "медленный и стеснительный"

        state = read_state(project)
        tx2 = {"expected_state_revision": state["state_revision"], "event": {"id": "TEST-REL-EVIDENCE", "summary": "Симуляция: сыгранное событие добавлено в историю отношений."}, "operations": [
            {"type": "append_relationship_event", "id": "REL-LYUTOBOR-RADA", "event": {"event_id": "SIM-001", "summary": "Рада сознательно осталась рядом с Лютобором после трудной сцены."}}
        ]}
        assert_ok(commit_tx(project, "evidence", tx2))
        assert read_state(project)["relationships"]["REL-LYUTOBOR-RADA"]["evidence"][-1]["event_id"] == "SIM-001"

        assert_ok(run_engine(project, "render"))
        gm = (project / "views" / "gm-context.md").read_text(encoding="utf-8")
        player = (project / "views" / "player-context.md").read_text(encoding="utf-8")
        assert "## Текущие отношения" in gm
        assert "эмоционально и бытово почти как молодожёны" in gm
        assert "медленный и стеснительный" in gm
        assert "Вера Ренк" in gm
        assert "## Отношения" in player
        assert "Между ними уже больше, чем дружба" in player
        assert "Вера Ренк" not in player
        assert "GM-only тест видимости" not in player

        before_bad = read_state(project)
        bad = {"expected_state_revision": before_bad["state_revision"], "event": {"id": "TEST-REL-NUMERIC-BAD", "summary": "Числовая шкала отношений должна быть отклонена."}, "operations": [
            {"type": "upsert_relationship", "id": "REL-BAD", "value": {"participants": ["yar", "daphne"], "formal_status": "test", "emotional_stage": "test", "directional": {"yar": {"trust": 87}}, "status": "active", "visibility": "party"}}
        ]}
        failed = commit_tx(project, "numeric-bad", bad)
        assert failed.returncode != 0, failed.stdout + failed.stderr
        assert read_state(project) == before_bad

    print("Relationship and rule-pack tests: OK")


if __name__ == "__main__":
    main()
