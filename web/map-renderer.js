'use strict';
// Camera, gestures and canvases only. Tile transport lives in TileSource.
globalThis.MapRenderer=class MapRenderer{
 constructor({canvas,overlay,source,onCamera=()=>{},onSelect=()=>{},onDimension=()=>{},onCoverage=()=>{}}){
  this.canvas=canvas;this.overlay=overlay;this.ctx=canvas.getContext('2d');this.ink=overlay.getContext('2d');this.source=source;
  this.onCamera=onCamera;this.onSelect=onSelect;this.onDimension=onDimension;this.onCoverage=onCoverage;
  this.camera={x:0,z:0,scale:2,dimension:0};this.targetScale=2;this.width=1;this.height=1;
  this.state={players:[],entities:[],terrain:{}};this.waypoints=[];this.motions=new Map();this.lastMotion=performance.now();
  this.style={mode:'relief',exaggeration:1.5,intensity:.8,cartographic:true,grid:true,dark:false};this.filters={animals:true,hostiles:true,others:true,aquatic:false,text:'',smooth:false};
  this.pointers=new Map();this.terrainDirty=true;this.overlayDirty=true;this.lastFrame=0;this.following=null;
  this.reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches||false;
  source.onChange=()=>this.invalidateTerrain();this.bindGestures();
  window.addEventListener('resize',()=>this.resize());document.addEventListener('visibilitychange',()=>this.invalidateTerrain());
  this.resize();this.animate=this.animate.bind(this);requestAnimationFrame(this.animate);
 }
 invalidateTerrain(){this.terrainDirty=true;this.overlayDirty=true}
 invalidateOverlay(){this.overlayDirty=true}
 resize(){this.width=this.canvas.clientWidth||innerWidth;this.height=this.canvas.clientHeight||innerHeight;this.ratio=devicePixelRatio||1;for(const c of [this.canvas,this.overlay]){c.width=Math.round(this.width*this.ratio);c.height=Math.round(this.height*this.ratio)}this.invalidateTerrain();this.reportCamera()}
 setCamera({x=this.camera.x,z=this.camera.z,scale=this.camera.scale,dimension=this.camera.dimension}={}){
  this.camera={x,z,scale:Math.max(.04,Math.min(32,scale)),dimension:Number(dimension)};this.targetScale=this.camera.scale;this.zoomAnchor=null;this.following=null;this.onDimension(this.camera.dimension);this.invalidateTerrain();this.reportCamera();
 }
 setDimension(dimension){this.setCamera({dimension});this.fit()}
 fit(){const b=this.source.bounds(this.camera.dimension);if(!b)return;this.setCamera({x:(b.minX+b.maxX)/2,z:(b.minZ+b.maxZ)/2,scale:Math.min(8,(this.width-64)/(b.maxX-b.minX+32),(this.height-64)/(b.maxZ-b.minZ+32))})}
 setStyle(style){this.style={...this.style,...style};this.invalidateTerrain()}
 setFilters(filters){const smooth=this.filters.smooth;this.filters={...this.filters,...filters};if(smooth!==this.filters.smooth)this.invalidateTerrain();else this.invalidateOverlay()}
 setWaypoints(waypoints){this.waypoints=waypoints;this.invalidateOverlay()}
 setTrail(points){this.trail=points;this.invalidateOverlay()}
 setSource(source){this.source.clear();this.source=source;source.onChange=()=>this.invalidateTerrain();source.update(this.state);this.invalidateTerrain()}
 update(state){
  const identity=state.session_id+':'+state.world_id;
  if(identity!==this.identity){this.identity=identity;this.motions.clear();this.following=null;this.lastMotion=performance.now();this.state={players:[],entities:[],terrain:{}}}
  const now=performance.now(),duration=this.reduced?1:Math.max(250,Math.min(1500,now-this.lastMotion));let changed=false;
  for(const list of ['players','entities']){
   const old=new Map((this.state[list]||[]).map(p=>[p.id,p]));
   if(JSON.stringify(this.state[list])!==JSON.stringify(state[list]))changed=true;
   for(const p of state[list]||[]){const prev=old.get(p.id);if(prev&&prev.dimension===p.dimension&&(prev.x!==p.x||prev.z!==p.z||prev.yaw!==p.yaw))this.motions.set(p.id,{from:this.position(prev),time:now,duration})}
  }
  const ids=new Set([...(state.players||[]),...(state.entities||[])].map(p=>p.id));for(const id of this.motions.keys())if(!ids.has(id))this.motions.delete(id);
  if(changed){this.lastMotion=now;this.invalidateOverlay()}
  if(JSON.stringify(this.state.terrain?.spawn)!==JSON.stringify(state.terrain?.spawn))this.invalidateOverlay();
  if(this.state.terrain?.observed_points!==state.terrain?.observed_points)this.invalidateOverlay();
  this.state=state;if(this.source.update(state))this.invalidateTerrain();
 }
 position(p){const m=this.motions.get(p.id);if(!m)return p;const t=Math.min(1,(performance.now()-m.time)/m.duration);return {...p,x:m.from.x+(p.x-m.from.x)*t,z:m.from.z+(p.z-m.from.z)*t,yaw:(m.from.yaw||0)+(((p.yaw||0)-(m.from.yaw||0)+540)%360-180)*t}}
 follow(id){this.following=id;this.invalidateOverlay()}
 screen(x,z){return {x:this.width/2+(x-this.camera.x)*this.camera.scale,y:this.height/2+(z-this.camera.z)*this.camera.scale}}
 world(x,y){return {x:this.camera.x+(x-this.width/2)/this.camera.scale,z:this.camera.z+(y-this.height/2)/this.camera.scale}}
 reportCamera(){this.onCamera({...this.camera,width:this.width,height:this.height,cursor:this.cursor?this.world(this.cursor.x,this.cursor.y):null,following:this.following})}
 zoom(factor,point={x:this.width/2,y:this.height/2}){this.following=null;this.zoomAnchor={world:this.world(point.x,point.y),point};this.targetScale=Math.max(.04,Math.min(32,this.targetScale*factor));this.invalidateOverlay()}
 animate(now){
  if(!document.hidden&&now-this.lastFrame>=(this.editor?.stroke?16:50)){
   let zooming=Math.abs(this.targetScale-this.camera.scale)>.001;
   if(zooming){this.camera.scale=this.reduced?this.targetScale:this.camera.scale+(this.targetScale-this.camera.scale)*.3;if(Math.abs(this.targetScale-this.camera.scale)<.001)this.camera.scale=this.targetScale;const a=this.zoomAnchor;if(a){this.camera.x=a.world.x-(a.point.x-this.width/2)/this.camera.scale;this.camera.z=a.world.z-(a.point.y-this.height/2)/this.camera.scale}this.invalidateTerrain();this.reportCamera()}
   if(this.following){const raw=this.state.players?.find(p=>p.id===this.following),p=raw&&this.position(raw);if(p&&(this.camera.x!==p.x||this.camera.z!==p.z||this.camera.dimension!==p.dimension)){this.camera.x=p.x;this.camera.z=p.z;this.camera.dimension=p.dimension;this.onDimension(p.dimension);this.invalidateTerrain();this.reportCamera()}}
   for(const[id,m]of this.motions)if(now>=m.time+m.duration){this.motions.delete(id);this.invalidateOverlay()}
   const moving=this.motions.size>0;
   if(this.terrainDirty){this.paintTerrain();this.terrainDirty=false}
   if(this.overlayDirty||moving){this.paintOverlay();this.overlayDirty=false}
   this.lastFrame=now;
  }
  requestAnimationFrame(this.animate);
 }
 paintTerrain({forceLight=false,includeSeed=true}={}){
  const dark=this.style.dark&&!forceLight;
  const c=this.ctx;c.setTransform(this.ratio,0,0,this.ratio,0,0);c.fillStyle=dark?'#101b21':this.style.palette==='atlas'?'#f4f0e4':this.style.cartographic?'#f7f5ed':'#f4f8fa';c.fillRect(0,0,this.width,this.height);c.imageSmoothingEnabled=this.style.palette!=='atlas'&&this.filters.smooth;
  const view={...this.camera,width:this.width,height:this.height};
  const tiles=this.source.visibleTiles(view,this.style);let loaded=0,failed=0,pending=0,seedLoaded=0,seedPending=0,seedFailed=0;
  const images=new Map();
  // Request observed tiles first; draw the translucent prediction underneath.
  for(const tile of [...tiles.filter(t=>t.kind!=='seed'),...tiles.filter(t=>t.kind==='seed')])images.set(tile,this.source.requestTile(tile));
  for(const tile of tiles){
   const image=images.get(tile),status=this.source.status?.(tile)||(image?.naturalWidth?'ready':'pending');
   if(tile.kind==='seed'){
    if(!includeSeed)continue;
    if(status==='failed')seedFailed++;else if(status!=='ready')seedPending++;
    if(image?.naturalWidth){seedLoaded++;const at=this.screen(tile.x*tile.size,tile.z*tile.size),size=tile.size*this.camera.scale;c.save();c.globalAlpha=Math.max(.1,Math.min(.7,this.style.seedOpacity??.32));c.imageSmoothingEnabled=this.style.palette!=='atlas'&&!!this.style.seedSmooth;c.drawImage(image,at.x,at.y,size+.05,size+.05);c.restore()}continue;
   }
   if(status==='failed')failed++;else if(status!=='ready')pending++;
   if(!image?.naturalWidth)continue;loaded++;const at=this.screen(tile.x*tile.size,tile.z*tile.size),size=tile.size*this.camera.scale;c.drawImage(image,at.x,at.y,size+.05,size+.05);
  }
  if(this.style.grid){let step=64;while(step*this.camera.scale<48)step*=4;const grid=step*this.camera.scale,p=this.screen(0,0);c.strokeStyle=dark?'#a8d4e322':'#365e7622';c.lineWidth=1;c.beginPath();for(let x=((p.x%grid)+grid)%grid;x<this.width;x+=grid){c.moveTo(x,0);c.lineTo(x,this.height)}for(let y=((p.y%grid)+grid)%grid;y<this.height;y+=grid){c.moveTo(0,y);c.lineTo(this.width,y)}c.stroke()}
  this.terrainCoverage={known:this.source.coverage?.known||0,loaded,failed,pending,seedKnown:includeSeed?tiles.filter(t=>t.kind==='seed').length:0,seedLoaded,seedPending,seedFailed};this.onCoverage(this.terrainCoverage);
 }
 exportLayout(maxSide=1600){
  if(![1024,1600,2048].includes(Number(maxSide)))throw Error('Escolha uma resolução disponível.');
  const factor=Math.min(1,Number(maxSide)/Math.max(this.width,this.height));
  const mapWidth=Math.max(1,Math.round(this.width*factor)),mapHeight=Math.max(1,Math.round(this.height*factor));
  const width=Math.max(320,mapWidth+48),height=mapHeight+(this.style.palette==='atlas'?208:190);
  if(!Number.isFinite(width*height)||width*height>16000000)throw Error('A imagem ultrapassa o limite de 16 megapixels.');
  return {width,height,mapWidth,mapHeight,factor,left:Math.round((width-mapWidth)/2),top:76};
 }
 antiquePixels(image){
  // One bounded pass over the exported map, never over the interactive canvas.
  const p=image.data;
  for(let i=0;i<p.length;i+=4){
   if(!p[i+3])continue;
   const r=p[i],g=p[i+1],b=p[i+2],lum=.2126*r+.7152*g+.0722*b;
   const grain=(((i>>>2)*13^((i>>>2)>>>5)*7)&7)-3;
   const water=b>r*1.12&&b>g*.95;
   if(water){p[i]=61+lum*.37+grain;p[i+1]=88+lum*.37+grain;p[i+2]=91+lum*.34+grain}
   else{p[i]=55+lum*.73+grain;p[i+1]=39+lum*.72+grain;p[i+2]=22+lum*.64+grain}
  }
  return image;
 }
 async prepareInkExport(){
  this.paintTerrain();const coverage=this.terrainCoverage;
  if(!coverage.known||!coverage.loaded)throw Error('Esta área ainda não tem terreno carregado para exportar.');
  if(coverage.pending||coverage.failed)throw Error('Há imagens carregando ou com falha. Aguarde antes de exportar.');
  const palette=this.style.palette,grid=this.style.grid,identity=this.identity,camera=JSON.stringify(this.camera);
  const restore=()=>{if(this.identity===identity)this.setStyle({palette,grid})};
  if(palette==='atlas'){this.setStyle({grid:false});return restore}
  this.setStyle({palette:'atlas',grid:false});
  try{
   for(let n=0;n<160;n++){
    if(this.identity!==identity||JSON.stringify(this.camera)!==camera)throw Error('O mapa mudou durante a preparação. Enquadre a área e tente novamente.');
    this.paintTerrain();const current=this.terrainCoverage;
    if(current.failed)throw Error('Não foi possível carregar o desenho cartográfico.');
    if(current.known&&current.loaded&&!current.pending)return restore;
    await new Promise(resolve=>setTimeout(resolve,100));
   }
   throw Error('O desenho ainda está carregando. Tente novamente em alguns instantes.');
  }catch(error){restore();throw error}
 }
 antiqueFrame(c,width,height){
  c.strokeStyle='#6e5338';c.lineWidth=1.5;
  for(const inset of [9,14]){c.beginPath();c.moveTo(inset,inset+2);c.lineTo(width*.32,inset);c.lineTo(width*.68,inset+1);c.lineTo(width-inset,inset);c.lineTo(width-inset-1,height*.5);c.lineTo(width-inset,height-inset);c.lineTo(width*.55,height-inset-1);c.lineTo(inset,height-inset);c.lineTo(inset+1,height*.45);c.closePath();c.stroke()}
 }
 compassRose(c,x,y,r){
  c.save();c.translate(x,y);c.lineWidth=.7;c.strokeStyle='#61492f';
  for(let n=0;n<8;n++){c.save();c.rotate(n*Math.PI/4);const size=n%2?r*.65:r;c.beginPath();c.moveTo(0,-size);c.lineTo(r*.22,0);c.lineTo(0,r*.22);c.closePath();c.fillStyle=n%2?'#a88b60':'#61492f';c.fill();c.stroke();c.beginPath();c.moveTo(0,-size);c.lineTo(-r*.22,0);c.lineTo(0,r*.22);c.closePath();c.fillStyle='#eadbb7';c.fill();c.stroke();c.restore()}c.restore();
 }
 createExport({title='',maxSide=1600,includeWaypoints=true,includeAnnotations=true,appearance='current'}={}){
  if(!['current','antique'].includes(appearance))throw Error('Escolha um estilo de exportação válido.');
  const antique=appearance==='antique';
  const layout=this.exportLayout(maxSide);
  // Paint synchronously so camera, terrain versions and bounds describe one frame.
  this.paintTerrain();
  const coverage=this.terrainCoverage;
  if(!coverage.known||!coverage.loaded)throw Error('Esta área ainda não tem terreno carregado para exportar.');
  if(coverage.failed)throw Error('Algumas imagens falharam. Atualize o mapa antes de exportar.');
  if(coverage.pending)throw Error('Há imagens ou versões novas carregando. Aguarde e tente novamente.');
  const camera={...this.camera},canvas=document.createElement('canvas');canvas.width=layout.width;canvas.height=layout.height;
  try{
   const c=canvas.getContext('2d');if(!c)throw Error('O navegador não conseguiu preparar a imagem.');
   const {width,height,mapWidth,mapHeight,left,top,factor}=layout;
   const fit=(text,maxWidth)=>{let s=String(text);if(c.measureText(s).width<=maxWidth)return s;while(s.length&&c.measureText(s+'…').width>maxWidth)s=s.slice(0,-1);return s+'…'};
   const date=new Date(),world=String(this.state.world_name||'Meu mundo').trim(),dimension=['Overworld','Nether','End'][camera.dimension]||String(camera.dimension);
   c.fillStyle=antique?'#f4f0e4':'#f7f5ed';c.fillRect(0,0,width,height);
   if(antique)this.antiqueFrame(c,width,height);
   c.fillStyle=antique?'#61492f':'#263e4b';c.textAlign='left';c.font=antique?'bold 22px Georgia, serif':'bold 22px system-ui';
   c.fillText(fit(String(title).trim().slice(0,80)||world,width-110),24,32);
   c.font='11px system-ui';c.fillText(fit(world+' · '+dimension+' · '+date.toLocaleString('pt-BR'),width-48),24,55);
   c.font='bold 12px system-ui';c.textAlign='center';c.fillText('N',width-45,22);
   if(antique)this.compassRose(c,width-45,45,17);else{c.font='28px system-ui';c.fillText('↑',width-45,50)}
   c.imageSmoothingEnabled=this.style.palette!=='atlas'&&this.filters.smooth;
   // Export always uses light paper; restore the live canvas synchronously.
   this.paintTerrain({forceLight:true,includeSeed:false});
   try{c.drawImage(this.canvas,0,0,this.canvas.width,this.canvas.height,left,top,mapWidth,mapHeight)}finally{this.paintTerrain()}
   c.strokeStyle=antique?'#6e5338':'#78949d';c.lineWidth=1;c.strokeRect(left,top,mapWidth,mapHeight);
   if(includeAnnotations&&this.editor){c.save();c.beginPath();c.rect(left,top,mapWidth,mapHeight);c.clip();c.translate(left,top);this.editor.draw(c,{...camera,scale:camera.scale*factor},mapWidth,mapHeight,false,true);c.restore()}
   let waypointCount=0;
   let observedPointCount=0;
   if(includeWaypoints){
    c.save();c.beginPath();c.rect(left,top,mapWidth,mapHeight);c.clip();c.translate(left,top);
    observedPointCount=this.drawObservedPoints(c,p=>({x:mapWidth/2+(p.x-camera.x)*camera.scale*factor,y:mapHeight/2+(p.z-camera.z)*camera.scale*factor}),mapWidth,mapHeight,camera.scale*factor,false);
    c.restore();
   }
   if(includeWaypoints){
    c.save();c.beginPath();c.rect(left,top,mapWidth,mapHeight);c.clip();c.font='11px system-ui';c.textAlign='left';
    for(const w of this.waypoints){
     if(w.dimension!==camera.dimension)continue;
     const x=mapWidth/2+(w.x-camera.x)*camera.scale*factor,y=mapHeight/2+(w.z-camera.z)*camera.scale*factor;
     if(x<0||y<0||x>mapWidth||y>mapHeight)continue;
     waypointCount++;c.beginPath();c.fillStyle=antique||this.style.palette==='atlas'?'#484238':'#ff8a1f';c.arc(left+x,top+y,4,0,Math.PI*2);c.fill();c.strokeStyle=antique?'#484238':'#263e4b';c.stroke();
     const text=fit(w.name,Math.max(1,mapWidth-20)),textWidth=c.measureText(text).width,tx=left+Math.max(6,Math.min(mapWidth-textWidth-6,x+8)),ty=top+Math.max(15,Math.min(mapHeight-5,y-8));
     c.fillStyle='#fcfaf3ed';c.fillRect(tx-3,ty-12,textWidth+6,16);c.fillStyle='#263e4b';c.fillText(text,tx,ty);
    }c.restore();
   }
   const west=camera.x-this.width/(2*camera.scale),east=camera.x+this.width/(2*camera.scale),north=camera.z-this.height/(2*camera.scale),south=camera.z+this.height/(2*camera.scale);
   c.textAlign='left';c.font='11px system-ui';c.fillStyle='#263e4b';const footer=top+mapHeight;
   c.fillText(fit('X '+Math.floor(west)+' … '+Math.ceil(east)+' · Z '+Math.floor(north)+' … '+Math.ceil(south),width-48),24,footer+25);
   c.fillText(fit('Superfície observada · papel vazio = sem dados · anotações: '+waypointCount,width-48),24,footer+46);
   const scale=camera.scale*factor,target=90/scale,power=10**Math.floor(Math.log10(target));let blocks=power;for(const n of [1,2,5])if(n*power<=target)blocks=n*power;
   const barWidth=blocks*scale;c.beginPath();c.strokeStyle='#263e4b';c.lineWidth=1.5;c.moveTo(24,footer+62);c.lineTo(24,footer+69);c.lineTo(24+barWidth,footer+69);c.lineTo(24+barWidth,footer+62);c.stroke();c.font='10px system-ui';c.fillText(blocks+' blocos',24,footer+85);
   c.fillText('Chiko · Cartógrafo',Math.max(24,width-140),footer+85);
   const artwork=this.style.palette==='atlas'?{project:'Antique Atlas',author:'Hunternif',license:'CC BY-NC-SA 3.0',licenseUrl:'https://creativecommons.org/licenses/by-nc-sa/3.0/',source:'https://github.com/AntiqueAtlasTeam/AntiqueAtlas',commit:'b706821d3f0203038de3de6e79a6d354fe2c7b18',changes:'Cores, recortes e composição adaptados'}:null;
   if(artwork){
    const credit='Arte adaptada: Antique Atlas / Hunternif · CC BY-NC-SA 3.0';
    c.font='8px system-ui';const measured=c.measureText(credit).width;
    if(measured>width-48)c.font=Math.max(5,8*(width-48)/measured)+'px system-ui';
    c.fillText(credit,24,footer+99);
    c.font='8px system-ui';c.fillText('github.com/AntiqueAtlasTeam/AntiqueAtlas',24,footer+110);
    c.fillText('creativecommons.org/licenses/by-nc-sa/3.0/',24,footer+121);
   }
   return {canvas,metadata:{world,worldId:this.state.world_id,dimension:camera.dimension,camera,created:date.toISOString(),waypointCount,observedPointCount,appearance,artwork,...layout}};
  }catch(error){canvas.width=1;canvas.height=1;throw error}
 }
 label(text,x,y){const c=this.ink;c.save();c.textAlign='center';if(this.style.palette==='atlas'){atlasPixelText(c,text,x,y,'#484238','#f4f0e4')}else{c.font='12px system-ui';const width=c.measureText(text).width;c.fillStyle=this.style.dark?'#192a32f2':'#fffffff0';c.fillRect(x-width/2-5,y-13,width+10,19);c.fillStyle=this.style.dark?'#e3edf1':'#1b303d';c.fillText(text,x,y)}c.restore()}
 entities(){return (this.state.entities||[]).filter(e=>e.dimension===this.camera.dimension&&(this.filters.aquatic||!/(?:^|:)(?:salmon|cod|pufferfish|tropicalfish|tropical_fish|squid|glow_squid|dolphin|tadpole|axolotl)$/.test(e.typeId||''))&&(e.category==='animal'?this.filters.animals:e.category==='hostile'?this.filters.hostiles:this.filters.others)&&(!this.filters.text||`${e.name} ${e.typeId}`.toLowerCase().includes(this.filters.text.toLowerCase())))}
 observedPoints(){return this.filters.observed===false?[]:(this.state.terrain?.observed_points?.points||[]).filter(p=>p.dimension===this.camera.dimension)}
 drawObservedPoints(c,project,width,height,scale,dark=this.style.dark){
  const atlas=this.style.palette==='atlas',ink=dark&&!atlas?'#e3edf1':'#484238',paper=dark&&!atlas?'#192a32':'#f4f0e4';
  const occupied=[];let count=0;c.save();c.imageSmoothingEnabled=false;
  for(const p of this.observedPoints()){
   const at=project(p),x=Math.round(at.x),y=Math.round(at.y);
   if(x<0||y<0||x>width||y>height)continue;count++;
   c.fillStyle=paper;c.fillRect(x-8,y-9,16,17);c.fillStyle=ink;
   if(p.kind==='bed'){
    c.fillRect(x-7,y-2,14,5);c.fillRect(x-7,y-5,2,11);c.fillRect(x+5,y,2,6);
    c.fillStyle=paper;c.fillRect(x-4,y-1,3,2);c.fillStyle=ink;c.fillRect(x-1,y-3,7,1);
   }else{
    c.fillRect(x-5,y-8,10,2);c.fillRect(x-5,y+6,10,2);c.fillRect(x-5,y-6,2,12);c.fillRect(x+3,y-6,2,12);
    c.fillRect(x-1,y-4,2,2);c.fillRect(x+1,y-1,1,2);c.fillRect(x-2,y+2,2,2);
    if(p.kind==='end_portal')c.fillRect(x-6,y+8,12,1);
   }
   if(scale>=.8){
    const text=p.name||'Ponto observado',w=text.length*(atlas?4:6)+8;
    const rect={x:x-w/2,y:y-24,w,h:12};
    if(!occupied.some(r=>rect.x<r.x+r.w&&rect.x+rect.w>r.x&&rect.y<r.y+r.h&&rect.y+rect.h>r.y)){
     occupied.push(rect);
     if(atlas)atlasPixelText(c,text,x,y-13,ink,paper);
     else{c.font='11px system-ui';c.textAlign='center';c.fillStyle=paper;c.fillRect(rect.x,rect.y,w,13);c.fillStyle=ink;c.fillText(text,x,y-14)}
    }
   }
  }c.restore();return count;
 }
 paintOverlay(){
  const c=this.ink;c.setTransform(this.ratio,0,0,this.ratio,0,0);c.clearRect(0,0,this.width,this.height);c.lineWidth=1.5;c.strokeStyle='#203f50';
  this.editor?.draw(c,this.camera,this.width,this.height,this.style.dark);
  const entities=this.entities();
  this.drawObservedPoints(c,p=>this.screen(p.x,p.z),this.width,this.height,this.camera.scale);
  const trail=new Map();c.save();c.strokeStyle=this.style.dark?'#b2cfdd':'#53788c';c.lineWidth=2;c.setLineDash([4,4]);c.beginPath();
  for(const p of this.trail||[]){const old=trail.get(p.id);trail.set(p.id,p);if(p.dimension!==this.camera.dimension)continue;const at=this.screen(p.x,p.z);if(!old||p.break||old.dimension!==p.dimension)c.moveTo(at.x,at.y);else{const from=this.screen(old.x,old.z);c.moveTo(from.x,from.y);c.lineTo(at.x,at.y)}}c.stroke();c.restore();
  if(this.camera.scale<1){const n=entities.filter(e=>{const p=this.screen(e.x,e.z);return p.x>=0&&p.y>=0&&p.x<=this.width&&p.y<=this.height}).length;if(n)this.label(n+' entidades · aproxime para ver',this.width/2,48)}
  for(const raw of this.camera.scale>=1?entities:[]){
   const e=this.position(raw),p=this.screen(e.x,e.z);if(p.x<0||p.y<0||p.x>this.width||p.y>this.height)continue;
   if(this.portraits?.drawAnimal(c,e,p.x,p.y,this.style.palette==='atlas')){if(this.camera.scale>=6)this.label(e.name||e.typeId,p.x,p.y-12);continue}
   c.beginPath();c.fillStyle=e.category==='animal'?'#c2e0e8':e.category==='hostile'?'#d6c7bf':'#c7c7df';
   if(e.category==='hostile'){c.moveTo(p.x,p.y-5);c.lineTo(p.x+5,p.y+4);c.lineTo(p.x-5,p.y+4);c.closePath()}
   else if(e.category==='other'){c.moveTo(p.x,p.y-5);c.lineTo(p.x+5,p.y);c.lineTo(p.x,p.y+5);c.lineTo(p.x-5,p.y);c.closePath()}
   else c.arc(p.x,p.y,4,0,Math.PI*2);c.fill();c.stroke();if(this.camera.scale>=6)this.label(e.name||e.typeId,p.x,p.y-10);
  }
  if(this.camera.dimension===0&&this.state.terrain?.spawn){const p=this.screen(this.state.terrain.spawn.x,this.state.terrain.spawn.z);c.fillStyle='#fff';c.fillRect(p.x-4,p.y-4,8,8);c.strokeRect(p.x-4,p.y-4,8,8);this.label('Spawn',p.x,p.y-10)}
  for(const w of this.waypoints){if(w.dimension!==this.camera.dimension)continue;const p=this.screen(w.x,w.z),atlas=this.style.palette==='atlas';c.beginPath();c.fillStyle=atlas?'#f4f0e4':'#ff8a1f';c.strokeStyle=atlas?'#484238':'#203f50';c.lineWidth=atlas?1.25:1.5;c.arc(p.x,p.y,atlas?3:4,0,Math.PI*2);c.fill();c.stroke();this.label(atlas?w.name:'⚑ '+w.name,p.x,p.y-10)}
  for(const raw of this.state.players||[]){const p=this.position(raw);if(p.dimension!==this.camera.dimension)continue;const at=this.screen(p.x,p.z);if(!this.portraits?.drawPlayer(c,p,at.x,at.y,this.style.palette==='atlas')){c.save();c.translate(at.x,at.y);c.rotate((p.yaw||0)*Math.PI/180);c.beginPath();c.moveTo(0,12);c.lineTo(-8,-8);c.lineTo(0,-4);c.lineTo(8,-8);c.closePath();c.fillStyle=p.host?'#c9e9f7':'#fff';c.fill();c.strokeStyle='#1c4e68';c.lineWidth=p.host?3:2;c.stroke();c.restore()}this.label((p.host?'★ ':'')+p.name,at.x,at.y-18)}
  this.portraits?.drawCursor(c,this.cursor,this.style.palette==='atlas');
 }
 select(point){
  let nearest=null,distance=16;
  const targets=[...(this.state.players||[]).map(p=>({...this.position(p),selectionType:'player'})),...(this.camera.scale>=1?this.entities():[]).map(e=>({...this.position(e),selectionType:'entity'})),...this.waypoints.map(w=>({...w,selectionType:'waypoint'})),...this.observedPoints().map(p=>({...p,selectionType:'observed'}))];
  for(const target of targets){if(target.dimension!==this.camera.dimension)continue;const p=this.screen(target.x,target.z),d=Math.hypot(point.x-p.x,point.y-p.y);if(d<distance){nearest=target;distance=d}}
  this.onSelect(nearest||{...this.world(point.x,point.y),dimension:this.camera.dimension,selectionType:'coordinate'});
 }
 bindGestures(){
  const el=this.overlay;
  const point=e=>{const r=el.getBoundingClientRect();return {x:e.clientX-r.left,y:e.clientY-r.top}};
  el.onwheel=e=>{e.preventDefault();this.zoom(Math.exp(-e.deltaY*.0015),point(e))};
  el.onpointerdown=e=>{
   if(e.button!==undefined&&e.button!==0)return;el.setPointerCapture(e.pointerId);this.following=null;const p=point(e);this.pointers.set(e.pointerId,p);
   if(this.pointers.size===1){this.gesturePinched=false;this.drag={point:p,x:this.camera.x,z:this.camera.z,moved:false}}
   if(this.pointers.size===1&&this.editor?.start(this.world(p.x,p.y),this.camera.dimension)){this.editingPointer=e.pointerId;return}
   if(this.pointers.size===2&&this.editingPointer!=null){this.editor?.cancel();this.editingPointer=null}
   if(this.pointers.size===2){this.gesturePinched=true;const[a,b]=[...this.pointers.values()],mid={x:(a.x+b.x)/2,y:(a.y+b.y)/2};this.pinch={distance:Math.max(1,Math.hypot(a.x-b.x,a.y-b.y)),scale:this.camera.scale,anchor:this.world(mid.x,mid.y)}}
  };
  el.onpointermove=e=>{
   const p=point(e);this.cursor=p;if(this.portraits?.settings.cursor)this.invalidateOverlay();
   if(this.editingPointer===e.pointerId&&this.pointers.size===1){this.pointers.set(e.pointerId,p);this.editor?.move(this.world(p.x,p.y));this.reportCamera();return}
   if(!this.pointers.size)this.editor?.move(this.world(p.x,p.y));
   if(this.pointers.has(e.pointerId)){
    this.pointers.set(e.pointerId,p);
    if(this.pointers.size===2&&this.pinch){const[a,b]=[...this.pointers.values()],mid={x:(a.x+b.x)/2,y:(a.y+b.y)/2};this.camera.scale=Math.max(.04,Math.min(32,this.pinch.scale*Math.hypot(a.x-b.x,a.y-b.y)/this.pinch.distance));this.targetScale=this.camera.scale;this.camera.x=this.pinch.anchor.x-(mid.x-this.width/2)/this.camera.scale;this.camera.z=this.pinch.anchor.z-(mid.y-this.height/2)/this.camera.scale}
    else if(this.drag){this.drag.moved||=Math.hypot(p.x-this.drag.point.x,p.y-this.drag.point.y)>5;this.camera.x=this.drag.x-(p.x-this.drag.point.x)/this.camera.scale;this.camera.z=this.drag.z-(p.y-this.drag.point.y)/this.camera.scale}
    this.targetScale=this.camera.scale;this.zoomAnchor=null;this.invalidateTerrain();
   }this.reportCamera();
  };
  const finish=(e,cancelled)=>{
   if(!this.pointers.has(e.pointerId))return;
   if(this.editingPointer===e.pointerId){if(cancelled)this.editor?.cancel();else this.editor?.end();this.editingPointer=null;this.pointers.delete(e.pointerId);this.drag=null;this.reportCamera();return}
   if(!cancelled&&this.pointers.size===1&&!this.gesturePinched&&this.drag&&!this.drag.moved)this.select(point(e));
   this.pointers.delete(e.pointerId);this.pinch=null;this.targetScale=this.camera.scale;
   if(this.pointers.size===1){const p=[...this.pointers.values()][0];this.drag={point:p,x:this.camera.x,z:this.camera.z,moved:true}}
   else this.drag=null;this.reportCamera();
  };
  el.onpointerup=e=>finish(e,false);el.onpointercancel=e=>finish(e,true);el.onlostpointercapture=e=>finish(e,true);
  el.onpointerleave=()=>{if(!this.pointers.size){this.cursor=null;if(this.editor){this.editor.hover=null;this.invalidateOverlay()}this.reportCamera()}};
 }
};
