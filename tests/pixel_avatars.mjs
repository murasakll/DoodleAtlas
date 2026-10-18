import fs from 'node:fs/promises';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

export async function run(){
 const elements=new Map(),storage=new Map(),draws=[],crops=[],revoked=[];let pixelWrites=0,decodeGate=null;
 const ctx=()=>({save(){},restore(){},clearRect(){},fillRect(){pixelWrites++},drawImage(...args){draws.push({args,smooth:this.imageSmoothingEnabled});if(args.length===9)crops.push(args.slice(1))},getImageData:()=>({data:Uint8ClampedArray.from({length:256},(_,i)=>i%4===3?255:100)})});
 const node=()=>({value:'',checked:false,children:[],append(x){this.children.push(x)},replaceChildren(){this.children=[]},getContext(){return this.context||=ctx()}});
 const el=id=>{if(!elements.has(id))elements.set(id,node());return elements.get(id)};
 const box={document:{getElementById:el,createElement:node},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:x=>revoked.push(x)},Image:class{naturalWidth=64;naturalHeight=64;async decode(){if(decodeGate)await decodeGate}},Uint8Array,DataView};
 vm.createContext(box);vm.runInContext(await fs.readFile(new URL('../web/pixel-avatars.js',import.meta.url),'utf8'),box);
 vm.runInContext(`for(const[type,entry]of Object.entries(PixelAnimalSpecies)){const sprite=pixelAnimal('minecraft:'+type);if(!sprite||sprite.rows.length!==8||sprite.rows.some(r=>r.length!==8))throw Error('Malformed portrait '+type);const a=pixelPortraitPixels(sprite,true),b=pixelPortraitPixels(sprite,false);if(a.flat().some(c=>c&&!['#484238','#a79f8d','#d8ceb8','#f4f0e4'].includes(c)))throw Error('Atlas palette '+type);if(a.flat().filter(Boolean).length!==b.flat().filter(Boolean).length)throw Error('Tint changed silhouette '+type)}
 if(pixelAnimal('addon:cow')||pixelAnimal('minecraft:unknown'))throw Error('Unknown entity mistaken for a vanilla animal');
 if(pixelProfile({preset:'__proto__',hat:'bad',face:[1]}).preset!=='explorer'||pixelProfile(null).face)throw Error('Invalid profile accepted');
 const a=pixelCharacter({preset:'explorer',hat:'none'}),b=pixelCharacter({preset:'explorer',hat:'crown'}),d=pixelCharacter({preset:'explorer',detail:'glasses'});if(JSON.stringify(a)===JSON.stringify(b)||JSON.stringify(a)===JSON.stringify(d))throw Error('Accessories have no effect');
 globalThis.map={invalidateOverlay(){},editor:{enabled:()=>true}};globalThis.portraits=new PixelAvatars({map});portraits.update({world_id:'one',players:[{name:'Mura'}]});
 portraits.el('portraitHat').value='crown';portraits.el('portraitHat').onchange();`,box);
 if(!storage.get('livemap-portraits-one')?.includes('crown'))throw Error('Appearance not saved');
 vm.runInContext("portraits.update({world_id:'two',players:[{name:'Mura'}]});if(portraits.current().hat==='crown')throw Error('Avatar leaked across worlds');portraits.update({world_id:'one',players:[{name:'Mura'}]});if(portraits.current().hat!=='crown')throw Error('Avatar not restored');",box);
 box.drawContext=ctx();draws.length=0;const before=pixelWrites;
 vm.runInContext("portraits.drawAnimal(drawContext,{typeId:'minecraft:cow'},10.2,20.7,true);portraits.drawAnimal(drawContext,{typeId:'minecraft:cow'},10.2,20.7,true)",box);
 const built=pixelWrites-before;
 if(draws.length!==2||draws.some(d=>d.smooth!==false||d.args.slice(1).some(n=>!Number.isInteger(n)))||built>64)throw Error('Raster cache / nearest-neighbour sampling failed');
 vm.runInContext("portraits.settings.animals=false;if(portraits.drawAnimal(drawContext,{typeId:'minecraft:cow'},0,0,false))throw Error('Animal toggle ignored');portraits.settings.animals=true;portraits.settings.players=false;if(portraits.drawPlayer(drawContext,{name:'Mura'},0,0,false))throw Error('Player toggle ignored');portraits.settings.players=true",box);
 function header(width,height){const a=new Uint8Array(24);a.set([137,80,78,71,13,10,26,10]);a.set([73,72,68,82],12);const view=new DataView(a.buffer);view.setUint32(16,width);view.setUint32(20,height);return a.buffer}
 for(const[w,h,valid]of [[8,8,true],[64,64,true],[64,32,true],[4096,4096,false],[16,16,false]]){box.headerBuffer=header(w,h);const accepted=vm.runInContext('(()=>{try{pixelSkinHeader(headerBuffer);return true}catch{return false}})()',box);if(accepted!==valid)throw Error('PNG dimensions accepted incorrectly')}
 box.uploadFile={size:200,arrayBuffer:async()=>header(64,64)};await vm.runInContext('portraits.upload(uploadFile)',box);
 if(crops.length!==2||crops[0].slice(0,4).join()!=='8,8,8,8'||crops[1].slice(0,4).join()!=='40,8,8,8'||!revoked.length)throw Error('Skin face/hat UV or URL cleanup failed');
 if(vm.runInContext("portraits.current().face?.length!==256||portraits.current().hat!=='none'",box))throw Error('Uploaded face not persisted');
 // Changing the player/world/preset while decoding must discard the old upload.
 let release;decodeGate=new Promise(r=>{release=r});const pending=vm.runInContext('portraits.upload(uploadFile)',box);await Promise.resolve();await Promise.resolve();
 vm.runInContext("portraits.change({preset:'farmer'})",box);release();await pending;decodeGate=null;
 if(vm.runInContext("portraits.current().face||portraits.current().preset!=='farmer'",box))throw Error('Stale upload replaced a newer choice');
 for(let i=0;i<120;i++){box.cacheId='test'+i;vm.runInContext("portraits.draw(drawContext,pixelCharacter({}),0,0,false,2,cacheId)",box)}
 if(vm.runInContext('portraits.cache.size>96',box))throw Error('Portrait cache unbounded');
 return {animal_species_and_fallback:'OK',atlas_palette:'OK',presets_and_accessories:'OK',world_local_persistence:'OK',pixel_cache_and_toggles:'OK',png_validation_and_skin_crop:'OK',stale_upload_and_url_cleanup:'OK',scope:'simulated canvas; real PNG decode requires browser'};
}
if(typeof process!=='undefined'&&process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)run().then(console.log).catch(e=>{console.error(e);process.exitCode=1});
