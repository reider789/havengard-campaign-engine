#!/usr/bin/env node
/* Optional desktop QA against already built rehearsals. Never opens live G5. */
'use strict';
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(process.argv[2]||'playwright'),executablePath=process.argv[3];
const root=path.resolve(__dirname,'..'),directory=path.join(root,'.build'),errors=[];
(async()=>{
 const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--no-zygote','--single-process']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.stack));
  for(const room of ['T8','P9','B8','G4','T5']){
   await page.goto('file://'+path.join(directory,room+'.html'));await page.waitForSelector('#pr-actor');
   assert(await page.locator('#prepared-gm').isHidden());
   const state=await page.evaluate(()=>{const e=PreparedGMPort.getEngine();e.constructor.validate(e.s);return {count:Object.values(e.s.units).filter(u=>u.controlled).length,runtime:!!e.s.prepared.runtime,round:e.s.round};});
   assert.equal(state.count,4);assert(state.runtime);
   assert((await page.locator('#pr-point').boundingBox()).width>=180);
   await page.locator('#pr-actor').selectOption('daphne');await page.locator('#pr-action').selectOption('cast:fireBolt');assert.equal(await page.locator('#pr-level').inputValue(),'0');
   await page.locator('#pr-action').selectOption('cast:scorchingRay');assert.equal(await page.locator('#pr-level').inputValue(),'2');
   await page.locator('#pr-point').fill('invalid');await page.locator('#pr-do').click();assert.match(await page.locator('#pr-error').innerText(),/Клетка/);assert.equal(await page.locator('#pr-point').inputValue(),'invalid');
   // Serialize the exact browser state including its initial player choice.
   await page.evaluate(()=>{const e=PreparedGMPort.getEngine(),value=JSON.parse(JSON.stringify(e.export()));const restored=new e.constructor(value.session);restored.constructor.validate(restored.s);});
   if(room==='T8'){
    await page.locator('#prepared-runtime').screenshot({path:path.join(directory,'prepared-runtime-panel.png')});
    await page.evaluate(()=>{const e=PreparedGMPort.getEngine();for(let i=0;i<10&&e.s.pending?.kind==='initiativeSwap';i++)PreparedGMPort.act({kind:'decide',id:e.s.pending.id,choice:'skip'});const id=e.s.order.find(id=>e.unit(id).prepared?.profile==='C32');e.s.index=e.s.order.indexOf(id);e.s.pending=null;e.s.queue=[];e.unit(id).action=1;Object.assign(e.unit('yar'),{x:e.unit(id).x+3,y:e.unit(id).y,altitude:0});PreparedGMPort.render();});
    await page.waitForTimeout(250);
    const actor=await page.evaluate(()=>PreparedGMPort.getEngine().actorId);await page.locator('#pr-actor').selectOption(actor);await page.locator('#pr-action').selectOption('prepared:pause');await page.locator('#pr-target').selectOption('yar');await page.locator('#pr-point').fill('');
    await page.locator('#pr-do').click();await page.waitForTimeout(250);
    assert.equal(await page.evaluate(()=>PreparedGMPort.getEngine().unit(PreparedGMPort.getEngine().actorId).prepared.uses.pause),1);
   }
  }
  assert.deepEqual(errors,[]);const result={ok:true,rooms:['T8','P9','B8','G4','T5'],javascript_errors:errors,player_heroes:4,save_restore:true,form_error_retained:true,actual_innate_button:true};
  fs.writeFileSync(path.join(directory,'prepared-browser-verification.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
