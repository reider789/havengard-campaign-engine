// Live session getter prevents stale journal after session load/reset.
class CombatJournal {
  constructor(getState,localize,limit=700){
    this._state=getState;this._localize=localize;this._limit=limit;
  }
  append(message){
    const s=this._state();
    if(!Array.isArray(s.history))throw Error('Журнал не инициализирован');
    s.history.push('Р'+s.round+' · '+this._localize(String(message)));
    if(s.history.length>this._limit)s.history.splice(0,s.history.length-this._limit);
  }
}
