#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const engineRoot=path.resolve(process.argv[2]),pack=JSON.parse(fs.readFileSync(process.argv[3])),output=path.resolve(process.argv[4]);
const {createBattle,CombatRulesEngine:E,CombatCampaignAdapter:A,CombatTacticalAI:AI}=require(engineRoot+'/sdk');
fs.mkdirSync(output,{recursive:true});
for(const seed of [7,31,104]){
 const p=structuredClone(pack),scene=p.encounters[p.default_encounter];scene.kind='story';scene.battle_id='shared-party-validation-'+seed;scene.source_revision=p.revision;scene.source_state_sha256=p.source_state_sha256;
 let {engine:e}=createBattle(p,undefined,seed);e.initialize();const casts=new Set();let reloads=0;
 for(let n=0;e.s.phase!=='ended'||e.s.pending||e.s.queue.length;n++){
  assert.ok(n<1400,'full party battle did not converge');
  const decision=e.s.pending;
  if(decision){
   let c={kind:'decide',id:decision.id,choice:'skip'};
   if(['precision','riposte','uncannyDodge','defensiveReaction','classRoll','deflect'].includes(decision.kind))c.choice='yes';
   if(decision.kind==='knockout')c.choice='lethal';
   if(decision.kind==='roll')c.choice='keep';
   if(decision.kind==='opportunity'||decision.kind==='ready')c.choice='yes';
   if(decision.kind==='redirect')c.choice='skip';
   if(decision.kind==='defenseLuck')c.choice='no';
   if(decision.kind==='magicChoice'){
    if(decision.options.includes('skip'))c.choice='skip';else if(decision.options.includes('no'))c.choice='no';else c.choice=decision.options[0];
    if(decision.choice==='vitality'){c.choice='heal';c.target=decision.targets[0];}
   }
   e.dispatch(c);
  }else if(e.s.queue.length)e.run();
  else{
   const id=e.actorId,u=e.unit(id),ai=new AI(e),foes=e.enemies(id).filter(t=>e.canSee(id,t));let c;
   if(id==='daphne'&&u.action&&foes.length){
    const target=foes.sort((a,b)=>e.distance(u,e.unit(a))-e.distance(u,e.unit(b)))[0];
    if(!casts.has(id)&&u.slots[3].current>0){c={kind:'cast',actor:id,spell:'fireball',point:{x:e.unit(target).x,y:e.unit(target).y},sculpt:e.s.order.filter(t=>t!==id&&e.unit(t).team===u.team&&e.canSee(id,t))};casts.add(id);}
    else c={kind:'cast',actor:id,spell:'fireBolt',target};
    if(!e.availableAction(c).enabled)c=null;
   }
   if(id==='lyutobor'&&!casts.has(id)&&u.action){c={kind:'cast',actor:id,spell:'bless',targets:['yar','daphne','rada'].filter(t=>e.distance(u,e.unit(t))<=30)};if(!e.availableAction(c).enabled)c=null;else casts.add(id);}
   e.dispatch(c||ai.choose(id));
  }
  // Reconstruct at every decision and regularly between commands, preserving exact pending work and RNG.
  if(e.s.pending||n%7===0){const saved=JSON.stringify(e.export());e=new E(JSON.parse(saved).session);assert.equal(JSON.stringify(e.export()),saved);reloads++;}
  for(const u of Object.values(e.s.units))for(const p of Object.values(u.counters))assert.ok(p.current>=0&&p.current<=p.max);
 }
 const result=A.outcome(e.s);assert.ok(result.events.some(x=>x.type==='cast'&&x.spell==='fireball'));assert.ok(result.events.some(x=>x.type==='cast'&&x.spell==='bless'));assert.ok(reloads>5);fs.writeFileSync(output+'/result-'+seed+'.json',JSON.stringify(result));console.log(JSON.stringify({seed,round:e.s.round,events:e.s.events.length,reloads,winner:e.s.winner}));
}
