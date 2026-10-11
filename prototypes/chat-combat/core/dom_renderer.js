// Keyed, incremental DOM renderer: preserves unaffected 88-cell battlefield nodes.
class CombatDOMRenderer {
 constructor(board){this._board=board;this._previous=[];this.stats={boardPaints:0,tilesCreated:0,tilesUpdated:0,tilesRetained:0};}
 paintBoard(html){
  this.stats.boardPaints++;
  const cells=html.match(/<button data-tile="\\d+,\\d+"[\\s\\S]*?<\\/button>/g);
  if(!cells||cells.length!==88||this._board.children.length!==88||this._previous.length!==88){
   this._board.innerHTML=html;
   this._previous=cells||[];
   this.stats.tilesCreated+=88;
   return;
  }
  for(let i=0;i<88;i++){
    if(this._previous[i]===cells[i]){this.stats.tilesRetained++;continue;}
    const template=document.createElement('template');
    template.innerHTML=cells[i];
    this._board.children[i].replaceWith(template.content.firstElementChild);
    this.stats.tilesUpdated++;
  }
  this._previous=cells;
 }
}
