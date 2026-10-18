'use strict';
// Original pixel portraits. No game textures, network skin lookups or resource packs.
const PixelAnimalFaces={
 cow:['s#....#s','.######.','.#ppssp#','.#epppe#','.#ppppp#','.#nnnnn#','.#n#n#n#','..#####.'],
 pig:['........','.s####s.','.#pppp#.','.#epppe#','.#pppp#.','.#nnnn#.','.#n##n#.','..####..'],
 sheep:['.ssssss.','ssssssss','ssppppss','sseppess','ssppppss','sspnnpss','.ssppss.','..ssss..'],
 chicken:['...nn...','..snnss.','.sppppps','.spepeps','.sppppps','..pnnpp.','...nn...','...ss...'],
 wolf:['##....##','#s####s#','.ppsspp.','.peppep.','.pppppp.','..pnnpp.','..p##pp.','...pp...'],
 cat:['#s....s#','#ps##sp#','.ppsspp.','.peppep.','ssppppss','..pnnpp.','.spppps.','...pp...'],
 horse:['.ss..ss.','.ps..sp.','..####..','..p##p..','..e##e..','..p##p..','..nnnn..','..n##n..'],
 rabbit:['.ss..ss.','.ps..sp.','.ps..sp.','..pppp..','.ppeepp.','.ppnnpp.','..pppp..','...ss...'],
 fox:['#s....s#','#ps##sp#','.pppppp.','.peppep.','.spppps.','..snns..','..ssss..','...ss...'],
 panda:['.##..##.','ssssssss','ss####ss','sse##ess','ssssssss','ssnnnnss','.ss##ss.','..ssss..'],
 goat:['#......#','.#....#.','.ss##ss.','.speeps.','.spppps.','..pnnp..','...pp...','...ss...'],
 bee:['........','.ss..ss.','spp##pps','ppeppepp','ppp##ppp','spp##pps','.pp##pp.','..ssss..'],
 turtle:['........','..ssss..','.spppps.','speppeps','spppppps','.snnnns.','..ssss..','........'],
 frog:['........','.ss..ss.','speppeps','spppppps','spnnnnps','.spppps.','..ssss..','........'],
 axolotl:['.s....s.','sps##sps','spppppps','speppeps','spppppps','spnnnnps','.ssssss.','........'],
 fish:['........','......s.','..ssssps','.spppeps','#pppppps','.spppps.','..ssss..','........'],
 squid:['..ssss..','.spppps.','spppppps','speppeps','spppppps','.ssssss.','.s.ss.s.','s..ss..s'],
 dolphin:['...ss...','..spps..','.spppps.','.speeps.','..pppp..','.ppnnpp.','..ssss..','........'],
 parrot:['...sss..','..sppps.','.sppppps','.spepeps','.sppnnps','..pnnpp.','..sspps.','...sss..'],
 bat:['s......s','ss....ss','sps..sps','.ppsspp.','.peppep.','..pnnp..','...ss...','........'],
 armadillo:['........','..ssss..','.spppps.','sp++++ps','speppeps','.ppnnpp.','..ssss..','........'],
 camel:['.ss..ss.','.ps..sp.','..pppp..','.ppsspp.','.peppep.','.ppnnpp.','..pppp..','..ssss..']
};
const PixelAnimalSpecies={
 cow:['cow','#9b7658','#f5efe0','#c9959c'],mooshroom:['cow','#a74f43','#f2e8d6','#c9959c'],pig:['pig','#e5aaa8','#b9777e','#bd7d89'],sheep:['sheep','#b29c83','#eee7d9','#aa8c83'],chicken:['chicken','#f5ead4','#ae4e3e','#d4a04b'],wolf:['wolf','#c3c4bd','#6c7470','#333a38'],cat:['cat','#d6ad72','#8a6748','#c88c90'],ocelot:['cat','#d4b35b','#76653b','#b18e77'],horse:['horse','#a17b55','#5e4937','#bda68c'],donkey:['horse','#a4a193','#66665f','#c2b5a1'],mule:['horse','#8d7b65','#544d44','#b9a68f'],llama:['horse','#ddd1b0','#957e62','#c4af91'],trader_llama:['horse','#d7cba5','#6e99a0','#bda68c'],rabbit:['rabbit','#d4bc9a','#a18f75','#d3a3a1'],fox:['fox','#d38d4f','#eee6d6','#423b36'],panda:['panda','#e8e3d6','#222d2c','#333c38'],polar_bear:['wolf','#eee8d9','#c7c9bd','#3b4540'],goat:['goat','#ddd4bf','#988d77','#c6a78b'],bee:['bee','#dcc05b','#dfdac9','#776c38'],turtle:['turtle','#87a47a','#536e54','#6e8062'],frog:['frog','#b89963','#827a50','#a08162'],axolotl:['axolotl','#dfa9b9','#ad6c91','#b67794'],cod:['fish','#baaa83','#817961','#aa9981'],salmon:['fish','#af7a6c','#788b74','#9a6d68'],tropicalfish:['fish','#d4a057','#7da8a6','#a57959'],tropical_fish:['fish','#d4a057','#7da8a6','#a57959'],pufferfish:['fish','#c8ad57','#a2873d','#a48c57'],squid:['squid','#718d99','#435d6c','#5c7586'],glow_squid:['squid','#66b6af','#397c80','#58aaa0'],dolphin:['dolphin','#8eafba','#c3d0cf','#829da7'],parrot:['parrot','#ba665c','#76a899','#c6a15c'],bat:['bat','#9c8d7b','#71675c','#b19b8a'],armadillo:['armadillo','#b69d85','#857663','#a88b78'],camel:['camel','#c5a878','#8b7658','#b0946a']
};
const PixelCharacterPresets={
 explorer:{skin:'#cda385',hair:'#65503c',accent:'#638d84',hat:'cap',detail:'none'},
 farmer:{skin:'#dbb697',hair:'#806045',accent:'#c5ac6b',hat:'straw',detail:'none'},
 knight:{skin:'#c59b7d',hair:'#594b42',accent:'#9daba9',hat:'helmet',detail:'none'},
 mage:{skin:'#d5b198',hair:'#cbc3ae',accent:'#887a9d',hat:'wizard',detail:'beard'}
};
function pixelProfile(raw={}){
 if(!raw||typeof raw!=='object')raw={};
 const preset=Object.hasOwn(PixelCharacterPresets,raw.preset)?raw.preset:'explorer',base=PixelCharacterPresets[preset],out={preset,...base};
 for(const key of ['skin','hair','accent'])if(/^#[0-9a-f]{6}$/i.test(raw[key]||''))out[key]=raw[key];
 if(['none','cap','straw','helmet','wizard','crown','hood'].includes(raw.hat))out.hat=raw.hat;
 if(['none','glasses','beard','scarf'].includes(raw.detail))out.detail=raw.detail;
 if(Array.isArray(raw.face)&&raw.face.length===256&&raw.face.every(n=>Number.isInteger(n)&&n>=0&&n<=255))out.face=[...raw.face];
 return out;
}
function pixelSkinHeader(buffer){
 const a=new Uint8Array(buffer),sig=[137,80,78,71,13,10,26,10];
 if(a.length<24||sig.some((v,i)=>a[i]!==v)||String.fromCharCode(...a.slice(12,16))!=='IHDR')throw Error('Escolha uma imagem PNG.');
 const view=new DataView(a.buffer,a.byteOffset,a.byteLength),width=view.getUint32(16),height=view.getUint32(20);
 if(!((width===64&&[32,64].includes(height))||(width===8&&height===8)))throw Error('Use skin PNG 64 × 64 / 64 × 32 ou um rosto 8 × 8.');
 return {width,height};
}
function pixelAnimal(typeId){
 if(typeof typeId!=='string'||!typeId.startsWith('minecraft:'))return null;
 const name=typeId.slice(10);if(!Object.hasOwn(PixelAnimalSpecies,name))return null;const species=PixelAnimalSpecies[name];
 const[face,p,s,n]=species;return {rows:PixelAnimalFaces[face],palette:{p,s,n,e:'#202928','#':'#34392f','+':s}};
}
function pixelCharacter(profile){
 const p=pixelProfile(profile),pixels=Array.from({length:12},()=>Array(12).fill(null)),put=(x,y,color)=>{if(x>=0&&x<12&&y>=0&&y<12)pixels[y][x]=color};
 if(p.face){for(let y=0;y<8;y++)for(let x=0;x<8;x++){const i=(y*8+x)*4;if(p.face[i+3]>=128)put(x+2,y+3,'#'+p.face.slice(i,i+3).map(v=>v.toString(16).padStart(2,'0')).join(''))}}
 else{
  for(let y=0;y<8;y++)for(let x=0;x<8;x++)put(x+2,y+3,y<2||x===0||x===7&&y<5?p.hair:p.skin);
  for(const x of [4,7])put(x,6,'#263332');for(const x of [5,6])put(x,9,'#976950');
 }
 const pattern=(rows,x,y,color)=>rows.forEach((row,j)=>[...row].forEach((ch,i)=>{if(ch==='#')put(x+i,y+j,color)}));
 const hats={cap:['.######.','########','########','....####'],straw:['..####..','.######.','########','########'],helmet:['.######.','########','##....##','##....##'],wizard:['...#....','..###...','.#####..','########'],crown:['#..##..#','########','.######.'],hood:['.######.','########','##....##','##....##','##....##']};
 if(hats[p.hat])pattern(hats[p.hat],2,0,p.accent);
 if(p.detail==='glasses')pattern(['###.###','#.#.#.#','###.###'],2,5,'#30322c');
 if(p.detail==='beard')pattern(['#....#','######','.####.','..##..'],3,8,p.hair);
 if(p.detail==='scarf')pattern(['########','....##..'],2,10,p.accent);
 return {pixels};
}
function pixelPortraitPixels(sprite,atlas=false){
 const pixels=sprite.pixels||sprite.rows.map(row=>[...row].map(code=>sprite.palette[code]||null));
 if(!atlas)return pixels;
 return pixels.map(row=>row.map(color=>{if(!color)return null;const n=parseInt(color.slice(1),16),l=.2126*(n>>16)+.7152*((n>>8)&255)+.0722*(n&255);return l<75?'#484238':l<145?'#a79f8d':l<215?'#d8ceb8':'#f4f0e4'}));
}
class PixelAvatars{
 constructor({map}){
  this.map=map;this.world=null;this.profiles={};this.cache=new Map();this.settings={players:true,animals:true,cursor:false};this.el=id=>document.getElementById(id);this.uploadGeneration=0;
  try{Object.assign(this.settings,JSON.parse(localStorage.getItem('livemap-portrait-settings')||'{}'))}catch{}
  for(const[key,id]of Object.entries({players:'portraitPlayers',animals:'portraitAnimals',cursor:'portraitCursor'})){this.settings[key]=typeof this.settings[key]==='boolean'?this.settings[key]:key!=='cursor';this.el(id).checked=this.settings[key];this.el(id).onchange=()=>{this.settings[key]=this.el(id).checked;try{localStorage.setItem('livemap-portrait-settings',JSON.stringify(this.settings))}catch{}map.invalidateOverlay()}}
  this.el('portraitPlayer').onchange=()=>{this.uploadGeneration++;this.sync()};
  this.el('portraitPreset').onchange=()=>this.change(pixelProfile({preset:this.el('portraitPreset').value}));
  for(const[key,id]of Object.entries({skin:'portraitSkin',hair:'portraitHair',accent:'portraitAccent',hat:'portraitHat',detail:'portraitDetail'}))this.el(id).onchange=()=>this.change({...this.current(),[key]:this.el(id).value});
  this.el('portraitUpload').onchange=()=>this.upload(this.el('portraitUpload').files?.[0]);
  this.el('portraitReset').onclick=()=>this.change(pixelProfile({preset:this.el('portraitPreset').value}));
 }
 key(name){return 'p:'+String(name||'').normalize('NFC').trim().toLowerCase().slice(0,80)}
 current(){return pixelProfile(this.profiles[this.key(this.el('portraitPlayer').value)])}
 change(profile){
  const name=this.el('portraitPlayer').value;if(!this.world||!name)return;
  const key=this.key(name);if(!Object.hasOwn(this.profiles,key)&&Object.keys(this.profiles).length>=32){this.status('Limite de 32 aparências por mundo neste navegador.');return}
  this.uploadGeneration++;this.profiles[key]=pixelProfile(profile);this.cache.clear();this.sync();this.map.invalidateOverlay();this.onChange?.();
  try{localStorage.setItem('livemap-portraits-'+this.world,JSON.stringify(this.profiles));this.status('Aparência salva neste navegador, para este mundo.')}catch{this.status('Sem espaço no navegador: aparência mantida apenas nesta aba.')}
 }
 status(text){this.el('portraitStatus').textContent=text}
 update(state){
  const world=state.world_id,changed=this.world!==world;
  if(changed){this.world=world;this.uploadGeneration++;this.profiles={};this.cache.clear();try{const raw=JSON.parse(localStorage.getItem('livemap-portraits-'+world)||'{}');for(const[key,value]of Object.entries(raw).slice(0,32))if(key.startsWith('p:')&&key.length<=82)this.profiles[key]=pixelProfile(value)}catch{}}
  const names=[...new Set((state.players||[]).map(p=>p.name).filter(Boolean))];
  for(const key of Object.keys(this.profiles))if(!names.some(n=>this.key(n)===key))names.push(key.slice(2));
  const signature=JSON.stringify([world,names]);if(signature===this.signature)return;this.signature=signature;
  const select=this.el('portraitPlayer'),previous=changed?'':select.value;select.replaceChildren();
  for(const name of names){const option=document.createElement('option');option.value=name;option.textContent=name;select.append(option)}
  select.value=names.includes(previous)?previous:names[0]||'';this.sync();
  if(changed)this.status(names.length?'Escolha um jogador para personalizar.':'Abra o mundo para escolher um jogador.');
 }
 sync(){
  const p=this.current(),disabled=!this.world||!this.el('portraitPlayer').value;
  for(const[key,id]of Object.entries({preset:'portraitPreset',skin:'portraitSkin',hair:'portraitHair',accent:'portraitAccent',hat:'portraitHat',detail:'portraitDetail'})){this.el(id).value=p[key];this.el(id).disabled=disabled}
  this.el('portraitUpload').disabled=disabled;this.el('portraitReset').disabled=disabled;
  const canvas=this.el('portraitPreview'),c=canvas.getContext('2d');if(c){canvas.width=96;canvas.height=96;c.clearRect(0,0,96,96);this.draw(c,pixelCharacter(p),48,48,false,6,'preview:'+JSON.stringify(p))}
 }
 async upload(file){
  if(!file)return;const world=this.world,name=this.el('portraitPlayer').value,ticket=++this.uploadGeneration;let url;
  try{
   if(file.size>256*1024)throw Error('O PNG deve ter no máximo 256 KiB.');
   const size=pixelSkinHeader(await file.arrayBuffer());url=URL.createObjectURL(file);const img=new Image();img.src=url;await img.decode();
   if(img.naturalWidth!==size.width||img.naturalHeight!==size.height)throw Error('Dimensões inválidas no PNG.');
   const canvas=document.createElement('canvas');canvas.width=8;canvas.height=8;const c=canvas.getContext('2d');if(!c)throw Error('Não foi possível ler a imagem.');c.imageSmoothingEnabled=false;
   c.drawImage(img,size.width===8?0:8,size.width===8?0:8,8,8,0,0,8,8);
   if(size.width===64)c.drawImage(img,40,8,8,8,0,0,8,8);
   const face=Array.from(c.getImageData(0,0,8,8).data);if(ticket!==this.uploadGeneration||world!==this.world||name!==this.el('portraitPlayer').value)return;
   this.change({...this.current(),face,hat:'none',detail:'none'});
  }catch(error){if(ticket===this.uploadGeneration)this.status(error.message)}finally{if(url)URL.revokeObjectURL(url);if(ticket===this.uploadGeneration||world===this.world&&name===this.el('portraitPlayer').value)this.el('portraitUpload').value=''}
 }
 draw(c,sprite,x,y,atlas=false,pixelSize=2,key=''){
  const id=key+':'+atlas;let canvas=this.cache.get(id);
  if(!canvas){const pixels=pixelPortraitPixels(sprite,atlas);canvas=document.createElement('canvas');canvas.width=pixels[0].length;canvas.height=pixels.length;const ctx=canvas.getContext('2d');if(!ctx)return false;for(let row=0;row<pixels.length;row++)for(let col=0;col<pixels[row].length;col++)if(pixels[row][col]){ctx.fillStyle=pixels[row][col];ctx.fillRect(col,row,1,1)}this.cache.set(id,canvas);if(this.cache.size>96)this.cache.delete(this.cache.keys().next().value)}
  c.save();c.imageSmoothingEnabled=false;c.drawImage(canvas,Math.round(x-canvas.width*pixelSize/2),Math.round(y-canvas.height*pixelSize/2),canvas.width*pixelSize,canvas.height*pixelSize);c.restore();return true;
 }
 drawAnimal(c,e,x,y,atlas){if(!this.settings.animals)return false;const sprite=pixelAnimal(e.typeId);return !!sprite&&this.draw(c,sprite,x,y,atlas,2,'animal:'+e.typeId)}
 drawPlayer(c,p,x,y,atlas){if(!this.settings.players)return false;const profile=pixelProfile(this.profiles[this.key(p.name)]),drawn=this.draw(c,pixelCharacter(profile),x,y,atlas,2,'player:'+JSON.stringify(profile));if(drawn&&Number.isFinite(p.yaw)){const angle=Math.round(p.yaw/45)*Math.PI/4;c.save();c.fillStyle=atlas?'#484238':'#263e4b';c.fillRect(Math.round(x-Math.sin(angle)*16)-1,Math.round(y+Math.cos(angle)*16)-1,3,3);c.restore()}return drawn}
 drawCursor(c,cursor,atlas){if(!this.settings.cursor||!cursor||!this.map.editor?.enabled()||!this.el('portraitPlayer').value)return;c.save();c.globalAlpha=.65;const profile=this.current();this.draw(c,pixelCharacter(profile),cursor.x+20,cursor.y+20,atlas,2,'player:'+JSON.stringify(profile));c.restore()}
}
