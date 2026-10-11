// Havengard tactical visual skin v1; injected into engine's IIFE by build_chat_bundle.py.
// Visual-only layer: gameplay terrain/path/LOS/collision remains defined by campaign state.
const HG_SKIN_THEME=['meadow','forest','ruins','city'];
const HG_SKIN_ENEMY=['warrior','rogue','archer','mage','wolf','orc','undead','dragon'];
const HG_SKIN_REQUIRED=[
 ...HG_SKIN_THEME.map(k=>'backgrounds.'+k),
 ...['yar','daphne','lyutobor','rada'].map(k=>'heroes.'+k),
 ...HG_SKIN_ENEMY.map(k=>'enemies.'+k),
 'obstacles.wall','obstacles.rubble'
];
const HG_SKIN_STORAGE='havengard-chat-visual-pack-1';
const HG_SKIN_ART_URL='https://cdn.jsdelivr.net/gh/reider789/havengard-campaign-engine@acb428fc97a3281800feb7111931cc73d058a67c/prototypes/chat-combat/art/hayvengard_art_v1.json';
let hgSkinLoading=false, hgSkinNotice='';
let hgSkinAssets=null;
function hgSkinValidate(raw){
 if(!raw||raw.schema!=='havengard-combat-art-v1'||raw.version!==1||
    !raw.assets||typeof raw.assets!=='object')throw Error('Нужен пакет графики Хейвенгарда v1');
 const verified={};
 for(const key of HG_SKIN_REQUIRED){
  const x=raw.assets[key];
  if(!x||x.mime!=='image/webp'||typeof x.data!=='string'||x.data.length>900000||
     !/^data:image\/webp;base64,[A-Za-z0-9+/]+={0,2}$/.test(x.data))
     throw Error('Неверное изображение '+key);
  verified[key]=x.data;
 }
 for(const name of ['broken_wall','barricade','log','boulder','bush','pillar']){
  const x=raw.assets['obstacles.'+name];
  if(x?.mime==='image/webp'&&typeof x.data==='string'&&x.data.length<900000&&
     /^data:image\/webp;base64,[A-Za-z0-9+/]+={0,2}$/.test(x.data))
    verified['obstacles.'+name]=x.data;
 }
 return verified;
}
function hgSkinTheme(){
 if(!HG_SKIN_THEME.includes(s.visualTheme)){
  const fromStory=v21EmbeddedStory?.theme;
  s.visualTheme=HG_SKIN_THEME.includes(fromStory)?fromStory:
    HG_SKIN_THEME[Math.floor(Math.random()*HG_SKIN_THEME.length)];
 }
 return s.visualTheme;
}
function hgSkinEnemy(id){
 const enemy=(s.extraEnemies||[]).find(e=>e.id===id);
 if(enemy?.tokenKey&&HG_SKIN_ENEMY.includes(enemy.tokenKey))return enemy.tokenKey;
 if(id==='archer')return 'archer';
 if(id==='guard')return 'warrior';
 const name=String(enemy?.name||names[id]||'').toLowerCase();
 if(/волк|wolf|зверь|хищник/.test(name))return 'wolf';
 if(/орк|orc|огр|тролл|великан/.test(name))return 'orc';
 if(/скелет|зомби|нежить|мертвец|упырь|undead/.test(name))return 'undead';
 if(/дракон|демон|dragon/.test(name))return 'dragon';
 if(/маг|чарод|жрец|шаман|колдун|mage|wizard/.test(name))return 'mage';
 if(/лучник|арбалет|стрелок|archer/.test(name))return 'archer';
 if(/разбой|вор|ассасин|rogue|thief/.test(name))return 'rogue';
 return 'warrior';
}
const hgSkinStyle=document.createElement('style');
hgSkinStyle.textContent='#hv12.hg-skin-on .tile{background-color:#385b4d26!important}'+
 '#hv12.hg-skin-on .tile:nth-child(even){background-color:#385b4d18!important}'+
 '#hv12.hg-skin-on .tile.wall{background-color:#36414bbb!important}'+
 '#hv12.hg-skin-on .tile.rubble{background-color:#8a75558a!important}'+
 '#hv12.hg-skin-on .tile.smoke{background-color:#6d8495cc!important}'+
 '#hv12.hg-skin-on .tile.aoe{background-color:#b3523ab3!important}'+
 '#hv12.hg-skin-on .unit{border-radius:50%;color:transparent;font-size:0;border:2px solid #9ccdfa;background-color:#2b4e72;box-shadow:0 1px 5px #0009}'+
 '#hv12.hg-skin-on .unit.foe{border-color:#f0a18e;background-color:#6e3739}'+
 '#hv12.hg-skin-on .unit.now{outline:2px solid #ffd37c;outline-offset:1px}'+
 '#hv12.hg-skin-on .unit small{display:none}'+
 '#hv12.hg-skin-on .health{position:absolute;bottom:0;width:83%;height:5px;border:1px solid #2a1a27;background:#87313c}'+
 '#hv12.hg-skin-on .status,#hv12.hg-skin-on .status2{font-size:12px;color:white}';
root.appendChild(hgSkinStyle);
function hgSkinPaint(){
 const theme=hgSkinTheme();
 let ctrl=$('hg-skin-settings');
 if(!ctrl){
  ctrl=document.createElement('div');ctrl.id='hg-skin-settings';ctrl.className='syncbar';
  ctrl.innerHTML='<div class="buttons"><b>🎨 Оформление</b>'+
   '<label>Местность <select id="hg-skin-theme" style="color:#edf4f9;background:#234155;border:1px solid #8295a3;border-radius:4px;padding:5px">'+
   '<option value="meadow">Луг и дорога</option><option value="forest">Лесная поляна</option>'+
   '<option value="ruins">Руины</option><option value="city">Город</option></select></label>'+
   '<button type="button" class="btn" data-hg-art-retry>↻ Обновить оформление</button></div>'+
   '<small id="hg-skin-note" style="color:#c0d2de;font-size:10px"></small>';
  root.querySelector('.legend')?.insertAdjacentElement('afterend',ctrl);
 }
 $('hg-skin-theme').value=theme;
 $('hg-skin-note').textContent=hgSkinAssets?'✓ 4 фона · 4 героя · 8 типов врагов · препятствия':
  (hgSkinLoading?'Загрузка изображений…':hgSkinNotice||'Оформление доступно автоматически при подключении к сети. Сейчас используется резервный стиль.');
 const frame=$('board')?.parentElement;
 if(!frame)return;
 if(!hgSkinAssets){
  root.classList.remove('hg-skin-on');
  frame.style.removeProperty('background-image');
  return;
 }
 root.classList.add('hg-skin-on');
 const nextBackground='url("'+hgSkinAssets['backgrounds.'+theme]+'")';
 if(frame.style.backgroundImage!==nextBackground)frame.style.backgroundImage=nextBackground;
 frame.style.backgroundSize='100% 100%';
 frame.style.backgroundPosition='center';
 for(const tile of root.querySelectorAll('#board .tile')){
  const actorToken=tile.querySelector('.unit');
  if(actorToken){
   const coord=(tile.dataset.tile||'').split(',').map(Number);
   const id=at(coord[0],coord[1]);
   const k=heroes.includes(id)?'heroes.'+id:'enemies.'+hgSkinEnemy(id);
   const url=hgSkinAssets[k];
   if(url&&actorToken.dataset.hgSkinKey!==k){
    actorToken.style.backgroundImage='url("'+url+'")';
    actorToken.style.backgroundSize='cover';
    actorToken.style.backgroundPosition='center';
    actorToken.dataset.hgSkinKey=k;
   }
  }
  if(tile.classList.contains('wall')||tile.classList.contains('rubble')){
   const which=tile.classList.contains('wall')?'wall':'rubble';
   const xy=(tile.dataset.tile||'').split(',').map(Number);
   const cell='ABCDEFGHIJK'[xy[0]]+(xy[1]+1);
   const variants=which==='wall'?['wall','barricade','broken_wall','pillar']:['rubble','boulder','log','bush'];
   const defaultVariant=variants[(xy[0]*3+xy[1])%variants.length];
   const desired=s.obstacleSkins?.[cell]||defaultVariant;
   const url=hgSkinAssets['obstacles.'+desired]||hgSkinAssets['obstacles.'+which];
   if(url&&tile.dataset.hgSkinKey!==desired){
    tile.style.backgroundImage='url("'+url+'")';
    tile.style.backgroundSize='90% 90%';
    tile.style.backgroundRepeat='no-repeat';
    tile.style.backgroundPosition='center';
    tile.dataset.hgSkinKey=desired;
   }
  }
 }
}
const hgSkinPriorRender=render;
render=function(){hgSkinPriorRender();hgSkinPaint();};
function hgSkinAutoLoad(){
 if(hgSkinAssets||hgSkinLoading)return;
 hgSkinLoading=true;hgSkinNotice='';
 const after=()=>{hgSkinLoading=false;render()};
 fetch(HG_SKIN_ART_URL,{cache:'force-cache'})
  .then(response=>{if(!response.ok)throw Error('HTTP '+response.status);return response.json()})
  .then(pack=>{
   hgSkinAssets=hgSkinValidate(pack);
   try{localStorage.setItem(HG_SKIN_STORAGE,JSON.stringify(pack))}catch(_){}
   after();
  }).catch(err=>{
   hgSkinNotice='Изображения недоступны: используется встроенный стиль. '+String(err.message||err).slice(0,90);
   after();
  });
}
root.addEventListener('change',event=>{
 if(event.target?.id!=='hg-skin-theme')return;
 s.visualTheme=event.target.value;render();hostSave();
},true);
root.addEventListener('click',event=>{
 if(!event.target.closest('[data-hg-art-retry]'))return;
 event.preventDefault();hgSkinAssets=null;hgSkinAutoLoad();
},true);
try{
 const bundled=root.querySelector('script[data-hg-artpack]')?.textContent;
 if(bundled)hgSkinAssets=hgSkinValidate(JSON.parse(bundled));
 else{
  const cached=localStorage.getItem(HG_SKIN_STORAGE);
  if(cached)hgSkinAssets=hgSkinValidate(JSON.parse(cached));
 }
}catch(_){hgSkinAssets=null}
render();
if(!hgSkinAssets)hgSkinAutoLoad();
if(globalThis.__HV_ENABLE_TEST_APIS===true){
 Object.assign(globalThis.__HV_TEST_API,{
  artLoaded:()=>!!hgSkinAssets,
  artLoading:()=>hgSkinLoading,
  artURL:()=>HG_SKIN_ART_URL,
  artTheme:()=>s.visualTheme,
  artInstall:pack=>{hgSkinAssets=hgSkinValidate(pack);render()}
 });
}
