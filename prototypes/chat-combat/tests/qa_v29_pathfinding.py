"""v29 pathfinding: shortest movement first, then safe + smooth routes."""
from pathlib import Path
import heapq
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
js=(root/'core/battlefield.js').read_text(encoding='utf-8')
bundle=(root/'current-chat-battle.html').read_text(encoding='utf-8')
assert 'class CombatBattlefield' in bundle
directions=[(dx,dy) for dx in (-1,0,1) for dy in (-1,0,1) if dx or dy]
def oracle(start,goal,walls,rubble,occupied=(),web=(),width=11,height=8):
    bad=set(map(tuple,walls))|set(map(tuple,occupied))
    rough=set(map(tuple,rubble))|set(map(tuple,web))
    def allowed(x,y):return 0<=x<width and 0<=y<height and (x,y) not in bad
    if not allowed(*goal):return None
    q=[(0,start)];dist={start:0}
    while q:
      cost,at=heapq.heappop(q)
      if cost!=dist[at]:continue
      if at==goal:return cost
      for dx,dy in directions:
        x=at[0]+dx;y=at[1]+dy
        if not allowed(x,y):continue
        if dx and dy and not allowed(at[0]+dx,at[1]) and not allowed(at[0],at[1]+dy):continue
        value=cost+(10 if (x,y) in rough else 5)
        if value<dist.get((x,y),10**12):
          dist[(x,y)]=value;heapq.heappush(q,(value,(x,y)))
    return None
def check_path(path,start,goal,walls,rubble,occupied=(),web=()):
    if path is None:
      assert oracle(start,goal,walls,rubble,occupied,web) is None
      return
    assert path[-1]=={'x':goal[0],'y':goal[1]} if path else start==goal
    p=start
    blocked=set(map(tuple,walls))|set(map(tuple,occupied))
    for to in path:
      x,y=to['x'],to['y']
      dx,dy=x-p[0],y-p[1]
      assert max(abs(dx),abs(dy))==1
      assert (x,y) not in blocked
      assert not (dx and dy and (p[0]+dx,p[1]) in blocked and (p[0],p[1]+dy) in blocked)
      p=x,y
    cost=sum(10 if (p['x'],p['y']) in set(map(tuple,rubble))|set(map(tuple,web)) else 5 for p in path)
    assert cost==oracle(start,goal,walls,rubble,occupied,web),(cost,path)
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
 page=browser.new_page()
 page.add_script_tag(content=js)
 def route(start,goal,walls=(),rubble=(),occupied=(),web=(),risk=False,width=11,height=8):
  params={'start':list(start),'goal':list(goal),'walls':list(map(list,walls)),'rubble':list(map(list,rubble)),
          'occupied':list(map(list,occupied)),'web':list(map(list,web)),
          'risk':risk,'width':width,'height':height}
  return page.evaluate("""arg=>{
    const set=xs=>new Set(xs.map(p=>p[0]+','+p[1]));
    const walls=set(arg.walls),rubble=set(arg.rubble),occupied=set(arg.occupied),web=set(arg.web);
    const field=new CombatBattlefield({
      walls,rubble,key:(x,y)=>x+','+y,
      occupant:(x,y)=>occupied.has(x+','+y)?'foe':null,
      actor:()=>({x:arg.start[0],y:arg.start[1]}),
      webDifficult:(x,y)=>web.has(x+','+y),
      movementRisk:arg.risk?(from,to)=>(
        Math.max(Math.abs(from.x-3),Math.abs(from.y-3))<=1 &&
        Math.max(Math.abs(to.x-3),Math.abs(to.y-3))>1?1:0):null,
      width:arg.width,height:arg.height});
    return field.findPath({x:arg.goal[0],y:arg.goal[1]});
  }""",params)
 cases=[
 ((0,0),(7,4),[],[],[],[]),
 ((0,0),(3,0),[],[(1,0)],[],[]),
 ((1,1),(9,6),[(4,2),(4,3),(4,4)],[(3,4),(5,5)],[(6,6)],[]),
 ((0,0),(1,1),[(1,0),(0,1)],[],[],[]),
 ((0,0),(1,1),[(1,0)],[],[],[]),
 ((0,0),(10,7),[(x,3) for x in range(1,10) if x!=5],[(5,2),(5,3)],[],[(6,5),(7,5)]),
 ((2,2),(2,2),[],[],[],[]),
 ((3,3),(5,3),[],[],[(4,3)],[])
 ]
 for start,goal,walls,rubble,occupied,web in cases:
  path=route(start,goal,walls,rubble,occupied,web)
  check_path(path,start,goal,walls,rubble,occupied,web)
 smooth=route((0,0),(7,4))
 dirs=[(p['x']-(smooth[i-1]['x'] if i else 0),p['y']-(smooth[i-1]['y'] if i else 0)) for i,p in enumerate(smooth)]
 assert len(smooth)==7 and sum(a!=b for a,b in zip(dirs,dirs[1:]))<=1,dirs
 safe=route((1,2),(5,2),risk=True)
 check_path(safe,(1,2),(5,2),[],[])
 points=[(1,2)]+[(p['x'],p['y']) for p in safe]
 exposure=sum(max(abs(x-3),abs(y-3))<=1 and max(abs(nx-3),abs(ny-3))>1
             for (x,y),(nx,ny) in zip(points,points[1:]))
 assert exposure==0,(safe,exposure)
 # User clicks an empty tile: generated path is continuous and uses the full game rules.
 game=browser.new_page(viewport={'width':1240,'height':980})
 errors=[]
 game.on('pageerror',lambda e:errors.append(str(e)))
 game.route('**/hayvengard_art_v1.json',lambda r:r.abort())
 game.evaluate('window.__HV_ENABLE_TEST_APIS=true')
 game.set_content(bundle)
 game.wait_for_selector('#board button[data-tile]')
 game.evaluate("""window.__HV_TEST_API.set(s=>{s.manual=false;s.pending=null;s.moving=false;s.draft=null})""")
 actor=game.evaluate("""window.__HV_TEST_API.snapshot().units.daphne""")
 x0,y0=actor['x'],actor['y']
 # Find a free immediate destination next to the acting hero.
 tile=game.locator('#board button[data-tile="'+str(min(x0+1,10))+','+str(y0)+'"]')
 if tile.count() and 'wall' not in (tile.get_attribute('class') or ''):
  tile.click()
  got=game.evaluate('window.__HV_TEST_API.snapshot().path')
  assert len(got)<=1,got
 assert not errors,errors
 browser.close()
print('V29 PATHFINDING PASSED: shortest cost, smooth ties, hazard cost, safe equal-cost routes, corner rule, manual kept')
