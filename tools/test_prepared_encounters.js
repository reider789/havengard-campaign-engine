"use strict";
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),cp=require('node:child_process');
const root=path.resolve(__dirname,'..'),engineRoot=path.resolve(process.env.ENGINE_ROOT||path.join(root,'../rin-engine'));
const sdk=require(path.join(engineRoot,'sdk')),cat=require('../prototypes/prepared-encounters/perelomye/catalog.json');
const base=require(path.join(root,'.build/T8.pack.json'));
const stock=cp.spawnSync(process.execPath,[path.join(engineRoot,'sdk/cli.js'),'validate',path.join(root,'.build/T8.pack.json')],{encoding:'utf8'});
require('../prototypes/prepared-encounters/gm-assist').installPreparedGM(sdk,cat);
require('../prototypes/prepared-encounters/prepared-runtime').installPreparedRuntime(sdk,cat);
const nativeCreate=sdk.createBattle; sdk.createBattle=(p,...args)=>{p=structuredClone(p);for(const v of Object.values(p.encounters))v.prepared_automation=false;return nativeCreate(p,...args);};
const E=sdk.CombatRulesEngine;
function setup(room='T8',profile){
 const pack=JSON.parse(fs.readFileSync(path.join(root,'.build',room+'.pack.json')));
 if(profile)pack.encounters[room].enemies=[{id:'subject',profile,cell:'G5'}];
 const {engine:e}=sdk.createBattle(pack,room,43);e.initialize();
 Object.assign(e.s,{pending:null,queue:[],effects:[],zones:[],objects:{},spellFrames:{},phase:'active',turnSerial:12,round:3});
 Object.assign(e.s.terrain,{walls:[],rubble:[],cover:{}});
 for(const u of Object.values(e.s.units)){
   u.action=1;u.bonus=1;u.reaction=1;u.move=u.speed;u.statuses=[];u.heroic=0;u.luck=0;u.policies={};
   if(!u.prepared){u.features={};u.casting=null;u.temp=0;u.hp=u.max=500;}
 }
 e.s.index=e.s.order.indexOf(profile?'subject':e.s.order.find(id=>e.unit(id).prepared));
 return e;
}
function turn(e,id){e.s.index=e.s.order.indexOf(id);e.s.pending=null;e.s.queue=[];}
function reload(e){return new E(JSON.parse(JSON.stringify(e.export())).session);}
function decide(e,choice,extra={}){e.dispatch({kind:'decide',id:e.s.pending.id,choice,...extra});}
function ability(e,key,targets=[],extra={}){e.dispatch({kind:'prepared',actor:e.actorId,creature:e.actorId,ability:key,targets,confirmed:true,...extra});}
test('stock engine refuses the extension pack instead of silently losing rules',()=>{
 assert.notEqual(stock.status,0);assert.match(stock.stderr,/perelomye-gm-assist/);
});
test('all 19 profiles preserve authored HP/AC/modifiers; all abilities retain source text',()=>{
 assert.equal(Object.keys(cat.profiles).length,19);
 for(const [id,p] of Object.entries(cat.profiles)){
  const c=cat.cards[id];assert.equal(p.hp,c.hp,id);assert.equal(p.ac,c.ac,id);
  assert.deepEqual(Object.values(p.scores).map(v=>Math.floor((v-10)/2)),c.abilities,id);
  for(const field of ['action','bonus','reaction','extra','defenses','skills','senses','language','behavior','gear'])assert(p.reference.some(s=>s.includes(c[field])),id+'/'+field);
 }
});
test('all deployed room templates compile, initialize, save and restore with four player heroes',()=>{
 for(const room of Object.keys(cat.encounters).filter(r=>cat.encounters[r].population.length)){
  const pack=JSON.parse(fs.readFileSync(path.join(root,'.build',room+'.pack.json'))),{engine:e}=sdk.createBattle(pack);
  e.initialize();E.validate(e.s);const restored=reload(e);assert.deepEqual(restored.s,e.s);
  assert.equal(Object.values(e.s.units).filter(u=>u.controlled).length,4);
 }
});
test('100 full turn boundaries preserve inactive minions and serializable legendary windows',()=>{
 let {engine:e}=sdk.createBattle(base);e.initialize();let count=0;
 while(count<100){
  E.validate(e.s);e=reload(e);
  if(e.s.pending){const p=e.s.pending;decide(e,p.kind==='initiativeSwap'?'skip':'no');}
  else{e.dispatch({kind:'endTurn',actor:e.actorId});count++;}
 }
 for(const u of Object.values(e.s.units).filter(u=>u.prepared?.profile==='C36'&&!u.prepared.active))assert.equal(u.turnCount,0);
});
test('swarm attacks only shared space, shrinks dice at half HP and imports a shared cell',()=>{
 const e=setup('G4','C10'),u=e.unit('subject'),v=e.unit('yar');Object.assign(u,{x:3,y:3});Object.assign(v,{x:4,y:3});
 assert.throws(()=>e.validateAttack(u.id,v.id,e.attackSpec(u.id,'sting')),/общем пространстве/);
 v.x=3;assert.doesNotThrow(()=>e.validateAttack(u.id,v.id,e.attackSpec(u.id,'sting')));
 assert.equal(e.attackSpec(u.id,'sting').count,4);u.hp=18;assert.equal(e.attackSpec(u.id,'sting').count,2);
 assert.equal(e.conditionImmune(u.id,'grappled'),true);E.validate(e.s);reload(e);
});
test('finite per-creature ammunition is consumed once; empty attacks roll back',()=>{
 const e=setup('L1','C05'),u=e.unit('subject'),v=e.unit('yar');Object.assign(u,{x:3,y:3});Object.assign(v,{x:5,y:3});
 u.prepared.ammo['spear-thrown']=1;e.s.random.tape=Array(100).fill(2);
 e.dispatch({kind:'attack',actor:u.id,target:v.id,weapon:'spear-thrown'});assert.equal(u.prepared.ammo['spear-thrown'],0);
 const before=JSON.stringify(e.s);assert.throws(()=>e.dispatch({kind:'attack',actor:u.id,target:v.id,weapon:'spear-thrown'}),/запас/);assert.equal(JSON.stringify(e.s),before);
});
test('mixed damage riders are typed, double on a critical and do not mutate the attack',()=>{
 const e=setup('T5','C29'),s=e.attackSpec('subject','pseudopod');e.s.random.tape=[3,4];
 const t=e.damageTask({actor:'subject',target:'yar',spec:s,critical:true},20);
 assert.deepEqual(t.components,[{amount:20,damageType:'bludgeoning'},{amount:7,damageType:'acid'}]);assert.equal(s.count,2);
});
test('poison lasts through the end of the target next turn, not its start',()=>{
 const e=setup('G4','C10');e.s.random.tape=[1];
 e.task({kind:'weaponHitEffects',actor:'subject',target:'yar',frame:{spec:{id:'sting'}}});e.run();
 const z=e.unit('yar').statuses.find(z=>z.kind==='poisoned');assert(z);assert.equal(z.expiresOnSourceEndTurn,e.unit('yar').turnCount+1);assert.equal(z.expiresAtStart,undefined);
});
test('dust consumes the whole action once, obscures, and clears at next source start',()=>{
 const e=setup('T3','C12');ability(e,'dust');assert.equal(e.unit('subject').action,0);assert.equal(e.unit('subject').prepared.uses.dust,0);assert(e.s.zones.some(z=>z.kind==='smoke'));
 e.task({kind:'startTurn',actor:'subject'});assert(!e.s.zones.some(z=>z.preparedDust));
 assert.throws(()=>ability(e,'dust'),/исчерпаны/);
});
test('boss resistance pauses a failed save, survives reload and burns exactly one source plus HP',()=>{
 let e=setup('T8','C32'),u=e.unit('subject');const object=Object.keys(e.s.prepared.objects)[0],hp=u.hp;
 e.finishRoll({actor:u.id,save:true,count:1,sides:20,rolls:[1],bonus:0,dc:20,label:'Тест',next:{kind:'checkResult',actor:u.id}});
 assert.equal(e.s.pending.choice,'resistance');e=reload(e);decide(e,'yes',{object});
 assert.equal(e.unit('subject').hp,hp-10);assert.equal(e.unit('subject').prepared.uses.resistance,1);assert.equal(e.s.prepared.objects[object].hp,0);
});
test('phase opens only at next own turn, loses Counterspell and restores no HP/uses',()=>{
 const e=setup('T8','C32'),u=e.unit('subject');u.hp=175;u.prepared.uses.chord=1;u.reaction=0;assert.equal(u.prepared.phase,1);
 e.task({kind:'startTurn',actor:u.id});assert.equal(u.prepared.phase,2);assert.equal(u.hp,175);assert.equal(u.prepared.uses.chord,1);assert(!u.casting.prepared.includes('counterspell'));
});
test('canonical multiattack alternatives reject extra crossbow shots and mixed boss sequences',()=>{
 const e=setup('T8','C23'),u=e.unit('subject'),v=e.unit('yar');Object.assign(u,{x:4,y:4});Object.assign(v,{x:5,y:4});e.s.random.tape=Array(100).fill(2);
 e.dispatch({kind:'attack',actor:u.id,target:v.id,weapon:'crossbow'});assert.equal(u.attacksLeft,0);
 assert.throws(()=>e.dispatch({kind:'attack',actor:u.id,target:v.id,weapon:'crossbow'}),/потрачено/);
 const f=setup('B8','C33');Object.assign(f.unit('subject'),{x:4,y:4});Object.assign(f.unit('yar'),{x:5,y:4});
 assert.throws(()=>f.dispatch({kind:'attack',actor:'subject',target:'yar',weapon:'beak'}),/последовательность/);
});
test('breath cannot open the fight; preparation is serialized and charge paid once',()=>{
 const e=setup('B8','C33'),u=e.unit('subject');
 assert.throws(()=>ability(e,'breath',['yar'],{telegraphValid:true}),/не было объявлено/);
 e.unit('subject').prepared.telegraph={round:e.s.round-1,x:u.x,y:u.y,axis:'запад'};e.s.random.tape=Array(100).fill(2);
 ability(e,'breath',['yar'],{telegraphValid:true});assert.equal(e.unit('subject').prepared.uses.breath,2);assert.equal(e.unit('subject').action,0);assert.equal(e.unit('subject').prepared.telegraph,undefined);
});
test('grounding does not erase stored breath; recharge requires a nearby ungrounded rod',()=>{
 const e=setup('B8','C33'),u=e.unit('subject');u.prepared.uses.breath=2;Object.assign(u,{x:4,y:5});e.s.random.tape=[6];
 e.task({kind:'startTurn',actor:u.id});assert.equal(u.prepared.uses.breath,3);
 for(const o of Object.values(e.s.prepared.objects))o.grounded=true;u.prepared.uses.breath=2;e.task({kind:'startTurn',actor:u.id});assert.equal(u.prepared.uses.breath,2);
});
test('Ark shield reduces a whole mixed package once and shares its reaction',()=>{
 let e=setup('P9','C34'),u=e.unit('subject');Object.assign(u,{x:4,y:4});Object.assign(e.unit('yar'),{x:3,y:4});
 e.task({kind:'damage',actor:'yar',target:u.id,amount:20,components:[{amount:8,damageType:'bludgeoning'},{amount:12,damageType:'force'}],attack:{kind:'melee',id:'test'}});
 assert.equal(e.s.pending.choice,'shield');e=reload(e);decide(e,'yes');assert.equal(e.unit('subject').hp,382);assert.equal(e.unit('subject').reaction,0);
});
test('object costs reduce remaining legendary budget without refunding spent points',()=>{
 const e=setup('P9','C34'),u=e.unit('subject');u.prepared.legendary=1;
 for(const o of Object.values(e.s.prepared.objects))e.dispatch({kind:'preparedRuling',actor:u.id,object:o.id,off:true,confirmed:true,ruling:'Объект выключен по проверенному исходу'});
 assert.equal(e.unit('subject').prepared.legendary,0);assert.equal(e.ac(u.id),17);
});
test('arena stores source and full-cycle delay; disabling source cancels the pending strike',()=>{
 const e=setup('T8','C32'),u=e.unit('subject'),object=Object.keys(e.s.prepared.objects)[0];
 e.dispatch({kind:'preparedArena',actor:u.id,operation:'mark',object,initiative20:true,confirmed:true,ruling:'Круг 10 фт у северного прибора'});
 assert.throws(()=>e.dispatch({kind:'preparedArena',actor:u.id,operation:'resolve',initiative20:true,confirmed:true,ruling:'Разрешение',targets:['yar']}),/следующей/);
 e.s.round++;e.s.prepared.objects[object].off=true;const hp=e.unit('yar').hp;
 e.dispatch({kind:'preparedArena',actor:u.id,operation:'resolve',initiative20:true,confirmed:true,ruling:'Источник выключен',targets:['yar']});assert.equal(e.unit('yar').hp,hp);assert.equal(e.s.prepared.environment,null);
});
test('authored innate magic cannot skip GM Counterspell/component confirmation',()=>{
 const e=setup('T8','C32'),before=JSON.stringify(e.s);
 assert.throws(()=>ability(e,'chord',['yar']),/Контрзаклинания/);assert.equal(JSON.stringify(e.s),before);
});
test('altitude changes distance and the T5 ooze starts 20 feet below the rim',()=>{
 const e=setup('T5');const u=Object.values(e.s.units).find(u=>u.prepared?.profile==='C29');assert.equal(u.altitude,-20);
 const v=e.unit('yar');Object.assign(v,{x:u.x,y:u.y,altitude:10});assert.equal(e.distance(u,v),30);
});
test('a legendary window cannot be used to cast an ordinary whole-action spell',()=>{
 const e=setup('T8','C32'),id='subject';e.s.prepared.legendaryBoundary={actor:'yar',used:[]};
 e.decision('preparedChoice','yar',{choice:'legendary',ended:'yar',label:'Тест'});
 const before=JSON.stringify(e.s);assert.throws(()=>decide(e,'ability',{creature:id,ability:'chord',targets:['yar'],confirmed:true,spellWindowConfirmed:true}),/только легендарные/);assert.equal(JSON.stringify(e.s),before);
});
test('activation uses an existing minion, its original initiative, and the next round',()=>{
 const e=setup('T8'),boss=e.s.order.find(id=>e.unit(id).prepared?.profile==='C32'),minion=e.s.order.find(id=>e.unit(id).prepared?.profile==='C36'&&!e.unit(id).prepared.active);
 turn(e,boss);const initiative=e.s.initiative[minion];e.s.prepared.legendaryBoundary={actor:'yar',used:[]};
 e.decision('preparedChoice','yar',{choice:'legendary',ended:'yar',label:'Активация'});
 decide(e,'ability',{creature:boss,ability:'activate',ally:minion,confirmed:true});
 assert.equal(e.unit(minion).prepared.activateRound,e.s.round+1);assert.equal(e.s.initiative[minion],initiative);assert.equal(e.unit(boss).prepared.legendary,1);
});
test('legendary movement restores the ordinary movement budget after its own path',()=>{
 const e=setup('T8','C32'),u=e.unit('subject');Object.assign(u,{x:5,y:4,move:7});e.s.prepared.legendaryBoundary={actor:'yar',used:[]};
 e.decision('preparedChoice','yar',{choice:'legendary',ended:'yar',label:'Движение'});
 decide(e,'ability',{creature:u.id,ability:'legend-move',confirmed:true,path:[{x:6,y:4}]});
 assert.equal(e.unit(u.id).x,6);assert.equal(e.unit(u.id).move,7);assert.equal(e.unit(u.id).prepared.legendary,2);reload(e);
});
test('Pause ends at the source next turn and on actual damage, not an immune hit',()=>{
 const e=setup('T8','C32'),u=e.unit('subject'),v=e.unit('yar');
 e.status(v.id,'incapacitated',{preparedPause:true,expiresAtStart:u.id});e.status(v.id,'rooted',{preparedPause:true,expiresAtStart:u.id});
 v.immunities=['psychic'];e.task({kind:'damage',actor:u.id,target:v.id,amount:5,damageType:'psychic'});assert(e.has(v.id,'incapacitated'));
 e.task({kind:'startTurn',actor:u.id});assert(!e.has(v.id,'incapacitated'));assert(!e.has(v.id,'rooted'));
 e.status(v.id,'incapacitated',{preparedPause:true});e.task({kind:'damage',actor:u.id,target:v.id,amount:5,damageType:'force'});assert(!e.has(v.id,'incapacitated'));
});
test('defeating the master immediately stops its finite servants without resurrecting them',()=>{
 const e=setup('T8'),boss=e.s.order.find(id=>e.unit(id).prepared?.profile==='C32');
 e.unit(boss).hp=1;e.unit(boss).prepared.uses.resistance=0;e.task({kind:'damage',actor:'yar',target:boss,amount:10,damageType:'force'});
 for(const u of Object.values(e.s.units).filter(u=>u.prepared?.profile==='C36'))assert.equal(u.prepared.active,false);
});
test('GM SDK bridge pins the save, writes a new checkpoint and refuses hero control',()=>{
 const crypto=require('node:crypto'),dir=fs.mkdtempSync(path.join(root,'.build/gm-cli-'));
 const e=setup('G4','C10'),session=path.join(dir,'session.json'),request=path.join(dir,'request.json'),out=path.join(dir,'next.json');
 const pack=JSON.parse(fs.readFileSync(path.join(root,'.build/G4.pack.json')));pack.encounters.G4.enemies=[{id:'subject',profile:'C10',cell:'G5'}];
 const bytes=JSON.stringify({...e.export(),contentPack:pack});fs.writeFileSync(session,bytes);
 const hash=crypto.createHash('sha256').update(bytes).digest('hex');
 const run=commands=>{fs.writeFileSync(request,JSON.stringify({session_sha256:hash,commands}));return cp.spawnSync(process.execPath,[path.join(root,'tools/prepared_gm_turn.js'),engineRoot,session,request,out],{encoding:'utf8'});};
 let r=run([{kind:'endTurn',actor:'subject'}]);assert.equal(r.status,0,r.stderr);assert(fs.existsSync(out));assert.equal(fs.readFileSync(session,'utf8'),bytes);
 r=run([{kind:'endTurn',actor:'yar'}]);assert.notEqual(r.status,0);assert.match(r.stderr,/cannot control/);
});
test('every generated HTML contains syntactically valid scripts and real inline SVG art',()=>{
 for(const room of Object.keys(cat.encounters).filter(r=>cat.encounters[r].population.length)){
  const html=fs.readFileSync(path.join(root,'.build',room+'.html'),'utf8');
  for(const match of html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)){
    if(match[1].includes('application/json'))JSON.parse(match[2]);else new vm.Script(match[2],{filename:room+'.html'});
  }
  assert(html.includes('image/svg+xml'));assert(html.includes('PreparedGMPort'));assert(html.includes('Режим с решениями ведущего'));
 }
});
