'use strict';
const AtlasKinds={"ink":"Pincel","road":"Estrada","fence":"Cerca","wall":"Muro","house":"Casa","temple":"Templo","shop":"Loja","field":"Cultivo","crops":"Planta\u00e7\u00e3o","animal":"Animal","territory":"Territ\u00f3rio","well":"Po\u00e7o","fountain":"Fonte","watchtower":"Torre","windmill":"Moinho","barn":"Celeiro","stable":"Est\u00e1bulo","bridge":"Ponte","square":"Pra\u00e7a","garden":"Horta","forge":"Ferraria","bakery":"Padaria","tavern":"Taverna","market":"Banca de feira","lamp":"Lampi\u00e3o","campfire":"Fogueira","townhall":"Prefeitura","library":"Biblioteca","warehouse":"Armaz\u00e9m","castle":"Castelo","mine":"Entrada de mina","dock":"Cais","boat":"Barco","wagon":"Carro\u00e7a","tent":"Barraca","bench":"Banco","tree":"\u00c1rvore","pine":"Pinheiro","flowers":"Flores","boulder":"Rochas","banner":"Estandarte","background":"Pintar fundo","eraseBackground":"Borracha do fundo","eraseAll":"Apagar todas as camadas"};
const AtlasStampFootprints={"house":[2,2],"temple":[3,3],"shop":[2,2],"animal":[1,1],"well":[2,2],"fountain":[2,2],"watchtower":[2,3],"windmill":[3,3],"barn":[3,2],"stable":[3,2],"bridge":[3,2],"square":[3,3],"garden":[2,2],"forge":[2,2],"bakery":[2,2],"tavern":[3,2],"market":[2,2],"lamp":[1,2],"campfire":[1,1],"townhall":[3,2],"library":[2,2],"warehouse":[3,2],"castle":[3,3],"mine":[2,2],"dock":[3,2],"boat":[2,1],"wagon":[2,2],"tent":[2,2],"bench":[2,1],"tree":[2,2],"pine":[2,3],"flowers":[1,1],"boulder":[1,1],"banner":[1,2]};
const AtlasPartLayers={part_floor:'floor',part_wall:'building-wall',part_door:'building-wall',part_window:'building-wall',part_roof:'roof',part_table:'furniture',part_bed:'furniture',part_chest:'furniture',part_chair:'furniture',part_stairs:'furniture'};
Object.assign(AtlasKinds,{part_floor:'Piso',part_wall:'Parede',part_door:'Porta',part_window:'Janela',part_roof:'Telhado',part_table:'Mesa',part_bed:'Cama',part_chest:'Baú',part_chair:'Cadeira',part_stairs:'Escada',part_erase:'Borracha da construção'});
Object.assign(AtlasKinds,{pan:'Mover mapa',erase:'Borracha do desenho'});
const atlasLayer=k=>AtlasPartLayers[k]||(['road','fence','wall'].includes(k)?'line':Object.hasOwn(AtlasStampFootprints,k)?'stamp':k);
const atlasFootprint=k=>AtlasStampFootprints[k]||[1,1];
const atlasKey=c=>[c.dimension,c.grid,c.x,c.z,atlasLayer(c.kind),...(c.buildingId?[c.buildingId]:[])].join(':');

// Background cells are kept disjoint even when painting with a smaller grid.
// Split only the touched branches, preserving the rest of the old colour.
function atlasBackgroundPatch(model,cell,erase=false){
 const patch=new Map(),overlaps=p=>p.x<cell.x+cell.grid&&p.x+p.grid>cell.x&&p.z<cell.z+cell.grid&&p.z+p.grid>cell.z;
 const retain=p=>{
  if(!overlaps(p)){patch.set(atlasKey(p),p);return}
  if(p.grid<=cell.grid)return;
  const half=p.grid/2;for(const dx of [0,half])for(const dz of [0,half])retain({...p,x:p.x+dx,z:p.z+dz,grid:half});
 };
 for(const old of model.visible(cell.dimension,cell.x,cell.z,cell.x+cell.grid,cell.z+cell.grid))if(old.kind==='background'&&overlaps(old)){patch.set(atlasKey(old),null);retain(old)}
 if(!erase){const p={...cell,kind:'background',label:''};patch.set(atlasKey(p),p)}
 return patch;
}

const AtlasPixelGlyphs={
 A:'010101111101101',B:'110101110101110',C:'011100100100011',D:'110101101101110',E:'111100110100111',F:'111100110100100',G:'011100101101011',H:'101101111101101',I:'111010010010111',J:'001001001101010',K:'101101110101101',L:'100100100100111',M:'101111111101101',N:'101111111111101',O:'010101101101010',P:'110101110100100',Q:'010101101111011',R:'110101110101101',S:'011100010001110',T:'111010010010010',U:'101101101101111',V:'101101101101010',W:'101101111111101',X:'101101010101101',Y:'101101010010010',Z:'111001010100111',
 '0':'111101101101111','1':'010110010010111','2':'110001010100111','3':'110001010001110','4':'101101111001001','5':'111100110001110','6':'011100111101111','7':'111001010010010','8':'111101111101111','9':'111101111001110','-':'000000111000000','.':'000000000000010',':':'000010000010000','/':'001001010100100','?':'110001010000010','*':'000101010101000'
};
function atlasPixelText(c,text,x,y,ink='#484238',paper='#f4f0e4'){
 const chars=String(text).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase().slice(0,60),left=Math.round(x-(chars.length*8-2)/2),top=Math.round(y)-10,points=[];
 for(let n=0;n<chars.length;n++){const glyph=AtlasPixelGlyphs[chars[n]];if(!glyph)continue;for(let i=0;i<15;i++)if(glyph[i]==='1')points.push([left+n*8+(i%3)*2,top+Math.floor(i/3)*2])}
 c.save();c.fillStyle=paper;for(const[a,b]of points)c.fillRect(a-1,b-1,4,4);c.fillStyle=ink;for(const[a,b]of points)c.fillRect(a,b,2,2);c.restore();
}
function atlasTerritoryContours(cells,model){
 const groups=new Map();
 for(const p of cells){if(p.kind!=='territory')continue;const groupKey=JSON.stringify([p.grid,p.color,p.label]),group=groups.get(groupKey)||{grid:p.grid,color:p.color,label:p.label,cells:[],edges:[]};groups.set(groupKey,group);group.cells.push(p);const g=p.grid;
  for(const[dx,dz,a,b,u,v]of [[0,-1,0,0,1,0],[1,0,1,0,1,1],[0,1,1,1,0,1],[-1,0,0,1,0,0]]){const n=model.cells.get(atlasKey({...p,x:p.x+dx*g,z:p.z+dz*g}));if(n?.label===p.label&&n?.color===p.color)continue;group.edges.push([[p.x+a*g,p.z+b*g],[p.x+u*g,p.z+v*g]])}
 }
 for(const group of groups.values()){
  const starts=new Map(),remaining=new Set(group.edges.map((_,i)=>i));group.paths=[];
  group.edges.forEach((edge,i)=>{const k=edge[0].join(':');if(!starts.has(k))starts.set(k,[]);starts.get(k).push(i)});
  const direction=e=>e[1][0]>e[0][0]?0:e[1][1]>e[0][1]?1:e[1][0]<e[0][0]?2:3;
  while(remaining.size){let index=remaining.values().next().value;const first=group.edges[index][0],points=[first];let closed=false;
   while(remaining.has(index)){const edge=group.edges[index];remaining.delete(index);points.push(edge[1]);if(edge[1][0]===first[0]&&edge[1][1]===first[1]){closed=true;break}const candidates=(starts.get(edge[1].join(':'))||[]).filter(i=>remaining.has(i));if(!candidates.length)break;const dir=direction(edge),rank={1:0,0:1,3:2,2:3};candidates.sort((a,b)=>rank[(direction(group.edges[a])-dir+4)%4]-rank[(direction(group.edges[b])-dir+4)%4]);index=candidates[0]}
   group.paths.push({points,closed});
  }
 }
 return [...groups.values()];
}
class CartographyModel{
 constructor(cells=[],structures=[]){this.cells=new Map();this.buckets=new Map();this.structures=new Map(structures.map(s=>[s.id,{...s}]));this.undoStack=[];this.redoStack=[];this.version=0;for(const c of cells)this.set(c);this.version=0}
 set(c,key=atlasKey(c)){
  const old=this.cells.get(key);if(old){const b=this.buckets.get(this.bucket(old));b?.delete(key);if(!b?.size)this.buckets.delete(this.bucket(old))}
  if(c){this.cells.set(key,{...c});const bucket=this.bucket(c);if(!this.buckets.has(bucket))this.buckets.set(bucket,new Set());this.buckets.get(bucket).add(key)}else this.cells.delete(key);this.version++;
 }
 bucket(c){return [c.dimension,Math.floor(c.x/64),Math.floor(c.z/64)].join(':')}
 visible(d,minX,minZ,maxX,maxZ){const out=[];for(const[b,keys]of this.buckets){const[dim,x,z]=b.split(':').map(Number);if(dim!==d||x*64>maxX||z*64>maxZ||(x+1)*64<minX-48||(z+1)*64<minZ-48)continue;for(const key of keys){const c=this.cells.get(key),[w,h]=atlasFootprint(c.kind);if(c.x<=maxX&&c.z<=maxZ&&c.x+w*c.grid>=minX&&c.z+h*c.grid>=minZ)out.push(c)}}return out}
 mask(c){let mask=0;for(const[dx,dz,bit]of [[0,-1,1],[1,0,2],[0,1,4],[-1,0,8]]){const n=this.cells.get(atlasKey({...c,x:c.x+dx*c.grid,z:c.z+dz*c.grid}));if(n?.kind===c.kind)mask|=bit}return mask}
 begin(){this.transaction=new Map()}
 setStructure(value,id=value?.id){if(value)this.structures.set(id,{...value});else this.structures.delete(id);this.version++}
 changeStructure(value,id=value?.id){const before=this.structures.get(id);if(JSON.stringify(before)===JSON.stringify(value))return;const key='@structure:'+id;if(!this.transaction.has(key))this.transaction.set(key,{key,id,type:'structure',before:before?{...before}:null});this.setStructure(value,id);this.transaction.get(key).after=value?{...value}:null}
 apply(p,side){if(p.type==='structure')this.setStructure(p[side],p.id);else this.set(p[side],p.key)}
 buildingBounds(){if(this.boundsVersion===this.version)return this.boundsCache;const bounds=new Map();for(const c of this.cells.values())if(c.buildingId){const b=bounds.get(c.buildingId)||{minX:c.x,minZ:c.z,maxX:c.x+c.grid,maxZ:c.z+c.grid};b.minX=Math.min(b.minX,c.x);b.minZ=Math.min(b.minZ,c.z);b.maxX=Math.max(b.maxX,c.x+c.grid);b.maxZ=Math.max(b.maxZ,c.z+c.grid);bounds.set(c.buildingId,b)}this.boundsVersion=this.version;return this.boundsCache=bounds}
 partMask(c){let mask=0;for(const[dx,dz,bit]of [[0,-1,1],[1,0,2],[0,1,4],[-1,0,8]]){const n=this.cells.get(atlasKey({...c,x:c.x+dx*c.grid,z:c.z+dz*c.grid}));if(n&&n.buildingId===c.buildingId&&atlasLayer(n.kind)===atlasLayer(c.kind)&&n.color===c.color)mask|=bit}return mask}
 change(c,key=atlasKey(c)){const old=this.cells.get(key);if(JSON.stringify(old)===JSON.stringify(c))return;if(!this.transaction.has(key))this.transaction.set(key,{key,before:old?{...old}:null});this.set(c,key);this.transaction.get(key).after=c?{...c}:null}
 commit(){const patch=[...(this.transaction?.values()||[])];this.transaction=null;if(!patch.length)return false;this.undoStack.push(patch);this.redoStack=[];while(this.undoStack.length>50||this.undoStack.reduce((n,p)=>n+p.length,0)>20000)this.undoStack.shift();return true}
 cancel(){for(const p of this.transaction?.values()||[])this.apply(p,'before');this.transaction=null}
 undo(){const p=this.undoStack.pop();if(!p)return false;for(const c of p)this.apply(c,'before');this.redoStack.push(p);return true}
 redo(){const p=this.redoStack.pop();if(!p)return false;for(const c of p)this.apply(c,'after');this.undoStack.push(p);return true}
}

class MapEditor{
 constructor({map,getState,getToken}){
  this.map=map;this.getState=getState;this.getToken=getToken;this.buffers=new Map();this.world=null;this.shown=true;this.backgroundShown=true;this.active=false;this.panKey=false;this.generation=0;this.timer=null;this.hover=null;
  const el=id=>document.getElementById(id);this.el=el;
  this.workspace='map';this.paletteButtons=[];this.toolMemory={map:{tool:el('editTool').value||'pan',grid:el('editGrid').value||'4',brush:el('editBrush').value||'1',color:el('editColor').value||'#484238',label:el('editLabel').value||''},building:{tool:'part_floor',grid:'4',brush:'1',color:'#484238',label:''}};
  el('editEnabled').onchange=()=>{this.active=el('editEnabled').checked;this.cancel();this.controls()};
  el('editVisible').onchange=()=>{this.shown=el('editVisible').checked;map.invalidateOverlay()};
  el('editBackgroundVisible').onchange=()=>{this.backgroundShown=el('editBackgroundVisible').checked;map.invalidateOverlay()};
  el('editBackgroundColor').onchange=()=>{this.cancel();this.controls()};
  el('editBackgroundPreset').onchange=()=>{this.cancel();el('editBackgroundColor').value=el('editBackgroundPreset').value;el('editTool').value='background';this.controls()};
  el('editBuilding').onchange=()=>{this.cancel();if(this.buffer)this.buffer.selectedBuilding=el('editBuilding').value;this.buildingUISignature=null;this.controls()};
  el('editBuildingNew').onclick=()=>this.newBuilding();
  for(const id of ['editBuildingName','editBuildingDisplay','editBuildingIcon'])el(id).onchange=()=>this.updateBuilding();
  this.roofsShown=true;el('editRoofs').onchange=()=>{this.roofsShown=el('editRoofs').checked;map.invalidateOverlay()};
  for(const id of ['editTool','editGrid','editBrush','editColor','editLabel'])el(id).onchange=()=>{this.cancel();this.controls()};
  el('editUndo').onclick=()=>this.history(false);el('editRedo').onclick=()=>this.history(true);el('editSave').onclick=()=>this.save();
  el('editReload').onclick=()=>{this.cancel();this.load(this.world,true)};el('editJSON').onclick=()=>this.download();
  document.addEventListener('keydown',e=>{if(/^(INPUT|SELECT|TEXTAREA)$/.test(e.target?.tagName)||e.target?.isContentEditable)return;if(e.code==='Space'){this.panKey=true;if(this.stroke){this.end();this.map.editingPointer=null;const p=[...(this.map.pointers?.values()||[])][0];if(p)this.map.drag={point:p,x:this.map.camera.x,z:this.map.camera.z,moved:true}}e.preventDefault()}if(e.key==='Escape'){this.cancel();this.active=false;el('editEnabled').checked=false;this.controls()}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'&&this.active){e.preventDefault();this.history(e.shiftKey)}});
  document.addEventListener('keyup',e=>{if(e.code==='Space')this.panKey=false});
  window.addEventListener('blur',()=>{this.panKey=false;this.cancel()});
  window.addEventListener('beforeunload',e=>{if([...this.buffers.values()].some(b=>b.dirty)){e.preventDefault();e.returnValue=''}});
  this.controls();this.initPalettes();
 }
 suspend(){if(!this.active&&!this.stroke)return;this.cancel();this.active=false;this.el('editEnabled').checked=false;this.controls();this.map.invalidateOverlay()}
 setWorkspace(workspace){
  if(!['map','building'].includes(workspace))return;
  const changed=this.workspace!==workspace;
  if(changed){
   this.toolMemory[this.workspace]={tool:this.el('editTool').value,grid:this.el('editGrid').value,brush:this.el('editBrush').value,color:this.el('editColor').value,label:this.el('editLabel').value};this.suspend();this.workspace=workspace;
   const p=this.toolMemory[workspace];for(const[key,id]of Object.entries({tool:'editTool',grid:'editGrid',brush:'editBrush',color:'editColor',label:'editLabel'}))this.el(id).value=p[key];
   this.buildingUISignature=null;
  }
  const common=this.el('editorCommon'),target=this.el(workspace==='building'?'editorBuildingSlot':'editorMapSlot');if(common.parentElement!==target)target.append(common);
  this.el('editLabelField').hidden=workspace==='building';if(changed)this.controls();
 }
 chooseTool(kind){
  const workspace=kind.startsWith('part_')?'building':'map';this.setWorkspace(workspace);this.cancel();this.el('editTool').value=kind;
  this.active=kind!=='pan'&&this.canWrite();this.el('editEnabled').checked=this.active;this.controls();
 }
 initPalettes(){
  const categories={nature:['animal','tree','pine','flowers','boulder'],village:['well','fountain','bridge','square','garden','market','lamp','campfire','dock','boat','wagon','bench','banner','tent']};
  const category=kind=>Object.entries(categories).find(([,kinds])=>kinds.includes(kind))?.[0]||(AtlasStampFootprints[kind]?'buildings':'tools');
  const add=(container,kind,purpose)=>{
   const button=document.createElement('button');button.type='button';button.className='object-choice';button.dataset.kind=kind;
   const icon=document.createElement('canvas');icon.width=48;icon.height=48;icon.setAttribute('aria-hidden','true');this.drawToolPreview(kind,icon);
   const name=document.createElement('span');name.textContent=AtlasKinds[kind]||kind;button.append(icon,name);
   const[w,h]=atlasFootprint(kind);button.title=name.textContent+(purpose==='icon'?'':AtlasStampFootprints[kind]?' · '+w+' × '+h+' células':'');button.setAttribute('aria-label',button.title);button.setAttribute('aria-pressed','false');
   button.onclick=()=>{if(purpose==='icon'){this.el('editBuildingIcon').value=kind;this.updateBuilding()}else this.chooseTool(kind)};
   container.append(button);this.paletteButtons.push({button,kind,purpose,category:category(kind)});
  };
  for(const kind of Object.keys(AtlasKinds).filter(k=>!k.startsWith('part_')))add(this.el('editObjectPalette'),kind,'map');
  for(const kind of [...Object.keys(AtlasPartLayers),'part_erase'])add(this.el('editPartPalette'),kind,'building');
  for(const kind of Object.keys(AtlasStampFootprints))add(this.el('editBuildingIconPalette'),kind,'icon');
  if(!this.el('editObjectCategory').value)this.el('editObjectCategory').value='buildings';
  this.el('editObjectCategory').onchange=()=>this.syncPalettes();this.el('editObjectSearch').oninput=()=>this.syncPalettes();this.syncPalettes();
 }
 syncPalettes(){
  const text=s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const query=text(this.el('editObjectSearch').value||''),category=this.el('editObjectCategory').value||'buildings',building=this.buffer?.model.structures.get(this.buffer?.selectedBuilding);let visible=0;
  const signature=JSON.stringify([this.world,this.workspace,this.canWrite(),this.el('editTool').value,building?.id,building?.icon,category,query,this.paletteButtons.length]);if(signature===this.paletteSignature)return;this.paletteSignature=signature;
  for(const entry of this.paletteButtons){
   const{button,kind,purpose}=entry;
   button.hidden=purpose==='map'&&((!query&&category!=='all'&&entry.category!==category)||!text(AtlasKinds[kind]||kind).includes(query));
   if(purpose==='map'&&!button.hidden)visible++;
   button.disabled=kind!=='pan'&&(!this.canWrite()||purpose!=='map'&&!building);
   button.setAttribute('aria-pressed',String(purpose==='icon'?building?.icon===kind:this.el('editTool').value===kind&&this.workspace===purpose));
  }
  this.el('editObjectEmpty').hidden=visible>0;
  this.el('editChosenTool').textContent=(this.workspace==='building'?'Construir · ':'Desenhar · ')+(AtlasKinds[this.el('editTool').value]||'Escolha um objeto');
 }
 drawToolPreview(kind,canvas){
  const c=canvas.getContext?.('2d');if(!c)return;c.imageSmoothingEnabled=false;
  const generic={pan:['...#....','..###...','...#....','#..#..#.','########','#..#..#.','...#....','..###...'],ink:['......##','.....##.','....##..','...##...','..##....','.##.....','##......','#.......'],background:['...##...','..#pp#..','.#pppp#.','#pppppp#','.######.','...ppp..','..ppppp.','.ppppppp'],erase:['...####.','..#ppp#.','.#ppp#..','#ppp#...','.###....','....###.','........','........']};
  const bitmap=generic[kind]||(['eraseBackground','eraseAll','part_erase'].includes(kind)?generic.erase:null);
  if(bitmap){for(let z=0;z<8;z++)for(let x=0;x<8;x++)if(bitmap[z][x]!=='.'){c.fillStyle=bitmap[z][x]==='#'?'#484238':'#d8ceb8';c.fillRect(8+x*4,8+z*4,4,4)}return}
  const part=kind.startsWith('part_'),g=part?8:4,base={kind,grid:g,x:0,z:0,dimension:0,color:'#484238',label:'',...(part?{buildingId:'preview'}:{})},cells=[base];let x=g/2,z=g/2,scale=4;
  if(['road','fence','wall'].includes(kind)){for(const[dx,dz]of [[0,-1],[1,0],[0,1],[-1,0]])cells.push({...base,x:dx*g,z:dz*g});scale=3}
  if(['part_wall','part_door','part_window'].includes(kind)){base.grid=4;cells.length=0;cells.push(base,{...base,kind:'part_wall',x:-4},{...base,kind:'part_wall',x:4});x=z=2;scale=3}
  if(kind==='part_roof'){base.grid=4;cells.push({...base,x:4},{...base,z:4},{...base,x:4,z:4});x=z=4;scale=4}
  if(AtlasStampFootprints[kind]){const[w,h]=atlasFootprint(kind);x=w*g/2;z=h*g/2;scale=Math.min(5,Math.floor(40/Math.max(w*g,h*g,8)))}
  const preview=Object.create(MapEditor.prototype);preview.buffers=new Map([['preview',{model:new CartographyModel(cells,part?[{id:'preview',display:'detailed',grid:base.grid,dimension:0}]:[])}]]);preview.world='preview';preview.shown=true;preview.roofsShown=true;preview.map={style:{palette:'atlas'}};preview.active=false;
  preview.drawContents(c,{x,z,dimension:0,scale},48,48,false,true);
 }
 get buffer(){return this.buffers.get(this.world)}
 update(state){if(this.world!==state.world_id){this.cancel();clearTimeout(this.timer);this.world=state.world_id;this.active=false;this.el('editEnabled').checked=false;this.load(this.world)}else{const b=this.buffer,revision=state.annotations?.revision;if(b&&revision!=null&&revision!==b.revision&&!b.saving&&this.loading!==this.world){if(b.dirty||this.stroke)this.message('Outro navegador alterou a edi??o. Preserve seu JSON antes de recarregar.');else this.load(this.world)}}this.controls()}
 async load(world,discard=false){
  if(!world)return;const generation=++this.generation;const previous=this.buffers.get(world);
  if(previous?.dirty&&!discard){this.ready=true;this.message('Rascunho pendente deste mundo. Salve ou exporte JSON antes de recarregar.');this.controls();this.map.invalidateOverlay();return}
  this.loading=world;this.ready=false;this.controls();
  try{const response=await fetch('/api/annotations');if(!response.ok)throw Error('Não foi possível ler a edição: HTTP '+response.status);const data=await response.json();if(this.world!==world||generation!==this.generation||data.world_id&&data.world_id!==world)return;
   this.buffers.set(world,{model:new CartographyModel(data.cells||[],data.structures||[]),selectedBuilding:previous?.selectedBuilding||'',revision:data.revision||0,dirty:false,available:!!data.available,pin:!!data.pin_writes});this.ready=true;
   for(const[key,b]of this.buffers)if(this.buffers.size>3&&key!==world&&!b.dirty)this.buffers.delete(key);
   this.message(data.available?'Edição carregada. Ative o editor e escolha uma ferramenta.':'O editor requer armazenamento por mundo.');
  }catch(error){if(this.world===world)this.message(error.message)}finally{if(this.world===world&&generation===this.generation){this.loading=null;this.controls();this.map.invalidateOverlay()}}
 }
 message(text){this.el('editStatus').textContent=text}
 canWrite(){const b=this.buffer;return !!this.ready&&!!b?.available&&!!(this.getToken()||b.pin)}
 buildingControls(){
  const b=this.buffer,m=b?.model,selected=b?.selectedBuilding||'',signature=JSON.stringify([this.world,m?.version,selected]);
  const building=m?.structures.get(selected),tool=this.el('editTool').value;
  this.el('editBuildingNew').disabled=!this.canWrite()||m?.structures.size>=256;
  for(const id of ['editBuildingName','editBuildingDisplay','editBuildingIcon'])this.el(id).disabled=!!building&&!this.canWrite()||id!=='editBuildingName'&&!building;
  this.el('editGrid').disabled=!!building&&tool.startsWith('part_');
  if(signature===this.buildingUISignature)return;this.buildingUISignature=signature;
  const select=this.el('editBuilding');select.replaceChildren();
  const option=(target,value,text)=>{const o=document.createElement('option');o.value=value;o.textContent=text;target.append(o)};
  option(select,'','Desenho livre / escolha uma construção');for(const s of m?.structures.values()||[])option(select,s.id,(s.name||'Sem nome')+' · '+['Overworld','Nether','End'][s.dimension]);
  select.value=building?selected:'';if(b&&!building)b.selectedBuilding='';
  const icons=this.el('editBuildingIcon');icons.replaceChildren();for(const kind of Object.keys(AtlasStampFootprints))option(icons,kind,AtlasKinds[kind]);
  this.el('editBuildingName').value=building?.name||'';this.el('editBuildingDisplay').value=building?.display||'detailed';icons.value=building?.icon||'house';
  if(building&&this.workspace==='building')this.el('editGrid').value=String(building.grid);
 }
 buildingChange(value){this.cancel();const m=this.buffer.model;m.begin();m.changeStructure(value);if(m.commit()){this.buffer.dirty=true;this.schedule()}this.controls();this.map.invalidateOverlay()}
 newBuilding(){
  if(!this.canWrite()||this.buffer.model.structures.size>=256)return;
  this.setWorkspace('building');
  const id=globalThis.crypto?.randomUUID?.()||'building-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,10);
  const value={id,name:this.el('editBuildingNewName').value.trim().slice(0,60)||'Nova construção',dimension:this.map.camera.dimension,grid:Number(this.el('editGrid').value)||4,display:'detailed',icon:'house',color:this.el('editColor').value||'#484238'};
  this.el('editBuildingNewName').value='';this.buffer.selectedBuilding=id;this.active=true;this.el('editEnabled').checked=true;this.el('editTool').value='part_floor';this.buildingChange(value);
 }
 updateBuilding(){const old=this.buffer?.model.structures.get(this.buffer.selectedBuilding);if(!old||!this.canWrite())return;this.buildingChange({...old,name:this.el('editBuildingName').value.trim().slice(0,60),display:this.el('editBuildingDisplay').value,icon:this.el('editBuildingIcon').value})}
 viewCells(camera,width,height){
  const m=this.buffer.model,west=camera.x-width/camera.scale/2,north=camera.z-height/camera.scale/2,east=west+width/camera.scale,south=north+height/camera.scale,hidden=new Set();
  for(const s of m.structures.values())if(s.display==='icon'||s.display==='auto'&&(camera.displayScale||camera.scale)<2&&!(this.active&&this.workspace==='building'&&this.buffer.selectedBuilding===s.id))hidden.add(s.id);
  const cells=m.visible(camera.dimension,west,north,east,south).filter(p=>!hidden.has(p.buildingId)&&(this.roofsShown||p.kind!=='part_roof'));
  for(const id of hidden){const s=m.structures.get(id),b=m.buildingBounds().get(id);if(!b||s.dimension!==camera.dimension)continue;const[w,h]=atlasFootprint(s.icon),g=4,x=Math.floor((b.minX+b.maxX-w*g)/2),z=Math.floor((b.minZ+b.maxZ-h*g)/2);if(x>east||z>south||x+w*g<west||z+h*g<north)continue;cells.push({kind:s.icon,grid:g,x,z,dimension:s.dimension,color:s.color,label:s.name,virtualBuilding:id})}
  return cells;
 }
 controls(){this.buildingControls();const b=this.buffer;this.el('editEnabled').disabled=!this.canWrite();this.el('editUndo').disabled=!b?.model.undoStack.length;this.el('editRedo').disabled=!b?.model.redoStack.length;this.el('editSave').disabled=!b?.dirty||!!b?.saving||!this.canWrite();this.el('editJSON').disabled=!b;this.el('editorMode').hidden=!this.active||!this.canWrite();this.el('editorMode').textContent=(AtlasKinds[this.el('editTool').value]||this.el('editTool').value)+' | '+(this.el('editGrid').value||4)+' blocos | Espaco: mover';this.el('editCount').textContent=(b?.model.cells.size||0)+' / 20.000 células · '+(b?.dirty?'alterações pendentes':'salvo');this.map.overlay.dataset.editing=String(this.active&&this.canWrite()&&this.el('editTool').value!=='pan');const signature=[this.world,b?.model.version,this.active,this.shown,this.canWrite(),this.el('editTool').value,b?.selectedBuilding,this.workspace].join(':');if(signature!==this.uiSignature){this.uiSignature=signature;this.map.invalidateOverlay()}this.syncPalettes()}
 enabled(){return this.active&&this.canWrite()&&!this.panKey&&this.el('editTool').value!=='pan'}
 start(point,dimension){
  if(!this.enabled())return false;
  const kind=this.el('editTool').value,part=kind.startsWith('part_'),building=this.buffer.model.structures.get(this.buffer.selectedBuilding);
  if(part&&(!building||building.dimension!==dimension)){this.message('Escolha uma constru??o desta dimens?o antes de colocar pe?as.');return true}
  const grid=part?building.grid:Number(this.el('editGrid').value||4);
  if(this.map.camera.scale*grid<4){this.message('Aproxime o mapa: cada c?lula precisa aparecer com ao menos 4 pixels.');return true}
  this.stroke={priorDirty:this.buffer.dirty,dimension,kind,grid,color:kind==='background'?(this.el('editBackgroundColor').value||'#e6dbc1'):(this.el('editColor').value||'#484238'),label:part?'':this.el('editLabel').value.trim().slice(0,60),buildingId:part?building.id:null,brush:Number(this.el('editBrush').value)||1,count:0};
  this.buffer.model.begin();if(part&&building.display==='icon')this.buffer.model.changeStructure({...building,display:'detailed'});this.move(point);return true;
 }

 move(point){
  this.hover=point;if(!this.stroke){if(this.active)this.map.invalidateOverlay();return}
  const s=this.stroke,g=s.grid,x=Math.floor(point.x/g)*g,z=Math.floor(point.z/g)*g;
  if(s.last&&s.last[0]===x&&s.last[1]===z)return;
  if(atlasLayer(s.kind)==='stamp'){if(!s.last)this.paint(x,z);s.last=[x,z];return}
  let[a,b]=s.last||[x,z],guard=0;
  while((a!==x||b!==z)&&guard++<1024){this.paint(a,b);const dx=Math.sign(x-a),dz=Math.sign(z-b);if(['road','fence','wall','part_wall','part_door','part_window'].includes(s.kind)){if(Math.abs(x-a)>=Math.abs(z-b))a+=dx*g;else b+=dz*g}else{a+=dx*g;b+=dz*g}}
  this.paint(x,z);s.last=[x,z];this.map.invalidateOverlay();
 }
 paint(x,z){
  const s=this.stroke,m=this.buffer.model,g=s.grid;if(s.count>=2000)return;const version=m.version;
  for(let dz=0;dz<(atlasLayer(s.kind)==='stamp'?1:s.brush);dz++)for(let dx=0;dx<(atlasLayer(s.kind)==='stamp'?1:s.brush);dx++){
   const c={dimension:s.dimension,grid:g,x:x+dx*g,z:z+dz*g,kind:s.kind,color:s.color,label:s.label,...(s.buildingId?{buildingId:s.buildingId}:{})};
   if(['background','eraseBackground','eraseAll'].includes(s.kind)){
    const patch=atlasBackgroundPatch(m,c,s.kind!=='background');
    const size=m.cells.size+[...patch].reduce((n,[key,value])=>n+(value?1:0)-(m.cells.has(key)?1:0),0);
    if(size>20000||s.count+patch.size>2000){this.message('Limite de pintura atingido. Salve e continue com outro gesto.');return}
    for(const[key,value]of patch)m.change(value,key);
    s.count+=Math.max(0,patch.size-1);if(m.version!==version)this.buffer.dirty=true;
   }
   if(s.kind==='part_erase'){
    for(const old of m.visible(c.dimension,c.x,c.z,c.x+g-.001,c.z+g-.001))if(old.buildingId===s.buildingId&&old.x+old.grid>c.x&&old.z+old.grid>c.z&&(this.el('editPartEraseLayer').value==='all'||atlasLayer(old.kind)===this.el('editPartEraseLayer').value))m.change(null,atlasKey(old));
   }else if(s.kind==='erase'||s.kind==='eraseAll'){
    for(const old of m.visible(c.dimension,c.x,c.z,c.x+g-.001,c.z+g-.001)){const[w,h]=atlasFootprint(old.kind);if(old.kind!=='background'&&old.x+w*old.grid>c.x&&old.z+h*old.grid>c.z)m.change(null,atlasKey(old))}
   }else if(!['background','eraseBackground'].includes(s.kind)){
    if(m.cells.size>=20000&&!m.cells.has(atlasKey(c))){this.message('Limite de 20.000 células atingido. Apague parte da edição ou exporte o JSON.');return}
    if(atlasLayer(c.kind)==='stamp'){const[w,h]=atlasFootprint(c.kind);for(const old of m.visible(c.dimension,c.x,c.z,c.x+w*g-.001,c.z+h*g-.001)){const[ow,oh]=atlasFootprint(old.kind);if(atlasLayer(old.kind)==='stamp'&&old.x+ow*old.grid>c.x&&old.z+oh*old.grid>c.z)m.change(null,atlasKey(old))}}
    m.change(c);
   }s.count++;
  }if(m.version!==version)this.buffer.dirty=true;
 }
 end(){if(!this.stroke)return;this.stroke=null;const b=this.buffer;if(b.model.commit()){b.dirty=true;this.message('Salvando edição…');this.schedule()}this.controls()}
 cancel(){if(this.stroke){this.buffer?.model.cancel();if(this.buffer)this.buffer.dirty=this.stroke.priorDirty||!!this.buffer.saving;this.stroke=null;this.map.invalidateOverlay()}this.hover=null}
 history(redo){this.cancel();if(this.buffer&&(redo?this.buffer.model.redo():this.buffer.model.undo())){this.buffer.dirty=true;this.schedule()}this.controls()}
 schedule(){clearTimeout(this.timer);this.timer=setTimeout(()=>this.save(),900)}
 async save(){
  if(this.stroke){this.schedule();return}
  const b=this.buffer,world=this.world;if(!b?.dirty||b.saving||!this.canWrite())return;
  const version=b.model.version;const cells=[...b.model.cells.values()],structures=[...b.model.structures.values()];b.saving=true;this.controls();
  try{const response=await fetch('/api/annotations',{method:'PUT',headers:{'Content-Type':'application/json','X-Host-Token':this.getToken()||''},body:JSON.stringify({world_id:world,revision:b.revision,cells,structures})});if(!response.ok)throw Error(await response.text());const data=await response.json();b.revision=data.revision;b.dirty=b.model.version!==version;if(this.world===world){this.message(b.dirty?'Salvando novas alterações…':'Edição salva na pasta deste mundo.');if(b.dirty)this.schedule()}}
  catch(error){if(this.world===world)this.message('Não salvo: '+error.message+' Seu desenho permanece nesta aba. Use Exportar JSON para preservá-lo.')}
  finally{b.saving=false;if(this.world===world)this.controls()}
 }
 download(){const b=this.buffer;if(!b)return;const blob=new Blob([JSON.stringify({format:'chiko-cartography',version:2,world_id:this.world,cells:[...b.model.cells.values()],structures:[...b.model.structures.values()]},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='cartografia-'+this.world.slice(0,12)+'.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000)}
 draw(c,camera,width,height,dark=false,force=false){
  const model=this.buffer?.model;
  if(!model||!this.shown&&!force||!model.cells.size&&(!this.enabled()||!this.hover)){
   if(this.cachedCanvas){this.cachedCanvas.width=1;this.cachedCanvas.height=1;this.cacheKey=null}return;
  }
  const grid=Number(this.el('editGrid').value)||4,hover=!force&&this.enabled()&&this.hover?[Math.floor(this.hover.x/grid),Math.floor(this.hover.z/grid),grid,this.el('editTool').value,this.el('editBrush').value]:null;
  // One raster pixel per world block, like the terrain atlas. The extra border
  // keeps outlines intact at the viewport edges; only distant views downsample.
  const west=Math.floor(camera.x-width/camera.scale/2)-2,north=Math.floor(camera.z-height/camera.scale/2)-2;
  const blocksW=Math.ceil(camera.x+width/camera.scale/2)-west+2,blocksH=Math.ceil(camera.z+height/camera.scale/2)-north+2;
  const density=Math.min(1,Math.sqrt(4000000/(blocksW*blocksH)));
  const key=JSON.stringify([this.world,model.version,camera.dimension,west,north,blocksW,blocksH,dark,this.map.style?.palette,hover,force,this.backgroundShown,this.roofsShown,this.buffer.selectedBuilding,this.active,this.workspace,camera.scale>=2]);
  if(key!==this.cacheKey){
   this.cachedCanvas||=document.createElement('canvas');
   this.cachedCanvas.width=Math.max(1,Math.floor(blocksW*density));this.cachedCanvas.height=Math.max(1,Math.floor(blocksH*density));
   const ink=this.cachedCanvas.getContext('2d');
   if(!ink){this.drawContents(c,camera,width,height,dark,force);this.drawLabels(c,camera,width,height,dark,force);return}
   // Use one uniform transform; sampling back to world space remains exact.
   const rasterCamera={x:west+this.cachedCanvas.width/density/2,z:north+this.cachedCanvas.height/density/2,dimension:camera.dimension,scale:density,displayScale:camera.scale};
   this.drawContents(ink,rasterCamera,this.cachedCanvas.width,this.cachedCanvas.height,dark,force);this.cacheKey=key;
  }
  c.save();c.imageSmoothingEnabled=false;
  c.drawImage(this.cachedCanvas,(west-camera.x)*camera.scale+width/2,(north-camera.z)*camera.scale+height/2,this.cachedCanvas.width/density*camera.scale,this.cachedCanvas.height/density*camera.scale);c.restore();
  this.drawLabels(c,camera,width,height,dark,force);
 }
 drawLabels(c,camera,width,height,dark=false,force=false){
  const scale=camera.scale;if(scale<1)return;
  const west=camera.x-width/scale/2,north=camera.z-height/scale/2,m=this.buffer.model;
  const cells=this.viewCells(camera,width,height),night=dark&&this.map.style?.palette!=='atlas';
  const label=(text,x,z,ink)=>atlasPixelText(c,text,(x-camera.x)*scale+width/2,(z-camera.z)*scale+height/2,ink,night?'#233039':'#f4f0e4');
  for(const p of cells){if(!p.label||atlasLayer(p.kind)!=='stamp')continue;const[w,h]=atlasFootprint(p.kind);label(p.label,p.x+w*p.grid/2,p.z+h*p.grid+2,night&&p.color==='#484238'?'#d9dfd9':p.color)}
  const labelled=new Set();for(const p of cells)if(p.buildingId&&!labelled.has(p.buildingId)){labelled.add(p.buildingId);const s=m.structures.get(p.buildingId),b=m.buildingBounds().get(p.buildingId);if(s?.name&&b)label(s.name,(b.minX+b.maxX)/2,b.maxZ+2,night?'#d9dfd9':s.color)}
  for(const group of atlasTerritoryContours(cells,m))if(group.label){const n=group.cells.length;label(group.label,group.cells.reduce((a,p)=>a+p.x+p.grid/2,0)/n,group.cells.reduce((a,p)=>a+p.z+p.grid/2,0)/n,night?'#d9dfd9':group.color)}
 }
 drawContents(c,camera,width,height,dark=false,force=false){
  const m=this.buffer?.model;if(!m||!this.shown&&!force)return;
  const scale=camera.scale,west=camera.x-width/scale/2,north=camera.z-height/scale/2,cells=this.viewCells(camera,width,height);
  const night=dark&&this.map.style?.palette!=='atlas',paper=night?'#233039':'#f4f0e4';
  const color=p=>night&&p.color.toLowerCase()==='#484238'?'#d9dfd9':p.color;
  c.save();c.imageSmoothingEnabled=false;c.translate(-west*scale,-north*scale);c.scale(scale,scale);
  const rect=(x,z,w,h,ink)=>{c.fillStyle=ink;c.fillRect(Math.floor(x),Math.floor(z),Math.max(1,Math.round(w)),Math.max(1,Math.round(h)))};
  const pixel=(x,z,ink,size=1)=>rect(x-Math.floor(size/2),z-Math.floor(size/2),size,size,ink);
  const line=(x,z,u,v,ink,size=1,dashed=false)=>{
   x=Math.floor(x);z=Math.floor(z);u=Math.floor(u);v=Math.floor(v);
   const dx=Math.abs(u-x),dz=-Math.abs(v-z),sx=x<u?1:-1,sz=z<v?1:-1;let error=dx+dz,n=0;
   for(;;){if(!dashed||n++%6<3)pixel(x,z,ink,size);if(x===u&&z===v)break;const twice=2*error;if(twice>=dz){error+=dz;x+=sx}if(twice<=dx){error+=dx;z+=sz}}
  };
  const network=(p,ink,size)=>{
   const g=p.grid,x=p.x+Math.floor(g/2),z=p.z+Math.floor(g/2),mask=m.mask(p);
   if(!mask)pixel(x,z,ink,size);
   for(const[dx,dz,bit]of [[0,-1,1],[1,0,2],[0,1,4],[-1,0,8]])if(mask&bit)line(x,z,x+dx*g/2,z+dz*g/2,ink,size);
  };
  const roads=cells.filter(p=>p.kind==='road'),networks=cells.filter(p=>['wall','fence'].includes(p.kind));
  const territories=atlasTerritoryContours(cells,m);
  // All clearings precede every annotation. They cover the terrain underneath,
  // without one building's clearing erasing another hand-drawn road or border.
  // This mask is derived from the saved cells: erase/undo reveals the terrain.
  for(const p of cells){
   if(p.kind==='territory'||p.kind==='background')continue;
   if(p.kind==='road'){network(p,paper,Math.max(1,Math.round(p.grid*.25))+4);continue}
   if(p.kind==='wall'||p.kind==='fence'){network(p,paper,p.kind==='wall'?5:3);continue}
   const[w,h]=atlasFootprint(p.kind),width=w*p.grid,height=h*p.grid;
   // One world pixel of clearance, with stepped corners matching the atlas.
   rect(p.x-1,p.z,width+2,height,paper);rect(p.x,p.z-1,width,height+2,paper);
  }
  // A territory only clears a thin band along its edge, never its interior.
  for(const group of territories)for(const[a,b]of group.edges)line(...a,...b,paper,3);
  if(this.backgroundShown)for(const p of cells)if(p.kind==='background')rect(p.x,p.z,p.grid,p.grid,p.color);
  for(const group of territories)for(const[a,b]of group.edges)line(...a,...b,color(group),1,true);
  // Union passes keep intersections open. Three native pixels at grid 4 form
  // a one-pixel paper centre with a one-pixel ink bank on either side.
  for(const pass of ['outline','inside'])for(const p of roads){
   const width=Math.max(1,Math.round(p.grid*.25));
   if(pass==='outline')network(p,color(p),p.grid<3?1:width+2);
   else if(p.grid>=3)network(p,paper,width);
  }
  for(const p of networks){network(p,color(p),p.kind==='wall'?3:1);if(p.kind==='wall')network(p,paper,1)}
  for(const p of networks){const x=p.x+Math.floor(p.grid/2),z=p.z+Math.floor(p.grid/2);if(p.kind==='fence')pixel(x,z,color(p),2);else pixel(x,z,color(p))}
  const sprites={
   house:['.....#..','...#.p..','..#p##..','.#pppp#.','#p+pppp#','.#+#p+#.','.#pp#p#.','.######.'],
   shop:['........','..####..','.#pppp#.','########','#p#p#p##','.#+pp+#.','.#pppp#.','.######.'],
   temple:['.....##.....','....#pp#....','...#p++p#...','..#pppppp#..','.##########.','..#p#pp#p#..','..#p#pp#p#..','..#p#++#p#..','..#p#++#p#..','.##########.','#pppppppppp#','############'],
   animal:['...#','###p','#pp#','.#.#'],
   well:["..####..",".#pppp#.","########",".#pppp#.",".#p++p#.",".#++++#.",".#pppp#.","..####.."],
   fountain:["...##...","..#pp#..","...##...","..#pp#..",".##pp##.","#pp++pp#","#p++++p#",".######."],
   watchtower:["#p#pp#p#","########",".#pppp#.",".#p++p#.",".#pppp#.",".#pppp#.",".#p++p#.",".#pppp#.",".#pppp#.",".#p##p#.",".#p##p#.","########"],
   windmill:[".##......##.",".p##....##p.","..p##..##p..","...p####p...","....####....","...######...","..##p##p##..",".##pppppp##.","##ppp##ppp##",".pppp##pppp.","..#pp##pp#..","..########.."],
   barn:[".....##.....","....#pp#....","...#pppp#...","..#p++++p#..",".##########.","..#pp##pp#..","..#p#pp#p#..","..########.."],
   stable:["....####....","...#pppp#...","..########..",".#pppppppp#.","############",".#p#pppp#p#.",".#p#p##p#p#.",".##########."],
   bridge:["............","###pppppp###","...######...","###++++++###","...######...","###pppppp###","............","............"],
   square:["..########..",".#p+pppp+p#.","#pppppppppp#","#+p++pp++p+#","#pppppppppp#","#pppp##pppp#","#pppp##pppp#","#pppppppppp#","#+p++pp++p+#","#pppppppppp#",".#p+pppp+p#.","..########.."],
   garden:["########","#pppppp#","#p#pp#p#","#+#++#+#","#pppppp#","#p#pp#p#","#+#++#+#","########"],
   forge:[".....##.","..##.pp.",".#pp####","########",".#pppp#.",".#p###p.",".#pp#pp.",".######."],
   bakery:["......#.","..####p.",".#pppp#.","########",".#pppp#.",".#p##p#.",".#p##p#.",".######."],
   tavern:["....####....","...#pppp#...","..########..",".##########.",".#p++p++p#p.",".#ppppppp###",".#p++p##p#..",".#########.."],
   market:["........",".######.","#p#p#p##","########",".#pppp#.",".#++++#.","########",".#pppp#."],
   lamp:[".##.","#pp#","#++#",".##.","..#.","..#.","..#.",".###"],
   campfire:[".#..","#p#.","####","+##+"],
   townhall:[".....##.....","....#pp#....","...######...","..#pppppp#..",".##########.","..#p#pp#p#..","..#p#++#p#..","..########.."],
   library:["...##...","..#pp#..",".######.","#pppppp#","#p#+#pp#","#p#+#pp#","#pp##pp#","########"],
   warehouse:["....####....","...#pppp#...","..#pppppp#..",".##########.","..#p####p#..","..#p#++#p#..","..#p#++#p#..","..########.."],
   castle:["#p#......#p#","###..##..###","#p#.#pp#.#p#","#p###pp###p#","#p#pppppp#p#","#p#p#pp#p#p#","#p#pppppp#p#","#p#pp##pp#p#","#p#p#pp#p#p#","#p#p#++#p#p#","#ppp#++#ppp#","############"],
   mine:["..####..",".#pppp#.","#p####p#","#p#++#p#","#p#++#p#","#p#++#p#","###pp###","..+..+.."],
   dock:[".#..#..#..#.","############","#+pp+pp+pp+#","############","....#pp#....","....#++#....","....#pp#....","....####...."],
   boat:["...#....","...###..","#pp#ppp#",".######."],
   wagon:["........",".######.",".#++++#.",".#++++#.",".######.","..#..#..",".##..##.","........"],
   tent:["...#....","..#p#...","..#pp#..",".#pppp#.",".#p##p#.","#pp##pp#","########","#......#"],
   bench:["########","#++++++#","########",".#....#."],
   tree:["..####..",".#pppp#.","#p+p+pp#","#pppp+p#",".#pppp#.","..####..","...##...","..+##+.."],
   pine:["...##...","..#pp#..","..#pp#..",".#pppp#.","..#pp#..",".#p++p#.","#pppppp#",".#pppp#.","#pp++pp#","########","...##...","..+##+.."],
   flowers:[".#.#","#+#+",".#.#","+.+."],
   boulder:[".##.","#p+#","#++#","####"],
   banner:[".#..",".###",".#p#",".###",".#..",".#..",".#..","###."]
  };
  const ordered=cells.filter(p=>!['road','wall','fence','territory','background'].includes(p.kind)).sort((a,b)=>(atlasLayer(a.kind)==='stamp')-(atlasLayer(b.kind)==='stamp'));
  const ranks={'floor':0,'building-wall':1,'furniture':2,'roof':3,'stamp':4};ordered.sort((a,b)=>(ranks[atlasLayer(a.kind)]??-1)-(ranks[atlasLayer(b.kind)]??-1));
  for(const p of ordered){
   const g=p.grid,x=p.x,z=p.z,ink=color(p),detail=p.color.toLowerCase()==='#484238'?(night?'#94a7a6':'#a79f8d'):ink;
   if(p.kind==='part_floor'){
    rect(x,z,g,g,night?'#394139':'#e7dfcc');
    for(let j=0;j<g;j++)for(let i=0;i<g;i++)if((x+i+z+j)%8===0)pixel(x+i,z+j,detail);
    continue;
   }
   if(atlasLayer(p.kind)==='building-wall'){
    const mask=m.partMask(p),cx=x+Math.floor(g/2),cz=z+Math.floor(g/2),thickness=g>=8?2:1;
    pixel(cx,cz,ink,thickness);for(const[dx,dz,bit]of [[0,-1,1],[1,0,2],[0,1,4],[-1,0,8]])if(mask&bit)line(cx,cz,cx+dx*g/2,cz+dz*g/2,ink,thickness);
    if(p.kind!=='part_wall'){
     const horizontal=!!(mask&10)||!(mask&5),r=Math.max(1,Math.floor(g/3));
     if(horizontal){rect(cx-r,cz,r*2+1,thickness,paper);line(cx-r,cz-1,cx+r,cz-1,ink);if(p.kind==='part_window')line(cx-r,cz+1,cx+r,cz+1,detail);else line(cx-r,cz-1,cx-r,cz-r-1,detail)}
     else{rect(cx,cz-r,thickness,r*2+1,paper);line(cx-1,cz-r,cx-1,cz+r,ink);if(p.kind==='part_window')line(cx+1,cz-r,cx+1,cz+r,detail);else line(cx-1,cz-r,cx-r-1,cz-r,detail)}
    }continue;
   }
   if(p.kind==='part_roof'){
    const mask=m.partMask(p);rect(x,z,g,g,night?'#40483e':'#d8ceb8');
    for(let j=0;j<g;j++)for(let i=0;i<g;i++)if((x+i+z+j)%4===0)pixel(x+i,z+j,detail);
    if(!(mask&1))line(x,z,x+g-1,z,ink);if(!(mask&2))line(x+g-1,z,x+g-1,z+g-1,ink);if(!(mask&4))line(x,z+g-1,x+g-1,z+g-1,ink);if(!(mask&8))line(x,z,x,z+g-1,ink);
    for(const[dx,dz,a,b]of [[-1,-1,8,1],[1,-1,2,1],[1,1,2,4],[-1,1,8,4]])if((mask&a)&&(mask&b)){const n=m.cells.get(atlasKey({...p,x:x+dx*g,z:z+dz*g}));if(!n||n.color!==p.color)pixel(dx>0?x+g-1:x,dz>0?z+g-1:z,ink)}
    continue;
   }
   const furniture={part_table:['####','#pp#','#pp#','####'],part_bed:['####','#ss#','#pp#','####'],part_chest:['####','#p##','####','#pp#'],part_chair:['####','#pp#','####','.#.#'],part_stairs:['...#','..##','.###','####']}[p.kind];
   if(furniture){for(let row=0;row<4;row++)for(let col=0;col<4;col++){const code=furniture[row][col];if(code==='.')continue;const px=x+Math.floor(col*g/4),pz=z+Math.floor(row*g/4),w=Math.floor((col+1)*g/4)-Math.floor(col*g/4),h=Math.floor((row+1)*g/4)-Math.floor(row*g/4);if(w&&h)rect(px,pz,w,h,code==='#'?ink:code==='s'?detail:paper)}continue}
   if(p.kind==='ink'){rect(x,z,g,g,ink);continue}
   if(['field','crops'].includes(p.kind)){
    for(let j=1;j<g;j+=2)for(let i=0;i<g;i++){if(p.kind==='field'||i%3===1)pixel(x+i,z+j,detail);if(p.kind==='crops'&&i%3===1)pixel(x+i,z+j-1,ink)}continue;
   }
   const sprite=sprites[p.kind];if(!sprite)continue;
   const[w,h]=atlasFootprint(p.kind),sw=sprite[0].length,sh=sprite.length;
   // Sprite gaps show the cleared paper prepared before the annotation pass.
   for(let row=0;row<sh;row++)for(let col=0;col<sw;col++){
    const code=sprite[row][col];if(code==='.')continue;
    const px=x+Math.floor(col*w*g/sw),pz=z+Math.floor(row*h*g/sh),pw=Math.floor((col+1)*w*g/sw)-Math.floor(col*w*g/sw),ph=Math.floor((row+1)*h*g/sh)-Math.floor(row*h*g/sh);
    if(pw&&ph)rect(px,pz,pw,ph,code==='#'?ink:code==='+'?detail:paper);
   }
  }
  if(!force&&this.enabled()&&this.hover){
   const g=Number(this.el('editGrid').value)||4,tool=this.el('editTool').value,[w,h]=atlasLayer(tool)==='stamp'?atlasFootprint(tool):[Number(this.el('editBrush').value)||1,Number(this.el('editBrush').value)||1];
   const x=Math.floor(this.hover.x/g)*g,z=Math.floor(this.hover.z/g)*g,ink=night?'#fff':'#484238';
   line(x,z,x+w*g,z,ink,1,true);line(x+w*g,z,x+w*g,z+h*g,ink,1,true);line(x+w*g,z+h*g,x,z+h*g,ink,1,true);line(x,z+h*g,x,z,ink,1,true);
  }
  c.restore();
 }
}
