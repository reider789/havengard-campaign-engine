"""Expire imported effects on the campaign clock, including retained summons."""
from copy import deepcopy


def synchronize(state):
    characters = state.get('characters', {})
    before = deepcopy(characters)
    now = state.get('world', {}).get('timekeeping', {}).get('elapsed_seconds_from_anchor', 0)
    expired, active, summons = [], [], {}
    for char in characters.values():
        for unit in char.get('combat_continuity', {}).get('summons', []):
            summons[unit['id']] = unit

    for char in characters.values():
        data = char.get('combat_continuity')
        if not data:
            continue
        keep = []
        for effect in data.get('effects', []):
            if (effect.get('expires_at', 0) <= now or
                    effect.get('concentration') and char['resources']['hp']['current'] <= 0):
                expired.append(effect)
            else:
                keep.append(effect)
                active.append(effect)
        data['effects'] = keep
        ids = {x['id'] for x in keep}
        data['objects'] = [x for x in data.get('objects', []) if x['id'] in ids]
        data['zones'] = [x for x in data.get('zones', []) if x.get('expires_at', 0) > now]
        data['statuses'] = [x for x in data.get('statuses', []) if x.get('expires_at', now + 1) > now]
        if char['resources']['hp']['current'] > 0:
            data['statuses'] = [z for z in data['statuses'] if not (z['kind'] == 'unconscious' and 'until' not in z)]
            # Healing resets death saves; resurrection remains explicit.
            if data.get('life') and not data['life']['dead']:
                data['life'] = dict(dead=False, stable=False, deathSuccesses=0, deathFailures=0)
        for unit in data.get('summons', []):
            unit['persistent_statuses'] = [z for z in unit.get('persistent_statuses', [])
                                           if z.get('expires_at', now + 1) > now]

    for effect in expired:
        for target in effect['targets']:
            char, unit = characters.get(target), summons.get(target)
            if effect['kind'] == 'aid':
                if char:
                    hp = char['resources']['hp']
                    previous = hp['current']
                    hp['max'] -= effect['amount']
                    hp['current'] = max(0, min(hp['current'] - effect['amount'], hp['max']))
                    if previous > 0 and hp['current'] == 0:
                        saved = char.setdefault('combat_continuity', {})
                        saved['life'] = dict(dead=False, stable=False, deathSuccesses=0, deathFailures=0)
                        for kind in ('unconscious', 'prone'):
                            if not any(z['kind'] == kind for z in saved.get('statuses', [])):
                                saved.setdefault('statuses', []).append(dict(kind=kind))
                elif unit:
                    previous = unit['hp']
                    unit['max'] -= effect['amount']
                    unit['hp'] = max(0, min(unit['hp'] - effect['amount'], unit['max']))
                    if previous > 0 and unit['hp'] == 0:
                        unit['persistent_life'] = dict(dead=True, stable=False, deathSuccesses=0, deathFailures=0)
            if effect['kind'] == 'heroism':
                saved = char.get('combat_continuity', {}) if char else {}
                if saved.get('temp_source') == effect['id']:
                    saved['temporary_hp'] = 0
                    saved.pop('temp_source', None)
                if unit and unit.get('persistent_temp_source') == effect['id']:
                    unit['persistent_temp'] = 0
                    unit.pop('persistent_temp_source', None)

    # Aid can expire before a longer concentration effect. End that effect
    # immediately on collapse, using the same clock and idempotent removal.
    fallen = {cid for cid,char in characters.items()
              if isinstance(char.get('resources', {}).get('hp'), dict)
              and char['resources']['hp']['current'] <= 0}
    if any(x.get('concentration') and x.get('owner') in fallen for x in active):
        synchronize(state)
        active = [x for char in characters.values() for x in char.get('combat_continuity', {}).get('effects', [])]

    dead_summons = {uid for uid,u in summons.items() if u.get('hp', 0) <= 0}
    for char in characters.values():
        data = char.get('combat_continuity', {})
        keep = []
        for effect in data.get('effects', []):
            targets = effect['targets']
            effect['targets'] = [uid for uid in targets if uid not in dead_summons]
            if not targets or effect['targets'] or effect.get('aura'):
                keep.append(effect)
        if 'effects' in data:
            data['effects'] = keep
        for obj in data.get('objects', []):
            if obj.get('grappled') in dead_summons:
                obj['grappled'] = None
    active = [x for char in characters.values() for x in char.get('combat_continuity', {}).get('effects', [])]
    live = {x['id'] for x in active}
    for char in characters.values():
        data = char.get('combat_continuity', {})
        def retained(z):
            return (not z.get('effect') or z['effect'] in live) and not (z['kind'] == 'grappled' and z.get('source') in fallen | dead_summons)
        if 'statuses' in data:
            data['statuses'] = [z for z in data['statuses'] if retained(z)]
        for unit in data.get('summons', []):
            if 'persistent_statuses' in unit:
                unit['persistent_statuses'] = [z for z in unit['persistent_statuses'] if retained(z)]

    for cid, char in characters.items():
        resources = char.get('resources', {})
        if not char.get('combat_continuity'):
            continue
        if 'mage_armor' in resources:
            resources['mage_armor'] = ('активен' if any(x['kind'] == 'mageArmor' and cid in x['targets'] for x in active)
                                       else 'не активен')
        if 'concentration' in resources:
            resources['concentration'] = ', '.join(x['kind'] for x in active if x['owner'] == cid and x.get('concentration')) or 'нет'
    return before != characters
