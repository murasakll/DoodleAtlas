import { world, system } from '@minecraft/server';
import * as mc from '@minecraft/server';
import { WORLD_ID } from './config.js';
import { CaptureQueue } from './capture_queue.js';
// Keep this in the existing entry module: Minecraft can cache the module list
// until the application restarts when a new script file is added to a pack.
function surfaceBlock(dimension,x,z){
 const range=dimension.heightRange;
 const top=dimension.id.includes('nether')?Math.min(120,range.max-1):range.max-1;
 const hit=dimension.getBlockFromRay({x:x+.5,y:top+.9,z:z+.5},{x:0,y:-1,z:0},
  {includeLiquidBlocks:true,includePassableBlocks:true,maxDistance:top-range.min+.9});
 if(!hit?.block)throw Error('Superfície indisponível');
 return hit.block;
}
const emit=data=>console.warn('[BEDROCK_LIVE_MAP]'+JSON.stringify({worldId:WORLD_ID,...data}));
const dimId=id=>id.includes('nether')?1:id.includes('end')?2:0;
const capture=new CaptureQueue(32);
const animalTypes=new Set(['cow','sheep','pig','chicken','wolf','cat','ocelot','horse','donkey','mule','llama','trader_llama','rabbit','fox','panda','polar_bear','bee','goat','camel','sniffer','armadillo','turtle','dolphin','squid','glow_squid','salmon','cod','pufferfish','tropicalfish','axolotl','frog','tadpole','bat','parrot','mooshroom','happy_ghast']);
let work=null;
let playerTicks=20,columnsPerTick=4,lastStatus='',lastEntities='',lastEntityTick=0;
capture.revisitTicks=6000;
system.runInterval(()=>{
 try{
  if(system.currentTick%playerTicks!==0)return;
  const players=world.getAllPlayers();
  const status={kind:'status',players:players.map(p=>({uniqueId:p.id,name:p.name,dimension:p.dimension.id,position:p.location,yaw:p.getRotation().y})),capabilities:{surface:true,entities:true,seedSearch:typeof world.getDimension('overworld').calculateClosestBiomeFromSeed==='function',playerSeconds:playerTicks/20,columnsPerTick,revisitSeconds:capture.revisitTicks/20}};
  const signature=JSON.stringify(status);
  if(signature!==lastStatus||system.currentTick%40<playerTicks){emit(status);lastStatus=signature}
  if(system.currentTick-lastEntityTick<Math.max(10,playerTicks))return;
  lastEntityTick=system.currentTick;
  const entities=[];
  for(const dimension of ['overworld','nether','the_end']){
   for(const e of world.getDimension(dimension).getEntities()){
    if(['minecraft:player','minecraft:item','minecraft:xp_orb'].includes(e.typeId))continue;
    let families=[];try{families=e.getComponent('minecraft:type_family')?.getTypeFamilies()||[]}catch{}
    const animal=families.includes('animal')||animalTypes.has(e.typeId.replace('minecraft:',''))||e.hasComponent('minecraft:breedable')||e.hasComponent('minecraft:tameable');
    const category=families.includes('monster')?'hostile':animal?'animal':'other';
    const position=e.location;
    entities.push({id:e.id,typeId:e.typeId,name:e.nameTag||e.typeId,dimension:dimId(e.dimension.id),x:Math.round(position.x*10)/10,y:Math.round(position.y*10)/10,z:Math.round(position.z*10)/10,category,families});
    if(entities.length>=512)break;
   }
   if(entities.length>=512)break;
  }
  const frame=system.currentTick,total=Math.max(1,Math.ceil(entities.length/24));
  const entitySignature=JSON.stringify(entities);
  if(entitySignature!==lastEntities||system.currentTick%40<Math.max(10,playerTicks)){
   for(let part=0;part<total;part++)emit({kind:'entities',frame,part,total,entities:entities.slice(part*24,(part+1)*24)});
   lastEntities=entitySignature;
  }
 }catch(e){emit({kind:'error',message:String(e)})}
},1);
// 32 column reads per tick, only in loaded chunks. No block/entity writes.
system.runInterval(()=>{
 try{
  if(system.currentTick%4===0)capture.probe(world.getAllPlayers(),system.currentTick,8);
  if(!work){
   const candidate=capture.next();
   if(!candidate)return;
   work={...candidate,next:0,palette:[],ids:[],heights:[],depth:[],biomes:[]};
  }
  let reads=0;
  for(let count=0;reads<columnsPerTick&&work.next<256;count++,work.next++){
   const x=work.x*16+work.next%16,z=work.z*16+Math.floor(work.next/16),block=surfaceBlock(work.dimension,x,z);reads++;
   if(!block)throw Error('Coluna indisponível');
   let id=work.palette.indexOf(block.typeId);if(id<0){id=work.palette.length;work.palette.push(block.typeId)}
   work.ids.push(id);work.heights.push(block.location.y);
   // Surface viewer: do not sample or shade the seabed.
   work.depth.push(0);
   if(work.next%4===0&&Math.floor(work.next/16)%4===0){
    try{work.biomes.push(work.dimension.getBiome({x,y:block.location.y,z})?.id||'')}catch{work.biomes.push('')}
   }
  }
  if(work.next===256){
   let biome=null;try{biome=work.dimension.getBiome({x:work.x*16+8,y:work.heights[136],z:work.z*16+8})?.id||null}catch{}
   emit({kind:'surface',surfaceVersion:2,dimension:dimId(work.dimension.id),x:work.x,z:work.z,palette:work.palette,ids:work.ids,heights:work.heights,depth:work.depth,biomes:work.biomes,biome,tick:system.currentTick});
   capture.complete(work.key,system.currentTick);work=null;
  }
 }catch{if(work)capture.complete(work.key,system.currentTick-capture.revisitTicks+100);work=null}
},1);
function findBiome(biome,player){
 if(!player)return;
 if(!/^[a-z0-9_]+:[a-z0-9_]+$/.test(biome))return;
 system.run(()=>{
  try{
   if(typeof player.dimension.calculateClosestBiomeFromSeed!=='function')throw Error('Busca nativa pela seed requer Script API 2.9+. Use /locate biome ou o mapa externo de seed.');
   const position=player.dimension.calculateClosestBiomeFromSeed(player.location,biome);if(!position)throw Error('Bioma não encontrado');
   emit({kind:'biome',biome,dimension:dimId(player.dimension.id),...position,source:'seed'});
   player.sendMessage(`${biome}: X ${Math.round(position.x)}, Z ${Math.round(position.z)}`);
  }catch(e){emit({kind:'biome',biome,error:String(e)});player.sendMessage(String(e))}
 });
}
system.afterEvents.scriptEventReceive.subscribe(event=>{
 if(event.id==='livemap:biome')findBiome(event.message.trim(),event.sourceEntity);
});
if(system.beforeEvents?.startup)system.beforeEvents.startup.subscribe(event=>{
 try{
  event.customCommandRegistry.registerCommand({name:'livemap:taxa',description:'Taxa do mapa: segundos, leituras por tick, revisita em segundos',permissionLevel:mc.CommandPermissionLevel.Any,cheatsRequired:false,mandatoryParameters:[{name:'segundos',type:mc.CustomCommandParamType.Float},{name:'leituras',type:mc.CustomCommandParamType.Integer},{name:'revisita',type:mc.CustomCommandParamType.Integer}]},(origin,seconds,columns,revisit)=>{
   if(!Number.isFinite(seconds)||seconds<.25||seconds>2||columns<1||columns>128||revisit<5||revisit>300)return {status:mc.CustomCommandStatus.Failure,message:'Use 0.25–2 s, 1–128 leituras, 5–300 s de revisita'};
   system.run(()=>{playerTicks=Math.round(seconds*20);columnsPerTick=columns;capture.revisitTicks=revisit*20;origin.sourceEntity?.sendMessage(`Mapa: ${playerTicks/20}s / ${columns} leituras / revisita ${revisit}s`)});
   return {status:mc.CustomCommandStatus.Success};
  });
  event.customCommandRegistry.registerCommand({name:'livemap:bioma',description:'Localizar bioma pela seed e mostrar no mapa web',permissionLevel:mc.CommandPermissionLevel.Any,cheatsRequired:false,mandatoryParameters:[{name:'bioma',type:mc.CustomCommandParamType.String}]},(origin,biome)=>{
   findBiome(biome.includes(':')?biome:'minecraft:'+biome,origin.sourceEntity);
   return {status:mc.CustomCommandStatus.Success};
  });
 }catch(e){emit({kind:'error',message:'Registro de /livemap:bioma: '+String(e)})}
});
