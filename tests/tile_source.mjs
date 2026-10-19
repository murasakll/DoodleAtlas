import fs from 'node:fs/promises';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

export async function run(){
 const timers=new Map(),urls=new Set(),requests=[];let nextTimer=0,attempt=0;
 const box={URL:class extends URL{static createObjectURL(){const s='blob:test-'+urls.size;urls.add(s);return s}static revokeObjectURL(s){urls.delete(s)}},URLSearchParams,
  AbortController:class{constructor(){this.signal={aborted:false}}abort(){this.signal.aborted=true}},
  Image:class{naturalWidth=256;naturalHeight=256;set src(value){queueMicrotask(()=>this.onload?.())}},
  setTimeout:(f,ms)=>{timers.set(++nextTimer,f);return nextTimer},clearTimeout:id=>timers.delete(id),
  fetch:async(url,options)=>{requests.push({url,options});attempt++;return {status:attempt===1?503:200,ok:attempt!==1,blob:async()=>({type:'image/webp'})}}};
 vm.createContext(box);vm.runInContext(await fs.readFile(new URL('../src/chiko/web/tile-source.js',import.meta.url),'utf8'),box);
 const state={world_id:'world',session_id:'session',terrain:{chunks:{'0':[[0,0,'chunk']]},regions:{}},live_chunks:{},tile_index:{'0/0':[[0,0,'base']],'0/1':[[0,0,'parent']]}};
 box.state=state;
 vm.runInContext("globalThis.source=new TileSource();source.update(state);globalThis.view={x:128,z:128,scale:.25,width:1024,height:768,dimension:0};globalThis.style={mode:'relief',exaggeration:1.5,intensity:.8};globalThis.tile=source.visibleTiles(view,style)[0];source.requestTile(tile)",box);
 const flush=()=>new Promise(resolve=>setTimeout(resolve,0));await flush();
 if(box.tile.level!==1||box.tile.size!==512||!requests[0].url.startsWith('/map/0/1/0/0.webp?'))throw Error('Pyramid selection or URL');
 if(!requests[0].url.includes('world=world')||!requests[0].url.includes('revision=parent'))throw Error('World/version omitted');
 if(box.source.status(box.tile)!=='pending'||timers.size!==1||box.source.active!==0)throw Error('503 not deferred safely');
 const retry=[...timers.values()][0];timers.clear();retry();await flush();
 if(box.source.status(box.tile)!=='ready'||box.source.requestTile(box.tile).naturalWidth!==256||urls.size)throw Error('WebP load/cache/blob cleanup');
 if(box.source.bytes!==256*256*4)throw Error('Decoded-byte accounting');
 const before=requests.length;
 vm.runInContext("source.visibleTiles(view,{...style,grid:false,cartographic:false}).forEach(t=>source.requestTile(t))",box);await flush();
 if(requests.length!==before)throw Error('Paper/grid change refetched terrain');
 const zoomed=box.source.visibleTiles({...box.view,scale:1},box.style),preview=zoomed.find(t=>t.previewImage);
 if(!preview||!box.source.requestTile(preview)||requests.length!==before)throw Error('Cached zoom preview missing or triggered requests');
 const natural=box.source.visibleTiles({...box.view,scale:1},{...box.style,palette:'minecraft'});
 if(natural.some(t=>t.previewImage)||!box.source.url(natural[0]).includes('palette=minecraft'))throw Error('Minecraft palette leaked paper preview or omitted URL option');
 box.source.update({...state,seed_layer:{available:true,revision:'seed-version'}});
 const predicted=box.source.visibleTiles({...box.view,dimension:0},{...box.style,seed:true,seedY:64}),seedTiles=predicted.filter(t=>t.kind==='seed');
 if(!seedTiles.length||seedTiles.length>16||!box.source.url(seedTiles[0]).includes('/seed/0/')||!box.source.url(seedTiles[0]).includes('y=64'))throw Error('Seed viewport bound/URL');
 const seedKey=box.source.key(seedTiles[0]);
 if(box.source.key({...seedTiles[0],style:{...seedTiles[0].style,seedOpacity:.7}})!==seedKey)throw Error('Opacity change refetched prediction');
 const soft={...seedTiles[0],style:{...seedTiles[0].style,seedSmooth:true}};
 if(box.source.key(soft)===seedKey||!box.source.url(soft).includes('smooth=1'))throw Error('Soft prediction cache/URL collision');
 if(box.source.key({...seedTiles[0],style:{...seedTiles[0].style,seedY:128}})===seedKey)throw Error('Seed height cache collision');
 if(box.source.visibleTiles({...box.view,dimension:1},{...box.style,seed:true}).some(t=>t.kind==='seed'))throw Error('Seed leaked into unsupported dimension');
 if(box.source.visibleTiles(box.view,{...box.style,seed:false}).some(t=>t.kind==='seed'))throw Error('Disabled seed still requested');
 const allSizes=[64,128,256,512,1024,2048],fullIndex=Object.fromEntries(Array.from({length:9},(_,l)=>['0/'+l,[[0,0,'level-'+l]]]));
 box.source.update({...state,tile_index:fullIndex,tile_options:{sizes:allSizes}});
 for(const pixels of allSizes){
  box.source.configure({pixels,maxBytes:16*1048576,concurrency:4});
  const visible=box.source.visibleTiles({x:128,z:128,scale:1,width:64,height:64,dimension:0},{...box.style,tilePixels:pixels}).filter(t=>!t.previewImage);
  if(!visible.length||visible.some(t=>t.pixels!==pixels||t.size!==pixels||t.level!==0||t.version!=='level-'+Math.max(0,Math.log2(pixels/256))))throw Error('Sized tile coordinates/version mismatch '+pixels);
  if(!box.source.url(visible[0]).includes('pixels='+pixels))throw Error('Tile pixel size omitted from URL');
  if(pixels===2048&&box.source.maxBytes<128*1048576)throw Error('Large tile minimum cache missing');
 }
 box.source.update(state);
 if(box.source.visibleTiles(box.view,{...box.style,tilePixels:2048}).filter(t=>t.kind==='map'&&!t.previewImage).some(t=>t.pixels!==256))throw Error('Old server fallback changed tile coordinates');
 box.source.visibleTiles(box.view,box.style);
 let release;
 box.fetch=async()=>new Promise(resolve=>{release=()=>resolve({status:200,ok:true,blob:async()=>({})})});
 vm.runInContext("source.clear();source.update(state);globalThis.tile2=source.visibleTiles(view,style)[0];source.requestTile(tile2);source.clear()",box);
 release();await flush();
 if(box.source.active!==0||box.source.cache.size||box.source.bytes||urls.size)throw Error('Stale load repopulated cleared world');
 return {pyramid_selection:'OK',world_and_version:'OK',retry_and_blob_cleanup:'OK',paper_reuses_tiles:'OK',world_switch_cancels_load:'OK',scope:'simulated; no browser'};
}
if(typeof process!=='undefined'&&process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)console.log(await run());
