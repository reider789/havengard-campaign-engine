#!/usr/bin/env node
"use strict";
const fs=require('node:fs'),path=require('node:path');
const [engineRoot,cataloguePath,packPath,encounter]=process.argv.slice(2);
const sdk=require(path.resolve(engineRoot,'sdk/index.js'));
const catalogue=JSON.parse(fs.readFileSync(cataloguePath,'utf8'));
require('../prototypes/prepared-encounters/gm-assist.js').installPreparedGM(sdk,catalogue);
 require('../prototypes/prepared-encounters/prepared-runtime').installPreparedRuntime(sdk,catalogue);
try {
 const pack=JSON.parse(fs.readFileSync(packPath,'utf8'));
 const {runtime,scene}=sdk.createBattle(pack,encounter);
 console.log(JSON.stringify({runtime,scene}));
}catch(e){console.error(e.stack);process.exitCode=1;}
