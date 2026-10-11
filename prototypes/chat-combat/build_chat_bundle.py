"""Build a no-network, self-contained ChatGPT combat HTML from canonical Campaign Engine.
This script does not publish or update GitHub Pages, nor write anything in prototypes/combat/app.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

ALIAS = [
    (r'^Обычное лечебное зелье$', 'healing'),
    (r'^Улучшенное лечебное зелье$', 'greater'),
    (r'^Противоядие$', 'antitoxin'),
    (r'^Алхимический огонь$', 'fire'),
    (r'^Кислота$', 'acid'),
    (r'^Дымовая бомба$', 'smoke'),
    (r'^Зелье скорости$', 'speed'),
    (r'^Зелье лазания$', 'climb'),
    (r'^Зелье силы холмового великана$', 'giant'),
    (r'^Зелье сопротивления огню$', 'fireRes'),
    (r'^Зелье роста$', 'growth'),
    (r'^Зелье героизма$', 'heroism'),
    (r'^Яд быстрого хищника$', 'poison'),
    (r'^Сигнальная ракета$', 'flare'),
    (r'^Металлическая ловушка$', 'trap'),
]
HEROES = ('yar', 'daphne', 'lyutobor', 'rada')


def make_manifest(state: dict, previous: dict | None = None) -> dict:
    previous = previous or {}
    chars = {}
    for hero in HEROES:
        live = state['characters'][hero]
        old = previous.get('characters', {}).get(hero, {})
        source_catalog = live.get('inventory_catalog', {})
        prior_mapping = {e.get('id'): e.get('consumable_type') for e in old.get('inventory', [])}
        inv, quantities = [], {}
        for key, item in source_catalog.items():
            name = str(item.get('name', key))
            amount = item.get('quantity', 0)
            n = amount if isinstance(amount, int) and amount > 0 else 0
            kind = prior_mapping.get(key) or next((type_name for pattern, type_name in ALIAS if re.search(pattern, name, flags=re.I)), None)
            inv.append({'id': key, 'name': name, 'quantity': n,
                        'description': item.get('description', ''), 'status': item.get('status', ''),
                        'consumable_type': kind})
            if kind and n:
                quantities[kind] = quantities.get(kind, 0) + n
        sheet = live.get('character_sheet', {})
        details = []
        for row in sheet.get('combat_reference', []):
            parts = row.get('cells') or []
            if not parts or not parts[0]:
                continue
            # Strip an adjacent unrelated skill occasionally carried on a
            # single live-sheet combat-reference row (without changing canon).
            description = ' · '.join(str(c) for c in parts[1:] if c is not None)
            skill_names = r'Атлетика|Акробатика|Ловкость рук|Скрытность|Магия|История|Расследование|Природа|Религия|Уход за животными|Проницательность|Медицина|Восприятие|Выживание|Обман|Запугивание|Выступление|Убеждение'
            description = re.split(r' · (?:' + skill_names + r') · [+-]?\d+ · ', description, maxsplit=1)[0]
            details.append({'id': f'{hero}-live-{row.get("source_row", "unknown")}',
                            'name': str(parts[0]),
                            'description': description[:1100],
                            'category': 'live_sheet'})
        prev_names = {v['name'] for v in details}
        for old_entry in old.get('skills_attacks_spells', []):
            if old_entry.get('name') and old_entry['name'] not in prev_names:
                details.append(old_entry)
        chars[hero] = {'name': live['name'], 'class_and_level': sheet.get('class_and_level'),
                       'ac_description': sheet.get('armor_class'),
                       'speed': sheet.get('speed'),
                       'resources': live.get('resources', {}),
                       'consumables': quantities,
                       'inventory': inv,
                       'skills_attacks_spells': details}
    return {'schema_version': 2, 'source_state_revision': state['state_revision'],
            'source': 'self-contained-chat-bundle-from-canonical', 'is_canonical': False,
            'characters': chars}



def validate_scene(raw: dict, expected_revision: int) -> dict:
    """Fail-closed canonical story encounter. Never invents combat statistics."""
    if not isinstance(raw, dict) or raw.get('schema_version') != 1:
        raise ValueError('Story scene needs schema_version=1')
    if raw.get('kind') != 'story':
        raise ValueError('A plot encounter must be explicitly marked kind=story')
    if type(raw.get('source_revision')) is not int or raw['source_revision'] != expected_revision:
        raise ValueError('Stale scene: canonical state revision changed; rebuild the encounter from current canon')
    battle_id = raw.get('battle_id')
    if not isinstance(battle_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{5,63}', battle_id):
        raise ValueError('battle_id must be a stable, explicit 6–64-character lowercase ID')
    name = raw.get('name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 48 or any(c in name for c in '<>"\'&\\'):
        raise ValueError('Scene name must be 1–48 safe characters')
    description = raw.get('narrative_context')
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1000:
        raise ValueError('Story scene requires a concise, grounded narrative_context')
    anchor = raw.get('chronicle_anchor')
    if not isinstance(anchor, str) or not 1 <= len(anchor.strip()) <= 160:
        raise ValueError('chronicle_anchor is required to link the fight to the story')

    def location(v):
        if not isinstance(v, str) or not re.fullmatch(r'[A-K][1-8]', v):
            raise ValueError(f'Invalid map cell: {v}')
        return v

    occupied = set()
    terrain = {}
    for key in ('walls', 'rubble'):
        arr = raw.get(key, [])
        if not isinstance(arr, list) or len(arr) > 88:
            raise ValueError(f'Invalid {key} cells')
        cleaned = [location(x) for x in arr]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError(f'Duplicate {key} cells')
        terrain[key] = cleaned
    if set(terrain['walls']) & set(terrain['rubble']):
        raise ValueError('Wall and rubble cells overlap')
    walls = set(terrain['walls'])
    obstacle_skins = raw.get('obstacleSkins', {})
    allowed_skins = {'wall','broken_wall','rubble','barricade','log','boulder','bush','pillar'}
    if not isinstance(obstacle_skins, dict) or any(
        not isinstance(k,str) or k not in set(terrain['walls'] + terrain['rubble'])
        or v not in allowed_skins
        for k,v in obstacle_skins.items()
    ):
        raise ValueError('Obstacle skins must refer only to blocked or rough cells')

    heroes = raw.get('heroes')
    if not isinstance(heroes, dict) or set(heroes) != set(HEROES):
        raise ValueError('All four heroes must have an explicit starting cell and rolled initiative')
    validated_heroes = {}
    for hero in HEROES:
        entry = heroes[hero]
        if not isinstance(entry, dict):
            raise ValueError(f'Invalid hero {hero}')
        cell = location(entry.get('cell'))
        initiative = entry.get('initiative')
        if type(initiative) is not int or not -10 <= initiative <= 50:
            raise ValueError(f'Invalid rolled initiative for {hero}')
        if cell in walls or cell in occupied:
            raise ValueError(f'Hero overlaps another unit or wall at {cell}')
        occupied.add(cell)
        hidden=entry.get('hidden',False)
        if type(hidden) is not bool:
            raise ValueError(f'Hero hidden value must be boolean for {hero}')
        validated_heroes[hero] = {'cell': cell, 'initiative': initiative, 'hidden': hidden}
    raw_enemies = raw.get('enemies')
    if not isinstance(raw_enemies, list) or not 1 <= len(raw_enemies) <= 20:
        raise ValueError('A story scene needs 1–20 defined opponents')
    theme = raw.get('theme', 'meadow')
    if theme not in ('meadow','forest','ruins','city'):
        raise ValueError('Scene theme must be meadow, forest, ruins or city')
    validated_enemies = []
    for n, e in enumerate(raw_enemies, start=1):
        if not isinstance(e, dict) or not isinstance(e.get('name'), str):
            raise ValueError(f'Invalid opponent #{n}')
        enemy_name = e['name']
        if not 1 <= len(enemy_name.strip()) <= 48 or any(ch in enemy_name for ch in '<>"\'&\\'):
            raise ValueError(f'Invalid opponent name #{n}')
        cell = location(e.get('cell'))
        if cell in occupied or cell in walls:
            raise ValueError(f'Enemy overlaps a wall or unit at {cell}')
        occupied.add(cell)
        for k,lo,hi in [('hp',1,2000),('ac',1,30),('initiative',-10,40)]:
            if type(e.get(k)) is not int or not lo <= e[k] <= hi:
                raise ValueError(f'Enemy #{n} requires a documented {k} in [{lo},{hi}]')
        attack = e.get('attack')
        if not isinstance(attack, dict):
            raise ValueError(f'Enemy #{n} needs an attack profile')
        for k,lo,hi in [('bonus',-10,25),('count',1,12),('die',4,12),('flat',-10,40),('range',5,600)]:
            if type(attack.get(k)) is not int or not lo <= attack[k] <= hi:
                raise ValueError(f'Invalid attack.{k} for enemy #{n}')
        if attack['die'] not in (4,6,8,10,12) or attack['range'] % 5:
            raise ValueError(f'Invalid attack die/range for enemy #{n}')
        saves = e.get('saves')
        if not isinstance(saves, dict):
            raise ValueError(f'Enemy #{n} requires explicit saving throw modifiers')
        save_keys = {'STR','DEX','CON','INT','WIS','CHA'}
        if set(saves) != save_keys or any(type(v) is not int or not -10 <= v <= 25 for v in saves.values()):
            raise ValueError(f'Enemy #{n} needs all six saving throw modifiers')
        abilities = e.get('abilities', [])
        if not isinstance(abilities, list) or len(abilities)>12 or any(not isinstance(x,str) or len(x)>48 for x in abilities):
            raise ValueError(f'Invalid reference abilities for enemy #{n}')
        token_key=e.get('tokenKey')
        if token_key is not None and token_key not in ('warrior','rogue','archer','mage','wolf','orc','undead','dragon'):
            raise ValueError(f'Unknown tokenKey for enemy #{n}')
        validated_enemies.append({'name':enemy_name.strip(),'cell':cell,'hp':e['hp'],'ac':e['ac'],
                                  'initiative':e['initiative'],'attack':{key:attack[key] for key in ('bonus','count','die','flat','range')},
                                  'saves':{key:saves[key] for key in sorted(save_keys)}, 'abilities':abilities,
                                  'tokenKey':token_key})
    return {
        'schema_version': 1, 'kind': 'story', 'battle_id': battle_id,
        'source_revision': expected_revision, 'name': name.strip(), 'theme': theme,
        'narrative_context': description.strip(), 'chronicle_anchor': anchor.strip(),
        'heroes': validated_heroes, **terrain, 'obstacleSkins': obstacle_skins, 'enemies': validated_enemies,
    }


def build(root: Path, scenario_path: Path | None = None, output_path: Path | None = None) -> dict:
    state = json.loads((root / 'state/_campaign-state.json').read_text(encoding='utf-8'))
    old_ref_path = root / 'prototypes/combat/app/runtime/latest.json'
    old_ref = json.loads(old_ref_path.read_text(encoding='utf-8')) if old_ref_path.exists() else {}
    source_path = root / 'prototypes/chat-combat/engine-v23.html'
    source = source_path.read_text(encoding='utf-8')
    # Compile all source modules into one self-contained script; no runtime network fetch.
    core_dir = root / 'prototypes/chat-combat/core'
    module_sites = {
        '/*__HV_COMBAT_CORE_MODULES__*/': ('dice.js', 'journal.js', 'conditions.js', 'battlefield.js'),
        '/*__HV_SPELL_RESOLVER__*/': ('spell_resolver.js',),
        '/*__HV_REACTION_RESOLVER__*/': ('reaction_resolver.js',),
    }
    for marker, module_names in module_sites.items():
        if source.count(marker) != 1:
            raise ValueError('Missing or duplicate combat module marker: ' + marker)
        source = source.replace(marker, '\n'.join(
            (core_dir / module).read_text(encoding='utf-8') for module in module_names), 1)
    modules = tuple(name for names in module_sites.values() for name in names)
    # Offline graphical add-on runs inside the exact same battle closure; no remote JS.
    skin_path = root / 'prototypes/chat-combat/visual_skin.js'
    if skin_path.exists():
        skin = skin_path.read_text(encoding='utf-8')
        terminal = chr(10) + '})();' + chr(10) + '</script>'
        if source.count(terminal) != 1:
            raise ValueError('Unexpected combat source ending, cannot attach visuals')
        source = source.replace(terminal, chr(10) + skin + terminal, 1)
    if '<div id="hv12">' not in source or '<script>' not in source:
        raise ValueError('Unknown combat HTML format')
    if '<script type="application/json" data-hg-runtime>' in source:
        raise ValueError('Source is already bundled; do not bundle twice')
    runtime = make_manifest(state, old_ref)
    scene = None
    if scenario_path is not None:
        scene = validate_scene(json.loads(scenario_path.read_text(encoding='utf-8')), state['state_revision'])
    payload = json.dumps(runtime, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('&', '\\u0026')
    # Text owned by application/json script tag (no executable remote code).
    tag = '<script type="application/json" data-hg-runtime>' + payload + '</script>\n'
    scene_tag = ''
    if scene:
        safe_scene = json.dumps(scene, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('&', '\\u0026')
        scene_tag = '<script type="application/json" data-hg-scene>' + safe_scene + '</script>\n'
    result = source.replace('<div id="hv12">', '<div id="hv12">\n' + tag + scene_tag, 1)
    output = output_path or root / 'prototypes/chat-combat' / ('story-chat-battle.html' if scene else 'current-chat-battle.html')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding='utf-8')
    metadata = {'schema_version': 2, 'engine': 'engine-v23.html',
                'bundle': output.name,
                'source_revision': state['state_revision'], 'hero_count': len(runtime['characters']),
                'usage': 'Self-contained ChatGPT panel; GitHub is the canonical source, not the combat save.',
                'canonical': False, 'mode': 'story' if scene else 'training',
                'architecture': {'version': 'v23', 'bundled_modules': list(modules), 'offline': True},
                'battle_id': scene['battle_id'] if scene else None,
                'chronicle_anchor': scene['chronicle_anchor'] if scene else None,
                'visual_skin': {'engine_module': 'visual_skin.js', 'offline_art_pack_schema': 'havengard-combat-art-v1', 'expected_assets': 24, 'embedded': skin_path.exists()},
                'bundle_sha256': hashlib.sha256(result.encode('utf-8')).hexdigest(),
                'bundle_size_bytes': len(result.encode('utf-8'))}
    manifest_path = output.parent / ('story-manifest.json' if scene else 'current-manifest.json')
    manifest_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--scenario', type=Path, help='Story encounter JSON written by narrator from confirmed chronicle')
    parser.add_argument('--output', type=Path, help='Optional standalone story HTML destination')
    args = parser.parse_args()
    print(json.dumps(build(args.root, args.scenario, args.output), ensure_ascii=False))