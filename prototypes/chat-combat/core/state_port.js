// Explicit dependency boundary for runtime state and host combat services.
// All reads are lazy: importing/resetting a saved battle changes the live state
// without keeping a stale reference in spell or reaction handlers.
class CombatStatePort {
  constructor(readState,resolveServices){
    if(typeof readState!=='function'||typeof resolveServices!=='function')
      throw Error('Некорректные зависимости боевого движка');
    this._readState=readState;
    this._resolveServices=resolveServices;
  }
  getState(){
    const state=this._readState();
    if(!state||typeof state!=='object'||!state.units||!Array.isArray(state.history))
      throw Error('Состояние боя не инициализировано');
    return state;
  }
  services(){return this._resolveServices();}
}
