// Movement, difficult terrain and least-cost pathfinding, separated from UI.
class CombatBattlefield {
  constructor({walls,rubble,key,occupant,actor,webDifficult,width=11,height=8}){
    Object.assign(this,{_walls:walls,_rubble:rubble,_key:key,_occupant:occupant,
      _actor:actor,_webDifficult:webDifficult,_width:width,_height:height});
  }
  isWall(x,y){return this._walls.has(this._key(x,y));}
  isDifficult(x,y){return this._rubble.has(this._key(x,y))||this._webDifficult(x,y);}
  pathCost(path){return path.reduce((n,p)=>n+(this.isDifficult(p.x,p.y)?10:5),0);}
  findPath(goal){
    if(this.isWall(goal.x,goal.y)||this._occupant(goal.x,goal.y))return null;
    const src=this._actor(),key=this._key;
    const q=[{x:src.x,y:src.y,c:0,path:[]}],best={[key(src.x,src.y)]:0};
    while(q.length){
      q.sort((a,b)=>a.c-b.c);
      const p=q.shift();
      if(best[key(p.x,p.y)]!==p.c)continue;
      if(p.x===goal.x&&p.y===goal.y)return p.path;
      for(let dx=-1;dx<=1;dx++)for(let dy=-1;dy<=1;dy++){
        if(!dx&&!dy)continue;
        const x=p.x+dx,y=p.y+dy;
        if(x<0||x>=this._width||y<0||y>=this._height||
           this.isWall(x,y)||this._occupant(x,y))continue;
        const c=p.c+(this.isDifficult(x,y)?10:5),k=key(x,y);
        if(c<(best[k]??Infinity)){
          best[k]=c;q.push({x,y,c,path:[...p.path,{x,y}]});
        }
      }
    }
    return null;
  }
}
