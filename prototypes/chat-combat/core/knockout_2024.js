// D&D 2024: Knock Out a Creature. No damage may be silently changed.
class CombatKnockout2024 {
 constructor(port){
  this.p=port;this.install();
 }
 install(){
  const p=this.p;
  const oldHurt=p.getHurt(),oldHit=p.getAfterWeaponHit(),oldEnemyTurn=p.getEnemyTurn(),
   oldHeal=p.getHeal(),oldRender=p.getRender();
  const s=()=>p.getState(),u=id=>s().units[id],names=()=>p.names();
  const knocked=id=>!!u(id)&&(u(id).status||[]).some(z=>z.kind==='unconscious'&&(z.until==null||z.until>s().elapsed));
  const allDefeated=()=>p.foes().length>0&&p.foes().every(id=>u(id)&&(+u(id).hp<=0||knocked(id)));
  function finish(){
   if(s().phase==='active'&&allDefeated()){
    s().phase='ended';
    p.log('Победа: все противники выведены из боя. Поверженные без сознания остаются живы.');
   }
  }
  p.setHurt((target,n,type='оружие')=>{
   const state=s(),mark=state.nonlethalMeleeContext,unit=u(target);
   if(mark&&mark.target===target&&p.party().includes(mark.attacker)&&
      p.foes().includes(target)&&unit&&unit.hp>0&&!knocked(target)&&
      Number.isFinite(n)&&n>0&&n-Math.max(0,unit.temp||0)>=unit.hp){
    state.pending={kind:'nonlethal2024',target,attacker:mark.attacker,rawDamage:n,damageType:type};
    p.log(names()[mark.attacker]+': решающий рукопашный удар по '+names()[target]+
      '. Выберите исход по правилам D&D 2024: оставить без сознания или нанести смертельный удар.');
    p.render();p.save();
    return;
   }
   const result=oldHurt(target,n,type);
   finish();
   return result;
  });
  p.setAfterWeaponHit((attacker,target,amount)=>{
   const state=s(),weapon=u(attacker)?.weapon;
   const melee=p.isMeleeWeapon(attacker,weapon,target);
   const previous=state.nonlethalMeleeContext;
   if(melee)state.nonlethalMeleeContext={attacker,target,source:'рукопашная атака'};
   try{return oldHit(attacker,target,amount);}
   finally{
    if(previous)state.nonlethalMeleeContext=previous;
    else delete state.nonlethalMeleeContext;
   }
  });
  p.setEnemyTurn(id=>{
   if(knocked(id)){
    p.log(names()[id]+': без сознания, не может действовать.');
    return false;
   }
   return oldEnemyTurn(id);
  });
  p.setHeal((id,amount)=>{
   const before=u(id)?.hp||0;
   const result=oldHeal(id,amount);
   if(knocked(id)&&u(id).hp>before){
    p.removeStatus(id,'unconscious');
    p.log(names()[id]+': приведён в сознание лечением.');
   }
   return result;
  });
  p.setRender(()=>{
   oldRender();
   const pending=s().pending;
   if(pending?.kind!=='nonlethal2024')return;
   const box=p.root().querySelector('#response');
   if(!box)return;
   const name=names()[pending.target]||pending.target;
   box.innerHTML='<div class="panel"><h3>⚔ Несмертельный удар — выбор исхода</h3>'+
    '<p>Рукопашная атака выводит '+p.escape(name)+' из боя. Удар и дополнительный урон уже рассчитаны.</p>'+
    '<p>По правилам D&D 2024: без сознания при 1 ПЗ, жив, пробуждение после короткого отдыха, лечения или успешной первой помощи.</p>'+
    '<div class="buttons">'+
    '<button class="btn primary" data-hg-ko="spare">Оставить в живых (вырубить)</button>'+
    '<button class="btn" data-hg-ko="lethal">Обычный завершающий удар</button></div></div>';
  });
  p.root().addEventListener('click',event=>{
   const button=event.target.closest('button[data-hg-ko]');
   if(!button||!p.root().contains(button))return;
   event.preventDefault();event.stopImmediatePropagation();
   const pending=s().pending;
   if(pending?.kind!=='nonlethal2024')return;
   const choice=button.dataset.hgKo;
   if(choice!=='spare'&&choice!=='lethal')return;
   s().pending=null;
   const target=pending.target;
   if(choice==='spare'){
    const targetUnit=u(target);
    targetUnit.temp=0;
    targetUnit.hp=1;
    targetUnit.reaction=0;
    targetUnit.knockedOutBy=pending.attacker;
    targetUnit.knockedOutAt=s().elapsed;
    p.addStatus(target,'unconscious',s().elapsed+3600);
    p.log(names()[pending.attacker]+' вырубил '+names()[target]+
      ': 1 ПЗ, «Без сознания» на время короткого отдыха. Цель жива.');
   }else{
    p.log(names()[pending.attacker]+': выбран обычный завершающий удар. '+names()[target]+' не оглушён.');
    oldHurt(target,pending.rawDamage,pending.damageType);
   }
   finish();p.render();p.save();
  },true);
  this.allDefeated=allDefeated;
  this.knocked=knocked;
 }
}
