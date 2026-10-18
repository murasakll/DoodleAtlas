'use strict';
// Adapter for today's HTTP routes. The renderer knows no URL or save format.
// Contract: update(state), visibleTiles(view, style), requestTile(tile), bounds(dim), clear().
globalThis.TileSource=class TileSource{
 constructor({onChange=()=>{},maxBytes=16*1024*1024,maxEntries=64,concurrency=4}={}){
  this.onChange=onChange;this.maxBytes=maxBytes;this.maxEntries=maxEntries;this.concurrency=concurrency;
  this.cache=new Map();this.queue=[];this.active=0;this.generation=0;this.bytes=0;this.dimensions=new Map();this.identity='';
 }
 clear(){this.generation++;for(const entry of this.cache.values()){clearTimeout(entry.retryTimer);entry.controller?.abort();if(entry.objectUrl)URL.revokeObjectURL(entry.objectUrl)}this.queue=[];this.active=0;this.cache.clear();this.bytes=0;this.dimensions.clear();this.refs=null;this.seedInfo=null;this.wanted=new Set()}
 update(state){
  const identity=state.session_id+':'+state.world_id;
  if(identity!==this.identity){this.clear();this.identity=identity}
  const seedChanged=JSON.stringify(this.seedInfo)!==JSON.stringify(state.seed_layer);this.seedInfo=state.seed_layer;
  const optionsChanged=JSON.stringify(this.tileOptions)!==JSON.stringify(state.tile_options);this.tileOptions=state.tile_options;
  const refs=[state.terrain?.chunks,state.terrain?.regions,state.live_chunks,state.tile_index];
  if(this.refs&&refs.every((r,i)=>r===this.refs[i]))return seedChanged||optionsChanged;
  this.refs=refs;this.tileIndex=state.tile_index??null;this.worldId=state.world_id;this.dimensions.clear();
  for(const dim of new Set([...refs.slice(0,3).flatMap(r=>Object.keys(r||{})),...Object.keys(this.tileIndex||{}).map(k=>k.split('/')[0])])){
   const saved=new Map((refs[0]?.[dim]||[]).map(c=>[c[0]+','+c[1],c]));
   const chunks=new Map(saved);
   for(const [x,z,version]of refs[2]?.[dim]||[]){
    const old=saved.get(x+','+z);chunks.set(x+','+z,[x,z,version+':'+(old?.[2]||'')]);
   }
   const levels=new Map(Object.entries(this.tileIndex||{}).filter(([k])=>k.split('/')[0]===dim).map(([k,rows])=>[Number(k.split('/')[1]),rows]));
   this.dimensions.set(Number(dim),{saved,chunks,regions:refs[1]?.[dim]||[],levels});
  }
  return true;
 }
 bounds(dimension){
  const chunks=this.dimensions.get(Number(dimension))?.chunks;if(!chunks?.size)return null;
  let minX=Infinity,minZ=Infinity,maxX=-Infinity,maxZ=-Infinity;
  for(const [x,z]of chunks.values()){minX=Math.min(minX,x*16);minZ=Math.min(minZ,z*16);maxX=Math.max(maxX,x*16+16);maxZ=Math.max(maxZ,z*16+16)}
  return {minX,minZ,maxX,maxZ};
 }
 configure({maxBytes=16*1024*1024,concurrency=4,pixels=256}={}){
  const minimum=pixels>=2048?128:pixels>=1024?32:16;
  this.maxBytes=Math.max(minimum*1048576,Math.min(256*1048576,maxBytes));
  this.maxEntries=Math.min(2048,Math.max(64,Math.floor(this.maxBytes/(64*64*4))));
  this.concurrency=Math.max(1,Math.min(8,Math.round(concurrency)));this.trim();this.pump();
 }
 seedTiles(view,style){
  if(!style.seed||!this.seedInfo?.available||Number(view.dimension)!==0)return [];
  let level=Math.max(0,Math.min(3,Math.floor(Math.log2(1/view.scale)/2)));
  let left,right,top,bottom,size;
  for(;;){size=256*4**level;left=Math.floor((view.x-view.width/(2*view.scale))/size);right=Math.floor((view.x+view.width/(2*view.scale))/size);top=Math.floor((view.z-view.height/(2*view.scale))/size);bottom=Math.floor((view.z+view.height/(2*view.scale))/size);if((right-left+1)*(bottom-top+1)<=16||level===3)break;level++}
  const tiles=[];
  for(let z=top;z<=bottom&&tiles.length<16;z++)for(let x=left;x<=right&&tiles.length<16;x++)if(Math.max(Math.abs(x),Math.abs(z))*size<=30000000)tiles.push({kind:'seed',x,z,size,level,version:this.seedInfo.revision,worldId:this.worldId,dimension:0,style,identity:this.identity});
  return tiles;
 }
 composeTiles(tiles,view,style){const all=[...this.seedTiles(view,style),...tiles];this.retainVisible(all);return all}
 visibleTiles(view,style){
  const data=this.dimensions.get(Number(view.dimension));this.coverage={known:0};if(!data)return this.composeTiles([],view,style);
  const left=view.x-view.width/(2*view.scale),right=view.x+view.width/(2*view.scale);
  const top=view.z-view.height/(2*view.scale),bottom=view.z+view.height/(2*view.scale);
  const visible=(x,z,size)=>x*size<=right&&(x+1)*size>=left&&z*size<=bottom&&(z+1)*size>=top;
  const tiles=[];
  const add=(kind,x,z,size,version,level=0,pixels=256)=>tiles.push({kind,x,z,size,version,level,pixels,worldId:this.worldId,dimension:view.dimension,style,identity:this.identity});
  if(this.tileIndex!==null){
   const requested=Number(style.tilePixels)||256,pixels=this.tileOptions?.sizes?.includes(requested)?requested:256;
   const shift=Math.max(0,Math.log2(pixels/256)),factor=Math.max(1,256/pixels);
   const max=Math.max(0,Math.max(0,...data.levels.keys())-shift);let level=Math.min(max,Math.max(0,Math.floor(Math.log2(1/view.scale))));
   const limit=Math.max(4,Math.min(512,Math.floor((this.maxBytes-4*1048576)/(pixels*pixels*4))));
   let rows=[];
   for(;;){
    rows=[];const nativeLevel=level+shift,size=pixels*2**level;
    for(const[x,z,v]of data.levels.get(nativeLevel)||[]){
     if(!visible(x,z,256*2**nativeLevel))continue;
     for(let dz=0;dz<factor;dz++)for(let dx=0;dx<factor;dx++){const tx=x*factor+dx,tz=z*factor+dz;if(visible(tx,tz,size))rows.push([tx,tz,v])}
    }
    if(rows.length<=limit||level>=max)break;level++;
   }
   for(const[x,z,v]of rows)add('map',x,z,pixels*2**level,v,level,pixels);
   if(tiles.some(t=>!this.cache.get(this.key(t))?.image)){
    const previews=[];
    for(const entry of this.cache.values()){
     const t=entry.tile,image=entry.image||entry.previous;
     if(t.kind!=='map'||(t.level===level&&(t.pixels||256)===pixels)||t.dimension!==view.dimension||!image||!visible(t.x,t.z,t.size))continue;
     if(t.style.exaggeration!==style.exaggeration||t.style.intensity!==style.intensity||(t.style.palette||'paper')!==(style.palette||'paper'))continue;
     const tp=t.pixels||256,ts=Math.max(0,Math.log2(tp/256)),tf=Math.max(1,256/tp);
     if(!(data.levels.get(t.level+ts)||[]).some(([x,z])=>x===Math.floor(t.x/tf)&&z===Math.floor(t.z/tf)))continue;
     previews.push({...t,previewImage:image});
    }
    previews.sort((a,b)=>b.level-a.level);tiles.unshift(...previews.slice(0,32));
   }
   this.coverage={known:rows.length};return this.composeTiles(tiles,view,style);
  }
  if(data.regions.length){for(const[x,z,v]of data.regions)if(visible(x,z,256))add('regions',x,z,256,v)}
  else for(const[x,z,v]of data.saved.values())if(visible(x,z,16))add('tiles',x,z,16,v);
  const nearby=[...data.chunks.values()].filter(([x,z])=>visible(x,z,16));
  // Bound requests while zoomed out. Region atlas remains the existing fallback.
  this.coverage={known:nearby.length};
  const detailed=view.scale>=.8&&nearby.length<=512;
  for(const[x,z,v]of nearby){
   if(detailed){
    const neighbors=[[-1,0],[1,0],[0,-1],[0,1]].map(([dx,dz])=>data.chunks.get((x+dx)+','+(z+dz))?.[2]||'').join(':');
    add('render',x,z,16,v+':'+neighbors);
   }else if(!data.saved.has(x+','+z))add('live',x,z,16,v);
  }
  return this.composeTiles(tiles,view,style);
 }
 retainVisible(tiles){this.wanted=new Set(tiles.map(t=>this.key(t)));this.queue=this.queue.filter(entry=>{if(this.wanted.has(entry.key))return true;this.remove(entry);return false});for(const entry of this.cache.values())if(!this.wanted.has(entry.key)&&(entry.controller||entry.retryTimer))this.remove(entry)}
 key(t){const s=t.kind==='seed'?JSON.stringify({palette:t.style.palette||'paper',y:t.style.seedY??64,smooth:!!t.style.seedSmooth}):['render','map'].includes(t.kind)?JSON.stringify({mode:t.style.mode,pixels:t.pixels||256,palette:t.style.palette||'paper',exaggeration:t.style.exaggeration,intensity:t.style.intensity}):'';return `${t.identity}/${t.kind}/${t.dimension}/${t.level||0}/${t.x}/${t.z}/${s}`}
 status(t){if(t.previewImage)return 'ready';const entry=this.cache.get(this.key(t));return entry?.failed?'failed':entry?.image&&entry.version===t.version?'ready':'pending'}
 url(t){
  const query=new URLSearchParams({v:t.identity+':'+t.version});
  if(t.kind==='seed'){query.set('world',t.worldId);query.set('revision',t.version);query.set('palette',t.style.palette||'paper');query.set('y',t.style.seedY??64);query.set('smooth',t.style.seedSmooth?'1':'0');return `/seed/0/${t.level}/${t.x}/${t.z}.webp?${query}`}
  if(t.kind==='map'){query.set('world',t.worldId);query.set('revision',t.version);query.set('pixels',t.pixels||256);query.set('palette',t.style.palette||'paper');query.set('exaggeration',t.style.exaggeration);query.set('intensity',t.style.intensity);return `/map/${t.dimension}/${t.level}/${t.x}/${t.z}.webp?${query}`}
  if(t.kind==='render'){query.set('mode',t.style.mode);query.set('exaggeration',t.style.exaggeration);query.set('intensity',t.style.intensity)}
  return `/${t.kind}/${t.dimension}/${t.x}/${t.z}.png?${query}`;
 }
 requestTile(tile){
  if(tile.previewImage)return tile.previewImage;
  const key=this.key(tile);let entry=this.cache.get(key);
  if(entry&&entry.version===tile.version){this.cache.delete(key);this.cache.set(key,entry);return entry.image||entry.previous||null}
  const previous=entry?.image||entry?.previous||null;
  if(entry)this.remove(entry);
  entry={key,version:tile.version,tile,previous,image:null,bytes:previous?previous.naturalWidth*previous.naturalHeight*4:0,generation:this.generation};
  this.bytes+=entry.bytes;this.cache.set(key,entry);this.queue.push(entry);this.pump();this.trim();return previous;
 }
 pump(){
  while(this.active<this.concurrency&&this.queue.length){
   const entry=this.queue.shift();if(this.cache.get(entry.key)!==entry)continue;
   this.active++;if(['map','seed'].includes(entry.tile.kind)){this.fetchMap(entry);continue}const image=new Image();
   const finish=()=>{if(entry.generation!==this.generation)return;this.active--;this.pump()};
   image.onload=()=>{
    if(entry.generation===this.generation&&this.cache.get(entry.key)===entry){
     this.bytes-=entry.bytes;entry.previous=null;entry.image=image;entry.bytes=image.naturalWidth*image.naturalHeight*4;this.bytes+=entry.bytes;this.trim();this.onChange();
    }finish();
   };
   image.onerror=()=>{entry.failed=true;finish();if(entry.generation===this.generation)this.onChange()};image.src=this.url(entry.tile);
  }
 }
 async fetchMap(entry){
  let retry=false;
  try{
   entry.controller=new AbortController();
   const response=await fetch(this.url(entry.tile),{signal:entry.controller.signal,credentials:'same-origin'});
   if([202,409,503].includes(response.status)){retry=true;return}
   if(!response.ok)throw Error('Tile HTTP '+response.status);
   const blob=await response.blob();
   if(entry.generation!==this.generation||this.cache.get(entry.key)!==entry)return;
   const image=await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(Error('Imagem WebP inválida'));entry.objectUrl=URL.createObjectURL(blob);img.src=entry.objectUrl});
   if(entry.generation===this.generation&&this.cache.get(entry.key)===entry){this.bytes-=entry.bytes;entry.previous=null;entry.image=image;entry.bytes=image.naturalWidth*image.naturalHeight*4;this.bytes+=entry.bytes;this.trim()}
  }catch(error){if(error.name!=='AbortError')entry.failed=true}
  finally{
   entry.controller=null;if(entry.objectUrl){URL.revokeObjectURL(entry.objectUrl);entry.objectUrl=null}
   if(entry.generation===this.generation){
    this.active--;
    if(retry&&this.cache.get(entry.key)===entry&&this.wanted?.has(entry.key)){
     entry.retries=(entry.retries||0)+1;
     if(entry.retries<=40)entry.retryTimer=setTimeout(()=>{entry.retryTimer=null;if(this.cache.get(entry.key)===entry&&this.wanted?.has(entry.key)){this.queue.push(entry);this.pump()}},Math.min(2000,250*entry.retries));else entry.failed=true;
    }
    this.pump();this.onChange();
   }
  }
 }
 remove(entry){if(this.cache.get(entry.key)===entry){clearTimeout(entry.retryTimer);entry.controller?.abort();this.cache.delete(entry.key);this.bytes-=entry.bytes}}
 trim(){while((this.bytes>this.maxBytes||this.cache.size>this.maxEntries)&&this.cache.size){this.remove(this.cache.values().next().value)}}
 stats(){return {entries:this.cache.size,estimatedDecodedBytes:this.bytes,loading:this.active,queued:this.queue.length}}
};
