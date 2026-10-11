// Nested Counterspell, serial attack reactions and resumable hit/damage frames.
class CombatReactionResolver {
  beginPlayerSpell(d){if(!d||turn()!=='daphne'||!v19HostileCounterFor('daphne'))return false;
   const level=v19SlotLevels[d.key];if(!level||!s.units.daphne.slots[level])return false;
   const err=d.type==='advanced'?v18TargetCheck(d):check(d);if(err){v19Alert(err);return true}
   const u=s.units.daphne,bonus=['misty','faith'].includes(d.key);if(bonus&&!u.bonus||!bonus&&!u.action){v19Alert('Не хватает действия');return true}
   if(bonus)u.bonus--;else u.action--;u.slots[level]--;u.spellSlotThisTurn=true;
   log('Дафна начинает колдовать '+d.key+'; окно Контрзаклинания врага.');s.draft=null;
   v19PushSpell({kind:'spell',caster:'daphne',spell:d.key,level,dc:19,slotSpent:true,playerDraft:JSON.parse(JSON.stringify(d)),playerBonus:bonus});return true;
  }

  finishPlayerSpell(top){const d=top.playerDraft,u=s.units.daphne;if(!d)return;
   if(top.playerBonus)u.bonus++;else u.action++;u.slots[top.level]++;
   const prev=u.spellSlotThisTurn;u.spellSlotThisTurn=false;
   s.v19ResolvingPrepaid=true;
   try{
    if(d.key==='bigby')v19HandPerform(d);
    else if(d.type==='advanced')v18Execute(d);
    else{s.draft=d;apply()}
   }finally{s.v19ResolvingPrepaid=false;u.spellSlotThisTurn=true}
  }

  pushSpell(event){s.spellStack??=[];s.spellStack.push({...event,prompted:[]});v19AdvanceSpellStack()}

  startEnemySpell(caster,kind='fireball'){
   const u=s.units[caster];if(!u||!u.action||!u.slots?.[3])return false;
   // Enemy has already begun to cast; reaction window opens before its effect.
   u.action--;u.slots[3]--;u.spellSlotThisTurn=true;s.v19ResumeEnemy=true;
   const center={x:3,y:5};log(names[caster]+' начинает колдовать Огненный шар (III круг), центр D6; открыто окно реакций.');
   v19PushSpell({kind:'spell',caster,spell:kind,level:3,center,dc:u.spellDC||14,slotSpent:true});return true;
  }

  advanceSpellStack(){if(s.pending?.kind==='v19react')return;
   while(s.spellStack?.length){let top=s.spellStack.at(-1);
    // A matching reaction can create nested Counterspell. Every reactor can respond once.
    const possible=v19UnitIds().filter(id=>id!==top.caster&&isHero(id)!==isHero(top.caster)&&!top.prompted.includes(id)&&v19CasterCanCounter(id,top.caster));
    const human=possible.find(id=>isHero(id));
    if(human){top.prompted.push(human);s.pending={kind:'v19react',phase:'spell',choiceFor:human,choices:['counterspell','no'],event:{caster:top.caster,spell:top.spell}};render();hostSave();return}
    const npc=possible.find(id=>!isHero(id));
    if(npc){top.prompted.push(npc); // NPC counters an opponent's Counterspell automatically, otherwise saves its slot.
     if(top.spell==='counterspell'||top.level>=3){const u=s.units[npc];u.reaction--;u.slots[3]--;u.spellSlotThisTurn=true;log(names[npc]+' применяет Контрзаклинание к '+names[top.caster]);s.spellStack.push({kind:'spell',caster:npc,spell:'counterspell',level:3,dc:u.spellDC||14,slotSpent:true,prompted:[]});continue}
    }
    s.spellStack.pop();
    if(top.cancelled){log('Заклинание '+names[top.caster]+' рассеялось; действия не возвращаются.');continue}
    if(top.playerDraft){v19FinishPlayerSpell(top);if(s.pending)return;continue}
    if(top.spell==='counterspell'){
      const victim=s.spellStack.at(-1);if(!victim)continue;
      const bonus=s.units[victim.caster]?.conSave??(victim.caster==='daphne'?2:0);
      const d=die(20),result=d+bonus,passed=result>=top.dc;
      log('Контрзаклинание: '+names[victim.caster]+' ТЕЛ '+d+'+'+bonus+'='+result+' против СЛ '+top.dc+(passed?' — выдержал':' — провалил'));
      if(!passed){victim.cancelled=true;if(victim.slotSpent&&s.units[victim.caster].slots?.[victim.level]!==undefined){s.units[victim.caster].slots[victim.level]++;victim.slotSpent=false;log('Ячейка прерванного заклинания возвращена; реакция/действие потрачены.')}}
      continue;
    }
    if(top.spell==='fireball'){
      const targets=v19UnitIds().filter(id=>s.units[id].hp>0&&rad(s.units[id],top.center)<=20);
      const rolled=sum(dice(8,6));log(names[top.caster]+': Огненный шар '+rolled+' урона огнём в D6, СЛ '+top.dc);
      // Use existing pause-on-failed-save logic for Yar; no Sculpt on enemy casting.
      s.pending=null;v18QueueArea(top.caster,targets,[],'DEX',top.dc,rolled,'огонь');
      if(s.pending)return;
    }
   }
   if(s.v19ResumeEnemy&&!s.pending){s.v19ResumeEnemy=false;advance()}
   render();hostSave();
  }

  attackFrame(attacker,target,test=false,forced,disadvantage=false){const e=s.units[attacker],t=s.units[target];if(!e||!t||e.hp<=0||t.hp<=0)return;
   const attackSpec=e.enemyAttack||{bonus:5,count:1,die:8,flat:3,range:attacker==='archer'?80:5};const bonus=attackSpec.bonus;const hinder=disadvantage||hasStatus(attacker,'restrained'),favored=hasStatus(target,'restrained');const d1=forced!==undefined?forced-bonus:die(20),d2=hinder!==favored?die(20):null,d=d2===null?d1:favored?Math.max(d1,d2):Math.min(d1,d2),total=d+bonus,crit=d===20;s.v19AttackSource=attacker;const hit=crit||(d!==1&&total>=AC(target));
   log(names[attacker]+' атакует '+names[target]+': '+(hinder&&favored?'преимущество и помеха взаимно отменены':favored?'ПРЕИМУЩЕСТВО':hinder?'ПОМЕХА':'обычный бросок')+'; к20 '+(d2===null?'['+d1+']':'['+d1+', '+d2+'] → '+d)+' +'+bonus+' (атака) = '+total+' против КД '+AC(target)+(hit?' — ПОПАДАНИЕ'+(crit?', КРИТИЧЕСКОЕ':''):' — ПРОМАХ'));
   const frame={attacker,target,test,total,crit,hit,raw:0,secondDamageDie:0,damageType:'оружие',applied:[],disadvantage:hinder};if(hit){const regularRolls=dice(attackSpec.count,attackSpec.die),criticalRolls=crit?dice(attackSpec.count,attackSpec.die):[];const initialDamage=sum(regularRolls),additionalDamage=sum(criticalRolls);frame.raw=initialDamage+additionalDamage+attackSpec.flat;frame.secondDamageDie=additionalDamage;log('Урон '+names[attacker]+': к'+attackSpec.die+' ['+regularRolls.join(', ')+'] = '+initialDamage+' (кости) +'+(crit?'к'+attackSpec.die+' ['+criticalRolls.join(', ')+'] = ':'')+additionalDamage+' (критические кости) +'+attackSpec.flat+' (бонус) = '+frame.raw+'.');}s.attackFrame=frame;v19NextAttackReaction();}

  nextAttackReaction(){const a=s.attackFrame;if(!a)return;
   const t=s.units[a.target],pal=s.units.lyutobor;
   if(a.hit){const options=[];
    if(a.target==='daphne'&&!a.crit&&t.reaction>0&&!effect('daphne','shield')&&a.total<AC('daphne')+5&&(t.shieldFree>0||t.slots[1]>0)&&!a.applied.includes('shield'))options.push('shield');
     if(a.crit&&a.target!=='lyutobor'&&pal.hp>0&&pal.reaction>0&&pal.mark>0&&dist(pal,t)<=30&&LOS(pal,t)&&!a.applied.includes('mark'))options.push('mark');
     if(a.target==='yar'&&t.reaction>0&&t.cloak>0&&!a.applied.includes('cloak'))options.push('cloak');
     if(a.target==='rada'&&t.reaction>0&&!a.applied.includes('uncanny'))options.push('uncanny');
     if(options.length){s.pending={kind:'v19react',phase:'attack-hit',choices:[...options,'no'],event:{target:a.target,attacker:a.attacker,total:a.total,damage:a.raw,crit:a.crit}};render();hostSave();return;}
   }else if(a.target==='yar'&&a.attacker!=='archer'&&t.reaction>0&&t.superiority>0&&dist(t,s.units[a.attacker])<=5&&!a.applied.includes('riposte')){
     s.pending={kind:'v19react',phase:'attack-miss',choices:['riposte','no'],event:{target:a.target,attacker:a.attacker}};render();hostSave();return;
   }
   v19FinishAttack();}

  finishAttack(){const a=s.attackFrame;if(!a)return;s.attackFrame=null;s.v19AttackSource=null;s.pending=null;if(a.hit&&a.raw>0)hurt(a.target,a.raw,'оружие');v19LogEvent('attack-closed',{attacker:a.attacker,target:a.target,damage:a.hit?a.raw:0,reactions:a.applied});
   if(!a.test){advance()}else if(s.moving&&!s.pending){setTimeout(walk,150)}render();hostSave()}

  reactChoice(choice){const p=s.pending;if(!p||p.kind!=='v19react')return;
   s.pending=null;
   if(p.phase==='spell'){
    if(choice==='counterspell'&&p.choiceFor==='daphne'&&v19CasterCanCounter('daphne',p.event.caster)){
      const u=s.units.daphne;u.reaction--;u.slots[3]--;u.spellSlotThisTurn=true;log('Дафна применяет Контрзаклинание III круга реакцией.');s.spellStack.push({kind:'spell',caster:'daphne',spell:'counterspell',level:3,dc:19,slotSpent:true,prompted:[]});
    }else log('Контрзаклинание не применено.');
    v19AdvanceSpellStack();return;
   }
   const a=s.attackFrame;if(!a){render();return}const pal=s.units.lyutobor,t=s.units[a.target];
   if(p.phase==='attack-before'){
    let disadv=false;if(choice==='protection'&&pal.reaction>0){pal.reaction--;disadv=true;log('Лютобор применяет Protection до броска атаки.');}
    v19AttackFrame(a.attacker,a.target,a.test,a.forced,disadv);return;
   }
   if(p.phase==='attack-hit'){
    if(choice==='shield'&&a.target==='daphne'&&!a.crit&&t.reaction>0&&!effect('daphne','shield')&&(t.shieldFree>0||t.slots[1]>0)){
      t.reaction--;if(t.shieldFree>0)t.shieldFree--;else t.slots[1]--;a.applied.push('shield');addBuff('daphne','shield',['daphne'],7200);
      if(a.total<AC('daphne')){a.hit=false;a.raw=0;log('Дафна применяет Щит: попадание предотвращено.')}else log('Дафна применяет Щит, но попадание сохраняется.');}
    else if(choice==='mark'&&a.crit&&pal.reaction&&pal.mark){pal.reaction--;pal.mark--;a.applied.push('mark');a.crit=false; // Crit to normal: remove second damage die, keeping the first result.
      a.raw=Math.max(0,a.raw-(a.secondDamageDie||0));log('Знак Стража отменяет крит; теперь обычное попадание.');}
    else if(choice==='cloak'&&t.reaction&&t.cloak){t.reaction--;t.cloak--;a.applied.push('cloak');if(!a.crit&&a.total<AC(a.target)+3){a.hit=false;a.raw=0;log('Плащ Ваэльтира: +3 КД, атака отражена.')}else log('Плащ Ваэльтира активирован: удар всё ещё попадает.');}
    else if(choice==='uncanny'&&t.reaction){t.reaction--;a.applied.push('uncanny');a.raw=Math.floor(a.raw/2);log('Рада уменьшает получаемый урон от попадания вдвое.');}
    else {a.applied.push('shield','mark','cloak','uncanny');}
    v19NextAttackReaction();return;
   }
   if(p.phase==='attack-miss'){
     a.applied.push('riposte');if(choice==='riposte'&&t.reaction&&t.superiority){t.reaction--;t.superiority--;const r=die(20),b=effect('yar','bless')?die(4):0,hit=r===20||(r!==1&&r+12+b>=AC(a.attacker));log('Ответный удар Яра: '+r+'+12'+(hit?' — попадание':' — промах'));if(hit)hurt(a.attacker,sum(dice(r===20?4:2,6).map(x=>Math.max(3,x)))+6+die(10),'оружие')}
     v19FinishAttack();return;
   }
  }
}
const combatReactionResolver=new CombatReactionResolver();
