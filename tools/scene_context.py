"""Render a bounded working context. Full state and rules remain available on demand."""
from __future__ import annotations

import json

from campaign_model import current_fact
from knowledgegraph import render_scene_slice, selected_branches


def resource_text(value):
    if isinstance(value, dict) and "current" in value:
        return f"{value['current']}/{value['max']}" + (f"; {value['note']}" if value.get("note") else "")
    if isinstance(value, dict):
        return "; ".join(f"{k}: {resource_text(v)}" for k, v in value.items())
    return str(value)


def render_scene_context(state: dict, rules: dict, mode: str | None = None) -> str:
    scene = state.get("scene_context", {})
    mode = mode or scene.get("mode", "social")
    world = state["world"]
    people = world.get("scene_participants", state["party"]["members"])
    graph = state.get("knowledge_graph", {})
    lines = ["# Контекст текущей сцены", "", f"> state_revision: {state['state_revision']}; mode: {mode}",
             "> Рабочая сводка. Полный отчёт: views/gm-context.md; данные: state/_campaign-state.json.",
             "", "## Точка продолжения", world.get("current_scene", "не установлена"),
             f"Время: {world.get('date_label', '')}; {world.get('time_label', '')}."]
    clock = world.get("timekeeping", {})
    if clock:
        lines.append(f"Игровое время от опоры: {clock.get('elapsed_seconds_from_anchor')} с; полных часов: {clock.get('elapsed_hours_from_anchor')}; полных дней: {clock.get('elapsed_full_days_from_anchor')}.")
    handoff = scene.get("handoff", {})
    lines.append("Намерение игрока: " + (handoff.get("player_intent") or "не зафиксировано; не придумывать"))
    if handoff.get("open_question"):
        lines.append("Незавершённый выбор/реплика: " + handoff["open_question"])
    if handoff.get("last_player_input"):
        lines += ["", "Последний точный ввод игрока:", handoff["last_player_input"]]
    if handoff.get("last_narrative_excerpt"):
        lines += ["", "Последний точный фрагмент повествования:", handoff["last_narrative_excerpt"],
                  "Источник фрагмента: " + handoff["source"]]
    elif handoff.get("source_note"):
        lines.append(handoff["source_note"])

    lines += ["", "## Участники и ограничения"]
    for pid in people:
        char = state.get("characters", {}).get(pid)
        if char is None:
            lines.append("- " + graph.get("principals", {}).get(pid, {}).get("name", pid))
            continue
        lines.append(f"- {char['name']}: {char.get('state', '')}. Цель: {char.get('goal', '')}.")
        if char.get("time_summary"):
            lines.append("  " + char["time_summary"])
        health = char.get("health", {}).get("pregnancy", {})
        if health and health.get("status") not in {"ended", "resolved", "disproven"}:
            lines.append("  Наблюдаемые симптомы: " + "; ".join(health.get("current_symptoms", [])) + ".")
            if health.get("estimate_uncertainty"):
                lines.append("  Неопределённость срока: " + health["estimate_uncertainty"])
            lines.append("  Возможные этапы не означают уже возникшие симптомы, осложнения или штрафы.")
        for anchor in rules.get("character_anchors", {}).get(pid, []):
            lines.append("  Характер: " + anchor)
        if mode == "combat":
            lines.append("  Ресурсы: " + "; ".join(f"{k}={resource_text(v)}" for k, v in char.get("resources", {}).items()))
            lines.append("  Импортированные предметы: " + ", ".join(char.get("inventory", [])))
        else:
            for key in scene.get("resource_keys", {}).get(pid, []):
                lines.append(f"  {key}: {resource_text(char.get('resources', {}).get(key, 'не импортировано'))}")
        coverage = char.get("source_coverage", {})
        if any(v.get("status") != "complete" for v in coverage.values()):
            lines.append("  Карточка/инвентарь перенесены частично: отсутствие записи не равно отсутствию вещи или способности; источник master_sheet.")

    lines += ["", "## Отношения в сцене"]
    relevant_relationships = set(scene.get("relationship_ids", []))
    for rid, rel in state.get("relationships", {}).items():
        if rel.get("status", "active") != "active":
            continue
        if rid not in relevant_relationships and not set(rel.get("participants", [])).issubset(set(people)):
            continue
        lines.append(f"- {rel.get('label', rid)}: {rel.get('formal_status', '')}; {rel.get('emotional_stage', '')}; темп: {rel.get('pace', '')}.")
        if rel.get("gm_summary"):
            lines.append("  " + rel["gm_summary"])
        for pid, feeling in rel.get("directional", {}).items():
            if feeling.get("summary"):
                lines.append(f"  {pid}: {feeling['summary']}")
        if rel.get("boundaries"):
            lines.append("  Границы: " + "; ".join(rel["boundaries"]))

    lines += ["", "## Значимые дела и последствия"]
    for tid in scene.get("thread_ids", []):
        thread = state.get("threads", {}).get(tid, {})
        lines.append(f"- {tid}: {thread.get('title')}; {thread.get('summary')}; статус {thread.get('status')}.")
    for pressure in state.get("world_pressures", {}).values():
        if pressure.get("status") == "active":
            lines.append(f"- {pressure.get('title')}: {pressure.get('condition')}; {pressure.get('consequence_if_ignored')}")
    for belief in state.get("beliefs", {}).values():
        if belief.get("status") == "active" and belief.get("character") in people:
            lines.append(f"- Убеждение (не факт): {belief.get('character')} — {belief.get('proposition')}")
    included = {kid for bid in selected_branches(state, graph) for kid in graph.get("branches", {}).get(bid, {}).get("knowledge_ids", [])} if graph else set()
    for kid in scene.get("fact_ids", []):
        if kid not in included:
            fact = state.get("knowledge", {}).get(kid, {})
            if current_fact(fact):
                lines.append(f"- {kid}: {fact.get('fact')}")
    if graph:
        lines += ["", render_scene_slice(state, graph)]

    lines += ["", "## Правила для этого ответа"]
    policy = rules.get("context_policy", {})
    for ref in policy.get("core_rule_refs", []):
        section, index = ref.split(":")
        lines.append("- " + rules[section]["rules"][int(index)])
    for section in policy.get("mode_sections", {}).get(mode, []):
        block = rules.get(section, {})
        for rule in block.get("rules", block.get("always_on_rules", [])):
            lines.append("- " + rule)
    if mode == "combat":
        if world.get("combat"):
            lines.append("Текущее состояние боя (раунд, очередь, позиции, реакции):")
            lines.append(json.dumps(world["combat"], ensure_ascii=False))
        lines.append("Действующие домашние правила и управление боем:")
        lines.append(json.dumps(state.get("play_rules", {}), ensure_ascii=False))
    if mode == "economy":
        source = next((s for s in rules.get("source_registry", []) if s["key"] == "economy_prompt"), {})
        lines.append(f"Перед расчётом загрузить полный экономический промт из GitHub: {source.get('repository_path', 'rules/economy-full-g1m8.txt')}.")
    lines += ["", "Читать дополнительные разделы правил и карточки, когда они меняют решение/расход/исход. Не считать эту сводку полным инвентарём.",
              "После значимого изменения провести транзакцию; при смене сцены обновить участников, mode, фокус знаний и handoff. Публикация live-файла ещё не означает применённое сохранение."]
    return "\n".join(lines) + "\n"
