"use strict";
const fs=require('node:fs'),assert=require('node:assert/strict');
const {createBattle,CombatCampaignAdapter:A}=require(process.argv[2]+'/sdk');
const p=JSON.parse(fs.readFileSync(0,'utf8')),mode=process.argv[3];
if(mode.startsWith('check-')){
 const {engine:e}=createBattle(p);e.initialize();
 if(mode==='check-web'){assert(e.has('yar','restrained'));assert.equal(e.speed('yar'),0);assert(e.s.zones.some(x=>x.kind==='web'));}
 else {assert(Object.values(e.s.objects).some(x=>x.x===17&&x.y===9));assert.notDeepEqual([e.unit('rada').x,e.unit('rada').y],[e.unit('yar').x,e.unit('yar').y]);}
 console.log('RESTORED '+mode);
}else{
 const scene=p.encounters[p.default_encounter];
 Object.assign(scene,{kind:'story',battle_id:'audit-3053-'+mode+'-'+p.revision,source_revision:p.revision,source_state_sha256:p.source_state_sha256,scene_id:mode==='first'?'audit-field-A':'audit-field-B'});
 if(mode!=='first'){
  scene.heroes={yar:{cell:mode==='web'?'C4':'C7'},daphne:{cell:'B6'}};scene.width=20;scene.height=12;
  if(mode==='web')p.profiles.daphne.casting.prepared.push('web');
 }
 const {engine:e}=createBattle(p);e.initialize();
 for(const u of Object.values(e.s.units)){u.controlled=false;u.policies={heroic:false,luck:false,defenseLuck:false};}e.s.pending=null;e.s.queue=[];
 if(mode!=='first'){
  e.s.index=e.s.order.indexOf('daphne');e.enqueue({kind:'startTurn'});e.run();e.s.random.tape=Array(300).fill(1);
  if(mode==='web'){
   e.dispatch({kind:'cast',actor:'daphne',spell:'web',point:{x:2,y:3}});e.s.index=e.s.order.indexOf('yar');e.enqueue({kind:'startTurn'});e.run();
  }else e.dispatch({kind:'cast',actor:'daphne',spell:'bigbyHand',point:{x:17,y:9}});
 }
 e.s.pending=null;e.s.queue=[];for(const u of Object.values(e.s.units))if(u.team==='enemies')u.fled=true;e.checkEnd();process.stdout.write(JSON.stringify(A.outcome(e.s)));
}
