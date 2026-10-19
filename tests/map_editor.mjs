import fs from 'node:fs/promises';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';
export async function run(){
 const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,{value:'',checked:false,dataset:{},children:[],append(item){this.children.push(item)},replaceChildren(){this.children=[]},addEventListener(){}});return elements.get(id)};
 for(const[id,value]of Object.entries({editTool:'road',editGrid:'4',editBrush:'1',editColor:'#484238',editLabel:'North'}))element(id).value=value;
 const tasks=[];let saves=0,conflict=false;
 const listeners={};const box={document:{getElementById:element,createElement:()=>({dataset:{},children:[],append(...items){this.children.push(...items)},setAttribute(k,v){this[k]=v}}),addEventListener:(event,fn)=>{listeners[event]=fn}},window:{addEventListener(){}},setTimeout:f=>{tasks.push(f);return 1},clearTimeout(){},fetch:async(url,options)=>{if(!options)return {ok:true,json:async()=>({world_id:'one',available:true,revision:0,cells:[]})};saves++;return conflict?{ok:false,text:async()=> 'Conflito'}:{ok:true,json:async()=>({revision:saves})}}};vm.createContext(box);
 vm.runInContext(await fs.readFile(new URL('../src/chiko/web/map-editor.js',import.meta.url),'utf8'),box);
 vm.runInContext("globalThis.region=new CartographyModel();for(let z=0;z<3;z++)for(let x=0;x<3;x++)if(x!==1||z!==1)region.set({kind:'territory',dimension:0,grid:4,x:x*4,z:z*4,color:'#484238',label:'Realm'});globalThis.contours=atlasTerritoryContours([...region.cells.values()],region)",box);
 if(vm.runInContext('contours.length!==1||contours[0].paths.length!==2||contours[0].paths.some(p=>!p.closed)||contours[0].edges.length!==16',box))throw Error('Territory contours contain internal seams or lost their hole');
 vm.runInContext("globalThis.diagonal=new CartographyModel([{kind:'territory',dimension:0,grid:4,x:0,z:0,color:'#484238',label:'Realm'},{kind:'territory',dimension:0,grid:4,x:4,z:4,color:'#484238',label:'Realm'}]);globalThis.diagonalPaths=atlasTerritoryContours([...diagonal.cells.values()],diagonal)[0].paths",box);
 if(vm.runInContext('diagonalPaths.length!==2||diagonalPaths.some(p=>!p.closed)',box))throw Error('Diagonal territories self-cross');
 for(let mask=0;mask<16;mask++){
  box.expectedMask=mask;vm.runInContext("globalThis.checkModel=new CartographyModel();globalThis.center={kind:'wall',dimension:2,grid:8,x:-16,z:-8,color:'#484238',label:''};checkModel.set(center);for(const[dx,dz,bit]of [[0,-1,1],[1,0,2],[0,1,4],[-1,0,8]])if(expectedMask&bit)checkModel.set({...center,x:center.x+dx*8,z:center.z+dz*8});globalThis.actualMask=checkModel.mask(center)",box);
  if(box.actualMask!==mask)throw Error('Connection mask '+mask+' failed');
 }
 vm.runInContext("globalThis.model=new CartographyModel();model.begin();globalThis.cell={kind:'road',dimension:0,grid:4,x:-4,z:0,color:'#484238',label:''};model.change(cell);for(const[dx,dz]of [[0,-1],[1,0],[0,1],[-1,0]])model.change({...cell,x:cell.x+dx*4,z:cell.z+dz*4});model.commit()",box);
 if(vm.runInContext('model.mask(cell)!==15',box))throw Error('Cross junction / negative coordinates');
 vm.runInContext("model.begin();model.change(null,atlasKey({...cell,z:4}));model.commit()",box);
 if(vm.runInContext('model.mask(cell)!==11',box))throw Error('T junction after erase');
 vm.runInContext('model.undo()',box);if(vm.runInContext('model.mask(cell)!==15',box))throw Error('Undo did not reconnect');
 vm.runInContext('model.redo()',box);if(vm.runInContext('model.mask(cell)!==11',box))throw Error('Redo failed');
 vm.runInContext("globalThis.map={camera:{scale:4},overlay:{dataset:{}},invalidateOverlay(){}};globalThis.editor=new MapEditor({map,getState:()=>({world_id:'one'}),getToken:()=> 'host'});editor.update({world_id:'one'})",box);
 await new Promise(resolve=>setTimeout(resolve,0));
 vm.runInContext("editor.active=true;editor.start({x:0,z:0},0);editor.move({x:12,z:12});editor.end()",box);
 if(vm.runInContext('editor.buffer.model.cells.size!==7',box))throw Error('Network diagonal did not create a connected Manhattan path');
 await vm.runInContext('editor.save()',box);
 if(vm.runInContext('editor.buffer.dirty||editor.buffer.revision!==1',box))throw Error('Persistence failed');
 vm.runInContext("editor.start({x:0,z:0},0);editor.move({x:-12,z:-12});editor.cancel()",box);
 if(vm.runInContext('editor.buffer.model.cells.size!==7||editor.buffer.dirty',box))throw Error('Cancelled gesture left marks');
 vm.runInContext('editor.start({x:32,z:32},0)',box);
 listeners.keydown({code:'Space',key:' ',target:{tagName:'DIV'},preventDefault(){}});
 if(vm.runInContext('editor.stroke!=null||!editor.panKey||editor.enabled()',box))throw Error('Space did not switch from drawing to navigation');
 listeners.keyup({code:'Space'});
 vm.runInContext("editor.el('editTool').value='temple';editor.start({x:40,z:40},0);editor.move({x:80,z:80});editor.end()",box);
 if(vm.runInContext("[...editor.buffer.model.cells.values()].filter(c=>c.kind==='temple').length!==1",box))throw Error('Stamp repeats on drag');
 vm.runInContext("editor.el('editTool').value='erase';editor.start({x:44,z:44},0);editor.end()",box);
 if(vm.runInContext("[...editor.buffer.model.cells.values()].some(c=>c.kind==='temple')",box))throw Error('Multi-tile stamp erase failed');
 conflict=true;await vm.runInContext('editor.save()',box);
 if(vm.runInContext('!editor.buffer.dirty',box)||!element('editStatus').textContent.includes('Conflito'))throw Error('Conflict discarded local work');
 const artOps=[];
 box.artContext=new Proxy({fillRect(x,z,w,h){artOps.push({kind:'pixel',color:this.fillStyle,x,z,w,h})}},{get:(o,k)=>o[k]??((...args)=>{if(['stroke','arc','ellipse','quadraticCurveTo','bezierCurveTo','strokeText','fillText'].includes(k))throw Error('Smooth/vector operation in pixel atlas: '+k)})});
 vm.runInContext("globalThis.originalModel=editor.buffer.model;editor.buffer.model=new CartographyModel([{kind:'road',dimension:0,grid:4,x:0,z:0,color:'#484238',label:''},{kind:'road',dimension:0,grid:4,x:4,z:0,color:'#484238',label:''},{kind:'road',dimension:0,grid:4,x:4,z:4,color:'#484238',label:''},{kind:'road',dimension:0,grid:4,x:8,z:0,color:'#484238',label:''},{kind:'temple',dimension:0,grid:4,x:12,z:0,color:'#484238',label:'Temple'}]);globalThis.modelBeforeDrawing=JSON.stringify([...editor.buffer.model.cells]);editor.drawContents(artContext,{x:12,z:8,dimension:0,scale:1},400,300,false,true);globalThis.modelAfterDrawing=JSON.stringify([...editor.buffer.model.cells]);",box);
 if(!artOps.length||artOps.some(o=>![o.x,o.z,o.w,o.h].every(Number.isInteger)))throw Error('Pixel art uses fractional world pixels');
 const pixelAt=(x,z)=>artOps.filter(o=>x>=o.x&&x<o.x+o.w&&z>=o.z&&z<o.z+o.h).at(-1)?.color;
 if([2,3,4,5,6,7,8,9,10].some(x=>pixelAt(x,2)!=='#f4f0e4')||pixelAt(6,4)!=='#f4f0e4')throw Error('Road / T junction contains an ink seam');
 if(pixelAt(5,3)!=='#484238'||pixelAt(7,3)!=='#484238')throw Error('Pixel road lost its ink banks');
 if(!artOps.some(o=>o.x>=12&&o.color==='#a79f8d')||!artOps.some(o=>o.x>=12&&o.color==='#f4f0e4'))throw Error('Temple sprite has no paper/detail pixels');
 if(box.modelBeforeDrawing!==box.modelAfterDrawing)throw Error('Pixel rendering mutated saved geometry');
 // Start on a separate patch of terrain so neighbouring road clearings cannot
 // accidentally satisfy the stamp clearing / erase assertions.
 artOps.length=0;
 vm.runInContext("editor.buffer.model=new CartographyModel([{kind:'house',dimension:0,grid:4,x:-32,z:-24,color:'#484238',label:''},{kind:'territory',dimension:0,grid:16,x:16,z:16,color:'#484238',label:''}]);editor.drawContents(artContext,{x:0,z:0,dimension:0,scale:1},400,300,false,true)",box);
 if(pixelAt(-32,-24)!=='#f4f0e4'||pixelAt(-33,-23)!=='#f4f0e4'||pixelAt(-32,-25)!=='#f4f0e4')throw Error('Tree clearing missing behind transparent stamp pixels / margin');
 if(pixelAt(-34,-24)!==undefined||pixelAt(24,24)!==undefined)throw Error('Clearing extends outside drawing / fills territory interior');
 vm.runInContext("editor.buffer.model.begin();editor.buffer.model.change(null,atlasKey({kind:'house',dimension:0,grid:4,x:-32,z:-24}));editor.buffer.model.commit()",box);
 artOps.length=0;vm.runInContext("editor.drawContents(artContext,{x:0,z:0,dimension:0,scale:1},400,300,false,true)",box);
 if(pixelAt(-32,-24)!==undefined)throw Error('Erasing stamp left its clearing over the terrain');
 vm.runInContext('editor.buffer.model.undo()',box);artOps.length=0;vm.runInContext("editor.drawContents(artContext,{x:0,z:0,dimension:0,scale:1},400,300,false,true)",box);
 if(pixelAt(-32,-24)!=='#f4f0e4')throw Error('Undo did not restore stamp clearing');
 artOps.length=0;vm.runInContext("atlasPixelText(artContext,'Templo S?o Jos?',100.25,30.5);editor.buffer.model=originalModel",box);
 if(!artOps.length||artOps.some(o=>![o.x,o.z,o.w,o.h].every(Number.isInteger)))throw Error('Bitmap labels are not pixel aligned');
 // Every new stamp must paint ink, place once, occupy its full footprint,
 // and erase/undo correctly, including the 3-cell symbols at grid 16.
 const village=['well','fountain','watchtower','windmill','barn','stable','bridge','square','garden','forge','bakery','tavern','market','lamp','campfire','townhall','library','warehouse','castle','mine','dock','boat','wagon','tent','bench','tree','pine','flowers','boulder','banner'];
 const html=await fs.readFile(new URL('../src/chiko/web/index.html',import.meta.url),'utf8');
 for(const kind of village){
  if(!html.includes('value="'+kind+'"'))throw Error('Village stamp absent from menu: '+kind);
  box.villageKind=kind;
  vm.runInContext("editor.buffer.model=new CartographyModel();editor.el('editGrid').value='16';editor.el('editTool').value=villageKind;editor.start({x:-32,z:-32},0);editor.move({x:128,z:128});editor.end()",box);
  if(vm.runInContext('editor.buffer.model.cells.size!==1||atlasLayer(villageKind)!==\'stamp\'',box))throw Error('Village stamp repeats on drag: '+kind);
  artOps.length=0;vm.runInContext("editor.drawContents(artContext,{x:0,z:0,dimension:0,scale:1},400,300,false,true)",box);
  if(!artOps.some(o=>o.color==='#484238'))throw Error('Village stamp has no pixel sprite: '+kind);
  vm.runInContext("globalThis.stampSize=atlasFootprint(villageKind);editor.el('editTool').value='erase';editor.start({x:-32+(stampSize[0]-1)*16,z:-32+(stampSize[1]-1)*16},0);editor.end()",box);
  if(vm.runInContext('editor.buffer.model.cells.size!==0',box))throw Error('Far edge of stamp not erased: '+kind);
  vm.runInContext('editor.buffer.model.undo()',box);
  if(vm.runInContext('editor.buffer.model.cells.size!==1',box))throw Error('Village stamp undo failed: '+kind);
 }
 vm.runInContext("editor.buffer.model=originalModel;editor.el('editGrid').value='4'",box);
 // Paint beneath a stamp, refine a coarse background, erase one small patch,
 // and undo without changing the stamp or neighbouring colours.
 vm.runInContext("editor.buffer.model=new CartographyModel();editor.el('editBackgroundColor').value='#ccd0b8';editor.el('editGrid').value='16';editor.el('editTool').value='background';editor.start({x:0,z:0},0);editor.end();editor.el('editGrid').value='4';editor.el('editTool').value='house';editor.start({x:0,z:0},0);editor.end();editor.el('editBackgroundColor').value='#c4d8dc';editor.el('editTool').value='background';editor.start({x:0,z:0},0);editor.end()",box);
 const backgroundAt=(x,z)=>vm.runInContext(`[...editor.buffer.model.cells.values()].filter(p=>p.kind==='background'&&${x}>=p.x&&${x}<p.x+p.grid&&${z}>=p.z&&${z}<p.z+p.grid).map(p=>p.color)`,box);
 if(backgroundAt(1,1).join()!=='#c4d8dc'||backgroundAt(10,10).join()!=='#ccd0b8')throw Error('Changing grid loses old background / overlaps paint');
 if(vm.runInContext("![...editor.buffer.model.cells.values()].some(p=>p.kind==='house')",box))throw Error('Background painting replaced a stamp');
 artOps.length=0;vm.runInContext("editor.drawContents(artContext,{x:0,z:0,dimension:0,scale:1},400,300,false,true)",box);
 if(pixelAt(0,0)!=='#c4d8dc'||pixelAt(3,1)!=='#484238'||pixelAt(10,10)!=='#ccd0b8')throw Error('Background rendered over the foreground / missing from export');
 vm.runInContext("editor.el('editGrid').value='1';editor.el('editTool').value='eraseBackground';editor.start({x:1,z:1},0);editor.end()",box);
 if(backgroundAt(1,1).length||backgroundAt(2,1).join()!=='#c4d8dc'||vm.runInContext("![...editor.buffer.model.cells.values()].some(p=>p.kind==='house')",box))throw Error('Background eraser affects neighbours / foreground');
 vm.runInContext('editor.buffer.model.undo()',box);
 if(backgroundAt(1,1).join()!=='#c4d8dc')throw Error('Background undo failed');
 vm.runInContext("editor.el('editTool').value='erase';editor.start({x:0,z:0},0);editor.end()",box);
 if(backgroundAt(0,0).join()!=='#c4d8dc'||vm.runInContext("[...editor.buffer.model.cells.values()].some(p=>p.kind==='house')",box))throw Error('Foreground eraser damages background');
 vm.runInContext('editor.buffer.model.undo();editor.backgroundShown=false',box);artOps.length=0;
 vm.runInContext("editor.drawContents(artContext,{x:0,z:0,dimension:0,scale:1},400,300,false,true)",box);
 if(artOps.some(o=>['#c4d8dc','#ccd0b8'].includes(o.color))||!artOps.some(o=>o.color==='#484238'))throw Error('Background visibility affects stamp visibility');
 vm.runInContext("editor.backgroundShown=true;editor.el('editTool').value='eraseAll';editor.start({x:0,z:0},0);editor.end()",box);
 if(backgroundAt(0,0).length||vm.runInContext("[...editor.buffer.model.cells.values()].some(p=>p.kind==='house')",box))throw Error('All-layer eraser left drawing or background');
 vm.runInContext("editor.buffer.model=originalModel;editor.el('editGrid').value='4'",box);
 box.document.createElement=()=>({getContext:()=>({scale(){}})});
 vm.runInContext('globalThis.drawBuilds=0;editor.drawContents=()=>{drawBuilds++};editor.active=false;globalThis.drawContext={save(){},restore(){},fillRect(){},drawImage(){globalThis.lastSmoothing=this.imageSmoothingEnabled;globalThis.lastRaster=[...arguments]}};editor.draw(drawContext,{x:0,z:0,dimension:0,scale:4},800,600);editor.draw(drawContext,{x:0,z:0,dimension:0,scale:4},800,600)',box);
 if(vm.runInContext('lastSmoothing!==false||editor.cachedCanvas.width!==204||editor.cachedCanvas.height!==154',box))throw Error('Native world raster / nearest-neighbour sampling failed');
 if(vm.runInContext('drawBuilds!==1',box))throw Error('Static annotations are rebuilt for each overlay frame');
 vm.runInContext("map.style={palette:'atlas'};editor.draw(drawContext,{x:0,z:0,dimension:0,scale:4},800,600)",box);
 if(vm.runInContext('drawBuilds!==2',box))throw Error('Atlas paper style did not invalidate annotation cache');
 vm.runInContext('editor.draw(drawContext,{x:0,z:0,dimension:0,scale:4},10000,10000)',box);
 if(vm.runInContext('editor.cachedCanvas.width*editor.cachedCanvas.height>4000000',box))throw Error('High resolution annotation cache exceeded its pixel budget');
 vm.runInContext('editor.draw(drawContext,{x:-12.25,z:0,dimension:0,scale:8},800,600,false,true)',box);
 if(vm.runInContext('lastSmoothing!==false',box))throw Error('Export smooths the annotation raster');
 vm.runInContext("globalThis.savedDraft=editor.buffer;editor.update({world_id:'two'});editor.update({world_id:'one'})",box);
 if(vm.runInContext('editor.buffer!==savedDraft||!editor.buffer.dirty',box))throw Error('World switch discarded unsaved draft');
 return {auto_connections:'OK',negative_coordinates:'OK',undo_redo:'OK',continuous_network:'OK',stamps_and_erase:'OK',territory_contours_and_holes:'OK',pixel_sprites_and_seamless_junctions:'OK',bitmap_labels:'OK',pixel_export:'OK',terrain_clearing_and_erase:'OK',village_stamps_menu_erase_undo:'OK',background_layer_and_mixed_grids:'OK',background_erase_undo_visibility_and_export:'OK',saved_geometry_unchanged:'OK',cancelled_gesture:'OK',space_navigation:'OK',visual_cache:'OK',persistence_and_conflict:'OK',world_drafts:'OK',scope:'model/DOM simulated'};
}
if(typeof process!=='undefined'&&process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)run().then(console.log).catch(e=>{console.error(e);process.exitCode=1});
