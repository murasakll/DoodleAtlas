"""Chiko adapter for licensed Antique Atlas artwork (no upstream Java included).

The unchanged source PNGs and their license/provenance live in third_party/.
Runtime artwork adaptations: recoloring, quarter selection, composition and masks.
Adapted artwork is CC BY-NC-SA 3.0; see THIRD_PARTY_NOTICES.md.
"""
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from chiko.paths import ASSETS as ALL_ASSETS
ASSETS=ALL_ASSETS/'antique_atlas'
ART_VERSION='antique-buildings-2-'+hashlib.sha256((ASSETS/'manifest.json').read_bytes()).hexdigest()[:16]
PAPER=(244,240,228,255)
INK=(72,66,56,255)
SHEETS={
    'forest':('forest','forest2','forest3'),'dense':('dense_forest',),
    'birch':('birch','birch2'),'pines':('pines','pines2'),'jungle':('jungle','jungle2'),
    'savanna':('savanna',),'mountains':('mountains','mountains2'),'hills':('hills',),
    'plains':('grass','grass2'),'sand':('sand','sand2'),'water':('water','water2'),
    'swamp':('swamp',),'snow':('snow',),'snow_pines':('snow_pines',),
    'mushroom':('mushroom',),'shore':('shore',)
}
WOODS={'forest','dense','birch','pines','jungle','savanna','swamp','snow_pines'}


def construction_material(name):
    namespace,_,block=str(name).partition(':')
    if namespace not in ('minecraft','universal_minecraft'):return False
    # Materials indicate a built footprint, not ownership or a proven house.
    return (any(k in block for k in ('planks','brick','concrete','glass','terracotta','quartz_block','purpur','chiseled','cut_copper'))
        or block in ('crafting_table','furnace','blast_furnace','smoker','bookshelf','chest','barrel','bed','cobblestone','mossy_cobblestone','iron_block','gold_block','diamond_block','emerald_block','netherite_block')
        or block.endswith(('_bed','_door','_stairs','_slab','_fence','_fence_gate','_wall')))


def draw_footprints(image,built,known):
    core=built[16:-16,16:-16]&known[16:-16,16:-16]
    if not core.any():return image
    height,width=core.shape;edge=np.zeros_like(core)
    for dz,dx in ((-1,0),(1,0),(0,-1),(0,1)):
        neighbor=np.s_[16+dz:16+dz+height,16+dx:16+dx+width]
        edge|=core&known[neighbor]&~built[neighbor]
    pixels=np.array(image);pixels[core]=(224,217,201,255);pixels[edge]=INK
    return Image.fromarray(pixels)


@lru_cache(maxsize=1)
def sheets():
    manifest=json.loads((ASSETS/'manifest.json').read_text(encoding='utf-8'))
    result={}
    for name,entry in manifest['files'].items():
        path=ASSETS/entry['file'];data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('Sprite Antique Atlas alterado: '+name)
        with Image.open(path) as source:
            if source.size!=(32,48):raise ValueError('Sprite Antique Atlas com tamanho inválido')
            rgba=np.array(source.convert('RGBA'))
        light=rgba[:,:,:3].mean(axis=2)>224
        rgba[:,:,:3]=INK[:3];rgba[light,:3]=PAPER[:3]
        result[name]=Image.fromarray(rgba)
    return result


def connected(kind,other):
    # Missing observations never create a fictional shoreline or forest edge.
    if other is None:return True
    if kind==other:return True
    if kind in WOODS and other in WOODS:return True
    if kind in ('mountains','hills') and other in ('mountains','hills'):return True
    if kind in ('plains','shore'):return other!='water'
    return False


def quarter_uv(qx,qz,horizontal,vertical,diagonal,opposite_horizontal,opposite_vertical):
    """Address an 8px quarter in the artwork's documented 4×6 layout."""
    if horizontal and vertical:
        return (2-qx,4-qz) if diagonal else (2+qx,qz)
    if horizontal:return 2-qx,2+qz*3
    if vertical:return qx*3,4-qz
    if not opposite_horizontal and not opposite_vertical:return qx,qz
    return qx*3,2+qz*3


def biome_symbol(name):
    """Only used for the explicitly predicted biome layer."""
    name=str(name).lower()
    if 'ocean' in name or 'river' in name:return 'water'
    if any(k in name for k in ('snow','frozen','ice','grove')):return 'snow_pines' if 'taiga' in name or 'grove' in name else 'snow'
    if 'mushroom' in name:return 'mushroom'
    if 'swamp' in name:return 'swamp'
    if 'jungle' in name:return 'jungle'
    if 'birch' in name:return 'birch'
    if 'taiga' in name:return 'pines'
    if 'dark_forest' in name:return 'dense'
    if 'forest' in name:return 'forest'
    if 'savanna' in name:return 'savanna'
    if any(k in name for k in ('desert','beach','badlands')):return 'sand'
    if any(k in name for k in ('peak','mountain','windswept')):return 'mountains'
    return 'plains'


def _compose(labels,known,water,rx,rz,step=1):
    height,width=known.shape[0]-32,known.shape[1]-32
    core=known[16:-16,16:-16];sea=water[16:-16,16:-16]
    pixels=np.zeros((height,width,4),dtype=np.uint8);pixels[core]=PAPER
    base=Image.fromarray(pixels);overlay=Image.new('RGBA',(width,height));art=sheets()
    for gz in range(1,labels.shape[0]-1):
        for gx in range(1,labels.shape[1]-1):
            kind=labels[gz,gx]
            if kind is None:continue
            wx=(rx*16+gx-1)*step;wz=(rz*16+gz-1)*step
            variation=(wx*73856093^wz*19349663)&0xffffffff
            choices=SHEETS[kind];sheet=art[choices[variation%len(choices)]]
            for qz in (0,1):
                for qx in (0,1):
                    dx=qx*2-1;dz=qz*2-1
                    h=connected(kind,labels[gz,gx+dx]);v=connected(kind,labels[gz+dz,gx]);d=connected(kind,labels[gz+dz,gx+dx])
                    oh=connected(kind,labels[gz,gx-dx]);ov=connected(kind,labels[gz-dz,gx])
                    u,t=quarter_uv(qx,qz,h,v,d,oh,ov)
                    piece=np.array(sheet.crop((u*8,t*8,u*8+8,t*8+8)))
                    x=(gx-1)*16+qx*8;z=(gz-1)*16+qz*8
                    valid=core[z:z+8,x:x+8]&(sea[z:z+8,x:x+8] if kind=='water' else ~sea[z:z+8,x:x+8])
                    piece[~valid,3]=0;overlay.paste(Image.fromarray(piece),(x,z))
    image=Image.alpha_composite(base,overlay)
    # Exact observed water/land interfaces take precedence over symbolic art.
    coast=np.zeros_like(core)
    for dz,dx in ((-1,0),(1,0),(0,-1),(0,1)):
        neighbor=np.s_[16+dz:16+dz+height,16+dx:16+dx+width]
        coast|=core&~sea&known[neighbor]&water[neighbor]
    pixels=np.array(image);pixels[coast]=INK;pixels[~core]=0
    return Image.fromarray(pixels)


def render_observed(names,heights,rx=0,rz=0,biomes=None):
    names=np.asarray(names,dtype=object);heights=np.asarray(heights)
    if names.shape!=heights.shape or names.ndim!=2 or any(n<48 or n%16 for n in names.shape):raise ValueError('Arte exige halo de 16 blocos em cada borda')
    known=heights!=-32768;water=np.zeros(names.shape,dtype=bool);built=water.copy()
    flags={key:water.copy() for key in ('leaves','birch','pines','sand','snow','mushroom')}
    for raw in set(names.flat):
        name=str(raw);mask=names==raw
        if name in ('minecraft:air','minecraft:cave_air','minecraft:void_air',''):known[mask]=False
        if construction_material(name):built[mask]=True
        if name in ('minecraft:water','minecraft:flowing_water'):water[mask]=True
        if 'leaves' in name:flags['leaves'][mask]=True
        if 'birch_leaves' in name:flags['birch'][mask]=True
        if 'spruce_leaves' in name:flags['pines'][mask]=True
        if 'sand' in name and 'sandstone' not in name:flags['sand'][mask]=True
        if any(k in name for k in ('snow','ice')):flags['snow'][mask]=True
        if 'mushroom' in name:flags['mushroom'][mask]=True
    water&=known
    rows,cols=names.shape[0]//16,names.shape[1]//16;labels=np.full((rows,cols),None,dtype=object)
    for gz in range(rows):
        for gx in range(cols):
            sl=np.s_[gz*16:(gz+1)*16,gx*16:(gx+1)*16];valid=known[sl];count=int(valid.sum())
            if not count:continue
            ratio=lambda key:float(np.count_nonzero(flags[key][sl]&valid))/count
            sea=float(water[sl].sum())/count;h=heights[sl][valid&~water[sl]]
            if sea>=.55:kind='water'
            elif ratio('leaves')>=.15:
                hint=''
                if biomes is not None:
                    values=np.asarray(biomes)[sl][valid];hint=Counter(str(x) for x in values if x).most_common(1);hint=hint[0][0] if hint else ''
                suggested=biome_symbol(hint)
                kind='birch' if ratio('birch')>=.1 else 'pines' if ratio('pines')>=.1 else suggested if suggested in WOODS else 'dense' if ratio('leaves')>.55 else 'forest'
            elif ratio('snow')>.25:kind='snow'
            elif ratio('mushroom')>.15:kind='mushroom'
            elif ratio('sand')>.35:kind='shore' if sea>.1 else 'sand'
            elif h.size and (h.max()>=140 or h.max()>=100 and np.ptp(h)>=10):kind='mountains'
            elif h.size and np.ptp(h)>=4:kind='hills'
            else:kind='plains'
            labels[gz,gx]=kind
    return draw_footprints(_compose(labels,known,water,rx,rz),built,known)


def render_predicted(biomes,rx=0,rz=0,step=1):
    """Biome symbols for the seed overlay only; no invented real surface records."""
    biomes=np.asarray(biomes,dtype=object)
    if biomes.shape!=(288,288):raise ValueError('Previsão cartográfica exige halo de 288 × 288')
    kinds=np.empty(biomes.shape,dtype=object)
    for name in set(biomes.flat):kinds[biomes==name]=biome_symbol(name)
    labels=np.empty((18,18),dtype=object)
    for z in range(18):
        for x in range(18):labels[z,x]=Counter(kinds[z*16:(z+1)*16,x*16:(x+1)*16].flat).most_common(1)[0][0]
    return _compose(labels,np.ones(biomes.shape,dtype=bool),kinds=='water',rx,rz,step)
