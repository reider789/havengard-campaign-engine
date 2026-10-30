/* Offline actions for the authored encounters. Every choice is explicit. */
(()=>{
 'use strict';const port=globalThis.PreparedGMPort;if(!port)return;
 const box=document.createElement('section');box.id='prepared-runtime';
 box.style.cssText='margin:20px;padding:20px;border:1px solid #b99c69;border-radius:12px;background:#192124;color:#f4ead9;line-height:1.6';document.querySelector('main').append(box);
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let last='',chosen='';
 const options=(items,selected)=>items.map(([value,label])=>'<option value="'+esc(value)+'" '+(value===selected?'selected':'')+'>'+esc(label)+'</option>').join('');
 function point(raw){const m=/^([A-Z]{1,2})([1-9][0-9]?)(?:@(-?\d+))?$/i.exec(raw.trim());if(m)return {x:[...m[1].toUpperCase()].reduce((a,c)=>a*26+c.charCodeAt(0)-64,0)-1,y:+m[2]-1,...(m[3]===undefined?{}:{altitude:+m[3]})};const n=/^(-?\d+),(-?\d+)(?:@(-?\d+))?$/.exec(raw.trim());if(n)return {x:+n[1],y:+n[2],...(n[3]===undefined?{}:{altitude:+n[3]})};throw Error('Клетка: H6@20 или мировая позиция -2,5@10');}
 function draw(){
  const e=port.getEngine();if(!e?.s.prepared?.runtime){box.hidden=true;return;}box.hidden=false;
  const fingerprint=JSON.stringify([e.revision,e.s.pending,e.s.turnSerial]);if(last===fingerprint)return;last=fingerprint;
  if(!e.s.units[chosen])chosen=e.actorId;const u=e.unit(chosen),card=PreparedCatalogue.cards[u.prepared?.profile],r=PreparedCatalogue.rules[u.prepared?.profile]||{};
  const spells=CombatMagic.catalogue(u).filter(s=>!['counterspell','shield','divineSmite','preparedChord','preparedPause'].includes(s.id));
  const actionOptions=[...u.attacks.map(a=>['attack:'+a.id,'Атака: '+a.name]),...Object.entries(r.actions||{}).filter(([,a])=>!['failedSave','onHit','endOwnTurn'].includes(a.cost)).map(([id,a])=>['prepared:'+id,a.name]),...spells.map(s=>['cast:'+s.id,s.name]),...['move','dash','disengage','dodge','hide','search','escape','flee','endTurn'].map(id=>['native:'+id,({move:'Перемещение',dash:'Рывок',disengage:'Отход',dodge:'Уклонение',hide:'Спрятаться',search:'Поиск',escape:'Освободиться',flee:'Покинуть бой',endTurn:'Завершить ход'})[id]])];
  box.innerHTML='<h2>Подготовленная встреча · '+esc(e.s.prepared.room)+'</h2><p>Особые заклинания, инициатива 20, приборы и высоты исполняются автоматически. Действия и необязательные реакции четырёх героев выбирает игрок. Противников и область арены выбирает ведущий.</p>'+
   '<label>Участник <select id="pr-actor">'+options(e.s.order.map(id=>[id,e.name(id)+(e.unit(id).controlled?' · игрок':' · ведущий')]),chosen)+'</select></label><p>Сейчас ход: '+esc(e.name(e.actorId))+' · высота '+(u.worldPosition?.altitude??u.altitude??0)+' фт'+(u.prepared?' · фаза '+u.prepared.phase+' · легендарные очки '+u.prepared.legendary+' · '+esc(JSON.stringify(u.prepared.uses)):'')+'</p>'+
   (card?'<details><summary>Полная карточка · '+esc(card.name)+'</summary>'+['action','bonus','reaction','extra','saves','skills','defenses','senses','language','behavior','gear'].map(k=>'<p>'+esc(card[k])+'</p>').join('')+'</details>':'')+
   '<label>Действие <select id="pr-action">'+options(actionOptions)+'</select></label><label>Цели <select id="pr-target" multiple size="4">'+options(e.s.order.filter(id=>id!==chosen).map(id=>[id,e.name(id)]))+'</select></label>'+
   '<label>Точка / направление <input id="pr-point" placeholder="H6@20"></label><label>Путь: клетки через пробел <input id="pr-path" placeholder="H6@5 H6@10 I6@10"></label>'+
   '<label>Движение <select id="pr-mode">'+options([['walk','Шаг'],['fly','Полёт'],['climb','Лазание'],['swim','Плавание']])+'</select></label><label>Круг <input id="pr-level" type="number" min="0" max="9" value="0"></label>'+
   '<label>Подчинённый <select id="pr-ally">'+options([['','—'],...e.s.order.filter(id=>e.unit(id).prepared).map(id=>[id,e.name(id)] )])+'</select></label><button id="pr-do">Выполнить</button>'+
   (u.prepared?.profile==='C33'?'<button id="pr-breath">Объявить направление дыхания и завершить ход</button>':'')+
   '<details open><summary>Приборы</summary><label>Прибор <select id="pr-object">'+options(Object.values(e.s.prepared.objects).map(o=>[o.id,o.id+' · '+o.name+' · '+o.hp+'/'+o.max+' ПЗ · КД '+o.ac+(o.off?' · выключен':'')+(o.suppressed?' · подавлен':'')+(o.grounded?' · заземлён':'')+(o.open?' · крышка открыта':'')]))+'</select></label><label>Способ <select id="pr-method">'+options([['arcana','Аркана'],['tools','Инструменты вора']])+'</select></label><button id="pr-interact">Взаимодействовать · действие</button><button id="pr-weapon">Атаковать выбранным оружием</button><button id="pr-spell">Применить выбранное заклинание к прибору</button><button id="pr-dispel">Рассеять питание</button></details>'+
   (u.prepared?'<label>Собственное брошенное оружие <select id="pr-drop">'+options(e.s.prepared.runtime.drops.filter(d=>d.owner===u.id).map(d=>[d.id,d.id+' · '+d.x+','+d.y]))+'</select></label><button id="pr-recover">Подобрать своё</button>':'')+
   (e.s.pending?.kind==='preparedRuntimeChoice'?'<div style="border:2px solid #ccb175;padding:12px"><p>'+esc(e.s.pending.label)+'</p>'+(e.s.pending.choice==='arenaMark'?'<button id="pr-mark">Отметить выбранную точку от прибора</button><button id="pr-skip">Пропустить</button>':'<button id="pr-athletics">Реакция: Атлетика</button><button id="pr-acrobatics">Реакция: Акробатика</button><button id="pr-skip">Без реакции</button>')+'</div>':'')+
   (e.s.pending?.kind==='preparedChoice'?'<p>'+esc(e.s.pending.label)+'</p><button id="pr-yes">Применить</button><button id="pr-no">Отказаться / продолжить</button>':'')+
   '<details><summary>Сведения ведущему: арена и награды</summary><p>'+esc(PreparedCatalogue.encounters[e.s.prepared.room].room.truth)+'</p><pre style="white-space:pre-wrap">'+esc(JSON.stringify({mark:e.s.prepared.environment,loot:PreparedCatalogue.encounters[e.s.prepared.room].loot},null,2))+'</pre></details><p id="pr-error" role="status"></p>';
  const $=id=>box.querySelector('#pr-'+id),targets=()=>[...$('target').selectedOptions].map(o=>o.value),path=()=>$('path').value.trim()?$('path').value.trim().split(/\s+/).map(point):undefined;
  const data=()=>({actor:chosen,targets:targets(),target:targets()[0],...($('point').value.trim()?{point:point($('point').value)}:{}),path:path(),mode:$('mode').value,ally:$('ally').value,confirmed:true});
  const run=c=>{try{port.act(c);const error=document.querySelector('#notice');if(error?.textContent)$('error').textContent=error.textContent;}catch(error){$('error').textContent=error.message;}draw();};
  const decide=(choice,more={})=>run({kind:'decide',id:e.s.pending.id,choice,...more});
  $('actor').onchange=()=>{chosen=$('actor').value;last='';draw();};
  $('action').onchange=()=>{const [kind,id]=$('action').value.split(':');$('level').value=kind==='cast'?CombatMagic.SPELLS[id][1]:0;};
  $('do').onclick=()=>{const [kind,id]=$('action').value.split(':');let c=data();if(e.s.pending?.kind==='preparedChoice'&&e.s.pending.choice==='legendary'){decide('ability',{...c,creature:chosen,ability:id});return;}
   run(kind==='attack'?{...c,kind:'attack',weapon:id}:kind==='prepared'?{...c,kind:'prepared',ability:id}:kind==='cast'?{...c,kind:'cast',spell:id,level:+$('level').value}:{...c,kind:id==='move'?'preparedMove':id});};
  if($('breath'))$('breath').onclick=()=>run({...data(),kind:'preparedEndTurn'});
  $('interact').onclick=()=>run({kind:'preparedInteract',actor:chosen,object:$('object').value,method:$('method').value});
  $('weapon').onclick=()=>{const [kind,id]=$('action').value.split(':');if(kind!=='attack'){$('error').textContent='Выберите оружие в списке действий';return;}run({kind:'attackObject',actor:chosen,object:$('object').value,weapon:id});};
  $('spell').onclick=()=>{const [kind,id]=$('action').value.split(':');if(kind!=='cast'){$('error').textContent='Выберите заклинание';return;}run({kind:'cast',actor:chosen,spell:id,level:+$('level').value,targets:Array(id==='scorchingRay'?+$('level').value+1:1).fill('object:'+$('object').value)});};
  $('dispel').onclick=()=>run({kind:'cast',actor:chosen,spell:'dispelMagic',level:Math.max(3,+$('level').value),dispelTarget:{kind:'object',id:$('object').value}});
  if($('recover'))$('recover').onclick=()=>run({kind:'preparedRecover',actor:chosen,drop:$('drop').value});
  if($('mark'))$('mark').onclick=()=>{try{decide('mark',{object:$('object').value,point:point($('point').value)});}catch(error){$('error').textContent=error.message;}};
  if($('skip'))$('skip').onclick=()=>decide('skip');
  if($('athletics'))$('athletics').onclick=()=>decide('athletics');if($('acrobatics'))$('acrobatics').onclick=()=>decide('acrobatics');
  if($('yes'))$('yes').onclick=()=>decide('yes',{object:$('object').value});if($('no'))$('no').onclick=()=>decide('no');
 }
 setInterval(draw,200);draw();
})();
