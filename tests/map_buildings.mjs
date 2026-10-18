import fs from 'node:fs/promises';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

export async function run(){
 const elements=new Map(),bodies=[];const element=()=>({value:'',checked:false,dataset:{},children:[],setAttribute(k,v){this[k]=v},append(...items){this.children.push(...items)},replaceChildren(){this.children=[]},addEventListener(){}});
 const el=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)};
 for(const[id,value]of Object.entries({editTool:'part_floor',editGrid:'4',editBrush:'1',editColor:'#484238',editLabel:'',editBuildingNewName:'Taverna',editPartEraseLayer:'all'}))el(id).value=value;
 const box={document:{getElementById:el,createElement:element,addEventListener(){}},window:{addEventListener(){}},setTimeout(){return 1},clearTimeout(){},fetch:async(url,options)=>{if(options){bodies.push(JSON.parse(options.body));return {ok:true,json:async()=>({revision:bodies.length})}}return {ok:true,json:async()=>({world_id:'one',available:true,revision:0,cells:[],structures:[]})}}};
 vm.createContext(box);vm.runInContext(await fs.readFile(new URL('../web/map-editor.js',import.meta.url),'utf8'),box);
 vm.runInContext("globalThis.map={camera:{scale:4,dimension:0},style:{palette:'atlas'},overlay:{dataset:{}},invalidateOverlay(){}};globalThis.editor=new MapEditor({map,getState:()=>({world_id:'one'}),getToken:()=> 'host'});editor.update({world_id:'one'})",box);
 await new Promise(resolve=>setTimeout(resolve,0));
 vm.runInContext("editor.newBuilding();globalThis.m=editor.buffer.model;globalThis.id=editor.buffer.selectedBuilding;editor.start({x:0,z:0},0);editor.move({x:12,z:0});editor.end();editor.el('editTool').value='part_wall';editor.start({x:0,z:0},0);editor.move({x:12,z:0});editor.end();editor.el('editTool').value='part_door';editor.start({x:4,z:0},0);editor.end();editor.el('editTool').value='part_window';editor.start({x:8,z:0},0);editor.end();globalThis.door=[...m.cells.values()].find(p=>p.kind==='part_door')",box);
 if(vm.runInContext("m.structures.size!==1||m.cells.size!==8||m.partMask(door)!==10||[...m.cells.values()].filter(p=>p.kind==='part_floor').length!==4",box))throw Error('Floor/wall layering or connected openings failed');
 for(let mask=0;mask<16;mask++){
  box.expected=mask;
  vm.runInContext("globalThis.check=new CartographyModel();globalThis.part={kind:'part_roof',buildingId:'a',dimension:0,grid:4,x:-8,z:-8,color:'#484238',label:''};check.set(part);for(const[dx,dz,bit]of [[0,-1,1],[1,0,2],[0,1,4],[-1,0,8]])if(expected&bit)check.set({...part,x:part.x+dx*4,z:part.z+dz*4});if(check.partMask(part)!==expected)throw Error('Roof mask '+expected);check.set({...part,buildingId:'b',x:-4});if(!(expected&2)&&check.partMask(part)&2)throw Error('Cross-building connection');",box);
 }
 vm.runInContext("editor.el('editTool').value='part_roof';editor.start({x:0,z:0},0);editor.move({x:12,z:0});editor.end();globalThis.savedCells=JSON.stringify([...m.cells.values()]);editor.el('editBuildingDisplay').value='icon';editor.updateBuilding();globalThis.iconView=editor.viewCells({x:6,z:0,dimension:0,scale:4},400,300)",box);
 if(vm.runInContext("JSON.stringify([...m.cells.values()])!==savedCells||iconView.some(p=>p.buildingId)||iconView.filter(p=>p.virtualBuilding).length!==1",box))throw Error('Icon view destroyed pieces or still shows details');
 vm.runInContext("editor.el('editTool').value='part_table';editor.start({x:0,z:0},0);editor.cancel()",box);
 if(vm.runInContext("m.structures.get(id).display!=='icon'||JSON.stringify([...m.cells.values()])!==savedCells",box))throw Error('Cancelled drawing changed saved view or geometry');
 vm.runInContext("editor.start({x:0,z:0},0);editor.end();editor.roofsShown=false;globalThis.interior=editor.viewCells({x:6,z:0,dimension:0,scale:4},400,300)",box);
 if(vm.runInContext("m.structures.get(id).display!=='detailed'||interior.some(p=>p.kind==='part_roof')||![...m.cells.values()].some(p=>p.kind==='part_roof')",box))throw Error('Editing icon / hiding roof lost data');
 vm.runInContext("editor.el('editTool').value='part_erase';editor.el('editPartEraseLayer').value='roof';editor.start({x:0,z:0},0);editor.end()",box);
 if(vm.runInContext("[...m.cells.values()].filter(p=>p.kind==='part_roof').length!==3||![...m.cells.values()].some(p=>p.kind==='part_table')||[...m.cells.values()].filter(p=>p.kind==='part_floor').length!==4",box))throw Error('Targeted roof eraser damaged interior');
 vm.runInContext("editor.history(false);editor.el('editBuildingDisplay').value='auto';editor.updateBuilding();editor.active=false;globalThis.detail=editor.viewCells({x:6,z:0,dimension:0,scale:1,displayScale:8},400,300);globalThis.far=editor.viewCells({x:6,z:0,dimension:0,scale:.5},400,300)",box);
 if(vm.runInContext("!detail.some(p=>p.buildingId)||!far.some(p=>p.virtualBuilding)",box))throw Error('Auto view uses cache density instead of display zoom');
 await vm.runInContext('editor.save()',box);
 if(!bodies.at(-1)?.structures?.length||!bodies.at(-1).cells.some(p=>p.buildingId))throw Error('Saving omits structure metadata');
 const pixels=[];box.drawContext=new Proxy({fillRect(x,z,w,h){pixels.push([x,z,w,h])}},{get:(o,k)=>o[k]??(()=>{})});
 vm.runInContext("editor.drawContents(drawContext,{x:6,z:0,dimension:0,scale:4},400,300,false,true)",box);
 if(!pixels.length||pixels.some(p=>p.some(n=>!Number.isInteger(n))))throw Error('Modular rendering is not pixel aligned');
 return {group_creation_and_layers:'OK',wall_openings_and_roof_masks:'OK',cross_building_isolation:'OK',icon_toggle_preserves_parts:'OK',cancel_and_targeted_eraser:'OK',auto_zoom_and_roof_visibility:'OK',metadata_save_and_export_raster:'OK',scope:'model and simulated DOM/canvas'};
}
if(typeof process!=='undefined'&&process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)run().then(console.log).catch(e=>{console.error(e);process.exitCode=1});
