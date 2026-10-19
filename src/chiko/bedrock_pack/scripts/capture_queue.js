// Probe in rings, with bounded work per tick. Never load or generate chunks.
export class CaptureQueue {
 constructor(radius=32){
  this.offsets=[];
  for(let x=-radius;x<=radius;x++)for(let z=-radius;z<=radius;z++)this.offsets.push([x,z]);
  this.offsets.sort((a,b)=>a[0]*a[0]+a[1]*a[1]-b[0]*b[0]-b[1]*b[1]);
  this.cursor=0;this.pending=[];this.queued=new Set();this.seen=new Map();this.revisitTicks=1200;
 }
 probe(players,tick,budget=32){
  if(!players.length)return;
  const origin=players.map(p=>`${p.dimension.id}/${Math.floor(p.location.x/16)}/${Math.floor(p.location.z/16)}`).join('|');
  if(origin!==this.origin){this.origin=origin;this.cursor=0}
  this.players=players;this.tick=tick;
  for(let i=0;i<budget;i++){
   const index=this.cursor++%(this.offsets.length*players.length);
   const p=players[index%players.length],[dx,dz]=this.offsets[Math.floor(index/players.length)];
   const x=Math.floor(p.location.x/16)+dx,z=Math.floor(p.location.z/16)+dz;
   const key=`${p.dimension.id}/${x}/${z}`;
   if(this.queued.has(key)||tick-(this.seen.get(key)??-10000)<this.revisitTicks)continue;
   let loaded=false;
   try{
    loaded=typeof p.dimension.isChunkLoaded==='function'
     ?p.dimension.isChunkLoaded({x:x*16+8,y:Math.floor(p.location.y),z:z*16+8})
     :!!p.dimension.getTopmostBlock({x:x*16+8,z:z*16+8});
   }catch{}
   if(!loaded)continue;
   this.queued.add(key);this.pending.push({dimension:p.dimension,x,z,key});
  }
 }
 next(){
  if(!this.pending.length)return null;
  // Balance proximity and age so distant work cannot starve indefinitely.
  const score=c=>{
   let distance=Infinity;
   for(const p of this.players||[])if(p.dimension.id===c.dimension.id)distance=Math.min(distance,Math.hypot(c.x-Math.floor(p.location.x/16),c.z-Math.floor(p.location.z/16)));
   return distance*20-((this.tick||0)-(this.seen.get(c.key)??-10000))*.05;
  };
  let best=0,value=score(this.pending[0]);
  for(let i=1;i<this.pending.length;i++){const next=score(this.pending[i]);if(next<value){best=i;value=next}}
  return this.pending.splice(best,1)[0];
 }
 complete(key,tick){
  this.queued.delete(key);this.seen.set(key,tick);
  if(this.seen.size>20000)this.seen.delete(this.seen.keys().next().value);
 }
}
