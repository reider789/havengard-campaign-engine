// Coalesced saves: one snapshot per change, not per wrapper layer or redraw.
// Save format stays 'havengard-combat-session' v12.
class CombatPersistenceCoordinator {
 constructor({getState,getSource,embeddedRevision,getSetter,store}){
   Object.assign(this,{_getState:getState,_getSource:getSource,_embeddedRevision:embeddedRevision,
     _getSetter:getSetter,_store:store});
   this._lastJSON=null;this._queued=false;this._lastResult=false;
   this.stats={serializationCount:0,saveCount:0,hostUpdates:0,localUpdates:0,skippedDuplicates:0,scheduledChecks:0};
 }
 save(){
   const state=this._getState();
   let json;
   try{json=JSON.stringify(state);this.stats.serializationCount++;}catch(err){return false}
   if(json===this._lastJSON){this.stats.skippedDuplicates++;return this._lastResult}
   const source=this._getSource(),setter=this._getSetter();
   let saved=false;
   if(typeof setter==='function'){
      try{
       // Bundled canon already exists in the HTML; never resend ~60k unchanged chars on every action.
       const sameSource=source&&source.source_state_revision===this._embeddedRevision;
       const value={session:JSON.parse(json)};
       if(!sameSource&&source)value.source=source;
       setter(value);saved=true;this.stats.hostUpdates++;
      }catch(err){}
   }
   try{
     const wrapped='{"kind":"havengard-combat-session","version":12,"source_revision":'+
       JSON.stringify(state.sourceRevision)+',"session":'+json+'}';
     this._store(wrapped);saved=true;this.stats.localUpdates++;
   }catch(err){}
   if(saved){this._lastJSON=json;this.stats.saveCount++;}
   this._lastResult=saved;
   return saved;
 }
 queueSave(){
   if(this._queued)return;
   this._queued=true;
   queueMicrotask(()=>{
     this._queued=false;
     this.stats.scheduledChecks++;
     this.save();
   });
 }
}
