'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),root=path.resolve(process.argv[2]);
const {createBattle,CombatCampaignAdapter:A}=require(root+'/sdk'),pack=JSON.parse(fs.readFileSync(process.argv[3]));
if(process.argv[4]==='check'){
 const {engine:e}=createBattle(pack);assert.equal(e.ac('daphne'),15);assert.equal(e.unit('lyutobor-steed').hp,21);assert.equal(e.unit('lyutobor-steed').max,25);assert.equal(Object.values(e.s.objects).length,1);assert.equal(e.unit('daphne').slots[5].current,1);console.log('PERSISTENT PARTY RESTORE OK: armor, hand, spent slots and injured summoned steed');
}else{
 const scene=pack.encounters[pack.default_encounter];Object.assign(scene,{kind:'story',battle_id:'shared-continuity-validation',source_revision:pack.revision,source_state_sha256:pack.source_state_sha256});const {engine:e}=createBattle(pack);
 const turn=id=>{e.s.started=true;e.s.pending=null;e.s.queue=[];e.s.index=e.s.order.indexOf(id);e.enqueue({kind:'startTurn'});e.run();};
 turn('daphne');e.dispatch({kind:'cast',actor:'daphne',spell:'mageArmor',target:'daphne'});turn('daphne');e.dispatch({kind:'cast',actor:'daphne',spell:'bigbyHand',point:{x:5,y:5},handMode:'interpose'});turn('lyutobor');e.dispatch({kind:'cast',actor:'lyutobor',spell:'findSteed',point:{x:4,y:5}});e.unit('lyutobor-steed').hp=21;for(const id of e.enemies('daphne'))e.unit(id).fled=true;e.checkEnd();assert.equal(e.s.phase,'ended');fs.writeFileSync(process.argv[4],JSON.stringify(A.outcome(e.s)));
}
