// Player-triggered battle handoff. Read-only reports, no canonical writes.
class CombatNarrativeHandoff {
 constructor(o){
  this.o=o;this.lastReport=null;this._mount();
 }
 _mount(){
  const footer=this.o.root.querySelector('.footer');
  const btn=document.createElement('button');
  btn.type='button';btn.id='hg-narrative-handoff';btn.className='btn primary';
  btn.textContent='✦ Завершить бой и передать мастеру';
  footer.prepend(btn);
  const notice=document.createElement('div');notice.id='hg-narrative-status';
  notice.setAttribute('role','status');
  notice.style.cssText='font-size:11px;color:#f1d59c;margin-top:8px';
  footer.insertAdjacentElement('afterend',notice);
  btn.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();this.send()});
 }
 _status(t){this.o.root.querySelector('#hg-narrative-status').textContent=t}
 _report(){
  const s=this.o.state(),names=this.o.names(),ids=this.o.party(),enemies=this.o.enemies();
  const u=id=>{const x=s.units[id];return{id,name:names[id]||s.extraEnemies?.find(e=>e.id===id)?.name||id,
   alive:x.hp>0,hp:x.hp,max_hp:x.max,status:(x.status||[]).map(v=>v.kind)}};
  const allies=ids.map(u),foes=enemies.filter(id=>s.units[id]).map(u);
  let draft=null,warning=null;
  try{draft=this.o.outcome()}catch(e){warning=String(e.message||e)}
  const source=(s.history||[]).map(String);
  const meaningful=source.filter(v=>!/^Р\d+ · Кости \d+к\d+:/.test(v));
  const full=meaningful.join('\n');
  const limit=65000;
  let journal=meaningful,coverage='complete';
  if(full.length>limit){
   const opening=meaningful.slice(0,30),ending=meaningful.slice(-200);
   const selected=new Set([...opening,...ending]);let used=[...selected].join('\n').length;
   const middle=meaningful.slice(30,-200);
   const stride=Math.max(1,Math.ceil(middle.join('\n').length/Math.max(1,limit-used)));
   for(let i=0;i<middle.length;i+=stride){
    if(used+middle[i].length+1>limit)break;
    selected.add(middle[i]);used+=middle[i].length+1;
   }
   journal=meaningful.filter(v=>selected.has(v));coverage='partial';
  }
  return {
   kind:'havengard-battle-report-v1',engine:'v27',
   battle:{name:s.battleName||'Старый мост',id:s.battleId||null,
    mode:s.sessionKind||'training',anchor:s.chronicleAnchor||null,
    context:s.narrativeContext||null,source_revision:s.sourceRevision,
    result:foes.length&&foes.every(x=>!x.alive)?'victory':allies.every(x=>!x.alive)?'defeat':'stopped'},
   allies,foes,
   journal:{all_entries:source.length,transferred:journal.length,coverage,events:journal},
   key_events:(s.eventHistory||[]).slice(-250),
   outcome:{draft,warning,canonical_unchanged:true,approval_required:true}
  };
 }
 send(){
  const s=this.o.state();
  if(s.pending||s.moving||(s.spellStack&&s.spellStack.length)){
   this._status('Завершите реакцию, движение или цепочку заклинаний прежде передачи.');return false;
  }
  // Do not end or clear the active combat when the host handoff is unavailable.
  // The DIL host control submits the report in an actual user click; calling
  // setValue only stages it, and MUST NOT claim a new chat turn was created.
  const callback=globalThis.__bindings?.setValue;
  if(typeof callback!=='function'){
   this._status('Связь с чатом недоступна. Бой НЕ завершён; прогресс сохранён локально.');
   return false;
  }
  if(s.phase!=='ended'){
   s.phase='ended';this.o.log('Бой остановлен по решению игрока.');
   this.o.render();this.o.save();
  }
  const report=this._report();this.lastReport=report;
  try{
   callback({kind:'havengard-battle-handoff-v1',report});
   this._status('Отчёт подготовлен. Нажмите «Передать мастеру» под игровой панелью — это отправит сообщение в чат.');
   return true;
  }catch(e){
   this._status('Отчёт сформирован, но связь с чатом не ответила: '+String(e.message||e));
   return false;
  }
 }
}
