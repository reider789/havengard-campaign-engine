#!/usr/bin/env node
/* GM-side SDK bridge. The player never has to author a JSON command. */
"use strict";
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const [engineRoot,sessionPath,requestPath,outputPath]=process.argv.slice(2);
const fail=s=>{throw Error(s);};
try{
 if(!outputPath)fail('Usage: prepared_gm_turn.js ENGINE SESSION REQUEST OUTPUT');
 if(path.resolve(outputPath)===path.resolve(sessionPath))fail('Write a new checkpoint; do not overwrite the received save');
 const bytes=fs.readFileSync(sessionPath),request=JSON.parse(fs.readFileSync(requestPath,'utf8'));
 const hash=crypto.createHash('sha256').update(bytes).digest('hex');
 if(request.session_sha256!==hash)fail('Stale or unpinned session');
 if(!Array.isArray(request.commands)||request.commands.length>100)fail('Expected at most 100 explicit GM commands');
 const value=JSON.parse(bytes),sdk=require(path.resolve(engineRoot,'sdk'));
 const catalogue=require('../prototypes/prepared-encounters/perelomye/catalog.json');
 require('../prototypes/prepared-encounters/gm-assist').installPreparedGM(sdk,catalogue);
 require('../prototypes/prepared-encounters/prepared-runtime').installPreparedRuntime(sdk,catalogue);
 if(!value.contentPack?.requires?.includes(catalogue.engine.requiredExtension))fail('A complete prepared content pack is required');
 const runtime=sdk.CombatContentPack.compile(value.contentPack),e=new sdk.CombatRulesEngine(value.session);
 if(e.s.meta.campaignId!==runtime.campaign_id||!e.s.prepared)fail('Wrong session/pack');
 const allowed=new Set(['attack','move','cast','dash','disengage','dodge','hide','search','escape','flee','helpAttack','ready','constrict','endTurn','prepared','preparedEndTurn','preparedArena','preparedRuling','preparedMove','preparedInteract','preparedRecover','preparedZone','attackObject','decide']);
 for(const command of request.commands){
   if(!allowed.has(command.kind))fail('Unsupported GM command');
   if(command.kind==='decide'){
     const p=e.s.pending;if(!p)fail('No pending decision');
     if(e.unit(p.actor).controlled&&!(p.kind==='preparedChoice'&&p.choice==='legendary'||p.kind==='preparedRuntimeChoice'&&p.choice==='arenaMark'))fail('Player decision required; GM must not answer for a hero');
   }else{
     const actor=command.actor||e.actorId;
     if(e.unit(actor).controlled&&!['preparedArena','preparedRuling'].includes(command.kind))fail('The GM cannot control a player hero');
     if(e.unit(actor).controlled&&command.spendAction)fail('Do not spend a hero action through a GM command');
     if(command.target&&e.unit(command.target).controlled&&(command.reaction||command.resource))fail('Player resource decision required');
   }
   e.dispatch(command);
 }
 sdk.CombatRulesEngine.validate(e.s);
 const result={...e.export(),contentPack:value.contentPack};
 fs.writeFileSync(outputPath,JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify({output:outputPath,source_session_sha256:hash,
   actor:e.actorId,round:e.s.round,phase:e.s.phase,pending:e.s.pending,
   canonical_state_modified:false}));
}catch(error){console.error(error.message);process.exitCode=1;}
