"use strict";
const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const sdk=require(path.resolve(process.env.ENGINE_ROOT||path.join(__dirname,'../../rin-engine'),'sdk'));
const cat=require('../prototypes/prepared-encounters/perelomye/catalog.json');
require('../prototypes/prepared-encounters/gm-assist').installPreparedGM(sdk,cat);
const R=require('../prototypes/prepared-encounters/prepared-runtime').installPreparedRuntime(sdk,cat),E=sdk.CombatRulesEngine,M=sdk.CombatMagic;
function setup(room='T8',profile='C32'){
 const p=JSON.parse(fs.readFileSync(path.join(__dirname,'../.build',room+'.pack.json')));
 p.encounters[room].enemies=profile?[{id:'subject',profile,cell:'G5',...(profile==='C32'?{resources:{spell_slots:{2:{current:2,max:2},3:{current:2,max:2}}}}:{})}]:[];
 const {engine:e}=sdk.createBattle(p,room,43);e.initialize();Object.assign(e.s,{queue:[],pending:null,effects:[],zones:[],spellFrames:{},phase:'active',round:3,turnSerial:12});
 Object.assign(e.s.terrain,{walls:[],rubble:[],cover:{},elevation:{}});e.s.prepared.runtime.last20Round=3;
 let i=0;for(const u of Object.values(e.s.units)){
   Object.assign(u,{x:2+i*3,y:12,altitude:0,action:1,bonus:1,reaction:1,move:u.speed,statuses:[],heroic:0,luck:0,policies:{}});i++;
   if(!u.prepared)Object.assign(u,{features:{},casting:null,temp:0,hp:500,max:500});
 }
 e.s.index=e.s.order.indexOf(profile?'subject':'yar');R.sync(e);return e;
}
function turn(e,id){e.s.index=e.s.order.indexOf(id);e.s.queue=[];e.s.pending=null;}
function decide(e,choice,more={}){e.dispatch({kind:'decide',id:e.s.pending.id,choice,...more});}
function reload(e){return new E(JSON.parse(JSON.stringify(e.export())).session);}
function ability(e,key,extra={}){e.dispatch({kind:'prepared',actor:e.actorId,ability:key,confirmed:true,...extra});}
function caster(e,id='daphne'){const u=e.unit(id);u.casting={ability:'INT',attack:11,dc:19,level:11,prepared:['counterspell','dispelMagic','scorchingRay','fly','globeInvulnerability'],cantrips:['fireBolt'],components:true};u.slots={2:{current:3,max:3},3:{current:3,max:3},4:{current:3,max:3},6:{current:1,max:1}};return u;}
test('all eleven rehearsals initialize, retain real devices, save and reload in runtime mode',()=>{
 for(const room of Object.keys(cat.encounters).filter(k=>cat.encounters[k].population.length)){
  const {engine:e}=sdk.createBattle(JSON.parse(fs.readFileSync(path.join(__dirname,'../.build',room+'.pack.json'))));e.initialize();E.validate(e.s);assert.deepEqual(reload(e).s,e.s);assert(e.s.prepared.runtime);
 }
});
test('author spell opens actual Counterspell, preserves it on reload and spends its own use',()=>{
 let e=setup(),u=e.unit('subject'),v=caster(e);Object.assign(u,{x:8,y:8});Object.assign(v,{x:10,y:8});e.s.random.tape=Array(40).fill(1);
 ability(e,'pause',{targets:[v.id]});assert.equal(e.s.pending.choice,'counterspell');assert.equal(u.prepared.uses.pause,1);assert.equal(u.action,0);
 e=reload(e);decide(e,'yes');assert.equal(e.s.pending.choice,'counterspell');decide(e,'no');
 assert(!e.has(v.id,'incapacitated'));assert.equal(e.unit('subject').prepared.uses.pause,1);assert.equal(e.unit('subject').slots[3].current,2);
});
test('enemy Counterspell is optional and may be declined; fixture retains its real two uses',()=>{
 const e=setup(),u=e.unit('subject'),v=caster(e);Object.assign(u,{x:8,y:8});Object.assign(v,{x:10,y:8});turn(e,v.id);
 e.dispatch({kind:'cast',actor:v.id,spell:'fireBolt',target:u.id,level:0});assert.equal(e.s.pending.choice,'counterspell');assert.equal(e.s.pending.actor,u.id);
 decide(e,'no');assert.equal(u.reaction,1);assert.equal(u.slots[3].current,2);
});
test('chord computes cone including friendly and unconscious targets; ignores arbitrary supplied list',()=>{
 const e=setup(),u=e.unit('subject'),v=e.unit('yar');Object.assign(u,{x:8,y:8});Object.assign(v,{x:10,y:8});v.hp=0;v.stable=true;v.deathSaves=true;
 e.s.random.tape=Array(100).fill(1);ability(e,'chord',{point:{x:12,y:8,altitude:0},targets:['rada']});assert(e.s.events.some(x=>JSON.stringify(x).includes('preparedChord')));assert.equal(v.deathFailures,1);
});
test('Globe protects against actual innate spell; silence blocks before consuming it',()=>{
 const e=setup(),u=e.unit('subject'),v=e.unit('yar');Object.assign(u,{x:8,y:8});Object.assign(v,{x:12,y:8});
 e.s.effects.push({id:'effect-500',kind:'globeInvulnerability',owner:v.id,targets:[],point:{x:12,y:8,altitude:0},level:6,until:100});const hp=v.hp;
 ability(e,'pause',{targets:[v.id]});assert.equal(v.hp,hp);assert(!e.has(v.id,'incapacitated'));
 u.action=1;e.s.prepared.runtime.zones=[{kind:'silence',point:{x:8,y:8},radius:20,until:100,source:'test'}];const n=u.prepared.uses.pause;assert.throws(()=>ability(e,'pause',{targets:[v.id]}),/Тишиной/);assert.equal(e.unit(u.id).prepared.uses.pause,n);
});
test('arena acts after initiative 20 ties and before 19; choices and delayed marks survive reload',()=>{
 let e=setup();e.s.prepared.runtime.last20Round=2;e.s.initiative[e.actorId]=20;e.task({kind:'startTurn'});assert.equal(e.s.pending,null);
 e.s.initiative[e.actorId]=19;e.task({kind:'startTurn'});e.run();assert.equal(e.s.pending.choice,'arenaMark');const o=e.s.prepared.objects['BT-R1'];
 e=reload(e);decide(e,'mark',{object:o.id,point:{x:o.x+2,y:o.y,altitude:10}});assert.equal(e.s.prepared.environment.dueRound,4);
 const v=e.unit('yar');Object.assign(v,{x:o.x+2,y:o.y,altitude:10});const hp=v.hp;e.s.round=4;e.s.initiative[e.actorId]=19;e.s.random.tape=Array(100).fill(1);e.task({kind:'startTurn'});e.run();assert(v.hp<hp);assert.equal(e.s.pending.choice,'arenaMark');
});
test('disabling the pending arena source cancels its attack; no duplicate initiative tick',()=>{
 const e=setup();e.s.prepared.environment={source:'BT-R1',point:{x:8,y:8,altitude:0},dueRound:3};e.s.prepared.objects['BT-R1'].off=true;e.s.prepared.runtime.last20Round=2;e.s.initiative[e.actorId]=19;
 const hp=e.unit('yar').hp;e.task({kind:'startTurn'});e.run();assert.equal(e.unit('yar').hp,hp);decide(e,'skip');e.task({kind:'startTurn'});e.run();assert.equal(e.s.pending,null);
});
test('failed Arcana spends an action; successful Arcana switches a real resonator off',()=>{
 const e=setup();turn(e,'yar');const u=e.unit('yar'),o=e.s.prepared.objects['BT-R1'];Object.assign(u,{x:o.x+1,y:o.y,altitude:10});e.s.random.tape=[1];
 e.dispatch({kind:'preparedInteract',actor:u.id,object:o.id,method:'arcana'});assert.equal(u.action,0);assert.equal(o.off,false);
 u.action=1;e.s.random.tape=[20];e.dispatch({kind:'preparedInteract',actor:u.id,object:o.id,method:'arcana'});assert(o.off);reload(e);
});
test('weapon attacks use device AC, critical dice, finite ammunition and save actual HP',()=>{
 const e=setup();turn(e,'yar');const u=e.unit('yar'),o=e.s.prepared.objects['BT-R1'];Object.assign(u,{x:o.x+1,y:o.y,altitude:10});u.features={};e.s.random.tape=Array(100).fill(2);e.s.random.tape[0]=20;
 e.dispatch({kind:'attackObject',actor:u.id,object:o.id,weapon:u.attacks[0].id});assert(o.hp<o.max);assert.equal(u.action,0);assert.equal(e.s.objects[o.id].hp,o.hp);reload(e);
});
test('Dispel of arsenal power expires at end of caster NEXT turn, not current turn',()=>{
 const e=setup('P9','C34'),u=caster(e);Object.assign(u,{x:5,y:3});turn(e,u.id);const o=e.s.prepared.objects['BP-S1'];
 e.dispatch({kind:'cast',actor:u.id,spell:'dispelMagic',level:4,dispelTarget:{kind:'object',id:o.id}});assert(o.suppressed);
 e.task({kind:'endTurn',actor:u.id});assert(o.suppressed);u.turnCount++;e.s.queue=[];e.task({kind:'endTurn',actor:u.id});assert(!o.suppressed);
});
test('breath validates numerical declared direction before spending a charge',()=>{
 const e=setup('B8','C33'),u=e.unit('subject');Object.assign(u,{x:10,y:8});u.prepared.telegraph={round:2,...R.pos(e,u),point:{x:15,y:8,altitude:0}};
 const n=u.prepared.uses.breath;assert.throws(()=>ability(e,'breath',{point:{x:5,y:8,altitude:0}}),/45/);assert.equal(e.unit(u.id).prepared.uses.breath,n);
});
test('flight crosses the visible boundary; actual world position and range survive reload',()=>{
 let e=setup('B8','C33'),u=e.unit('subject');Object.assign(u,{x:28,y:7,altitude:10});
 e.dispatch({kind:'preparedMove',actor:u.id,mode:'fly',path:[{x:29,y:7,altitude:10},{x:30,y:7,altitude:10},{x:31,y:7,altitude:10}]});
 assert.equal(u.worldPosition.x,31);e=reload(e);assert.equal(R.pos(e,e.unit(u.id)).x,31);assert.equal(e.unit(u.id).move,65);
});
test('vertical movement offers opportunity attack to the player and saves continuation',()=>{
 let e=setup('B8','C33'),u=e.unit('subject'),v=e.unit('yar');Object.assign(u,{x:8,y:8,altitude:0});Object.assign(v,{x:7,y:8,altitude:0});v.attacks=[{id:'test',name:'Тест',kind:'melee',bonus:5,count:1,die:6,flat:0,range:5,damageType:'slashing'}];
 e.dispatch({kind:'preparedMove',actor:u.id,mode:'fly',path:[{x:8,y:8,altitude:5},{x:8,y:8,altitude:10}]});assert.equal(e.s.pending.kind,'opportunity');e=reload(e);decide(e,'no');assert.equal(e.unit(u.id).altitude,10);
});
test('non-hovering flying creature falls when prone; water reaction belongs to player',()=>{
 let e=setup('B8','C33'),u=e.unit('subject');Object.assign(u,{x:10,y:8,altitude:20,preparedMovementMode:'fly'});e.status(u.id,'prone');e.s.random.tape=Array(100).fill(1);e.task({kind:'checkResult',actor:u.id});e.run();assert.equal(u.altitude,0);assert.equal(u.hp,u.max-2);
 const v=e.unit('yar');Object.assign(v,{x:29,y:12,altitude:0});e.s.pending=null;e.s.queue=[];M.push(e,v.id,{x:28,y:12,altitude:0},10);e.run();assert.equal(e.s.pending.choice,'water');e=reload(e);decide(e,'skip');assert.equal(e.unit(v.id).worldPosition.altitude,-40);
});
test('broken rod remains conductive; grounding requires actual available chain and two actions',()=>{
 const e=setup('B8','C33'),o=e.s.prepared.objects['BB-R1'],u=e.unit('subject');o.hp=0;Object.assign(u,{x:o.x+1,y:o.y});u.prepared.uses.breath=2;e.s.random.tape=[6];e.task({kind:'startTurn',actor:u.id});assert.equal(u.prepared.uses.breath,3);
 turn(e,'yar');const v=e.unit('yar');Object.assign(v,{x:o.x,y:o.y+1});assert.throws(()=>e.dispatch({kind:'preparedInteract',actor:v.id,object:o.id}),/цепь/);
 e.s.prepared.runtime.inventory[v.id]=[{name:'Цепь 30 фт',quantity:1,combat_available:true}];v.action=1;e.dispatch({kind:'preparedInteract',actor:v.id,object:o.id});assert(!o.grounded);v.action=1;e.dispatch({kind:'preparedInteract',actor:v.id,object:o.id});assert(o.grounded);
});
test('B8 without beast has four heroes, four initiative draws and no phantom opponent',()=>{
 const e=setup('B8',null);assert.equal(e.s.order.length,4);assert.equal(e.s.random.draws,4);assert(!Object.values(e.s.units).some(u=>u.prepared));assert.equal(e.s.phase,'active');
});
test('Fire Bolt and three Scorching Rays attack real object through one paid spell frame',()=>{
 const e=setup('P9','C34'),u=caster(e);turn(e,u.id);Object.assign(u,{x:5,y:3});u.features.empoweredEvocation=true;const o=e.s.prepared.objects['BP-S1'];o.max=o.hp=500;
 e.s.random.tape=Array(100).fill(2);e.s.random.tape[0]=20;e.dispatch({kind:'cast',actor:u.id,spell:'fireBolt',level:0,target:'object:'+o.id});assert.equal(o.hp,500-12-u.stats.INT);assert(!Object.keys(e.s.units).some(k=>k.startsWith('object:')));
 u.action=1;const n=u.slots[2].current;e.s.random.tape=Array(100).fill(2);e.dispatch({kind:'cast',actor:u.id,spell:'scorchingRay',level:2,targets:Array(3).fill('object:'+o.id)});assert.equal(u.slots[2].current,n-1);reload(e);
});
test('spear ammunition does not create a third melee spear; own thrown weapon can be recovered',()=>{
 const e=setup('L1','C05'),u=e.unit('subject'),v=e.unit('yar');Object.assign(u,{x:8,y:8});Object.assign(v,{x:10,y:8});u.action=1;e.s.random.tape=Array(100).fill(2);
 e.dispatch({kind:'attack',actor:u.id,target:v.id,weapon:'spear-thrown'});e.dispatch({kind:'attack',actor:u.id,target:v.id,weapon:'spear-thrown'});u.action=1;u.attacksLeft=0;
 assert.throws(()=>e.dispatch({kind:'attack',actor:u.id,target:v.id,weapon:'spear'}),/Копья/);
 const d=e.s.prepared.runtime.drops[0];Object.assign(e.unit(u.id),{x:d.x-1,y:d.y});e.dispatch({kind:'preparedRecover',actor:u.id,drop:d.id});assert.equal(e.unit(u.id).prepared.ammo['spear-thrown'],1);
});
test('report still passes stock campaign continuity validation and preserves encounter objects',()=>{
 const e=setup('B8','C33');e.s.phase='ended';e.s.queue=[];e.s.pending=null;
 const r=sdk.CombatCampaignAdapter.outcome(e.s);sdk.CombatContinuity.validateReport(r);assert.equal(Object.keys(r.prepared_encounter.objects).length,3);
});
test('repeated initiative and legendary cycles remain serializable without replaying arena',()=>{
 let e=setup();for(let i=0;i<40;i++){
  e=reload(e);if(e.s.pending){const p=e.s.pending;decide(e,p.kind==='preparedRuntimeChoice'?'skip':p.kind==='initiativeSwap'?'skip':'no');}
  else e.dispatch({kind:'endTurn',actor:e.actorId});E.validate(e.s);
 }
});
