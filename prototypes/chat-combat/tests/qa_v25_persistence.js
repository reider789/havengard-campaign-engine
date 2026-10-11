// V25 persistence/DOM: verified without outside ChatGPT bindings or browser storage.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const directory=path.resolve(__dirname,'../core');
const script=fs.readFileSync(path.join(directory,'persistence.js'),'utf8');
const ctx=vm.createContext({JSON,Object,queueMicrotask});
vm.runInContext(script+';globalThis.TestCoordinator=CombatPersistenceCoordinator;',ctx);
let state={version:12,sourceRevision:27,units:{yar:{hp:100}},history:[]};
let writes=[],posted=[];
const c=new ctx.TestCoordinator({
 getState:()=>state,
 getSource:()=>({source_state_revision:27,data:'do not retransmit'}),
 embeddedRevision:27,getSetter:()=>v=>posted.push(v),
 store:v=>writes.push(v)
});
assert.equal(c.save(),true);
assert.equal(writes.length,1);
assert.equal(posted.length,1);
assert.equal(posted[0].source,undefined);
assert.deepEqual(JSON.parse(writes[0]).session.units.yar,{hp:100});
assert.equal(c.save(),true);
assert.equal(writes.length,1);
c.queueSave();c.queueSave();c.queueSave();
Promise.resolve().then(()=>{
 assert.equal(c.stats.scheduledChecks,1);
 assert.equal(writes.length,1);
 state.units.yar.hp=88;c.queueSave();c.queueSave();
 return Promise.resolve();
}).then(()=>{
 assert.equal(writes.length,2);
 assert.equal(posted.length,2);
 assert.equal(posted.at(-1).session.units.yar.hp,88);
 assert.equal(c.stats.scheduledChecks,2);
 // If runtime is newer than embedded data, the full source travels with the save.
 state.sourceRevision=28;
 const next=new ctx.TestCoordinator({getState:()=>state,
 getSource:()=>({source_state_revision:28,data:'new'}),
 embeddedRevision:27,getSetter:()=>v=>posted.push(v),store:v=>writes.push(v)});
 next.save();assert.equal(posted.at(-1).source.data,'new');
 console.log('V25 PERSISTENCE COORDINATOR QA PASSED');
}).catch(err=>{console.error(err);process.exitCode=1});
