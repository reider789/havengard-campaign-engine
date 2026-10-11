// Unit-level isolation: class handlers have no ambient battle state or free host helpers.
// The same handler instance MUST follow a swapped/imported session, not the first one.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const core=path.join(__dirname,'../core');
const context=vm.createContext({Math,Number,JSON,Array,Object,Set,Map,Error});
for(const [file,clazz,variable] of [
 ['state_port.js','CombatStatePort',null],
 ['spell_resolver.js','CombatSpellResolver','combatSpellResolver'],
 ['reaction_resolver.js','CombatReactionResolver','combatReactionResolver'],
]){
 let code=fs.readFileSync(path.join(core,file),'utf8');
 if(variable)code=code.slice(0,code.lastIndexOf('const '+variable+'='));
 vm.runInContext(code+';globalThis.'+clazz+'='+clazz+';',context);
}
const StatePort=context.CombatStatePort;
const Spell=context.CombatSpellResolver;
const Reaction=context.CombatReactionResolver;
function newSession(){return {units:{daphne:{hp:50}},history:[],spellStack:[],pending:null,round:1};}
let current=newSession(),areaCalls=0,stackCalls=0;
const spellPort=new StatePort(()=>current,()=>({v18ContinueArea:()=>areaCalls++}));
const reactPort=new StatePort(()=>current,()=>({v19AdvanceSpellStack:()=>stackCalls++}));
const spells=new Spell(spellPort),reactions=new Reaction(reactPort);
spells.queueArea('daphne',['daphne'],[],'DEX',19,8,'огонь');
assert.equal(current.areaWork.raw,8);
assert.equal(current.areaWork.index,0);
assert.equal(areaCalls,1);
reactions.pushSpell({kind:'spell',caster:'daphne',spell:'web',level:2});
assert.equal(current.spellStack.length,1);
assert.equal(current.spellStack[0].prompted.length,0);
assert.equal(stackCalls,1);
const previous=current;
current=newSession();
spells.queueArea('daphne',['daphne'],[],'CON',15,11,'гром');
reactions.pushSpell({kind:'spell',caster:'daphne',spell:'hold',level:5});
assert.equal(current.areaWork.raw,11);
assert.equal(current.spellStack[0].spell,'hold');
assert.equal(previous.areaWork.raw,8);
assert.equal(previous.spellStack[0].spell,'web');
assert.equal(areaCalls,2);
assert.equal(stackCalls,2);
assert.throws(()=>new StatePort(null,()=>({})),/зависимости/);
assert.throws(()=>new StatePort(()=>null,()=>({})).getState(),/Состояние боя/);
assert.throws(()=>new Spell(null),/зависимости/);
assert.throws(()=>new Reaction(null),/зависимости/);
for(const [file,count] of [['spell_resolver.js',10],['reaction_resolver.js',9]]){
 const code=fs.readFileSync(path.join(core,file),'utf8');
 const matches=code.match(/const s=this\._port\.getState\(\)/g)||[];
 assert.equal(matches.length,count,file+' must read state inside each method');
 assert.doesNotMatch(code,/\bconst combat(?:Spell|Reaction)Resolver=new Combat(?:Spell|Reaction)Resolver\(\);/);
}
console.log('V24 STATE PORT DEPENDENCY INJECTION QA PASSED');
