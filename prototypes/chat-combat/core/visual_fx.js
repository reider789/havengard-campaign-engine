// Decorative visual layer. No mutation of game state, resources or dice rolls.
class CombatVisualFX {
 constructor(root,getState,getNames){
  this.root=root;this._state=getState;this._names=getNames;
  this.mode='standard';this.pending=[];this.active=[];this.processing=false;
  this.stats={events:0,created:0,dropped:0,peak:0};
  this.frame=root.querySelector('.boardframe');
  this.layer=document.createElement('div');this.layer.className='hvfx-layer';
  this.frame.appendChild(this.layer);
  this._controls();
  this.syncStatuses();
 }
 _controls(){
  const bar=document.createElement('div');bar.className='hvfx-toolbar';
  const label=document.createElement('label');label.textContent='✦ Анимации: ';
  const select=document.createElement('select');select.id='hvfx-quality';
  select.setAttribute('aria-label','Качество анимаций боя');
  for(const [value,name] of [['off','Выключены'],['standard','Стандарт'],['rich','Красиво']]){
   const op=document.createElement('option');op.value=value;op.textContent=name;select.appendChild(op);
  }
  let saved=null;try{saved=localStorage.getItem('hv-fx-quality-v1')}catch(_){}
  const reduced=typeof matchMedia==='function'&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  this.mode=['off','standard','rich'].includes(saved)?saved:(reduced?'off':'standard');
  select.value=this.mode;
  select.addEventListener('change',()=>{
   this.setMode(select.value);
   try{localStorage.setItem('hv-fx-quality-v1',this.mode)}catch(_){}
  });
  const hint=document.createElement('small');hint.textContent='Удары · заклинания · состояния';
  label.appendChild(select);bar.append(label,hint);
  const row=this.root.querySelector('.boardrow');row.parentElement.insertBefore(bar,row);
  this.select=select;
 }
 setMode(mode){
  if(!['off','standard','rich'].includes(mode))return false;
  this.mode=mode;if(this.select)this.select.value=mode;
  if(mode==='off'){for(const node of this.active)node.remove();this.active=[];this.pending=[]}
  this.syncStatuses();return true;
 }
 _byName(label){
  const names=this._names();
  return Object.keys(this._state().units).find(id=>names[id]===label)||null;
 }
 _school(text){
  if(/огн|плам|fire|шар/i.test(text))return'fire';
  if(/лед|лёд|мороз|холод|ice/i.test(text))return'ice';
  if(/молни|гроз|гром|thunder/i.test(text))return'storm';
  if(/разум|псих|ментал/i.test(text))return'mind';
  if(/паутин|опут|web/i.test(text))return'web';
  if(/леч|благослов|свет|священ|божеств/i.test(text))return'holy';
  return'arcane';
 }
 observeLog(raw){
  if(this.mode==='off'||!raw)return;
  const line=String(raw);let match=line.match(/^(.+?): −(\d+) ПЗ \(([^)]+)\)/);
  if(match){this.emit({kind:'damage',target:this._byName(match[1]),amount:+match[2],school:this._school(match[3])});return}
  match=line.match(/^(.+?): (.+?) → ([^;]+);[\s\S]*(ПОПАДАНИЕ|ПРОМАХ)/);
  if(match){
   this.emit({kind:match[4]==='ПОПАДАНИЕ'?'hit':'miss',
    source:this._byName(match[1]),target:this._byName(match[3]),
    school:this._school(match[2])});return;
  }
  match=line.match(/^(.+?) (?:использует|применяет|начинает колдовать|сотворяет) (.+)$/);
  if(match){
   const s=this._state(),caster=this._byName(match[1]);
   if(caster){this.emit({kind:'cast',source:caster,target:s.draft?.target||s.target,
     school:this._school(match[2]),point:s.draft?.point||null});return}
  }
  if(/Контрзаклинан|применяет Щит|использует Щит|Protection|Знак Стража/.test(line)){
   const actor=Object.keys(this._state().units).find(id=>line.includes(this._names()[id]))||'daphne';
   this.emit({kind:'reaction',target:actor,school:'ice'});return;
  }
  if(/получает состояние «|состояние «.+» прекращено/.test(line)){
   const label=line.split(/ получает|: состояние/)[0];
   this.emit({kind:'status',target:this._byName(label),school:this._school(line)});
  }
 }
 emit(event){
  if(this.mode==='off'||!event||!['hit','miss','damage','cast','reaction','status'].includes(event.kind))return false;
  this.stats.events++;
  if(this.pending.length>=24){this.pending.shift();this.stats.dropped++}
  this.pending.push({...event});
  if(!this.processing){this.processing=true;queueMicrotask(()=>{this.processing=false;this._flush()})}
  return true;
 }
 _center(id,point){
  const s=this._state(),unit=id?s.units[id]:null;
  const x=point?.x??unit?.x,y=point?.y??unit?.y;
  if(!Number.isInteger(x)||!Number.isInteger(y)||x<0||x>10||y<0||y>7)return null;
  const tile=this.root.querySelector('[data-tile="'+x+','+y+'"]');
  if(!tile)return null;
  const b=tile.getBoundingClientRect(),f=this.frame.getBoundingClientRect();
  return{x:b.left-f.left+b.width/2,y:b.top-f.top+b.height/2,size:Math.min(b.width,b.height)};
 }
 _node(type,center,txt,school){
  if(!center)return null;
  if(this.active.length>=16){this.stats.dropped++;return null}
  const node=document.createElement('span');
  node.className='hvfx-mark hvfx-'+type+' hvfx-'+(school||'arcane');
  node.style.left=center.x+'px';node.style.top=center.y+'px';
  if(txt)node.textContent=txt;
  this.layer.appendChild(node);this.active.push(node);
  this.stats.created++;this.stats.peak=Math.max(this.stats.peak,this.active.length);
  const remove=()=>{node.remove();const index=this.active.indexOf(node);if(index>=0)this.active.splice(index,1)};
  node.addEventListener('animationend',remove,{once:true});
  setTimeout(remove,1000);
  return node;
 }
 _projectile(from,to,school){
  const bullet=this._node('projectile',from,'',school);
  if(bullet){
   bullet.style.setProperty('--hvfx-dx',(to.x-from.x)+'px');
   bullet.style.setProperty('--hvfx-dy',(to.y-from.y)+'px');
  }
 }
 _flush(){
  const events=this.pending.splice(0);
  if(this.mode==='off')return;
  for(const ev of events){
   const target=this._center(ev.target,ev.point),source=this._center(ev.source);
   const school=ev.school||'arcane';
   if(ev.kind==='hit'){this._node('spark',target,'⚔',school);if(this.mode==='rich'&&source&&target)this._projectile(source,target,school)}
   else if(ev.kind==='miss')this._node('spark',target,'○','miss');
   else if(ev.kind==='damage'&&ev.amount>0)this._node('damage',target,'−'+ev.amount,school);
   else if(ev.kind==='cast'){
    this._node('rune',source,'✧',school);
    if(this.mode==='rich'&&source&&target)this._projectile(source,target,school);
    if(this.mode==='rich'&&ev.point&&target){
     const area=this._node('area',target,'',school);
     if(area)area.style.setProperty('--hvfx-size',(Math.round(target.size*5))+'px');
    }
   }
   else if(ev.kind==='reaction')this._node('shield',target||source,'⬡',school);
   else if(ev.kind==='status'&&this.mode==='rich')this._node('spark',target,'✦',school);
  }
  this.syncStatuses();
 }
 syncStatuses(){
  const s=this._state();
  for(const [id,u] of Object.entries(s.units)){
   if(!u||u.hp<=0)continue;
   const tile=this.root.querySelector('[data-tile="'+u.x+','+u.y+'"]');
   const unit=tile?.querySelector('.unit');if(!unit)continue;
   const status=k=>u.status?.some(v=>v.kind===k&&(v.until==null||v.until>s.elapsed));
   const buff=k=>s.effects?.some(e=>e.kind===k&&e.until>s.elapsed&&e.targets?.includes(id));
   const flags={burn:status('burn'),poison:status('poisoned')||status('toxic'),
     frost:status('frost'),web:status('restrained'),
     bless:buff('bless')||buff('heroism'),shield:buff('shield'),aim:status('aim')};
   for(const [k,on] of Object.entries(flags))unit.classList.toggle('hvfx-state-'+k,this.mode!=='off'&&!!on);
  }
 }
 afterRender(){this.syncStatuses()}
}
