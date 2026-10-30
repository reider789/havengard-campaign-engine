/* Perelomye encounter executor. Data stays in the catalogue; the pinned SDK
 * remains untouched. No campaign writes and no automatic player decisions. */
"use strict";
function installPreparedRuntime(SDK, catalogue) {
  const {CombatRulesEngine:E,CombatCampaignAdapter:A,CombatContentPack:P,
    CombatMagic:M,CombatActivities:Activities}=SDK;
  if(E.preparedRuntimeInstalled)return;
  E.preparedRuntimeInstalled=true;
  const requirement='perelomye-runtime-v1',copy=v=>structuredClone(v);
  const req=(v,m)=>{if(!v)throw Error(m);};
  const enabled=e=>!!e.s.prepared?.runtime,rt=e=>e.s.prepared.runtime;
  const profile=u=>u?.prepared?.profile,rules=u=>catalogue.rules[profile(u)]||{};
  const job=(op,actor,data={})=>({kind:'preparedRuntimeTask',op,actor,...data});
  const log=(e,id,text,data={})=>e.emit('preparedRuntime',id,text,{extension:requirement,...data});
  const pos=(e,u)=>{const p=u.worldPosition||u;return {x:p.x,y:p.y,altitude:p.altitude??u.altitude??e.s.terrain.elevation?.[u.x+','+u.y]??ground(e,p),footprint:u.footprint||1};};
  const dist=(e,a,b)=>{a=pos(e,a);b=pos(e,b);return Math.max(Math.abs(a.x-b.x)*5,Math.abs(a.y-b.y)*5,Math.abs(a.altitude-b.altitude));};
  function ground(e,p){
    const t=e.s.prepared.room;
    if(t==='T5'&&p.x>=5&&p.x<=11&&p.y>=4&&p.y<=9)return -20;
    if(t==='T8')return p.x<=3||p.x>=20?10:([4,19].includes(p.x)&&[0,19].includes(p.y)?5:0);
    if(t==='B8'){
      if(p.x<0&&p.y>=9&&p.y<=11)return 0;
      if(p.x<0||p.x>=e.s.terrain.width||p.y<0||p.y>=e.s.terrain.height)return -40;
      if(p.y>=18)return -20;
    }
    return 0;
  }
  const silence=(e,p)=>rt(e).zones.some(z=>z.kind==='silence'&&z.until>e.s.elapsed&&dist(e,p,z.point)<=z.radius);
  const hear=(e,u)=>!e.has(u.id,'deafened')&&!silence(e,u);
  const insideArena=(e,u)=>{const p=pos(e,u);return e.inside(p)&&!u.fled&&!u.prepared?.outsideArena;};
  const live=e=>Object.values(e.s.prepared.objects).filter(o=>e.s.prepared.room==='B8'?!o.grounded:o.hp>0&&!o.off&&!o.suppressed&&!(e.s.prepared.room==='T8'&&silence(e,o)));
  const roll=(e,id,count,sides,flat=0,label='Урон')=>{const rolls=Array.from({length:count},()=>e.roll(sides)),amount=rolls.reduce((a,b)=>a+b,flat);log(e,id,label+': ['+rolls.join(', ')+'] + '+flat+' = '+amount,{rolls,amount});return amount;};
  function lineClear(e,a,b){
    a=pos(e,a);b=pos(e,b);const n=Math.max(Math.abs(b.x-a.x),Math.abs(b.y-a.y))*4;
    for(let i=1;i<n;i++){const f=i/n,x=Math.floor(a.x+(b.x-a.x)*f+.5),y=Math.floor(a.y+(b.y-a.y)*f+.5),key=x+','+y;
      if(e.s.terrain.walls.includes(key)&&a.altitude+(b.altitude-a.altitude)*f<(rt(e).wallHeights[key]??rt(e).ceiling??1000))return false;}
    return true;
  }
  function cone(e,origin,point,length){
    const a=pos(e,origin),p=pos(e,point),v=[(p.x-a.x)*5,(p.y-a.y)*5,p.altitude-a.altitude],vl=Math.hypot(...v);req(vl>0,'Укажите направление');
    return Object.values(e.s.units).filter(u=>!u.dead&&!u.fled&&u.id!==origin.id&&lineClear(e,a,u)).filter(u=>{
      const b=pos(e,u),d=[(b.x-a.x)*5,(b.y-a.y)*5,b.altitude-a.altitude],dl=Math.hypot(...d);
      return dl<=length&&d.reduce((s,x,i)=>s+x*v[i],0)>=dl*vl*Math.SQRT1_2-1e-7;
    }).map(u=>u.id);
  }
  function sync(e){
    for(const o of Object.values(e.s.prepared.objects)){o.preparedObject=true;o.owner||=e.s.order.find(id=>e.unit(id).prepared)||e.s.order[0];o.altitude=ground(e,o);e.s.objects[o.id]=o;}
    for(const u of Object.values(e.s.units))if(u.prepared)u.prepared.silenced=silence(e,u);
    // Grounded rods protect against authored lightning while within ten feet.
    for(const u of Object.values(e.s.units))u.preparedGrounded=Object.values(e.s.prepared.objects).some(o=>o.grounded&&dist(e,u,o)<=10);
  }
  const compile=P.compile;
  P.compile=function(input){const data=copy(input),needs=data.requires?.includes(requirement);if(needs)data.requires=data.requires.filter(x=>x!==requirement);const r=compile.call(this,data);if(needs)r.content_pack=copy(input);return r;};
  E.VERSION='30.9.0';
  const create=A.create;
  A.create=function(runtime,scene,seed){
    const weatherOnly=scene.scene_id==='B8'&&scene.enemies.length===0&&runtime.content_pack?.requires?.includes(requirement);
    const bootstrap=weatherOnly?{...scene,enemies:[{id:'weather-bootstrap',profile:'C03',cell:'A1',initiative:0}]}:scene;
    const s=create.call(this,runtime,bootstrap,seed);
    if(weatherOnly){delete s.units['weather-bootstrap'];delete s.initiative['weather-bootstrap'];s.order=s.order.filter(id=>id!=='weather-bootstrap');s.index=0;}
    if(!s.prepared||scene.prepared_automation===false||!runtime.content_pack?.requires?.includes(requirement))return s;
    const room=catalogue.encounters[scene.scene_id].room;
    s.prepared.runtime={version:1,last20Round:0,wallHeights:{},zones:[],drops:[],openSky:room.ceil===0,ceiling:room.ceil||null,
      inventory:Object.fromEntries(Object.entries(runtime.content_pack.characters).map(([id,c])=>[id,copy(c.inventory||[])])),baseWalk:Object.fromEntries(Object.values(s.units).map(u=>[u.id,u.speed]))};
    s.engineVersion=E.VERSION;
    for(const u of Object.values(s.units))u.altitude=ground({s},u);
    // Objects are installed without constructing an engine, avoiding recursive validation.
    for(const o of Object.values(s.prepared.objects)){Object.assign(o,{preparedObject:true,owner:s.order.find(id=>s.units[id].prepared)||s.order[0],altitude:ground({s},o)});s.objects[o.id]=o;}
    return s;
  };
  const validateMagic=M.validateState;
  M.validateState=function(s){if(!s.prepared?.runtime)return validateMagic.call(this,s);const data=copy(s);data.objects=Object.fromEntries(Object.entries(data.objects||{}).filter(([,o])=>!o.preparedObject));return validateMagic.call(this,data);};
  const continuations=E.validateContinuations;
  const ops=new Set(['arena','arenaMark','save','interact','dispel','move','fall','land','objectHit','objectDamage']);
  E.validateContinuations=function(s){
    if(!s.prepared?.runtime)return continuations.call(this,s);
    const data=copy(s),extra=[];
    const visit=v=>{
      if(!v||typeof v!=='object')return v;
      if(v.kind==='preparedRuntimeTask'){
        req(ops.has(v.op)&&s.units[v.actor],'Повреждён шаг исполнителя');
        if(v.target)req(s.units[v.target],'Нет цели шага');
        if(v.object)req(s.prepared.objects[v.object],'Нет прибора');
        if(v.op==='move')req(Array.isArray(v.path)&&v.path.length<=1000&&v.path.every(p=>Number.isInteger(p.x)&&Number.isInteger(p.y)&&Number.isInteger(p.altitude)&&p.altitude%5===0),'Повреждён маршрут');
        if(v.op==='save')req(Number.isInteger(v.amount)&&v.amount>=0&&['arena','chord','pause','breath','wings','push'].includes(v.key),'Повреждён исход');
        return {kind:'startTurn'};
      }
      if(v.kind==='preparedRuntimeChoice'){
        req(['arenaMark','water'].includes(v.choice)&&s.units[v.actor],'Повреждено окно исполнителя');
        if(v.resume)extra.push(visit(copy(v.resume)));return null;
      }
      if(Array.isArray(v))return v.map(visit);
      for(const k of Object.keys(v))v[k]=visit(v[k]);return v;
    };
    visit(data);data.queue.push(...extra);continuations.call(this,data);
  };
  const validate=E.validate;
  E.validate=function(s){
    if(s.prepared?.runtime){const r=s.prepared.runtime;req(r.version===1&&Number.isInteger(r.last20Round)&&r.last20Round>=0&&r.last20Round<=s.round,'Повреждена отметка инициативы');
      req(Array.isArray(r.zones)&&r.zones.every(z=>z.kind==='silence'&&Number.isFinite(z.until)&&Number.isFinite(z.radius)&&z.radius>=0&&z.radius<=1000&&Number.isInteger(z.point?.x)&&Number.isInteger(z.point?.y)),'Повреждены внешние зоны');
      for(const o of Object.values(s.prepared.objects))req(o.id&&Number.isInteger(o.ac)&&o.ac>0&&o.max>=o.hp,'Повреждён прибор');
      for(const u of Object.values(s.units))if(u.worldPosition)req(r.openSky&&Number.isInteger(u.worldPosition.x)&&Number.isInteger(u.worldPosition.y)&&Number.isInteger(u.worldPosition.altitude),'Повреждена мировая позиция');
    }
    return validate.call(this,s);
  };
  const distance=E.prototype.distance,wallLOS=E.prototype.wallLOS;
  E.prototype.distance=function(a,b){return enabled(this)?dist(this,a,b):distance.call(this,a,b);};
  E.prototype.wallLOS=function(a,b){return enabled(this)?lineClear(this,a,b):wallLOS.call(this,a,b);};
  const globe=M.globeBlocked;
  M.globeBlocked=function(e,f,target){
    if(!enabled(e))return globe.call(this,e,f,target);
    const v=typeof target==='string'&&target.startsWith('object:')?e.s.objects[target.slice(7)]:e.s.units[target],origin=f.castOrigin||e.s.units[f.actor];
    return !!v&&Number.isInteger(f.level)&&e.s.effects.some(x=>x.kind==='globeInvulnerability'&&x.until>e.s.elapsed&&f.level<x.level&&dist(e,v,x.point)<=10&&dist(e,origin,x.point)>10);
  };
  const areaTargets=M.areaTargets;
  M.areaTargets=function(e,f,range,shape='radius'){
    if(!enabled(e))return areaTargets.call(this,e,f,range,shape);
    if(shape==='cone')return cone(e,e.unit(f.actor),f.point,range);
    if(shape==='radius')return Object.values(e.s.units).filter(u=>!u.dead&&!u.fled&&Math.hypot((pos(e,u).x-f.point.x)*5,(pos(e,u).y-f.point.y)*5,pos(e,u).altitude-(f.point.altitude??ground(e,f.point)))<=range&&lineClear(e,f.point,u)).map(u=>u.id);
    return areaTargets.call(this,e,f,range,shape);
  };
  for(const [id,key] of [['preparedChord','chord'],['preparedPause','pause']]){
    const d=catalogue.rules.C32.actions[key];Activities.SPELLS[id]={name:d.name,level:3,cost:'action',range:d.range||0,target:key==='chord'?'direction':'enemy',school:key==='chord'?'evocation':'enchantment'};
    M.SPELLS[id]=[d.name,3,'action',d.range||0,key==='chord'?'direction':'enemy',key==='chord'?'evocation':'enchantment',0];
  }
  function targets(e,u,key,c){
    const d=rules(u).actions[key];
    if(d.shape==='cone')return cone(e,u,c.point,d.length);
    if(d.radius)return Object.values(e.s.units).filter(v=>v.id!==u.id&&!v.dead&&!v.fled&&dist(e,u,v)<=d.radius&&lineClear(e,u,v)).map(v=>v.id);
    if(d.shape==='line'){
      const a=pos(e,u),p=pos(e,c.point),dx=(p.x-a.x)*5,dy=(p.y-a.y)*5,dz=p.altitude-a.altitude,len=Math.hypot(dx,dy,dz);req(len>0,'Укажите направление');
      return Object.values(e.s.units).filter(v=>v.id!==u.id&&!v.dead&&!v.fled&&lineClear(e,a,v)).filter(v=>{const b=pos(e,v),x=(b.x-a.x)*5,y=(b.y-a.y)*5,z=b.altitude-a.altitude,forward=(x*dx+y*dy+z*dz)/len;return forward>=0&&forward<=d.length&&Math.sqrt(Math.max(0,x*x+y*y+z*z-forward*forward))<=d.width/2;}).map(v=>v.id);
    }
    return c.targets||[];
  }
  function innate(e,u,key,c){
    const d=rules(u).actions[key];req(profile(u)==='C32'&&e.active(u.id)&&!e.incapacitated(u.id),'Заклинание недоступно');
    req(!silence(e,u),'Вербальный компонент запрещён Тишиной');
    const ids=targets(e,u,key,c);req(ids.every(id=>e.s.units[id]),'Нет цели');
    if(key==='pause')req(ids.length===1&&dist(e,u,e.unit(ids[0]))<=90&&e.canSee(u.id,ids[0])&&hear(e,e.unit(ids[0])),'Нужна видимая слышащая цель в 90 фт');
    req(u.prepared.uses[d.resource]>0,'Применения исчерпаны');
    M.beforeCommand(e,{kind:'cast',actor:u.id,spell:'fireball'},u);e.spendAction(u.id,true);u.prepared.uses[d.resource]--;
    const f={id:'spell-'+(++e.s.sequence),actor:u.id,spell:key==='chord'?'preparedChord':'preparedPause',level:3,targets:ids,point:c.point?copy(c.point):undefined,
      castOrigin:pos(e,u),preparedKey:key,paidSlot:false,offered:[],cancelled:false};
    e.s.spellFrames[f.id]=f;log(e,u.id,d.name,{spell:f.spell,targets:ids,point:f.point});e.enqueue(M.task(u.id,'window',{frame:f.id}));
  }
  const before=M.beforeCommand;
  M.beforeCommand=function(e,c,u){if(enabled(e)&&c.kind==='cast'&&silence(e,u)&&!['counterspell'].includes(c.spell))throw Error('Вербальный компонент запрещён Тишиной');return before.call(this,e,c,u);};
  const eligible=M.eligibleCounter;
  M.eligibleCounter=function(e,f){return eligible.call(this,e,f).filter(id=>!enabled(e)||!silence(e,e.unit(id)));};
  const resolveSpell=M.resolve;
  M.resolve=function(e,f){
    if(!enabled(e))return resolveSpell.call(this,e,f);
    if(f.preparedKey){
      const d=catalogue.rules.C32.actions[f.preparedKey],ids=f.targets.filter(id=>!M.globeBlocked(e,f,id));
      const amount=d.dice?roll(e,f.actor,...d.dice,d.name):0;
      e.enqueue(...ids.map(target=>e.saveTask(target,d.stat,d.dc,job('save',f.actor,{target,key:f.preparedKey,amount}),{origin:f.castOrigin})));return;
    }
    if(f.spell==='dispelMagic'&&f.dispelTarget?.kind==='object'&&e.s.prepared.objects[f.dispelTarget.id]){
      const object=f.dispelTarget.id;req(e.s.prepared.room!=='B8','Природная опора не заклинание');
      if(M.globeBlocked(e,f,'object:'+object))return;
      const level=e.s.prepared.room==='T8'?3:4;
      if(f.level>=level)e.enqueue(job('dispel',f.actor,{object}));
      else e.enqueue({kind:'roll',actor:f.actor,count:1,sides:20,bonus:e.unit(f.actor).stats[e.unit(f.actor).casting.ability],dc:10+level,label:'Рассеивание питания',next:job('dispel',f.actor,{object})});return;
    }
    if(f.preparedObjects){
      const u=e.unit(f.actor);let empowered=M.empowered(e,f);
      for(const object of f.preparedObjects){const o=e.s.prepared.objects[object];if(!o||o.hp<=0||M.globeBlocked(e,f,'object:'+object))continue;
        const count=f.spell==='fireBolt'?(u.level>=17?4:u.level>=11?3:u.level>=5?2:1):2;
        const spec={id:f.spell,name:M.SPELLS[f.spell][0],kind:'rangedSpell',count,die:f.spell==='fireBolt'?10:6,flat:empowered,bonus:u.casting.attack,damageType:'fire'};empowered=0;
        const dis=e.enemies(u.id).some(id=>!e.incapacitated(id)&&dist(e,u,e.unit(id))<=5&&e.canSee(id,u.id));
        e.enqueue({kind:'roll',actor:u.id,count:1,sides:20,mode:dis?-1:0,bonus:spec.bonus,attackRoll:true,label:spec.name+' → '+o.name,next:job('objectHit',u.id,{object,spec,potent:f.spell==='fireBolt'&&!!u.features.potentCantrip})});}
      return;
    }
    return resolveSpell.call(this,e,f);
  };
  const magicTask=M.taskRun;
  M.taskRun=function(e,t){
    if(enabled(e)&&t.kind==='magicTask'&&t.op==='window'){
      const f=M.frame(e,t.frame),id=!f.cancelled&&M.eligibleCounter(e,f)[0];
      if(id){M.choice(e,id,'counterspell',['yes','no'],{frame:f.id});return true;}
    }
    if(enabled(e)&&t.kind==='magicTask'&&['objectHit','objectDamage'].includes(t.op)&&e.s.prepared.objects[t.object]){e.task({...t,kind:'preparedRuntimeTask'});return true;}
    const r=magicTask.call(this,e,t);if(enabled(e))sync(e);return r;
  };
  // Preserve the real cast and reaction frame while allowing the two spells
  // whose authored target type includes an object. Proxies exist for validation only.
  const validateSpell=M.validate;
  M.validate=function(e,c,u){
    if(!enabled(e))return validateSpell.call(this,e,c,u);
    if(c.spell==='dispelMagic'&&c.dispelTarget?.kind==='object'&&e.s.prepared.objects[c.dispelTarget.id])req(e.s.prepared.room!=='B8','Природная опора не заклинание');
    const ids=c.targets||[c.target];
    if(!['fireBolt','scorchingRay'].includes(c.spell)||!ids.some(id=>String(id).startsWith('object:')))return validateSpell.call(this,e,c,u);
    req(ids.every(id=>String(id).startsWith('object:')),'В этом действии выберите только приборы');
    const inserted=[];
    try{for(const id of new Set(ids)){const o=e.s.prepared.objects[id.slice(7)];req(o&&o.hp>0,'Предмет разрушен');e.s.units[id]={...copy(u),id,name:o.name,team:u.team==='heroes'?'enemies':'heroes',hp:o.hp,max:o.max,ac:o.ac,x:o.x,y:o.y,altitude:o.altitude,controlled:false,dead:false,fled:false};inserted.push(id);}
      const f=validateSpell.call(this,e,c,u);f.preparedObjects=ids.map(id=>id.slice(7));f.targets=[];return f;
    }finally{for(const id of inserted)delete e.s.units[id];}
  };
  function capable(e){const boss={T8:'C32',P9:'C34'}[e.s.prepared.room];return !boss||Object.values(e.s.units).some(u=>profile(u)===boss&&e.active(u.id)&&!e.incapacitated(u.id)&&insideArena(e,u));}
  function arenaTargets(e,mark){
    const source=e.s.prepared.objects[mark.source],room=e.s.prepared.room,p=mark.point,a=pos(e,source),b=pos(e,p),dx=(b.x-a.x)*5,dy=(b.y-a.y)*5,len=Math.hypot(dx,dy);
    return Object.values(e.s.units).filter(u=>!u.dead&&!u.fled).filter(u=>{
      const v=pos(e,u);if(room==='P9'){if(!len)return false;const vx=(v.x-a.x)*5,vy=(v.y-a.y)*5,forward=(vx*dx+vy*dy)/len,side=Math.abs(vx*dy-vy*dx)/len;return forward>=0&&forward<=60&&side<=5&&Math.abs(v.altitude-a.altitude)<=5&&lineClear(e,a,v);}
      const radial=Math.hypot((v.x-b.x)*5,(v.y-b.y)*5)<=10;
      return radial&&(room==='B8'?v.altitude>=b.altitude&&v.altitude<=b.altitude+60:Math.abs(v.altitude-b.altitude)<=10&&hear(e,u))&&lineClear(e,b,v);
    }).map(u=>u.id);
  }
  function arena(e,actor){
    const old=e.s.prepared.environment;e.s.prepared.environment=null;
    e.enqueue(job('arenaMark',actor));
    if(!old||!capable(e)||!live(e).some(o=>o.id===old.source))return;
    const d={T8:{stat:'WIS',dc:17,dice:[3,8,0],damageType:'psychic'},P9:{stat:'DEX',dc:18,dice:[5,8,0],damageType:'force'},B8:{stat:'DEX',dc:18,dice:[4,8,0],damageType:'lightning'}}[e.s.prepared.room],amount=roll(e,actor,...d.dice,'Удар арены');
    e.enqueue(...arenaTargets(e,old).map(target=>e.saveTask(target,d.stat,d.dc,job('save',actor,{target,key:'arena',amount,definition:d}),{origin:e.s.prepared.objects[old.source]})));
  }
  const choose=E.prototype.resolveDecision;
  E.prototype.resolveDecision=function(c){
    const p=this.s.pending;
    if(!enabled(this)||p?.kind!=='preparedRuntimeChoice')return choose.call(this,c);
    req(c.id===p.id,'Устаревшее решение');
    if(p.choice==='arenaMark'){
      req(['mark','skip'].includes(c.choice),'Отметить или пропустить');
      if(c.choice==='mark'){
        const o=this.s.prepared.objects[c.object];req(o&&live(this).includes(o)&&capable(this),'Источник не работает');
        req(c.point&&Number.isInteger(c.point.x)&&Number.isInteger(c.point.y)&&this.inside(c.point),'Укажите клетку области');
        if(this.s.prepared.room!=='P9')req(dist(this,o,c.point)<=30,'Область дальше 30 фт от источника');
        else req(c.point.x!==o.x||c.point.y!==o.y,'Укажите направление полосы');
        this.s.prepared.environment={source:o.id,point:pos(this,c.point),dueRound:this.s.round+1};log(this,p.actor,'Область отмечена до следующей инициативы 20.',{mark:copy(this.s.prepared.environment)});
      }
      this.s.pending=null;return;
    }
    if(p.choice==='water'){
      req(['skip','athletics','acrobatics'].includes(c.choice),'Выберите реакцию на падение в воду');this.s.pending=null;
      if(c.choice==='skip'){this.enqueue(p.resume);return;}
      const u=this.unit(p.actor);req(u.reaction>0&&M.canReact(this,u.id),'Реакция недоступна');u.reaction--;
      const stat=c.choice==='athletics'?'STR':'DEX';this.enqueue({kind:'roll',actor:u.id,count:1,sides:20,check:true,bonus:u.skills?.[c.choice]??u.stats[stat],dc:15,label:'Падение в воду',next:{...p.resume,waterCheck:true}});return;
    }
  };
  function speed(e,u,mode){
    if(mode==='fly'){const f=M.effects(e,u.id,'fly').length;return f?60:((u.prepared?.phase===2?rules(u).phase?.fly:0)||rules(u).movement?.fly||0)-(u.prepared?.flightLoss||0);}
    const walk=(u.prepared?.phase===2?rules(u).phase?.walk:0)||rules(u).movement?.walk||rt(e).baseWalk[u.id]||u.speed;
    return mode==='walk'?walk:rules(u).movement?.[mode]||walk;
  }
  function setpos(e,u,p){u.altitude=p.altitude;if(e.inside(p)){u.x=p.x;u.y=p.y;delete u.worldPosition;}else{req(rt(e).openSky,'Поле закрыто');u.worldPosition=copy(p);u.x=Math.max(0,Math.min(e.s.terrain.width-(u.footprint||1),p.x));u.y=Math.max(0,Math.min(e.s.terrain.height-(u.footprint||1),p.y));}}
  function movement(e,u,c,budget){
    req(Array.isArray(c.path)&&c.path.length>0&&c.path.length<=1000,'Нужен пошаговый путь');
    const mode=c.mode||u.preparedMovementMode||'walk',s=speed(e,u,mode);req(['walk','fly','climb','swim'].includes(mode)&&s>0,'Нет такой скорости');
    let from=pos(e,u),cost=0;
    const path=c.path.map(p=>{p={x:p.x,y:p.y,altitude:p.altitude??(mode==='fly'?from.altitude:ground(e,p))};
      req(Number.isInteger(p.x)&&Number.isInteger(p.y)&&Number.isInteger(p.altitude)&&p.altitude%5===0,'Высота кратна 5 фт');
      req(Math.max(Math.abs(p.x-from.x),Math.abs(p.y-from.y),Math.abs(p.altitude-from.altitude)/5)<=1||mode==='walk'&&Math.max(Math.abs(p.x-from.x),Math.abs(p.y-from.y))===1&&p.altitude<from.altitude,'Путь должен состоять из соседних клеток');
      req(rt(e).openSky||e.inside(p),'Поле закрыто');req(!rt(e).ceiling||p.altitude+(u.footprint||1)*5<=rt(e).ceiling,'Свод мешает полёту');
      req(lineClear(e,from,p),'Путь пересекает стену');
      if(mode==='walk')req(p.altitude===ground(e,p),'Для подъёма выберите лазание или полёт');
      const multiplier=['climb','swim'].includes(mode)&&!rules(u).movement?.[mode]?2:1;
      cost+=5*multiplier;from=p;return p;});
    const spent=u.preparedDistanceSpent||0,remaining=budget??Math.max(0,s-spent);
    req(cost<=remaining,'Недостаточно перемещения');
    if(budget===undefined){u.speed=s;u.move=remaining;u.preparedMovementMode=mode;}
    e.enqueue(job('move',u.id,{path,mode,provoked:[],...(budget===undefined?{}:{budget})}));
  }
  E.prototype.preparedRuntimeMove=function(id,path,budget){const u=this.unit(id);movement(this,u,{path,mode:rules(u).actions['legend-move']?.halfFly?'fly':u.preparedMovementMode||'walk'},budget);};
  E.prototype.preparedRuntimeTargets=function(id,key,c){const u=this.unit(id),d=rules(u).actions[key];
    if(d?.op==='command')req(!silence(this,u)&&c.ally&&hear(this,this.unit(c.ally)),'Приказ должен быть слышен');
    return d?.shape||d?.radius?{...c,targets:targets(this,u,key,c),confirmed:true}:c;
  };
  function fall(e,u){
    const p=pos(e,u),height=p.altitude-ground(e,p),supported=u.preparedMovementMode==='fly'&&speed(e,u,'fly')>0&&!e.incapacitated(u.id)&&!e.has(u.id,'prone')&&e.speed(u.id)>0,
      hover=M.effects(e,u.id,'fly').length>0;
    if(height<=0||supported||hover||u.preparedMovementMode==='climb'&&!e.incapacitated(u.id)||e.s.queue.some(t=>t.kind==='preparedRuntimeTask'&&['fall','land'].includes(t.op)&&t.actor===u.id)||e.s.pending?.choice==='water'&&e.s.pending.actor===u.id)return;
    e.enqueue(job('fall',u.id,{height}));
  }
  const command=E.prototype.command;
  E.prototype.command=function(c,u){
    if(!enabled(this))return command.call(this,c,u);sync(this);
    if(c.kind==='preparedZone'){
      req(c.source&&c.point&&Number.isInteger(c.radius)&&c.radius>0&&c.radius<=100&&Number.isFinite(c.until)&&c.until>this.s.elapsed,'Нужны источник и срок уже разрешённой Тишины');
      req(c.zone==='silence','Поддерживается только внешняя Тишина');rt(this).zones.push({kind:'silence',point:pos(this,c.point),radius:c.radius,until:c.until,source:String(c.source)});sync(this);return;
    }
    if(c.kind==='preparedInteract'){
      const o=this.s.prepared.objects[c.object];req(o&&dist(this,u,o)<=5,'Подойдите к прибору');const room=this.s.prepared.room;
      if(room==='B8'){
        if(o.hp===0){req(JSON.stringify(rt(this).inventory[u.id]).match(/цепь|chain/i),'Нужна настоящая цепь 30 фт');o.groundActions=(o.groundActions||0)+1;}
        this.spendAction(u.id);if(o.hp>0||o.groundActions>=2)o.grounded=true;
      }else if(room==='P9'&&o.open){this.spendAction(u.id);o.off=true;}
      else{
        req(c.method==='arcana'&&room==='T8'||c.method==='tools'&&JSON.stringify(rt(this).inventory[u.id]).match(/thieves|воров|вора/i),'Нужна Аркана или настоящие инструменты вора');
        this.spendAction(u.id);const bonus=c.method==='arcana'?(u.skills?.arcana??u.stats.INT):u.stats.DEX+(u.prof||0);
        this.enqueue({kind:'roll',actor:u.id,count:1,sides:20,check:true,bonus,dc:16,label:'Отключение прибора',next:job('interact',u.id,{object:o.id})});
      }sync(this);return;
    }
    if(c.kind==='preparedRecover'){
      const d=rt(this).drops.find(d=>d.id===c.drop);req(d&&d.owner===u.id&&dist(this,u,d)<=5,'Собственное оружие недоступно');
      if(u.preparedInteractionTurn===this.s.turnSerial)this.spendAction(u.id);u.preparedInteractionTurn=this.s.turnSerial;
      u.prepared.ammo[d.weapon]++;rt(this).drops=rt(this).drops.filter(x=>x!==d);return;
    }
    if(c.kind==='preparedMove'||c.kind==='move'){movement(this,u,c);return;}
    if(c.kind==='preparedEndTurn'){
      req(profile(u)==='C33'&&c.point,'Укажите направление дыхания');cone(this,u,c.point,60);
      u.prepared.telegraph={round:this.s.round,...pos(this,u),point:pos(this,c.point)};log(this,u.id,'Подготовлено дыхание',{telegraph:copy(u.prepared.telegraph)});this.enqueue({kind:'endTurn',actor:u.id});return;
    }
    if(c.kind==='prepared'){
      const key=c.ability,d=rules(u).actions?.[key];req(d,'Неизвестная способность');
      if(d.spell){innate(this,u,key,c);return;}
      if(d.requiresTelegraph){const t=u.prepared.telegraph;req(t&&t.round===this.s.round-1,'Дыхание не было объявлено в конце предыдущего хода');
        req(dist(this,u,t)<=10,'Подготовка дыхания сорвана перемещением');const a=pos(this,u),p=c.point||t.point,v=[p.x-a.x,p.y-a.y,(p.altitude-a.altitude)/5],w=[t.point.x-t.x,t.point.y-t.y,(t.point.altitude-t.altitude)/5];
        req(v.reduce((s,x,i)=>s+x*w[i],0)>=Math.hypot(...v)*Math.hypot(...w)*Math.SQRT1_2-1e-7,'Поворот дыхания больше 45 градусов');
      }
      if(d.op==='command')req(!silence(this,u)&&c.ally&&hear(this,this.unit(c.ally)),'Приказ должен быть слышен');
      if(d.shape||d.radius){const actual=targets(this,u,key,{...c,point:c.point||u.prepared.telegraph?.point});
        if(!actual.length){req(u.prepared.uses[d.resource]>0,'Применения исчерпаны');this.spendAction(u.id);u.prepared.uses[d.resource]--;delete u.prepared.telegraph;return;}
        return command.call(this,{...c,point:c.point||u.prepared.telegraph?.point,targets:actual,confirmed:true,telegraphValid:true},u);}
    }
    if(c.kind==='attack'&&['C05','C05_company'].includes(profile(u))&&c.weapon==='spear')req(u.prepared.ammo['spear-thrown']>0,'Копья закончились: подберите своё');
    return command.call(this,c,u);
  };
  const checkEnd=E.prototype.checkEnd;
  E.prototype.checkEnd=function(){if(enabled(this)&&this.s.prepared.room==='B8'&&live(this).length&&Object.values(this.s.units).some(u=>u.controlled&&!u.dead&&!u.fled))return;return checkEnd.call(this);};
  const push=M.push;
  M.push=function(e,id,from,feet){if(!enabled(e))return push.call(this,e,id,from,feet);const u=e.unit(id),a=pos(e,from),b=pos(e,u),dx=Math.sign(b.x-a.x),dy=Math.sign(b.y-a.y);if(!dx&&!dy)return;
    for(let n=0;n<feet/5;n++){const p={x:pos(e,u).x+dx,y:pos(e,u).y+dy,altitude:pos(e,u).altitude};if(!rt(e).openSky&&!e.inside(p)||!lineClear(e,u,p))break;setpos(e,u,p);if(p.altitude-ground(e,p)>=10){e.enqueue(job('fall',id,{height:p.altitude-ground(e,p)}));break;}}
  };
  const task=E.prototype.task;
  E.prototype.task=function(t){
    if(!enabled(this))return task.call(this,t);const u=t.actor?this.unit(t.actor):null;sync(this);
    if(t.kind==='preparedRuntimeTask'){
      if(t.op==='arena'){arena(this,t.actor);return;}
      if(t.op==='arenaMark'){if(capable(this)&&live(this).length)this.decision('preparedRuntimeChoice',t.actor,{choice:'arenaMark',label:'Инициатива 20: источник и область либо пропустить'});return;}
      if(t.op==='interact'){if(t.result.success){const o=this.s.prepared.objects[t.object];if(this.s.prepared.room==='P9')o.open=true;else o.off=true;}return;}
      if(t.op==='dispel'){if(!t.result||t.result.success){const o=this.s.prepared.objects[t.object];if(this.s.prepared.room==='T8')o.off=true;else{o.suppressed=true;o.suppression={actor:t.actor,turn:this.unit(t.actor).turnCount+1};}}return;}
      if(t.op==='save'){
        const d=t.definition||catalogue.rules.C32.actions[t.key],success=t.result.success;
        if(t.key==='pause'){if(!success){this.status(t.target,'incapacitated',{source:t.actor,preparedPause:true,expiresAtStart:t.actor});this.status(t.target,'rooted',{source:t.actor,preparedPause:true,expiresAtStart:t.actor});}}
        else M.apply(this,{actor:t.actor,target:t.target,type:d.damageType,amount:t.amount,stat:d.stat,half:d.half??true},success);return;
      }
      if(t.op==='objectHit'){
        const o=this.s.prepared.objects[t.object],hit=t.result.kept===20||t.result.kept!==1&&t.result.total>=o.ac,critical=t.result.kept===20;
        log(this,t.actor,t.spec.name+' → '+o.name+': '+t.result.total+' против КД '+o.ac+(hit?' — попадание':' — промах'),{object:o.id,hit,critical});
        if(hit||t.potent)this.enqueue({kind:'roll',actor:t.actor,count:t.spec.count*(critical?2:1),sides:t.spec.die,bonus:t.spec.flat||0,minimumDie:u.features.greatWeaponFighting&&t.spec.twoHanded?3:0,label:'Урон прибору',next:job('objectDamage',t.actor,{object:t.object,spec:t.spec,half:!hit})});return;
      }
      if(t.op==='objectDamage'){
        const o=this.s.prepared.objects[t.object],multiplier=t.spec.id==='forgeMaul'&&u.equipment?.forgeAttuned?2:1,amount=Math.floor(t.result.total*multiplier/(t.half?2:1));o.hp=Math.max(0,o.hp-amount);log(this,t.actor,o.name+': '+amount+' урона, осталось '+o.hp+' ПЗ',{object:o.id,amount});sync(this);return;
      }
      if(t.op==='move'){
        if(!t.path.length||!this.active(u.id)||this.speed(u.id)===0)return;
        const p=t.path[0],from=pos(this,u),cost=5*(['climb','swim'].includes(t.mode)&&!rules(u).movement?.[t.mode]?2:1);
        if((t.budget??u.move)<cost||!lineClear(this,from,p))return;
        const collision=Object.values(this.s.units).some(v=>v.id!==u.id&&!v.dead&&!v.fled&&!rules(v).sharedSpace&&!rules(u).sharedSpace&&Math.abs(pos(this,v).altitude-p.altitude)<5&&p.x<pos(this,v).x+(v.footprint||1)&&p.x+(u.footprint||1)>pos(this,v).x&&p.y<pos(this,v).y+(v.footprint||1)&&p.y+(u.footprint||1)>pos(this,v).y);
        req(!collision,'Площадь занята существом');
        if(!u.disengaged){const enemy=this.enemies(u.id).find(id=>!t.provoked.includes(id)&&this.unit(id).reaction>0&&M.canReact(this,id)&&!this.incapacitated(id)&&this.canSee(id,u.id)&&this.unit(id).attacks.some(a=>a.kind==='melee'&&dist(this,from,this.unit(id))<=a.range&&dist(this,p,this.unit(id))>a.range));
          if(enemy){const attack={kind:'attackRoll',actor:enemy,target:u.id,spec:this.unit(enemy).attacks.find(a=>a.kind==='melee'&&dist(this,from,this.unit(enemy))<=a.range&&dist(this,p,this.unit(enemy))>a.range),mode:'reaction'};
            t.provoked.push(enemy);this.decision('opportunity',enemy,{attack,movement:t});return;}}
        if(t.budget!==undefined)t.budget-=cost;else{u.move-=cost;u.preparedDistanceSpent=(u.preparedDistanceSpent||0)+cost;}
        setpos(this,u,p);log(this,u.id,'Перемещение: '+p.x+','+p.y+'; высота '+p.altitude+' фт',{from,to:p,cost});
        if(t.mode==='walk'&&from.altitude-p.altitude>=10){u.altitude=from.altitude;this.enqueue(job('fall',u.id,{height:from.altitude-p.altitude}));return;}
        this.enqueue({kind:'moveCompleted',actor:u.id},{...t,path:t.path.slice(1),provoked:[]});M.moved(this,u.id);return;
      }
      if(t.op==='fall'){
        const p=pos(this,u),height=Math.max(0,p.altitude-ground(this,p)),amount=roll(this,u.id,Math.min(20,Math.floor(height/10)),6,0,'Падение'),water=ground(this,p)===-40&&this.s.prepared.room==='B8';
        const resume=job('land',u.id,{amount,point:{...p,altitude:ground(this,p)}});
        if(water&&u.reaction>0&&M.canReact(this,u.id))this.decision('preparedRuntimeChoice',u.id,{choice:'water',label:'Падение в воду: реакция Атлетика / Акробатика либо пропустить',resume});else this.enqueue(resume);return;
      }
      if(t.op==='land'){
        const amount=t.waterCheck&&t.result.success?Math.floor(t.amount/2):t.amount;setpos(this,u,t.point);u.preparedMovementMode='walk';u.speed=speed(this,u,'walk');u.move=Math.max(0,u.speed-(u.preparedDistanceSpent||0));
        this.enqueue({kind:'damage',actor:u.id,target:u.id,amount,damageType:'bludgeoning',preparedFall:true});return;
      }
    }
    if(t.kind==='startTurn'){
      const id=this.actorId,round=this.s.round,initiative=this.s.initiative[id],due=initiative<20?round:round-1;
      if(['T8','P9','B8'].includes(this.s.prepared.room)&&due>rt(this).last20Round){rt(this).last20Round=due;this.enqueue(job('arena',id),t);return;}
      rt(this).zones=rt(this).zones.filter(z=>z.until>this.s.elapsed);this.unit(id).preparedDistanceSpent=0;
    }
    if(t.kind==='endTurn')for(const o of Object.values(this.s.prepared.objects))if(o.suppression?.actor===t.actor&&this.unit(t.actor).turnCount>=o.suppression.turn){o.suppressed=false;delete o.suppression;}
    const beforeHP=t.kind==='damage'?this.unit(t.target).hp+this.unit(t.target).temp:0;
    // Damaged rods still conduct: temporarily count them for the authored recharge.
    const rods=t.kind==='startTurn'&&this.s.prepared.room==='B8'?Object.values(this.s.prepared.objects).filter(o=>!o.grounded&&o.hp===0):[];
    for(const o of rods){o.hp=1;o.runtimeBroken=true;}
    if(t.kind==='damage'&&this.unit(t.target).preparedGrounded&&((t.damageType==='lightning')||t.components?.some(c=>c.damageType==='lightning'))){
      if(t.components)t={...t,components:t.components.map(c=>({...c,amount:c.damageType==='lightning'?Math.floor(c.amount/2):c.amount}))};else t={...t,amount:Math.floor(t.amount/2)};
      if(t.components)t.amount=t.components.reduce((s,c)=>s+c.amount,0);
    }
    const result=task.call(this,t);
    for(const o of rods){o.hp=0;delete o.runtimeBroken;}
    if(t.kind==='damage'&&t.preparedFall&&this.unit(t.target).hp+this.unit(t.target).temp<beforeHP)this.status(t.target,'prone');
    if(t.kind==='attackRoll'&&u?.prepared&&t.spec.id==='spear-thrown')rt(this).drops.push({id:'drop-'+(++this.s.sequence),owner:u.id,weapon:'spear-thrown',...pos(this,this.unit(t.target))});
    for(const v of Object.values(this.s.units))fall(this,v);
    sync(this);return result;
  };
  const outcome=A.outcome;
  A.outcome=function(state){
    if(!state.prepared?.runtime)return outcome.call(this,state);
    const s=copy(state);
    for(const u of Object.values(s.units))u.statuses=u.statuses.filter(z=>!z.preparedPause&&!z.preparedPoison).map(z=>{const {preparedGrapple,reach,...rest}=z;return rest;});
    const result=outcome.call(this,s);result.prepared_encounter={room:state.prepared.room,objects:copy(state.prepared.objects),environment:copy(state.prepared.environment),zones:copy(state.prepared.runtime.zones),drops:copy(state.prepared.runtime.drops),partyPositions:Object.fromEntries(Object.values(state.units).filter(u=>u.controlled).map(u=>[u.id,pos({s:state},u)])),opponents:copy(Object.fromEntries(Object.entries(state.units).filter(([,u])=>u.prepared)))};return result;
  };
  return {requirement,pos,ground,dist,cone,live,sync,movement};
}
if(typeof module!=='undefined')module.exports={installPreparedRuntime};
