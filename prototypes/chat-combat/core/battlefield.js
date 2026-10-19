// Stable, minimum-cost movement on the 8-direction battle grid.
// Among equal-cost paths prefer fewer opportunity attacks, fewer turns,
// then cells nearer the direct line. This avoids arbitrary zigzags.
class CombatBattlefield {
  constructor({walls,rubble,key,occupant,actor,webDifficult,movementRisk=null,stepCost=null,canStop=null,width=11,height=8}){
    Object.assign(this,{_walls:walls,_rubble:rubble,_key:key,_occupant:occupant,
      _actor:actor,_webDifficult:webDifficult,_movementRisk:movementRisk,
      _stepCost:stepCost,_canStop:canStop,_width:width,_height:height});
  }
  inBounds(x,y){return Number.isInteger(x)&&Number.isInteger(y)&&x>=0&&y>=0&&x<this._width&&y<this._height;}
  isWall(x,y){return this._walls.has(this._key(x,y));}
  isDifficult(x,y){return this._rubble.has(this._key(x,y))||this._webDifficult(x,y);}
  isBlocked(x,y){return !this.inBounds(x,y)||this.isWall(x,y)||Boolean(this._occupant(x,y));}
  stepCost(p){return this._stepCost?this._stepCost(p):(this.isDifficult(p.x,p.y)?10:5);}
  pathCost(path){return path.reduce((n,p)=>n+this.stepCost(p),0);}
  findPath(goal){
    if(!goal||!this.inBounds(goal.x,goal.y))return null;
    const src=this._actor(),key=this._key;
    if(!src||!this.inBounds(src.x,src.y))return null;
    if(src.x===goal.x&&src.y===goal.y)return [];
    if(this.isBlocked(goal.x,goal.y)||(this._canStop&&!this._canStop(goal)))return null;
    const dxTarget=goal.x-src.x,dyTarget=goal.y-src.y;
    const directions=[[1,1],[-1,-1],[-1,1],[1,-1],[1,0],[-1,0],[0,1],[0,-1]];
    // Each incoming direction is a separate Dijkstra state: otherwise
    // arriving from a bad heading can discard a smoother continuation.
    const cmp=(a,b)=>a.cost-b.cost||a.risk-b.risk||a.turns-b.turns||
      a.deviation-b.deviation||a.serial-b.serial;
    let serial=0;
    const root={x:src.x,y:src.y,dir:-1,cost:0,risk:0,turns:0,deviation:0,parent:null,serial:serial++};
    const queue=[root],best=new Map([[key(src.x,src.y)+':-1',root]]);
    // Binary min-heap; the serial tie-break keeps exactly the previous paths.
    const push=(node)=>{let i=queue.length;queue.push(node);while(i){const p=(i-1)>>1;if(cmp(queue[p],node)<=0)break;queue[i]=queue[p];i=p;}queue[i]=node;};
    const pop=()=>{const first=queue[0],last=queue.pop();if(queue.length){let i=0;while(2*i+1<queue.length){let child=2*i+1;if(child+1<queue.length&&cmp(queue[child+1],queue[child])<0)child++;if(cmp(last,queue[child])<=0)break;queue[i]=queue[child];i=child;}queue[i]=last;}return first;};
    while(queue.length){
      const node=pop();
      if(best.get(key(node.x,node.y)+':'+node.dir)!==node)continue;
      if(node.x===goal.x&&node.y===goal.y){
        const path=[];let p=node;
        while(p.parent){path.push({x:p.x,y:p.y});p=p.parent;}
        return path.reverse();
      }
      for(let d=0;d<directions.length;d++){
        const [mx,my]=directions[d],x=node.x+mx,y=node.y+my;
        if(this.isBlocked(x,y))continue;
        // Legacy v29 corner policy is retained until the campaign migration.
        if(mx!==0&&my!==0&&this.isBlocked(node.x+mx,node.y)&&this.isBlocked(node.x,node.y+my))continue;
        const step=this.stepCost({x,y});
        const exposure=typeof this._movementRisk==='function'?
          Math.max(0,Number(this._movementRisk(node,{x,y}))||0):0;
        const cross=(x-src.x)*dyTarget-(y-src.y)*dxTarget;
        const candidate={x,y,dir:d,cost:node.cost+step,risk:node.risk+exposure,
          turns:node.turns+(node.dir>=0&&node.dir!==d?1:0),
          deviation:node.deviation+cross*cross,parent:node,serial:serial++};
        const stateKey=key(x,y)+':'+d,previous=best.get(stateKey);
        if(!previous||cmp(candidate,previous)<0){
          best.set(stateKey,candidate);push(candidate);
        }
      }
    }
    return null;
  }
}
if(typeof module!=="undefined")module.exports={CombatBattlefield};
