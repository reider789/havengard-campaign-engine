/* Offline, GM-only companion. No network, no automatic hero decisions. */
(()=>{
 'use strict';
 const port=globalThis.PreparedGMPort;if(!port)return;
 const catalogue=PreparedCatalogue;
 const box=document.createElement('section');box.id='prepared-gm';
 box.style.cssText='margin:20px;padding:18px;border:1px solid #b99c69;border-radius:12px;background:#192124;color:#f4ead9';
 document.querySelector('main').append(box);
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let last='',chosen='';
 function draw(){
  const e=port.getEngine();if(!e?.s.prepared)return;
  const fingerprint=JSON.stringify([e.s.turnSerial,e.s.pending,e.revision,e.s.prepared,Object.values(e.s.units).map(u=>[u.id,u.hp,u.prepared])]);
  if(last===fingerprint)return;last=fingerprint;
  const ids=e.s.order.filter(id=>e.unit(id).prepared);if(!ids.includes(chosen))chosen=ids[0];
  const u=e.unit(chosen),key=u.prepared.profile,card=catalogue.cards[key],r=catalogue.rules[key];
  box.innerHTML='<h2>Стол ведущего · подготовленная встреча</h2>'+
   '<p>Режим с решениями ведущего. Проверьте реальные условия нападения, слышимость, укрытие, высоту и состав целей. Полёт, сложные взаимодействия с приборами и авторская магия требуют подтверждения по карточке. Героями управляет игрок.</p>'+
   '<label>Противник <select id="pg-unit">'+ids.map(id=>'<option '+(id===chosen?'selected':'')+' value="'+esc(id)+'">'+esc(e.name(id))+' · '+esc(id)+'</option>').join('')+'</select></label>'+
   '<p>'+esc('Фаза '+u.prepared.phase+' · легендарные очки '+u.prepared.legendary+' · применения '+JSON.stringify(u.prepared.uses)+' · боеприпасы '+JSON.stringify(u.prepared.ammo))+'</p>'+
   '<details><summary>Полная карточка: '+esc(card.name)+'</summary>'+['action','bonus','reaction','extra','saves','skills','defenses','senses','language','behavior','gear'].map(k=>'<p><b>'+esc({action:'Действия',bonus:'Бонусное действие',reaction:'Реакции',extra:'Особенности',saves:'Спасброски',skills:'Навыки',defenses:'Защита',senses:'Чувства',language:'Языки',behavior:'Мотивация и поведение',gear:'Имущество'}[k])+':</b> '+esc(card[k])+'</p>').join('')+'</details>'+
   '<details><summary>Комната, история, календарь, опасности и награды (для ведущего)</summary><p>'+esc(catalogue.encounters[e.s.prepared.room].room.truth)+'</p><pre style="white-space:pre-wrap">'+esc(JSON.stringify({boss:Object.values(catalogue.bosses||{}).find(b=>b.arena===e.s.prepared.room),objects:e.s.prepared.objects,loot:catalogue.encounters[e.s.prepared.room].loot,hazards:catalogue.encounters[e.s.prepared.room].hazards},null,2))+'</pre></details>'+
   '<label>Действие <select id="pg-action">'+u.attacks.map(a=>'<option value="attack:'+esc(a.id)+'">Атака: '+esc(a.name)+'</option>').join('')+
    Object.entries(r.actions||{}).map(([id,a])=>'<option value="ability:'+esc(id)+'">'+esc(a.name)+' · '+esc(a.cost)+'</option>').join('')+
    (u.casting?.prepared||[]).filter(id=>id==='mistyStep').map(id=>'<option value="cast:'+id+'">Туманный шаг · бонусное действие</option>').join('')+
    ['move','dash','disengage','dodge','flee',...(key==='C09'?['constrict']:[]),'endTurn'].map(id=>'<option value="native:'+id+'">'+({move:'Движение',dash:'Рывок',disengage:'Отход',dodge:'Уклонение',flee:'Покинуть поле у края',constrict:'Сжатие удерживаемых целей',endTurn:'Закончить ход'})[id]+'</option>').join('')+'</select></label>'+
   '<label>Цели (можно несколько) <select id="pg-target" multiple size="4">'+e.s.order.filter(id=>id!==chosen).map(id=>'<option value="'+esc(id)+'">'+esc(e.name(id))+' · '+esc(id)+'</option>').join('')+'</select></label>'+
   '<label>Подчинённый <select id="pg-ally"><option value="">—</option>'+ids.filter(id=>id!==chosen).map(id=>'<option value="'+esc(id)+'">'+esc(e.name(id))+' · '+esc(id)+'</option>').join('')+'</select></label>'+
   '<label>Путь, клетки через пробел <input id="pg-path" placeholder="D5 E5 F5"></label>'+
   '<label><input type="checkbox" id="pg-confirm"> Условия и цели проверены по полной карточке</label>'+
   '<label><input type="checkbox" id="pg-spell"> Для авторского заклинания разрешены компоненты, Тишина, Сфера и окно Контрзаклинания</label>'+
   '<label><input type="checkbox" id="pg-telegraph"> Для дыхания сохранены объявленная ось, сдвиг до 10 фт и поворот до 45°</label>'+
   '<button id="pg-execute">Выполнить</button><label>Объявленная точка и ось дыхания <input id="pg-axis" placeholder="Например: из N8 на северо-запад, конус 60 фт"></label><button id="pg-prepare-breath">Объявить дыхание и закончить ход</button>'+
   (e.s.pending?.kind==='preparedChoice'?'<div style="padding:12px;border:2px solid #c9aa68"><p>'+esc(e.s.pending.label)+'</p><label>Объект для цены устойчивости <select id="pg-object">'+Object.values(e.s.prepared.objects).map(o=>'<option value="'+esc(o.id)+'">'+esc(o.name)+' '+esc(o.id)+' · '+o.hp+' ПЗ</option>').join('')+'</select></label><button id="pg-yes">Применить / да</button><button id="pg-no">Отказаться / продолжить</button></div>':'')+
   '<details><summary>Зафиксировать решение ведущего: прибор, среда, отдельный урон</summary>'+
   '<p>Для взаимодействия с прибором сначала разрешите проверку/атаку по полной карточке. Здесь записывается подтверждённый исход; кнопка не выполняет проверку инструментов, попадание или геометрию за ведущего.</p>'+
   '<label>Объект <select id="pg-rule-object"><option value="">—</option>'+Object.values(e.s.prepared.objects).map(o=>'<option value="'+esc(o.id)+'">'+esc(o.id)+' · '+o.hp+' ПЗ</option>').join('')+'</select></label>'+
   '<label>Полученный объектом урон <input id="pg-object-damage" type="number" min="0" max="1000"></label>'+
   '<label>Состояние объекта <select id="pg-object-state"><option value="">без изменения</option><option value="off">выключен</option><option value="suppressed">подавлен</option><option value="grounded">заземлён</option><option value="unsuppressed">подавление закончилось</option></select></label>'+
   '<label>Полученный существом урон <input id="pg-damage" type="number" min="0" max="1000"></label>'+
   '<label>Тип урона <select id="pg-type">'+['acid','bludgeoning','cold','fire','force','lightning','necrotic','piercing','poison','psychic','radiant','slashing','thunder'].map(s=>'<option>'+s+'</option>').join('')+'</select></label>'+
   '<label>Состояние цели <select id="pg-status"><option value="">без изменения</option>'+['poisoned','incapacitated','rooted','grappled','prone','deafened','restrained'].map(s=>'<option>'+s+'</option>').join('')+'</select></label>'+
   '<label>Высота цели относительно основного пола, фт <input id="pg-altitude" type="number" min="-60" max="1000" step="5"></label><label>Скорость передвижения цели <select id="pg-movement"><option value="">без изменения</option><option value="walk">шаг</option><option value="fly">полёт</option><option value="climb">лазание</option><option value="swim">плавание</option></select></label>'+
   '<label>Подтверждённая конечная клетка цели <input id="pg-point" placeholder="D5"></label><label><input id="pg-outside" type="checkbox">цель покинула арену (нет подпитки)</label><label><input id="pg-clear-dust" type="checkbox">пыль выбранного источника рассеяна</label><label><input id="pg-stop" type="checkbox">предусмотренная остановка выбранного стража</label>'+
   '<label>Списание применения цели <input id="pg-resource" placeholder="например breath"></label><label>Количество <input id="pg-spend-resource" type="number" min="1" max="10" value="1"></label><label><input id="pg-reaction" type="checkbox">потратить реакцию цели</label>'+
   '<label><input id="pg-remove" type="checkbox">снять состояние</label><label><input id="pg-spend" type="checkbox">потратить действие текущего участника</label>'+
   '<label>Решение и основание <textarea id="pg-ruling" rows="3" style="width:100%"></textarea></label><button id="pg-record">Записать подтверждённый исход</button>'+
   '<p>Арена: источник выбирается выше, область описывается в решении. Инициативу 20 отслеживает ведущий; цели выбираются заново при ударе.</p><label><input id="pg-init20" type="checkbox">Сейчас инициатива 20, после существ с 20</label><button id="pg-mark">Отметить удар арены</button><button id="pg-resolve">Разрешить ранее отмеченный удар</button></details>'+
   '<p id="pg-error" role="status"></p>';
  const $=id=>box.querySelector('#'+id);
  $('pg-unit').onchange=()=>{chosen=$('pg-unit').value;last='';draw();};
  const targets=()=>[...$('pg-target').selectedOptions].map(o=>o.value);
  function act(c){try{if(c.kind==='decide')c.id=e.s.pending?.id;port.act(c);last='';draw();}catch(err){$('pg-error').textContent=err.message;}}
  $('pg-execute').onclick=()=>{
    const [type,id]=$('pg-action').value.split(':'),ts=targets(),path=$('pg-path').value.trim().split(/\s+/).filter(Boolean).map(c=>CombatCampaignAdapter.cell(c.toUpperCase()));
    const c={actor:e.actorId,creature:chosen,ability:id,targets:ts,ally:$('pg-ally').value,confirmed:$('pg-confirm').checked,spellWindowConfirmed:$('pg-spell').checked,telegraphValid:$('pg-telegraph').checked};
    if(path.length)c.path=path;
    if(type==='ability'){
      if(e.s.pending?.choice==='legendary')act({...c,kind:'decide',choice:'ability'});
      else act({...c,kind:'prepared'});
    }else{
      if(chosen!==e.actorId){$('pg-error').textContent='Это действие доступно в собственный ход выбранного участника.';return;}
      if(type==='cast')act({kind:'cast',actor:chosen,spell:id,level:2,point:path.at(-1)});
      else act({kind:type==='attack'?'attack':id,actor:chosen,target:ts[0],weapon:id,...(path.length?{path}:{} )});
    }
  };
  if($('pg-yes'))$('pg-yes').onclick=()=>act({kind:'decide',choice:'yes',object:$('pg-object').value});
  if($('pg-no'))$('pg-no').onclick=()=>act({kind:'decide',choice:'no'});
  $('pg-prepare-breath').onclick=()=>act({kind:'preparedEndTurn',actor:e.actorId,confirmed:$('pg-confirm').checked,ruling:$('pg-axis').value});
  for(const [button,operation] of [['pg-mark','mark'],['pg-resolve','resolve']])$(button).onclick=()=>act({kind:'preparedArena',actor:e.actorId,operation,object:$('pg-rule-object').value,targets:targets(),initiative20:$('pg-init20').checked,confirmed:$('pg-confirm').checked,ruling:$('pg-ruling').value});
  $('pg-record').onclick=()=>{
    const ts=targets(),object=$('pg-rule-object').value,state=$('pg-object-state').value;
    const c={kind:'preparedRuling',actor:e.actorId,creature:chosen,confirmed:$('pg-confirm').checked,ruling:$('pg-ruling').value,spendAction:$('pg-spend').checked};
    if(object){c.object=object;if($('pg-object-damage').value!=='')c.damage=Number($('pg-object-damage').value);
      if(state)c[state==='unsuppressed'?'suppressed':state]=state!=='unsuppressed';}
    if(ts.length===1){c.target=ts[0];if($('pg-damage').value!=='')c.components=[{amount:Number($('pg-damage').value),damageType:$('pg-type').value}];
      if($('pg-altitude').value!=='')c.altitude=Number($('pg-altitude').value);
      if($('pg-movement').value)c.movementMode=$('pg-movement').value;
      if($('pg-point').value)c.point=CombatCampaignAdapter.cell($('pg-point').value.trim().toUpperCase());
      if($('pg-outside').checked)c.outsideArena=true;
      if($('pg-clear-dust').checked)c.clearDust=true;
      if($('pg-stop').checked)c.deactivate=true;
      if($('pg-resource').value){c.resource=$('pg-resource').value;c.spend=Number($('pg-spend-resource').value);}
      if($('pg-reaction').checked)c.reaction=true;
      if($('pg-status').value){c.status=$('pg-status').value;c.remove=$('pg-remove').checked;}}
    act(c);
  };
 }
 setInterval(draw,400);draw();
})();
