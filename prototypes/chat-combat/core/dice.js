// Deterministic, injectable random source; journal output stays with game actions.
class CombatDiceRoller {
  constructor(random=()=>Math.random()){this._random=random;}
  roll(sides){
    if(!Number.isInteger(sides)||sides<1)throw Error('Неверная кость');
    return Math.floor(this._random()*sides)+1;
  }
  rollMany(count,sides){
    if(!Number.isInteger(count)||count<0||count>1000)throw Error('Неверное число костей');
    return Array.from({length:count},()=>this.roll(sides));
  }
}
