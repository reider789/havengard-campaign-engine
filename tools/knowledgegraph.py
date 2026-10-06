#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

GRAPH_RELATIVE_PATH = Path("state") / "_knowledge-graph.json"
STATE_RELATIVE_PATH = Path("state") / "_campaign-state.json"
VIEW_RELATIVE_PATH = Path("views") / "scene-knowledge.md"
GRAPH_SCHEMA_VERSION = 1
AWARENESS_STATES = {"knows", "heard_of", "suspects", "believes", "misinformed", "unknown"}
BRANCH_STATUSES = {"active", "dormant", "resolved", "historical"}


class KnowledgeGraphError(Exception):
    pass


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise KnowledgeGraphError(f"Файл не найден: {path}")
    except json.JSONDecodeError as exc:
        raise KnowledgeGraphError(f"Некорректный JSON в {path}: {exc}")


def principal_known(pid: str, state: dict[str, Any], graph: dict[str, Any]) -> bool:
    return (
        pid in state.get("characters", {})
        or pid in graph.get("principals", {})
        or state.get("schema_version", 1) == 1 and (pid.startswith("npc:") or pid.startswith("group:"))
    )


def principal_name(pid: str, state: dict[str, Any], graph: dict[str, Any]) -> str:
    if pid in state.get("characters", {}):
        return state["characters"][pid].get("name", pid)
    principal = graph.get("principals", {}).get(pid, {})
    if principal.get("name"):
        return principal["name"]
    if ":" in pid:
        return pid.split(":", 1)[1]
    return pid


def validate_graph(state: dict[str, Any], graph: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if graph.get("schema_version") != GRAPH_SCHEMA_VERSION:
        errors.append(f"knowledge_graph.schema_version должен быть {GRAPH_SCHEMA_VERSION}")
    if graph.get("campaign_id") != state.get("campaign", {}).get("id"):
        errors.append("knowledge_graph относится к другой кампании")
    if not isinstance(graph.get("graph_revision"), int) or graph.get("graph_revision", -1) < 0:
        errors.append("knowledge_graph.graph_revision должен быть неотрицательным целым")

    knowledge = state.get("knowledge", {})
    branches = graph.get("branches", {})
    if not isinstance(branches, dict):
        errors.append("knowledge_graph.branches должен быть объектом")
        branches = {}
    for bid, branch in branches.items():
        if not isinstance(branch, dict):
            errors.append(f"{bid} должен быть объектом")
            continue
        if branch.get("status") not in BRANCH_STATUSES:
            errors.append(f"{bid}.status имеет недопустимое значение")
        kids = branch.get("knowledge_ids", [])
        if not isinstance(kids, list):
            errors.append(f"{bid}.knowledge_ids должен быть списком")
            continue
        if len(kids) != len(set(kids)):
            errors.append(f"{bid}.knowledge_ids содержит дубликаты")
        for kid in kids:
            if kid not in knowledge:
                errors.append(f"{bid} ссылается на неизвестный факт {kid}")
        linked_thread = branch.get("linked_thread_id")
        if linked_thread and linked_thread not in state.get("threads", {}):
            errors.append(f"{bid}.linked_thread_id ссылается на неизвестную линию {linked_thread}")
        for pid in branch.get("key_principals", []):
            if not principal_known(pid, state, graph):
                errors.append(f"{bid}.key_principals содержит неизвестного участника {pid}")

    awareness = graph.get("awareness", {})
    if not isinstance(awareness, dict):
        errors.append("knowledge_graph.awareness должен быть объектом")
        awareness = {}
    for kid, people in awareness.items():
        if kid not in knowledge:
            errors.append(f"awareness ссылается на неизвестный факт {kid}")
            continue
        if not isinstance(people, dict):
            errors.append(f"awareness.{kid} должен быть объектом")
            continue
        for pid, record in people.items():
            if not principal_known(pid, state, graph):
                errors.append(f"awareness.{kid} содержит неизвестного участника {pid}")
            if not isinstance(record, dict):
                errors.append(f"awareness.{kid}.{pid} должен быть объектом")
                continue
            if record.get("state") not in AWARENESS_STATES:
                errors.append(f"awareness.{kid}.{pid}.state имеет недопустимое значение")
            if knowledge[kid].get("status") == "candidate" and record.get("state") != "unknown":
                errors.append(f"awareness.{kid}: candidate не является знанием персонажа")
            if record.get("state") != "unknown" and not record.get("source"):
                errors.append(f"awareness.{kid}.{pid} должен содержать source")
            if record.get("state") == "misinformed" and not record.get("version"):
                errors.append(f"awareness.{kid}.{pid} для misinformed должен содержать version")

    focus = state.get("world", {}).get("scene_knowledge_branches", [])
    for pid in state.get("world", {}).get("scene_participants", []):
        if not principal_known(pid, state, graph):
            errors.append(f"scene_participants: незарегистрированный участник {pid}")
    if focus is not None and not isinstance(focus, list):
        errors.append("world.scene_knowledge_branches должен быть списком")
    elif isinstance(focus, list):
        for bid in focus:
            if bid not in branches:
                errors.append(f"world.scene_knowledge_branches содержит неизвестную ветку {bid}")
    return errors


def effective_awareness(kid: str, pid: str, state: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any] | None:
    explicit = graph.get("awareness", {}).get(kid, {}).get(pid)
    if explicit is not None:
        return explicit
    fact = state.get("knowledge", {}).get(kid, {})
    if pid in fact.get("known_by", []):
        return {"state": "knows", "source": fact.get("source_event", "legacy known_by")}
    return None


def selected_branches(state: dict[str, Any], graph: dict[str, Any]) -> list[str]:
    focus = state.get("world", {}).get("scene_knowledge_branches")
    if isinstance(focus, list):
        return [bid for bid in focus if bid in graph.get("branches", {})]

    scene_people = set(state.get("world", {}).get("scene_participants", []))
    out: list[str] = []
    for bid, branch in graph.get("branches", {}).items():
        if branch.get("status") != "active":
            continue
        if scene_people.intersection(branch.get("key_principals", [])):
            out.append(bid)
    return out


def render_scene_slice(state: dict[str, Any], graph: dict[str, Any]) -> str:
    errors = validate_graph(state, graph)
    if errors:
        raise KnowledgeGraphError("Некорректный knowledge graph:\n" + "\n".join(errors))

    branch_ids = selected_branches(state, graph)
    scene_people = state.get("world", {}).get("scene_participants", [])
    lines = [
        "# Scene Knowledge",
        "",
        f"> state_revision: {state.get('state_revision')}",
        f"> graph_revision: {graph.get('graph_revision')}",
        "> Этот файл отвечает на вопрос: кто из участников текущей сцены что знает по релевантным сюжетным веткам.",
        "",
        "## Фокус сцены",
    ]
    if branch_ids:
        for bid in branch_ids:
            branch = graph["branches"][bid]
            lines.append(f"- {bid} — {branch.get('title', bid)} ({branch.get('status')})")
    else:
        lines.append("- Явно релевантных веток не выбрано.")

    lines += ["", "## Факты выбранных веток"]
    fact_ids = list(dict.fromkeys(kid for bid in branch_ids for kid in graph["branches"][bid].get("knowledge_ids", [])))
    for kid in fact_ids:
        fact = state["knowledge"][kid]
        if fact.get("status") == "candidate":
            continue
        label = "ОПРОВЕРГНУТО" if fact.get("status") == "disproven" else "исторический" if fact.get("temporal_status") == "historical" else "текущий"
        lines.append(f"- {kid} [{label}]: {fact.get('fact')}")
    lines += ["", "## Знания участников сцены", "Отсутствие записи означает отсутствие зафиксированного источника; не приписывать знание автоматически."]
    any_person = False
    for pid in scene_people:
        person_lines: list[str] = []
        for bid in branch_ids:
            branch = graph["branches"][bid]
            for kid in branch.get("knowledge_ids", []):
                record = effective_awareness(kid, pid, state, graph)
                if not record or record.get("state") == "unknown":
                    continue
                fact = state["knowledge"][kid]
                if fact.get("status") == "candidate":
                    continue
                if fact.get("status") == "disproven" and record.get("state") != "misinformed":
                    continue
                status = record.get("state")
                extra = ""
                if status == "misinformed":
                    extra = f"; версия персонажа: {record.get('version')}"
                elif record.get("note"):
                    extra = f"; {record.get('note')}"
                person_lines.append(
                    f"  - {kid}: {status} "
                    f"(источник знания: {record.get('source')}{extra})"
                )
        any_person = True
        lines.append(f"- **{principal_name(pid, state, graph)}**")
        lines.extend(person_lines or ["  - Источники знаний по этим фактам не зафиксированы."])
    if not any_person:
        lines.append("- Для участников сцены нет явно зафиксированных знаний по выбранным веткам.")

    lines += ["", "## Вне сцены: ключевые контакты веток"]
    seen: set[str] = set(scene_people)
    any_contact = False
    for bid in branch_ids:
        branch = graph["branches"][bid]
        for pid in branch.get("key_principals", []):
            if pid in seen:
                continue
            relevant: list[str] = []
            for kid in branch.get("knowledge_ids", []):
                record = effective_awareness(kid, pid, state, graph)
                fact = state["knowledge"][kid]
                if record and record.get("state") != "unknown" and fact.get("status") != "candidate" and (fact.get("status") != "disproven" or record.get("state") == "misinformed"):
                    relevant.append(f"{kid}:{record.get('state')}")
            if relevant:
                any_contact = True
                seen.add(pid)
                lines.append(f"- {principal_name(pid, state, graph)} — {', '.join(relevant)}")
    if not any_contact:
        lines.append("- Нет.")
    return "\n".join(lines) + "\n"


def load(project: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    state = read_json(project / STATE_RELATIVE_PATH)
    graph = state.get("knowledge_graph") if state.get("schema_version") == 2 else read_json(project / GRAPH_RELATIVE_PATH)
    return state, graph


def cmd_check(project: Path) -> None:
    state, graph = load(project)
    errors = validate_graph(state, graph)
    if errors:
        raise KnowledgeGraphError("\n".join(errors))
    print(json.dumps({"status": "ok", "state_revision": state["state_revision"], "graph_revision": graph["graph_revision"]}, ensure_ascii=False))


def cmd_render(project: Path) -> None:
    state, graph = load(project)
    text = render_scene_slice(state, graph)
    path = project / VIEW_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(json.dumps({"status": "rendered", "path": str(VIEW_RELATIVE_PATH), "graph_revision": graph["graph_revision"]}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Campaign Engine NPC/thread knowledge graph")
    parser.add_argument("--project", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("render")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    try:
        if args.command == "check":
            cmd_check(project)
        elif args.command == "render":
            cmd_render(project)
        return 0
    except KnowledgeGraphError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
