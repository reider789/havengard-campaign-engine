/* GM workbench. Pinned stock modules are never modified on disk.
 * This is explicitly assisted adjudication, not a claim of 3D automation.
 * Every nonstandard outcome requires a named rule and a GM confirmation.
 */
"use strict";
function installPreparedGM(SDK, catalogue) {
  const {CombatContentPack:P,CombatCampaignAdapter:A,CombatRulesEngine:E,CombatMagic:M}=SDK;
  if (E.preparedInstalled) return;
  E.preparedInstalled=true;
  const requirement='perelomye-gm-assist-v1';
  const req=(v,m)=>{if(!v)throw Error(m);};
  const copy=v=>structuredClone(v);
  const card=u=>u?.prepared?.profile;
  const rule=u=>catalogue.rules[card(u)]||{};
  const log=(e,id,text,data={})=>e.emit('preparedRule',id,text,{extension:requirement,...data});
  const task=(op,actor,data={})=>({kind:'preparedTask',op,actor,...data});
  const die=(e,id,d,label)=>{
    const rolls=Array.from({length:d[0]},()=>e.roll(d[1]));
    const amount=rolls.reduce((a,b)=>a+b,0)+(d[2]||0);
    log(e,id,label+': ['+rolls.join(', ')+']'+((d[2]||0)>=0?'+':'')+(d[2]||0)+' = '+amount,{rolls,amount});return amount;
  };
  const liveObjects=e=>Object.values(e.s.prepared?.objects||{}).filter(o=>o.hp>0&&!o.off&&!o.suppressed&&!o.grounded);
  const compile=P.compile;
  P.compile=function(input){
    const data=copy(input),needs=data.requires?.includes(requirement);
    if(needs)data.requires=data.requires.filter(x=>x!==requirement);
    const r=compile.call(this,data);
    if(needs)r.content_pack=copy(input);
    return r;
  };
  // Save files are deliberately newer than the stock engine: old UIs reject
  // them instead of silently ignoring an assisted rule or continuation.
  E.VERSION='30.8.0';
  const adapterUnit=A.unit;
  A.unit=function(id,p,raw,r){
    const u=adapterUnit.call(this,id,p,raw,r);
    const key=p.reference?.find(x=>typeof x==='string'&&x.startsWith('prepared:'))?.slice(9);
    if(key){
      req(catalogue.cards[key],'Нет подготовленной карточки '+key);
      u.prepared={profile:key,uses:copy(catalogue.rules[key].uses),ammo:copy(catalogue.rules[key].ammo),
        phase:1,legendary:catalogue.rules[key].legendary?.max||0,once:[],active:true};
      if(key==='C10')u.conditionImmunities.push('grappled');
      if(catalogue.rules[key].noReaction)u.reaction=0;
    }
    return u;
  };
  // The stock adapter has a single-letter parser despite its 40-cell limit.
  A.cell=function(v){const m=/^([A-Z]{1,2})([1-9][0-9]?)$/.exec(v||'');req(m,'Неверная клетка '+v);
    const x=[...m[1]].reduce((a,c)=>a*26+c.charCodeAt(0)-64,0)-1;
    req(x<40,'Клетка вне поддержанной ширины');return {x,y:Number(m[2])-1};};
  const create=A.create;
  A.create=function(runtime,scene,seed){
    const s=create.call(this,runtime,scene,seed);
    if(!runtime.content_pack?.requires?.includes(requirement))return s;
    const template=catalogue.encounters[scene.scene_id];
    req(template,'Нет подготовленного шаблона комнаты');
    s.engineVersion=E.VERSION;
    s.prepared={version:1,catalogue:catalogue.version,catalogueSha256:catalogue.source.sha256,room:scene.scene_id,mode:'gm-assisted',
      objects:Object.fromEntries((template.room.objects||[]).map(o=>[o.id,{...copy(o),max:o.hp,off:false,grounded:false}])),
      environment:null,environmentRound:0,legendaryBoundary:null};
    for(const u of Object.values(s.units))if(u.prepared){
      const spawn=template.population.find(p=>p.id===u.id);
      u.prepared.active=spawn?.active!==false;
      u.prepared.activateRound=u.prepared.active?1:null;
      if(scene.scene_id==='T5'&&u.prepared.profile==='C29')u.altitude=-20;
    }
    return s;
  };
  const validate=E.validate;
  const validateExtra=s=>{
    if(!s.prepared)return;
    req(s.prepared.version===1&&s.prepared.catalogue===catalogue.version&&s.prepared.catalogueSha256===catalogue.source.sha256&&s.prepared.mode==='gm-assisted'&&catalogue.encounters[s.prepared.room],'Неверный GM-пакет или другая версия каталога');
    for(const u of Object.values(s.units))if(u.prepared){
      const p=u.prepared,r=catalogue.rules[p.profile];req(r,'Неизвестная GM-карточка');
      req([1,2].includes(p.phase)&&typeof p.active==='boolean','Повреждена фаза/активация');
      req(Number.isInteger(p.legendary)&&p.legendary>=0&&p.legendary<=3,'Повреждены легендарные очки');
      for(const [id,n] of Object.entries(p.uses))req(Number.isInteger(n)&&n>=0&&n<=(r.uses[id]??-1),'Повреждён лимит '+id);
      for(const [id,n] of Object.entries(p.ammo))req(Number.isInteger(n)&&n>=0&&n<=(r.ammo[id]??-1),'Повреждены боеприпасы');
    }
    for(const o of Object.values(s.prepared.objects))req(Number.isInteger(o.hp)&&o.hp>=0&&o.hp<=o.max&&typeof o.off==='boolean','Повреждён объект арены');
    const occupied=new Map(),moving=s.queue.find(t=>t.kind==='moveStep')?.actor||s.pending?.movement?.actor;
    for(const u of Object.values(s.units).filter(u=>u.hp>0&&!u.fled)){
      const span=u.footprint||1;
      for(let dx=0;dx<span;dx++)for(let dy=0;dy<span;dy++){
        const x=u.x+dx,y=u.y+dy;req(x<s.terrain.width&&y<s.terrain.height,'Площадь существа выходит за поле');
        req(!s.terrain.walls.includes(x+','+y),'Площадь существа пересекает стену');
        const h=u.altitude??s.terrain.elevation?.[u.x+','+u.y]??0,k=x+','+y+','+h,other=occupied.get(k);
        req(!other||rule(u).sharedSpace||rule(other).sharedSpace||u.id===moving||other.id===moving||u.involuntarySharedSpace||other.involuntarySharedSpace,'Перекрываются площади существ');occupied.set(k,u);
      }
    }
  };
  E.validate=function(s){
    validateExtra(s);
    if(!s.prepared)return validate.call(this,s);
    const data=copy(s);
    for(const u of Object.values(data.units))if(rule(u).sharedSpace||u.altitude)u.involuntarySharedSpace=true;
    return validate.call(this,data);
  };
  const continuations=E.validateContinuations;
  E.validateContinuations=function(s){
    if(!s.prepared)return continuations.call(this,s);
    const clean=copy(s),roots=[];
    const visit=v=>{
      if(!v||typeof v!=='object')return v;
      if(v.kind==='preparedTask'){
        req(['saveResult','boundary','restoreMove'].includes(v.op)&&s.units[v.actor],'Повреждён GM-шаг');
        if(v.target)req(s.units[v.target],'Нет цели GM-шага');
        if(v.op==='restoreMove')req(Number.isInteger(v.budget)&&v.budget>=0&&v.budget<=10000,'Повреждён бюджет движения');
        if(v.op==='saveResult'){
          const d=catalogue.rules[card(s.units[v.actor])]?.actions?.[v.key]||v.definition;
          req(d&&['saveDamage','saveStatus','pushSave','grappleSave','poison'].includes(d.op)&&Number.isInteger(v.amount)&&v.amount>=0&&v.amount<=1000000&&s.units[v.target],'Повреждён результат способности');
        }
        return {kind:'startTurn'};
      }
      if(v.kind==='preparedChoice'){
        req(['legendary','resistance','onHit','parry','shield'].includes(v.choice)&&s.units[v.actor],'Повреждено решение ведущего');
        if(v.resume)roots.push(visit(copy(v.resume)));
        if(v.roll)roots.push(visit({...copy(v.roll),kind:'roll'}));
        return null;
      }
      if(Array.isArray(v))return v.map(visit);
      for(const k of Object.keys(v))v[k]=visit(v[k]);return v;
    };
    visit(clean);clean.queue.push(...roots);continuations.call(this,clean);
  };
  const conditionImmune=E.prototype.conditionImmune;
  E.prototype.conditionImmune=function(id,kind){
    if(kind==='exhaustion'&&['C32','C34','C36','C37'].includes(card(this.unit(id))))return true;
    return conditionImmune.call(this,id,kind);
  };
  const active=E.prototype.active;
  E.prototype.active=function(id){return active.call(this,id)&&this.unit(id).prepared?.active!==false;};
  const occupied=E.prototype.occupied;
  E.prototype.occupied=function(x,y,except=null){
    if(!this.s.prepared||except===null)return occupied.call(this,x,y,except);
    const actor=this.unit(except);
    return this.s.order.find(id=>{
      const u=this.unit(id);
      return id!==except&&u.hp>0&&!u.fled&&!rule(u).sharedSpace&&!rule(actor).sharedSpace&&
        Math.abs((u.altitude||0)-(actor.altitude||0))<5&&
        x>=u.x&&x<u.x+(u.footprint||1)&&y>=u.y&&y<u.y+(u.footprint||1);
    });
  };
  const distance=E.prototype.distance;
  E.prototype.distance=function(a,b){
    const height=p=>p.altitude??this.s.terrain.elevation?.[p.x+','+p.y]??0;
    return Math.max(distance.call(this,a,b),Math.abs(height(a)-height(b)));
  };
  const ac=E.prototype.ac;
  E.prototype.ac=function(id,from,spec){
    if(this.s.prepared&&card(this.unit(id))==='C34')this.unit(id).ac=this.unit(id).prepared.phase===2||liveObjects(this).length<2?17:19;
    return ac.call(this,id,from,spec);
  };
  if(M){
    const pay=M.pay;
    M.pay=function(e,f,cost){
      if(card(e.unit(f.actor))==='C32'){
        req((f.spell==='mistyStep'&&f.level===2)||(f.spell==='counterspell'&&f.level===3),'У Эссы только отдельные 2/сутки Туманного шага и 2/сутки Контрзаклинания; повышать круг нельзя');
        if(f.spell==='mistyStep')req(!e.unit(f.actor).prepared.silenced,'Туманный шаг требует вербальный компонент');
        if(f.spell==='counterspell')req(e.unit(f.actor).prepared.phase===1,'Во второй фазе Контрзаклинание недоступно');
      }
      return pay.call(this,e,f,cost);
    };
  }
  const attackSpec=E.prototype.attackSpec;
  E.prototype.attackSpec=function(id,key){
    const s=attackSpec.call(this,id,key),u=this.unit(id),r=rule(u);
    if(r.halfHPAttack?.attack===key&&u.hp<=r.halfHPAttack.threshold)s.count=r.halfHPAttack.count;
    return s;
  };
  const validateAttack=E.prototype.validateAttack;
  E.prototype.validateAttack=function(id,target,spec,from){
    const u=this.unit(id),r=rule(u);
    if(r.sharedSpace)req(this.distance(u,this.unit(target))===0,'Рой жалит только в общем пространстве');
    if(r.hearingAttacks?.includes(spec.id)){
      req(!this.has(target,'deafened'),'Глухая цель невосприимчива к гласу');
      req(!u.prepared?.silenced,'Источник находится в Тишине');
      req(this.canSee(id,target),'Глас требует видимую цель');
    }
    if(r.ammo?.[spec.id]!==undefined)req(u.prepared.ammo[spec.id]>0,'Конечный запас боеприпасов исчерпан');
    return validateAttack.call(this,id,target,spec,from);
  };
  const spendAmmo=E.prototype.spendAmmo;
  E.prototype.spendAmmo=function(u,spec){
    if(u.prepared?.ammo?.[spec.id]!==undefined)u.prepared.ammo[spec.id]--;
    return spendAmmo.call(this,u,spec);
  };
  const damageTask=E.prototype.damageTask;
  E.prototype.damageTask=function(t,amount){
    const result=damageTask.call(this,t,amount),u=this.unit(t.actor),r=rule(u);
    const riders=[...(r.riders?.[t.spec.id]||[]),...(u.prepared?.phase===2?r.phase?.riders?.[t.spec.id]||[]:[])];
    if(riders.length)result.components=[{amount,damageType:t.spec.damageType},...riders.map(d=>({
      amount:die(this,t.actor,[d[0]*(t.critical?2:1),d[1],d[2]],'Дополнительный '+d[3]),damageType:d[3]}))];
    return result;
  };
  function cost(e,id,key,d,c){
    const u=e.unit(id),p=u.prepared;
    req(p&&e.active(id)&&!e.incapacitated(id),'Существо не может применить способность');
    if(M&&['action','attack','bonus'].includes(d.cost))M.beforeCommand(e,{kind:'cast',actor:id,spell:d.cost==='bonus'?'mistyStep':'fireball'},u);
    if(d.resource){req(p.uses[d.resource]>0,'Применения исчерпаны');p.uses[d.resource]--;}
    if(d.cost==='legendary'){
      req(e.s.prepared.legendaryBoundary&&e.s.prepared.legendaryBoundary.actor!==id,'Нужен конец чужого хода');
      req(!e.s.prepared.legendaryBoundary.used.includes(id),'Только одно легендарное действие после этого хода');
      req(p.legendary>=d.points,'Недостаточно легендарных очков');p.legendary-=d.points;
      e.s.prepared.legendaryBoundary.used.push(id);
    }else if(d.cost==='action')e.spendAction(id);
    else if(d.cost==='bonus'){req(u.bonus>0,'Нет бонусного действия');u.bonus--;}
    else if(d.cost==='attack'){
      req(u.attacksLeft>0||u.action>0,'Нет атаки для замены');
      if(u.attacksLeft>0)u.attacksLeft--;else {e.spendAction(id);u.attacksLeft=(u.features.extraAttack||1)-1;}
    }else if(d.cost==='reaction'){req(u.reaction>0,'Нет реакции');u.reaction--;}
    if(d.once){req(!p.once.includes(key),'Способность уже применена между своими ходами');p.once.push(key);}
    if(d.spell)req(c.spellWindowConfirmed===true,'Сначала подтвердите компоненты, Тишину, Сферу и окно Контрзаклинания');
    log(e,id,d.name,{action:key,cost:d.cost,uses:p.uses,legendary:p.legendary});
  }
  function moveWithBudget(e,id,path,budget){
    if(e.s.prepared?.runtime&&e.preparedRuntimeMove){e.preparedRuntimeMove(id,path,budget);return;}
    const u=e.unit(id),old=u.move,rest=e.s.queue;e.s.queue=[];u.move=budget;
    E.preparedBaseCommand.call(e,{kind:'move',actor:id,path},u);
    e.s.queue=[...e.s.queue,task('restoreMove',id,{budget:old}),...rest];
  }
  function resolve(e,id,key,c){
    if(e.s.prepared?.runtime&&e.preparedRuntimeTargets)c=e.preparedRuntimeTargets(id,key,c);
    const u=e.unit(id),r=rule(u),d=r.actions?.[key];req(d,'Неизвестная подготовленная способность');
    req(c.confirmed===true,'Подтвердите цели, геометрию и условия по полной карточке');
    const targets=c.targets||[];req(Array.isArray(targets)&&new Set(targets).size===targets.length&&targets.every(t=>e.s.units[t]),'Неверные цели');
    if(d.range)for(const t of targets)req(e.distance(u,e.unit(t))<=d.range,'Цель вне дальности');
    if(d.hearing)for(const t of targets)req(!e.has(t,'deafened')&&e.canSee(id,t),'Нужна видимая слышащая цель');
    if(d.spell)req(!u.prepared.silenced,'Вербальный компонент запрещён Тишиной');
    if(d.op==='saveStatus')req(targets.length===1,'Пауза действует на одну цель');
    if(d.op==='pushSave'||d.op==='grappleSave')req(targets.length===1,'Нужна одна цель');
    if(d.op==='grappleSave'){
      const v=e.unit(targets[0]);req(d.maxSize===undefined||e.size(v.id)<=d.maxSize,'Цель слишком велика');
      const captives=e.s.order.filter(k=>e.unit(k).statuses.some(z=>z.kind==='grappled'&&z.source===id));
      req(captives.includes(v.id)||captives.length<d.maxTargets,'Лимит захваченных целей');
    }
    if(d.attackIndex)req(u.prepared.attackSequence?.length===d.attackIndex-1,'Можно заменить только вторую атаку');
    if(d.requiresTelegraph){
      req(u.prepared.telegraph&&u.prepared.telegraph.round===e.s.round-1,'Дыхание не было объявлено в конце предыдущего хода');
      req(c.telegraphValid===true,'Проверьте: сдвиг до 10 фт, поворот до 45°, прежняя объявленная ось');
    }
    req(!['failedSave','onHit','endOwnTurn','reaction'].includes(d.cost),'Эта способность доступна только в соответствующем окне; используйте решение ведущего');
    cost(e,id,key,d,c);
    if(d.spell&&c.cancelled){log(e,id,'Заклинание отменено в подтверждённом окне; применение потрачено.');return;}
    if(d.requiresTelegraph)delete u.prepared.telegraph;
    if(['saveDamage','saveStatus','pushSave','grappleSave'].includes(d.op)){
      req(targets.length>0,'Выберите цели');
      const amount=d.dice?die(e,id,d.dice,d.name):0;
      e.enqueue(...targets.map(target=>{
        let stat=d.stat;
        if(d.stats)stat=d.stats.reduce((a,b)=>(e.unit(target).saves[a]||0)>=(e.unit(target).saves[b]||0)?a:b);
        return e.saveTask(target,stat,d.dc,task('saveResult',id,{target,key,amount,stat,source:id}),{origin:u});
      }));
    }else if(d.op==='obscure'){
      const zone={kind:'smoke',x:u.x,y:u.y,radius:d.radius,until:e.s.elapsed+12,owner:id,preparedDust:true};
      // Native zones use point; provide both forms for display and containment.
      zone.point={x:u.x,y:u.y};e.s.zones.push(zone);
    }else if(d.op==='attack'){
      req(targets.length===1,'Нужна одна цель');const spec=e.attackSpec(id,d.attack);e.validateAttack(id,targets[0],spec);
      e.enqueue({kind:'attackRoll',actor:id,target:targets[0],spec,mode:'prepared'});
    }else if(d.op==='activate'){
      const v=e.unit(c.ally);req(card(v)===d.profile&&v.prepared.active===false&&v.hp>0,'Нужна существующая неактивная оболочка');
      req(liveObjects(e).some(o=>e.distance(v,o)<=10),'У оболочки нет работающего прибора');
      v.prepared.active=true;v.prepared.activateRound=e.s.round+1;
      log(e,id,v.name+' активирована; первый ход со следующего раунда.',{target:c.ally});
    }else if(d.op==='command'){
      const v=e.unit(c.ally);req(card(v)===d.profile&&e.active(c.ally)&&v.prepared.activateRound<=e.s.round&&!e.incapacitated(c.ally)&&!e.has(c.ally,'deafened')&&e.distance(u,v)<=d.range&&v.reaction>0,'Подчинённый не может выполнить приказ');
      v.reaction--;
      if(c.path)moveWithBudget(e,c.ally,c.path,15);
      else{req(targets.length===1,'Нужна цель атаки');const spec=e.attackSpec(c.ally,c.attack||v.attacks[0].id);e.validateAttack(c.ally,targets[0],spec);e.enqueue({kind:'attackRoll',actor:c.ally,target:targets[0],spec,mode:'reaction'});}
    }else if(d.op==='move'){
      req(Array.isArray(c.path),'Нужен явный путь для движения с атаками по возможности');
      let distance=d.distance;
      if(d.halfFly){const old=u.speed;u.speed=(u.prepared.phase===2?r.phase.fly:r.movement.fly)-(u.prepared.flightLoss||0);distance=Math.floor(e.speed(id)/10)*5;u.speed=old;}
      moveWithBudget(e,id,c.path,distance);
    }else{
      // Explicit table adjudication: never manufacture an unimplemented effect.
      req(c.ruling&&typeof c.ruling==='string','Нужно записать конкретное решение по карточке');
      log(e,id,c.ruling,{action:key,manual:true});
    }
  }
  E.preparedBaseCommand=E.prototype.command;
  E.prototype.command=function(c,u){
    if(!this.s.prepared)return E.preparedBaseCommand.call(this,c,u);
    if(c.kind==='prepared'){
      const id=c.creature||c.actor;
      req(id===this.actorId,'Обычная способность применяется в свой ход');resolve(this,id,c.ability,c);return;
    }
    if(c.kind==='preparedRuling'){
      req(c.confirmed===true&&typeof c.ruling==='string'&&c.ruling.trim(),'Подтвердите и опишите решение ведущего');
      // This bounded workbench records spatial and object decisions that the
      // 2D core cannot decide. It is not an arbitrary state/script evaluator.
      if(c.object){
        const o=this.s.prepared.objects[c.object];req(o,'Нет объекта');
        if(c.damage!==undefined){req(Number.isInteger(c.damage)&&c.damage>=0&&c.damage<=1000,'Неверный урон объекту');o.hp=Math.max(0,o.hp-c.damage);}
        if(c.off!==undefined){req(typeof c.off==='boolean','Неверное отключение');o.off=c.off;}
        if(c.suppressed!==undefined){req(typeof c.suppressed==='boolean','Неверное подавление');o.suppressed=c.suppressed;}
        if(c.grounded!==undefined){req(typeof c.grounded==='boolean','Неверное заземление');o.grounded=c.grounded;}
        for(const v of Object.values(this.s.units))if(card(v)==='C34'&&!liveObjects(this).length&&!v.prepared.reducedLegendary){
          v.prepared.legendary=Math.max(0,2-(3-v.prepared.legendary));v.prepared.reducedLegendary=true;
        }
      }
      if(c.target){
        const v=this.unit(c.target);
        if(c.movementMode){
          const r=rule(v),p=v.prepared;req(p&&Object.hasOwn(r.movement,c.movementMode),'Нет такой скорости движения');
          const speed=c.movementMode==='fly'?(p.phase===2?r.phase?.fly||r.movement.fly:r.movement.fly)-(p.flightLoss||0):c.movementMode==='walk'?(p.phase===2?r.phase?.walk||r.movement.walk:r.movement.walk):r.movement[c.movementMode];
          const previous=this.speed(c.target);p.movementMode=c.movementMode;v.speed=speed;this.adjustMovementForSpeed(c.target,previous);
        }
        if(c.altitude!==undefined){req(Number.isInteger(c.altitude)&&c.altitude>=-60&&c.altitude<=1000&&c.altitude%5===0,'Высота в футах, кратно 5');v.altitude=c.altitude;}
        if(c.point){req(this.inside(c.point)&&Number.isInteger(c.point.x)&&Number.isInteger(c.point.y),'Неверная точка');v.x=c.point.x;v.y=c.point.y;}
        if(c.outsideArena!==undefined){req(v.prepared&&typeof c.outsideArena==='boolean','Неверная граница арены');v.prepared.outsideArena=c.outsideArena;}
        if(c.deactivate){req(['C36','C37'].includes(card(v)),'Только предусмотренная остановка стражей');v.prepared.active=false;}
        if(c.clearDust)this.s.zones=this.s.zones.filter(z=>!(z.preparedDust&&z.owner===c.target));
        if(c.resource){req(v.prepared&&Object.hasOwn(v.prepared.uses,c.resource)&&Number.isInteger(c.spend)&&c.spend>0&&v.prepared.uses[c.resource]>=c.spend,'Неверное списание применений');v.prepared.uses[c.resource]-=c.spend;}
        if(c.reaction){req(v.reaction>0,'Реакция уже потрачена');v.reaction--;}
        if(c.silenced!==undefined){req(v.prepared&&typeof c.silenced==='boolean','Неверная Тишина');v.prepared.silenced=c.silenced;}
        if(c.status){req(['poisoned','incapacitated','rooted','grappled','prone','deafened','restrained'].includes(c.status),'Недопустимое состояние');
          if(c.remove)this.removeStatus(c.target,c.status);else this.status(c.target,c.status,{source:c.actor});}
        if(c.components){req(Array.isArray(c.components)&&c.components.length>0&&c.components.length<=8,'Нужны части урона');
          req(c.components.every(p=>Number.isInteger(p.amount)&&p.amount>=0&&p.amount<=1000&&['acid','bludgeoning','cold','fire','force','lightning','necrotic','piercing','poison','psychic','radiant','slashing','thunder'].includes(p.damageType)),'Неверные части урона');
          const source=c.creature||c.actor;req(this.s.units[source],'Неизвестный источник урона');
          this.enqueue({kind:'damage',actor:source,target:c.target,amount:c.components.reduce((n,p)=>n+p.amount,0),components:c.components,damageType:c.components[0].damageType});}
      }
      if(c.spendAction)this.spendAction(c.actor);
      log(this,c.actor,c.ruling,{manual:true,object:c.object,target:c.target});return;
    }
    if(c.kind==='preparedEndTurn'){
      req(card(u)==='C33'&&c.confirmed===true&&typeof c.ruling==='string'&&c.ruling.trim(),'Объявите точку и ось будущего дыхания');
      u.prepared.telegraph={round:this.s.round,x:u.x,y:u.y,altitude:u.altitude||0,axis:c.ruling};
      log(this,c.actor,'Подготовка дыхания: '+c.ruling,{telegraph:u.prepared.telegraph});
      this.enqueue({kind:'endTurn',actor:c.actor});return;
    }
    if(c.kind==='preparedArena'){
      req(c.confirmed===true&&c.initiative20===true&&c.ruling,'Подтвердите инициативу 20 (после существ с 20), цели, высоту и геометрию');
      const room=this.s.prepared.room,defs={T8:{stat:'WIS',dc:17,dice:[3,8,0],damageType:'psychic',boss:'C32'},B8:{stat:'DEX',dc:18,dice:[4,8,0],damageType:'lightning'},P9:{stat:'DEX',dc:18,dice:[5,8,0],damageType:'force',boss:'C34'}};
      const d=defs[room];req(d,'В этой комнате нет подготовленного действия арены');
      const capable=!d.boss||this.s.order.some(id=>card(this.unit(id))===d.boss&&this.active(id)&&!this.incapacitated(id)&&!this.unit(id).prepared.outsideArena);
      const old=this.s.prepared.environment;
      if(c.operation==='mark'){
        req(!old&&this.s.prepared.environmentRound!==this.s.round,'Можно отметить только одну область на инициативе 20');
        const o=this.s.prepared.objects[c.object];req(o&&liveObjects(this).includes(o)&&capable,'Источник не работает или босс не может направлять арену');
        this.s.prepared.environment={source:o.id,dueRound:this.s.round+1,geometry:c.ruling};this.s.prepared.environmentRound=this.s.round;
      }else{
        req(old&&this.s.round>=old.dueRound,'Область разрешается только на следующей инициативе 20');
        const o=this.s.prepared.objects[old.source];this.s.prepared.environment=null;
        if(!capable||!liveObjects(this).includes(o)){log(this,c.actor,'Отмеченный удар отменён: источник или условие не работает.');return;}
        req(Array.isArray(c.targets)&&c.targets.every(id=>this.s.units[id]),'Нужны подтверждённые цели');
        const amount=die(this,c.actor,d.dice,'Удар арены');
        const targets=c.targets.filter(id=>!(room==='T8'&&this.has(id,'deafened')));
        this.enqueue(...targets.map(target=>this.saveTask(target,d.stat,d.dc,task('saveResult',c.actor,{target,key:'arena',definition:{...d,op:'saveDamage',half:true},amount,stat:d.stat}),{origin:o})));
      }
      log(this,c.actor,c.ruling,{arena:room,operation:c.operation});return;
    }
    if(c.kind==='attack'&&u.prepared){
      const r=rule(u),p=u.prepared;
      if(u.action>0&&u.attacksLeft===0)p.attackSequence=[];
      const seq=p.attackSequence||[];
      if(r.attackSequence){const standalone=r.singleAttackAlternatives?.includes(c.weapon);req(standalone?seq.length===0: r.attackSequence[seq.length]===c.weapon,'Используйте каноническую последовательность мультиатаки');
        if(standalone){const old=u.features.extraAttack;u.features.extraAttack=1;try{return E.preparedBaseCommand.call(this,c,u);}finally{u.features.extraAttack=old;}}}
      if(r.attackAlternatives){req(!seq.length||seq[0]===c.weapon,'Нельзя смешивать альтернативные мультиатаки');u.features.extraAttack=r.attackAlternatives[c.weapon];}
      if(r.singleAttackAlternatives?.includes(c.weapon)&&!r.attackSequence){req(seq.length===0,'Рукопашная альтернатива заменяет всю мультиатаку');const old=u.features.extraAttack;u.features.extraAttack=1;try{return E.preparedBaseCommand.call(this,c,u);}finally{u.features.extraAttack=old;}}
      const result=E.preparedBaseCommand.call(this,c,u);p.attackSequence=[...seq,c.weapon];return result;
    }
    return E.preparedBaseCommand.call(this,c,u);
  };
  const finishRoll=E.prototype.finishRoll;
  E.prototype.finishRoll=function(t){
    if(this.s.prepared&&t.save&&!t.preparedResistanceConsidered){
      const u=this.unit(t.actor),r=rule(u),kept=t.mode>0?Math.max(...t.rolls):t.mode<0?Math.min(...t.rolls):t.rolls[0];
      if(r.resistance&&u.prepared.uses.resistance>0&&u.hp>r.resistance.hpCost&&(t.autoFail||kept+(t.bonus||0)-2*(u.exhaustion||0)<t.dc)&&(!r.resistance.objectCost||liveObjects(this).length)){
        this.decision('preparedChoice',t.actor,{choice:'resistance',roll:copy(t),label:'Провален спасбросок: применить устойчивость?'});return;
      }
    }
    return finishRoll.call(this,t);
  };
  const resolveDecision=E.prototype.resolveDecision;
  E.prototype.resolveDecision=function(c){
    const p=this.s.pending;
    if(p?.kind!=='preparedChoice')return resolveDecision.call(this,c);
    req(c.id===p.id,'Это решение уже завершено или устарело');
    req(c.choice==='yes'||c.choice==='no'||c.choice==='ability','Неверное решение');this.s.pending=null;
    if(p.choice==='resistance'){
      const u=this.unit(p.actor),r=rule(u);
      if(c.choice==='yes'){
        if(r.resistance.objectCost){const o=this.s.prepared.objects[c.object];req(o&&liveObjects(this).includes(o),'Выберите работающий объект');o.hp=0;o.off=true;}
        req(u.hp>r.resistance.hpCost&&u.prepared.uses.resistance>0,'Устойчивость недоступна');
        u.hp-=r.resistance.hpCost;u.prepared.uses.resistance--;if(card(u)==='C33')u.prepared.flightLoss=(u.prepared.flightLoss||0)+5;
        if(card(u)==='C34'&&!liveObjects(this).length&&!u.prepared.reducedLegendary){u.prepared.legendary=Math.max(0,2-(3-u.prepared.legendary));u.prepared.reducedLegendary=true;}
        const next=copy(p.roll.next);next.result={rolls:p.roll.rolls,kept:p.roll.rolls[0],total:p.roll.dc,dc:p.roll.dc,success:true,legendaryResistance:true};
        log(this,p.actor,'Провал спасброска заменён успехом; цена устойчивости списана.',{cost:r.resistance});this.enqueue(next);
      }else finishRoll.call(this,{...p.roll,preparedResistanceConsidered:true});
    }else if(p.choice==='legendary'){
      if(c.choice==='ability'){
        req(rule(this.unit(c.creature)).actions?.[c.ability]?.cost==='legendary','В этом окне доступны только легендарные действия');
        const rest=this.s.queue;this.s.queue=[];
        resolve(this,c.creature,c.ability,c);
        this.s.queue=[...this.s.queue,task('boundary',p.actor,{ended:p.ended}),...rest];
      }else this.s.prepared.legendaryBoundary=null;
    }else if(p.choice==='parry'||p.choice==='shield'){
      const u=this.unit(p.actor);let resume=p.resume;
      if(c.choice==='yes'){
        req(u.reaction>0&&!this.incapacitated(p.actor),'Реакция недоступна');u.reaction--;
        if(p.choice==='parry')resume={...resume,acBonus:(resume.acBonus||0)+3};
        else resume=this.reduceDamage(resume,12,null,'prepared.shield','Щит Арк-Ома');
        log(this,p.actor,p.choice==='parry'?'Парирование: +3 КД против этого попадания.':'Щит: весь пакет урона уменьшен на 12.');
      }
      this.enqueue(resume);
    }else if(p.choice==='onHit'){
      if(c.choice==='yes'){
        const u=this.unit(p.actor),d=rule(u).actions.grapple;
        log(this,p.actor,'Выбран захват по полной карточке.',{target:p.target});
        const target=this.unit(p.target);req(!d.maxSize||target.size<=d.maxSize,'Цель слишком велика');
        const captives=this.s.order.filter(k=>this.unit(k).statuses.some(z=>z.kind==='grappled'&&z.source===p.actor));
        req(captives.length<d.maxTargets,'Лимит захваченных целей');
        const stat=target.saves.STR>=target.saves.DEX?'STR':'DEX';
        this.enqueue(this.saveTask(p.target,stat,d.dc,task('saveResult',p.actor,{target:p.target,key:'grapple',stat,amount:0,source:p.actor}),{origin:u}));
        if(!d.replaceDamage&&p.resume)this.enqueue(p.resume);
      }else if(p.resume)this.enqueue(p.resume);
    }
  };
  const nativeTask=E.prototype.task;
  E.prototype.task=function(t){
    if(!this.s.prepared)return nativeTask.call(this,t);
    if(t.kind==='preparedTask'){
      if(t.op==='restoreMove')this.unit(t.actor).move=t.budget;
      else if(t.op==='boundary'){
        const boundary=this.s.prepared.legendaryBoundary;
        if(boundary&&this.s.order.some(id=>id!==t.ended&&this.active(id)&&!this.incapacitated(id)&&this.unit(id).prepared?.legendary>0&&!boundary.used.includes(id)))
          this.decision('preparedChoice',t.actor,{choice:'legendary',ended:t.ended,label:'Конец чужого хода: легендарное действие либо продолжить'});
      }else if(t.op==='saveResult'){
        const d=rule(this.unit(t.actor)).actions[t.key]||t.definition,success=t.result.success;
        if(d.op==='saveDamage'){
          if(M){M.apply(this,{actor:t.actor,target:t.target,type:d.damageType,amount:t.amount,stat:t.stat,half:d.half,push:d.push},success);return;}
          let amount=success?(d.half?Math.floor(t.amount/2):0):t.amount;
          if(t.stat==='DEX'&&d.half&&this.unit(t.target).features.evasion&&!this.incapacitated(t.target))amount=success?0:Math.floor(t.amount/2);
          this.enqueue({kind:'damage',actor:t.actor,target:t.target,amount,damageType:d.damageType});
          if(!success&&d.push)log(this,t.actor,'Сдвинуть цель на '+d.push+' фт: подтвердить конечную точку по геометрии.',{target:t.target,manual:true});
        }else if(!success&&d.op==='saveStatus'){
          this.status(t.target,d.condition,{source:t.actor,preparedPause:true,expiresAtStart:t.actor});
          if(d.rooted)this.status(t.target,'rooted',{source:t.actor,preparedPause:true,expiresAtStart:t.actor});
        }else if(!success&&d.op==='grappleSave')this.status(t.target,'grappled',{source:t.actor,dc:d.dc,reach:d.range,preparedGrapple:true});
        else if(!success&&d.op==='pushSave'){if(this.s.prepared?.runtime)M.push(this,t.target,this.unit(t.actor),d.distance);else log(this,t.actor,'Толчок: сдвинуть на '+d.distance+' фт по полной карточке.',{target:t.target,manual:true});}
        if(!success&&d.condition==='poisoned'){
          this.status(t.target,'poisoned',{source:t.actor,preparedPoison:true,expiresOnSourceEnd:t.target,expiresOnSourceEndTurn:this.unit(t.target).turnCount+1});
        }
      }
      return;
    }
    const u=t.actor?this.unit(t.actor):null;
    if(t.kind==='startTurn'){
      if(u?.prepared&&(!u.prepared.active||u.prepared.activateRound>this.s.round)){
        this.enqueue({kind:'endTurn',actor:t.actor,preparedInactive:true});return;
      }
      if(u?.prepared){
        const p=u.prepared,r=rule(u),objects=liveObjects(this);
        if(r.phase&&p.phase===1&&u.hp>0&&(u.hp<=r.phase.threshold||(r.phase.objectsOff!==undefined&&Object.values(this.s.prepared.objects).length-objects.length>=r.phase.objectsOff))){
          p.phase=2;if(r.phase.ac)u.ac=r.phase.ac;if(r.phase.walk)u.speed=r.phase.walk;
          if(r.phase.loseSpell)u.casting.prepared=u.casting.prepared.filter(x=>x!==r.phase.loseSpell);
          log(this,u.id,'Фаза II: ПЗ, реакции, заряды и применения не восстановлены.');
        }
        p.legendary=r.legendary?.max||0;if(card(u)==='C34'&&!objects.length)p.legendary=2;
        if(p.movementMode==='fly')u.speed=(p.phase===2?r.phase?.fly||r.movement.fly:r.movement.fly)-(p.flightLoss||0);
        p.once=[];p.attackSequence=[];
        this.s.zones=this.s.zones.filter(z=>!(z.preparedDust&&z.owner===u.id));
        if(r.recharge&&p.uses[r.recharge.resource]<r.recharge.max&&(!r.recharge.requiresUngroundedRod||(!p.outsideArena&&this.s.prepared.room==='B8'&&objects.some(o=>this.distance(u,o)<=r.recharge.range)))){
          const roll=this.roll(6);log(this,u.id,'Перезарядка: '+roll,{roll});if(roll>=r.recharge.min)p.uses[r.recharge.resource]++;
        }
      }
      if(u)for(const v of Object.values(this.s.units))v.statuses=v.statuses.filter(z=>!(z.preparedPause&&z.expiresAtStart===u.id));
      const current=this.actorId;const v=this.unit(current);
      // startTurn tasks do not carry actor in the stock queue.
      if(!u&&v.prepared){this.task({...t,actor:current});return;}
    }
    if(t.kind==='attackResult'&&card(this.unit(t.target))==='C23'&&!t.preparedParryConsidered&&u&&['melee','meleeSpell'].includes(t.spec.kind)&&this.unit(t.target).reaction>0&&!this.incapacitated(t.target)&&this.canSee(t.target,t.actor)){
      const d=t.result.kept,hit=d===20||(d!==1&&t.result.total>=this.ac(t.target,this.attackOrigin(t),t.spec)+(t.acBonus||0));
      if(hit){this.decision('preparedChoice',t.target,{choice:'parry',resume:{...t,preparedParryConsidered:true},label:'Видимое рукопашное попадание: Парирование +3 КД?'});return;}
    }
    if(t.kind==='weaponDamage'&&!t.preparedOnHitConsidered&&rule(u).actions?.grapple?.cost==='onHit'){
      this.decision('preparedChoice',t.actor,{choice:'onHit',target:t.target,resume:{...t,preparedOnHitConsidered:true},label:'Попадание: применить захват по карточке?'});return;
    }
    if(t.kind==='weaponHitEffects'&&rule(u).onHit?.[t.frame.spec.id]){
      const d=rule(u).onHit[t.frame.spec.id];
      this.enqueue(this.saveTask(t.target,d.stat,d.dc,task('saveResult',t.actor,{target:t.target,key:'poison-on-hit',definition:{...d,op:'poison'},stat:d.stat,amount:0}),{origin:u}));
    }
    if(t.kind==='damage'){
      if(card(this.unit(t.target))==='C34'&&!t.preparedShieldConsidered&&t.attack&&this.unit(t.target).reaction>0&&!this.incapacitated(t.target)&&liveObjects(this).length&&this.canSee(t.target,t.actor)){
        this.decision('preparedChoice',t.target,{choice:'shield',resume:{...t,preparedShieldConsidered:true},label:'Видимое попадание: реакцией уменьшить весь пакет на 12?'});return;
      }
      if(card(this.unit(t.target))==='C34'){
        const target=this.unit(t.target);target.ac=target.prepared.phase===2||liveObjects(this).length<2?17:19;
      }
    }
    const beforeDamage=t.kind==='damage'?this.unit(t.target).hp+this.unit(t.target).temp:null;
    const result=nativeTask.call(this,t);
    if(t.kind==='startTurn'&&u?.prepared&&rule(u).noReaction)u.reaction=0;
    if(beforeDamage!==null&&this.unit(t.target).hp+this.unit(t.target).temp<beforeDamage)this.unit(t.target).statuses=this.unit(t.target).statuses.filter(z=>!z.preparedPause);
    if(t.kind==='damage'&&['C32','C34'].includes(card(this.unit(t.target)))&&this.unit(t.target).hp===0){
      const slave=card(this.unit(t.target))==='C32'?'C36':'C37';
      for(const v of Object.values(this.s.units))if(card(v)===slave)v.prepared.active=false;
    }
    if(t.kind==='moveCompleted'&&u?.prepared?.telegraph&&Math.max(Math.abs(u.x-u.prepared.telegraph.x),Math.abs(u.y-u.prepared.telegraph.y))*5>10){delete u.prepared.telegraph;log(this,u.id,'Подготовка дыхания отменена перемещением больше 10 фт; заряд не потрачен.');}
    if(t.kind==='endTurn'&&u&&!t.preparedInactive){
      this.s.prepared.legendaryBoundary={actor:t.actor,used:[]};
      this.enqueue(task('boundary',this.actorId,{ended:t.actor}));
    }
    return result;
  };
  // Deliberately documented manual surfaces: engine 30.7.1 has no volumetric
  // flight, arbitrary object interaction, innate spell catalogue, or arena AI.
  // The full source card and typed ruling workbench remain available offline.
  return {requirement,resolve,rule,card,log};
}
if(typeof module!=='undefined')module.exports={installPreparedGM};
