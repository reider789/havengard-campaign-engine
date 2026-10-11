// Single manager for statuses, concentration, temporary effects and expiry.
class CombatConditions {
  constructor({getState,log,name,statusName,effectName,isHero,distance}){
    Object.assign(this,{_state:getState,_log:log,_name:name,_statusName:statusName,
      _effectName:effectName,_isHero:isHero,_distance:distance});
  }
  has(id,k){const s=this._state();return s.units[id].status.some(z=>z.kind===k&&(z.until===null||z.until>s.elapsed));}
  add(id,k,until=null){
    const u=this._state().units[id];u.status=u.status.filter(z=>z.kind!==k);
    u.status.push({kind:k,until});
    const special={burn:'Горит',toxic:'Яд — нет реакций',poisoned:'Отравлен',prone:'Лежит'};
    this._log(this._name(id)+' получает состояние «'+(special[k]||this._statusName(k))+'».');
  }
  remove(id,k){
    const u=this._state().units[id];u.status=u.status.filter(z=>z.kind!==k);
    this._log(this._name(id)+': состояние «'+this._statusName(k)+'» прекращено.');
  }
  findEffect(id,k){
    const s=this._state();
    return s.effects.find(e=>e.kind===k&&e.until>s.elapsed&&
      (e.targets.includes(id)||(k==='mantle'&&this._isHero(id)&&s.units[e.owner]?.hp>0&&
        this._distance(s.units[e.owner],s.units[id])<=30)));
  }
  apply(owner,k,targets,duration,concentration=false){
    const s=this._state();
    if(concentration){
      s.effects.filter(e=>e.owner===owner&&e.concentration)
        .forEach(e=>this._log(this._name(owner)+': концентрация на '+this._effectName(e.kind)+' прекращена.'));
      s.effects=s.effects.filter(e=>e.owner!==owner||!e.concentration);
    }
    s.effects.push({owner,kind:k,targets:[...targets],until:s.elapsed+duration,concentration});
    this._log(this._name(owner)+': эффект '+this._effectName(k)+' → '+targets.map(id=>this._name(id)).join(', ')+'.');
  }
  expire(){
    const s=this._state();
    for(const e of s.effects.filter(e=>e.until<=s.elapsed&&e.kind==='aid'))
      for(const h of e.targets){
        const u=s.units[h];u.max=Math.max(1,u.max-5);u.hp=Math.min(u.hp,u.max);
      }
    s.effects=s.effects.filter(e=>e.until>s.elapsed);
    s.smoke=s.smoke.filter(e=>e.until>s.elapsed);
    for(const id of Object.keys(s.units))
      s.units[id].status=s.units[id].status.filter(z=>z.until===null||z.until>s.elapsed);
  }
}
