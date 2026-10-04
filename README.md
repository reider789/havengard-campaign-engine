# Campaign Engine MVP

Минимальный прототип ядра состояния для D&D-кампании «Яр воин».

## Что уже умеет

- один структурированный источник текущего состояния: `state/_campaign-state.json`;
- номер ревизии `state_revision`;
- транзакции с `expected_state_revision`;
- атомарный commit;
- операции передачи предмета, изменения состояния персонажа, добавления/раскрытия/утверждения знания;
- статусы знания `canonical / candidate / disproven`;
- автоматический `views/gm-context.md`;
- отдельный `views/player-context.md` без мастерских candidate-идей;
- проверка ручных изменений производных views;
- тест на stale transaction.

## Команды

```bash
python tools/campaignctl.py --project . render
python tools/campaignctl.py --project . check
python tools/campaignctl.py --project . preview --transaction transactions/example_transfer.json
python tools/campaignctl.py --project . commit --transaction transactions/example_transfer.json
```

## Принцип

Модель или мастер не редактирует `_campaign-state.json` напрямую во время игрового хода. Сначала создаётся транзакция, затем движок валидирует её, применяет к копии состояния, повышает `state_revision` и заново строит производные контексты.

## Это пока MVP

Пока не реализованы: проверки D&D-механики, временные таймеры, экономика, поселения, сложный инвентарь, отношения как отдельная сущность, журнал транзакций, откат, снапшоты и импорт старых летописей.

## Добавлено во второй итерации

- `beliefs`: отдельные убеждения персонажей, которые могут быть истинными, ложными или неизвестными; они не становятся каноном автоматически;
- `world_pressures`: процессы и последствия, которые двигают мир независимо от игрока;
- `commit_history`: краткий журнал подтверждённых ревизий внутри authoritative state;
- запрет раскрывать `candidate`-факт персонажам до перевода в `canonical`;
- операции `add_belief`, `retire_belief`, `add_world_pressure`, `resolve_world_pressure`, `set_thread_status`.

## Третья итерация — живой D&D-ход

- baseline импортирован из актуального состояния «Яр воин»;
- добавлены `world.scene_participants`, чтобы знания персонажей вне сцены не подмешивались в текущий разговор;
- добавлены безопасные операции `set_world_field`, `set_party_field`, `set_scene_participants`, `set_character_resource`, `set_project_field`, `set_world_pressure_field`, `set_thread_field`;
- добавлен сценарный тест на копии реальной кампании: разговор → ночь → продолжение дороги;
- сценарные транзакции из `scenario-tests/` помечены как simulation и не меняют реальный baseline.

Запуск всех тестов:

```bash
python tests/test_mvp.py
python tests/test_real_scenario.py
```

## Preview перед commit

`preview` валидирует транзакцию, применяет её только к копии state и показывает семантический diff. Файл `_campaign-state.json`, views и `state_revision` при этом не меняются. Служебное добавление event/commit-history выводится отдельно от смысловых изменений.

## Постоянные правила стола

Раздел `play_rules` в state хранит правила управления персонажами и формат тактической информации. Эти правила входят в GM Context и должны переживать перезапуск/перезагрузку контекста.
