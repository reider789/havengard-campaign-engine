"""Expire imported temporary combat effects on the existing campaign clock."""
def synchronize(state):
    now=state.get('world',{}).get('timekeeping',{}).get('elapsed_seconds_from_anchor',0);changed=False;expired=[];active=[]
    for cid,char in state.get('characters',{}).items():
        data=char.get('combat_continuity')
        if not data:continue
        keep=[]
        for effect in data.get('effects',[]):
            if effect.get('expires_at',0)<=now or effect.get('concentration') and char['resources']['hp']['current']<=0:expired.append(effect);changed=True
            else:keep.append(effect);active.append(effect)
        data['effects']=keep
        ids={x['id'] for x in keep}
        data['objects']=[x for x in data.get('objects',[]) if x['id'] in ids]
        data['zones']=[x for x in data.get('zones',[]) if x.get('expires_at',0)>now]
        data['statuses']=[x for x in data.get('statuses',[]) if x.get('expires_at',now+1)>now]
        if char['resources']['hp']['current']>0:
            statuses=data.get('statuses',[]);new=[z for z in statuses if not(z['kind']=='unconscious' and 'until' not in z)]
            if new!=statuses:data['statuses']=new;changed=True
    for effect in expired:
        if effect['kind']=='aid':
            for cid in effect['targets']:
                hp=state['characters'][cid]['resources']['hp'];hp['max']-=effect['amount'];hp['current']=min(hp['current'],hp['max'])
        if effect['kind']=='heroism':
            for cid in effect['targets']:
                saved=state['characters'][cid].get('combat_continuity',{})
                if saved.get('temp_source')==effect['id']:saved['temporary_hp']=0
    for cid,char in state.get('characters',{}).items():
        resources=char.get('resources',{})
        if 'mage_armor' in resources and char.get('combat_continuity'):
            value='активен' if any(x['kind']=='mageArmor' and cid in x['targets'] for x in active) else 'не активен'
            if resources['mage_armor']!=value:resources['mage_armor']=value;changed=True
        if 'concentration' in resources and char.get('combat_continuity'):
            value=', '.join(x['kind'] for x in active if x['owner']==cid and x.get('concentration')) or 'нет'
            if resources['concentration']!=value:resources['concentration']=value;changed=True
    return changed
