"""Build a no-network, self-contained ChatGPT combat HTML from canonical Campaign Engine.
This script does not publish or update GitHub Pages, nor write anything in prototypes/combat/app.
"""
from __future__ import annotations
import argparse
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
            details.append({'id': f'{hero}-live-{row.get("source_row", "unknown")}',
                            'name': str(parts[0]),
                            'description': ' · '.join(str(c) for c in parts[1:] if c is not None)[:1100],
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


def build(root: Path) -> dict:
    state = json.loads((root / 'state/_campaign-state.json').read_text(encoding='utf-8'))
    old_ref_path = root / 'prototypes/combat/app/runtime/latest.json'
    old_ref = json.loads(old_ref_path.read_text(encoding='utf-8')) if old_ref_path.exists() else {}
    source_path = root / 'prototypes/chat-combat/engine-v21.html'
    source = source_path.read_text(encoding='utf-8')
    if '<div id="hv12">' not in source or '<script>' not in source:
        raise ValueError('Unknown combat HTML format')
    if '<script type="application/json" data-hg-runtime>' in source:
        raise ValueError('Source is already bundled; do not bundle twice')
    runtime = make_manifest(state, old_ref)
    payload = json.dumps(runtime, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('&', '\\u0026')
    # Text owned by application/json script tag (no executable remote code).
    tag = '<script type="application/json" data-hg-runtime>' + payload + '</script>\n'
    result = source.replace('<div id="hv12">', '<div id="hv12">\n' + tag, 1)
    output = root / 'prototypes/chat-combat/current-chat-battle.html'
    output.write_text(result, encoding='utf-8')
    metadata = {'schema_version': 1, 'engine': 'engine-v21.html',
                'bundle': 'current-chat-battle.html',
                'source_revision': state['state_revision'], 'hero_count': len(runtime['characters']),
                'usage': 'Self-contained ChatGPT panel; GitHub is the canonical source, not the combat save.',
                'canonical': False}
    (root / 'prototypes/chat-combat/current-manifest.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    print(json.dumps(build(parser.parse_args().root), ensure_ascii=False))