// Advanced spells, staged saves, Indomitable and Bigby's Hand. Runtime state remains serialized.
class CombatSpellResolver {
  execute(d){const id=turn(),u=me(),k=d.key,t=d.target,p=d.point||{x:u.x,y:u.y};const error=v18TargetCheck(d);if(error){s.info=error;render();return false}v18Cost(id,k);let amount=0;log(names[id]+' использует «'+(v18Catalogue[id].find(z=>z[0]===k)?.[1]||k)+'».');
   switch(k){
   case 'know':{const enemy=s.units[t];log('Анализ '+names[t]+': броня '+AC(t)+', ПЗ '+enemy.hp+'/'+enemy.max+', известных иммунитетов и уязвимостей нет в учебном профиле');break}
   case 'bait':{const friend=s.units[t];const old={x:u.x,y:u.y};u.x=friend.x;u.y=friend.y;friend.x=old.x;friend.y=old.y;u.superiority--;const extra=die(10);addBuff(id,'bait',[t],6);friend.baitAC=extra;log('Приманка и смена: '+names[t]+' получает +'+extra+' КД до следующего хода Яра.');break}
   case 'hewrule':u.hewReady=false;u.bonus++;log('Hew: бонусная атака становится доступна на это бонусное действие.');break;
   case 'shieldbash':u.shieldBashReady=false;u.shieldBashUsed=true;if(!saving(t,'STR',16))addStatus(t,'prone',null);break;
   case 'sacred':u.channel--;addBuff(id,'sacred',[id],600);break;
   case 'abjure':{u.channel--;const targets=foes.filter(z=>s.units[z].hp>0&&dist(u,s.units[z])<=60&&wallLOS(u,s.units[z])).slice(0,2);for(const f of targets)if(!saving(f,'WIS',14))addStatus(f,'abjured',s.elapsed+60);break}
   case 'compelled':if(!saving(t,'WIS',14))addBuff(id,'compelled',[t],60,true);break;
   case 'protectionEvil':addBuff(id,'protectionEvil',[t],600,true);break;
   case 'beacon':addBuff(id,'beacon',heroes.filter(x=>s.units[x].hp>0),60,true);break;
   case 'dispel':{const found=s.effects.filter(e=>e.targets.includes(t)&&e.owner!==id);if(found.length){const e=found[0];const level=e.level||3;if(level<=3||die(20)+6>=10+level){s.effects=s.effects.filter(f=>f!==e);log('Развеяно '+v21EffectName(e.kind)+' на '+names[t]);}else log('Рассеивание не преодолело мощность заклинания')}else log('На цели не обнаружено действующего заклинания');break}
   case 'vitality':addBuff(id,'vitality',heroes,60,true);break;
   case 'vitalityHeal':{let n=sum(dice(2,6));if(effect(id,'beacon'))n=12;heal(t,n);break}
   case 'zone':addBuff(id,'zone',foes,600);log('Зона истины: следующие попытки лгать требуют спасбросок ХАР СЛ14; не наносит урон');break;
   case 'thunder':{const hit=Object.keys(s.units).filter(z=>z!==id&&s.units[z].hp>0&&v18InThunderCube(s.units[z],p,u));amount=sum(dice(2,8))+5;v18AreaDamage(d,hit,19,'CON',amount,'гром');/* Push is resolved ONLY after a failed Constitution save by v18ApplyAreaTarget. */break}
   case 'web':{
     s.web={x:Math.max(0,Math.min(7,p.x-1)),y:Math.max(0,Math.min(4,p.y-1)),owner:id,until:s.elapsed+3600};
     addBuff(id,'web',[id],3600,true);
     log('Паутина: куб 20×20 фт от '+pos(s.web.x,s.web.y)+' до '+pos(s.web.x+3,s.web.y+3)+'. Труднопроходимая область; ЛОВ СЛ 19 при входе и в начале хода.');
     break;
    }
   case 'fog':s.smoke.push({...p,radius:20,until:s.elapsed+3600});addBuff(id,'fog',[],3600,true);break;
   case 'slow':{const targets=foes.filter(z=>s.units[z].hp>0&&rad(s.units[z],p)<=20).slice(0,6);for(const z of targets){if(!saving(z,'WIS',19))addStatus(z,'slow',s.elapsed+60)}addBuff(id,'slow',targets,60,true);break}
   case 'invisible':addBuff(id,'invisible',[t],60,true);break;
   case 'cone':{const targets=Object.keys(s.units).filter(z=>z!==id&&s.units[z].hp>0&&v18InCone(u,s.units[z],p,60)&&wallLOS(u,s.units[z]));amount=sum(dice(8,8))+5;v18AreaDamage(d,targets,19,'CON',amount,'холод');break}
   case 'hold':{if(!saving(t,'WIS',19))addStatus(t,'paralyzed',s.elapsed+60);addBuff(id,'hold',[t],60,true);break}
   case 'dimension':u.x=p.x;u.y=p.y;log(names[id]+' переместился через дверь в измерение в '+pos(p.x,p.y));break;
   case 'bigby':addBuff(id,'bigby',[id],60,true);s.bigby={x:p.x,y:p.y,owner:id};log('Рука Бигби создана в '+pos(p.x,p.y));break;
   case 'bigbyMove':{s.bigby={x:p.x,y:p.y,owner:id};log('Рука Бигби перемещается в '+pos(p.x,p.y));break}
   case 'bigbyStrike':{const hand=s.bigby;if(!hand||dist(hand,s.units[t])>5){s.info='Цель должна быть рядом с рукой Бигби (5 футов)';u.bonus++;render();return false}const die20=die(20);if(die20===20||die20!==1&&die20+11>=AC(t)){amount=sum(dice(die20===20?8:4,8));hurt(t,amount,'силовой')}log('Рука Бигби: атака '+die20+'+11');break}
   case 'bigbyGrasp':{const hand=s.bigby;if(!hand||dist(hand,s.units[t])>5){s.info='Цель должна быть рядом с рукой Бигби';u.bonus++;render();return false}if(!saving(t,'STR',19))addStatus(t,'grappled',s.elapsed+6);break}
   case 'seeming':addBuff(id,'seeming',[t],28800);log('Облик цели изменён; косметический эффект без боевого преимущества');break;
   case 'stormSphere':s.stormSphere={...p,owner:id};addBuff(id,'stormSphere',[id],60,true);for(const z of v18AreaTargets(p,20)){if(z===id)continue;if(!saving(z,'STR',16))hurt(z,sum(dice(2,6)),'дробящий')}break;
   case 'stormStrike':{const orb=s.stormSphere;if(!orb||dist(orb,s.units[t])>60){s.info='Цель вне 60 фт от сферы бури';u.bonus++;render();return false}const d20=die(20);if(d20===20||d20!==1&&d20+8>=AC(t))hurt(t,sum(dice(d20===20?8:4,6)),'молния');break}
   case 'hand':addBuff(id,'mageHand',[],600);log('Магическая рука создана; может переносить предметы до 10 фунтов, но не атакует');break;
   case 'prestidigitation':log('Фокусы: небольшой иллюзорный / бытовой эффект без боевого урона');break;
   case 'aim':addStatus(id,'aim',s.elapsed+6);u.move=0;break;
   case 'leaf':u.leafReady=false;u.move=Math.min(30,u.move+10);u.disengaged=true;break;
   case 'living':u.livingReady=false;if(!saving(t,'STR',15))addStatus(t,'living',s.elapsed+6);break;
   case 'nick':u.nickReady=false;u.nickUsed=true;u.attacks++;log('Nick: одна дополнительная атака лёгким оружием внутри действия Атака');break;
   }
   s.draft=null;render();hostSave();return true;
  }

  queueArea(caster,targets,protectedTargets,stat,dc,raw,type,opts={}){
   s.areaWork={caster,targets:targets.filter(z=>s.units[z]?.hp>0),protectedTargets,stat,dc,raw,type,index:0,opts};
   v18ContinueArea();
  }

  applyAreaTarget(t,passed){const q=s.areaWork;if(!q)return;let n=passed?Math.floor(q.raw/2):q.raw;if(t==='rada'&&q.stat==='DEX')n=passed?0:Math.floor(q.raw/2);if(n)hurt(t,n,q.type);if(q.opts.pushOnFail&&!passed){const u=s.units[q.caster],v=s.units[t],x=v.x+Math.sign(v.x-u.x),y=v.y+Math.sign(v.y-u.y);if(x>=0&&y>=0&&x<11&&y<8&&!wall(x,y)&&!at(x,y)){v.x=x;v.y=y;log(names[t]+' отброшен в '+pos(x,y))}}}

  continueArea(){const q=s.areaWork;if(!q)return;while(q.index<q.targets.length){const t=q.targets[q.index];if(!s.units[t]||s.units[t].hp<=0){q.index++;continue}if(q.protectedTargets.includes(t)){log('Скульптура: '+names[t]+' защищён, 0 урона');q.index++;continue}const ok=saving(t,q.stat,q.dc);if(!ok&&t==='yar'&&(s.units.yar.indomitable??1)>0){s.pending={kind:'indomitable',stat:q.stat,dc:q.dc,target:t};render();hostSave();return}v18ApplyAreaTarget(t,ok);q.index++}s.areaWork=null;s.pending=null;render();hostSave()}

  retryIndomitable(stat,dc){const scores={DEX:2,CON:8,WIS:2,STR:10,INT:0,CHA:0},u=s.units.yar,ly=s.units.lyutobor,aur=ly.hp>0&&dist(u,ly)<=10?2:0,shield=ly.hp>0&&dist(u,ly)<=5?1:0,b=(effect('yar','bless')||effect('yar','heroism'))?die(4):0,d=die(20),total=d+(scores[stat]??0)+10+aur+shield+b;log('Несгибаемость Яра: новый к20 '+d+' +10 уровень + бонусы '+(total-d-10)+' = '+total+' против СЛ '+dc);return total>=dc}

  cancelHand(){s.bigby=null;s.effects=s.effects.filter(z=>!(z.owner==='daphne'&&z.kind==='bigby'));for(const id of v19UnitIds()){if(hasStatus(id,'bigbyGrappled'))removeStatus(id,'bigbyGrappled')}log('Рука Бигби исчезла.');}

  placeHand(d){const point=d.point;if(!point||point.x<0||point.x>=11||point.y<0||point.y>=8||wall(point.x,point.y))return'Выбери доступную клетку для руки';
   const isCreation=d.key==='bigby',loc=s.bigby;
   if(isCreation){if(at(point.x,point.y))return'Рука создаётся в свободном пространстве'}else {if(!v19HandActive())return'Рука Бигби не существует';if(dist(loc,point)>60)return'Рука может переместиться не дальше 60 фт за команду'}
   if(isCreation&&dist(s.units.daphne,point)>120)return'Рука должна создаваться в 120 фт';
   if(!wallLOS(s.units.daphne,point)&&isCreation)return'Точка создания за стеной';
   // Bigby's hand is a non-occupying object; it may later pass into an occupied square.
   return null;
  }

  validateHand(d){const k=d.key,isCreation=k==='bigby',error=v19PlaceHand(d);if(error)return error;
   const id=turn(),u=me();if(id!=='daphne')return'Рукой управляет Дафна';
   if(isCreation){if(!u.action||!u.slots?.[5])return'Нужны действие и ячейка V круга';if(u.spellSlotThisTurn)return'В этом ходу уже использована ячейка заклинания'}
   else if(!u.bonus)return'Для команды нужно бонусное действие';
   else if(s.bigby.createdRound===s.round)return'Следующая команда доступна на последующих ходах после создания руки';
   const mode=d.handMode||(k==='bigbyStrike'?'fist':k==='bigbyGrasp'?'grasp':k==='bigbyPush'?'push':k==='bigbyCrush'?'crush':k==='bigbyInterpose'?'interpose':'move');
   if(mode==='move'||mode==='interpose')return null;
   if(!v19HandTarget(d.target,d.point))return'Цель должна быть в 5 фт от новой позиции руки';
   if(mode==='crush'&&s.bigby?.grappled!==d.target)return'Можно сдавливать только существо, удерживаемое этой рукой';
   return null;
  }

  pushHandTarget(target,caster,steps){const unit=s.units[target],src=s.bigby,vx=Math.sign(unit.x-src.x),vy=Math.sign(unit.y-src.y);let moved=0;for(let i=0;i<steps;i++){const nx=unit.x+vx,ny=unit.y+vy;if(nx<0||ny<0||nx>10||ny>7||wall(nx,ny)||at(nx,ny))break;unit.x=nx;unit.y=ny;moved+=5;}return moved}

  performHand(d){if(d?.key==='bigby'&&!s.v19ResolvingPrepaid&&v19BeginPlayerSpell(d))return true;const k=d.key,id=turn(),u=me(),mode=d.handMode||(k==='bigbyStrike'?'fist':k==='bigbyGrasp'?'grasp':k==='bigbyPush'?'push':k==='bigbyCrush'?'crush':k==='bigbyInterpose'?'interpose':'move');
   const err=v19HandValidate(d);if(err){v19Alert(err);return false}
   const creation=k==='bigby';if(creation){u.action--;u.slots[5]--;u.spellSlotThisTurn=true;v18EndConcentration(id);addBuff(id,'bigby',[id],60,true);s.bigby={x:d.point.x,y:d.point.y,owner:id,hp:u.max,max:u.max,ac:20,grappled:null,interposing:false,createdRound:s.round};log('Дафна создаёт Руку Бигби: КД 20, ПЗ '+s.bigby.hp)}else u.bonus--;
   const oldTarget=s.bigby.grappled;
   // Moving away from a grappled victim ends the grapple.
   if(oldTarget&&dist(d.point,s.units[oldTarget])>5){if(hasStatus(oldTarget,'bigbyGrappled'))removeStatus(oldTarget,'bigbyGrappled');s.bigby.grappled=null}
   s.bigby.x=d.point.x;s.bigby.y=d.point.y;s.bigby.interposing=mode==='interpose';
   if(mode==='fist'){
     const r=die(20),hit=r===20||(r!==1&&r+11>=AC(d.target));log('Кулак Бигби: к20 '+r+'+11 против КД '+AC(d.target)+(hit?' попадание':' промах'));
     if(hit){let dmg=sum(dice(r===20?10:5,8));if(!s.bigby.evocationUsed){dmg+=5;s.bigby.evocationUsed=true;log('Усиленное воплощение +5 один раз за срок заклинания')}hurt(d.target,dmg,'силовой')}
   }else if(mode==='push'){
     if(!saving(d.target,'STR',19)){const moved=v19PushObject(d.target,id,6);log('Толкающая рука Бигби: '+names[d.target]+' оттеснён на '+moved+' фт.');s.bigby.x=s.units[d.target].x;s.bigby.y=s.units[d.target].y;}
   }else if(mode==='grasp'){
     if(!saving(d.target,'DEX',19)){if(s.bigby.grappled&&s.bigby.grappled!==d.target)removeStatus(s.bigby.grappled,'bigbyGrappled');s.bigby.grappled=d.target;addStatus(d.target,'bigbyGrappled',s.elapsed+60);log('Рука Бигби удерживает '+names[d.target]+'. Освобождение — действие, СЛ19.')}
   }else if(mode==='crush'){hurt(d.target,sum(dice(4,6))+5,'дробящий');}
   else if(mode==='interpose'){log('Рука Бигби прикрывает линию атак: полуукрытие (+2 КД), клетка руки — трудная местность для врагов.');}
   else log('Рука Бигби перемещена без дополнительного эффекта.');
   s.draft=null;render();hostSave();return true;
  }
}
const combatSpellResolver=new CombatSpellResolver();
