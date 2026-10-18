// An explicit downward ray includes liquids and vegetation; no player Y or
// sea-level assumption. A failed/unloaded column must not become a seabed tile.
export function surfaceBlock(dimension,x,z){
 const range=dimension.heightRange;
 const top=dimension.id.includes('nether')?Math.min(120,range.max-1):range.max-1;
 const hit=dimension.getBlockFromRay({x:x+.5,y:top+.9,z:z+.5},{x:0,y:-1,z:0},
  {includeLiquidBlocks:true,includePassableBlocks:true,maxDistance:top-range.min+.9});
 if(!hit?.block)throw Error('Superfície indisponível');
 return hit.block;
}
