"""Optional local Overworld biome prediction. Never opens a world's LevelDB."""
import ctypes
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
import zlib
import io
from contextlib import closing
from functools import lru_cache

import numpy as np

ROOT=Path(__file__).resolve().parent
NATIVE=ROOT/'vendor'/'seed-generator'
ALIASES={'snowy_tundra':'snowy_plains','mountains':'windswept_hills','wooded_mountains':'windswept_forest',
         'gravelly_mountains':'windswept_gravelly_hills','stone_shore':'stony_shore','jungle_edge':'sparse_jungle',
         'giant_tree_taiga':'old_growth_pine_taiga','giant_spruce_taiga':'old_growth_spruce_taiga',
         'tall_birch_forest':'old_growth_birch_forest','wooded_badlands_plateau':'wooded_badlands',
         'extreme_hills':'windswept_hills','extreme_hills_plus_trees':'windswept_forest',
         'ice_plains':'snowy_plains','roofed_forest':'dark_forest','birch_forest_mutated':'old_growth_birch_forest',
         'swampland':'swamp','mesa':'badlands','redwood_taiga':'old_growth_pine_taiga','cold_taiga':'snowy_taiga',
         'extreme_hills_mutated':'windswept_gravelly_hills','stone_beach':'stony_shore'}

def canonical(name):
    value=str(name or '').split(':')[-1]
    return ALIASES.get(value,value)

def seed_number(value):
    if not isinstance(value,(str,int)) or isinstance(value,bool):raise ValueError('Seed deve ser um inteiro decimal exato')
    text=str(value)
    if not text or text.strip()!=text or text.lstrip('-').isdigit() is False:raise ValueError('Seed decimal inválida')
    number=int(text)
    if not -(1<<63)<=number<(1<<64):raise ValueError('Seed fora de 64 bits')
    return number&((1<<64)-1)

@lru_cache(maxsize=1)
def native_library():
    manifest=json.loads((NATIVE/'manifest.json').read_text(encoding='utf-8'))
    path=NATIVE/'seed-generator.dll'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['files']['seed-generator.dll']:raise RuntimeError('DLL de seed divergente; recompile')
    return ctypes.CDLL(str(path))

class SeedGenerator:
    def __init__(self,seed):
        self.seed=seed_number(seed);self.lock=threading.Lock();self.handle=None
        self.lib=native_library()
        self.lib.chiko_create.argtypes=[ctypes.c_uint64];self.lib.chiko_create.restype=ctypes.c_void_p
        self.lib.chiko_free.argtypes=[ctypes.c_void_p]
        self.lib.chiko_biome.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int];self.lib.chiko_biome.restype=ctypes.c_int
        self.lib.chiko_grid.argtypes=[ctypes.c_void_p,*([ctypes.c_int]*5),ctypes.POINTER(ctypes.c_int)];self.lib.chiko_grid.restype=ctypes.c_int
        self.lib.chiko_name.argtypes=[ctypes.c_int];self.lib.chiko_name.restype=ctypes.c_char_p
        self.handle=self.lib.chiko_create(self.seed)
        if not self.handle:raise MemoryError('Gerador indisponível')

    def close(self):
        with self.lock:
            if self.handle:self.lib.chiko_free(self.handle);self.handle=None

    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    def name(self,biome):
        name=self.lib.chiko_name(int(biome))
        return canonical(name.decode() if name else str(biome))

    def biome(self,x,y,z):
        if not all(isinstance(n,int) and -(1<<30)<=n<(1<<30) for n in (x,y,z)):raise ValueError('Coordenadas inválidas')
        with self.lock:
            if not self.handle:raise RuntimeError('Gerador fechado')
            return self.name(self.lib.chiko_biome(self.handle,x,y,z))

    def grid(self,scale,x,y,z,side=64):
        if scale not in (4,16,64,256) or not 1<=side<=256:raise ValueError('Grade inválida')
        if not all(isinstance(n,int) and -(1<<29)<=n<(1<<29) for n in (x,y,z)):raise ValueError('Coordenadas inválidas')
        out=np.empty((side,side),dtype=np.int32)
        with self.lock:
            if not self.handle:raise RuntimeError('Gerador fechado')
            code=self.lib.chiko_grid(self.handle,scale,x,y,z,side,out.ctypes.data_as(ctypes.POINTER(ctypes.c_int)))
        if code:raise RuntimeError('Falha na previsão de biomas: '+str(code))
        return out

def validate_capture(seed,path,limit=512):
    """Compare at the exact XYZ used by pack samples, in a read-only transaction.

    Captures contain no per-column biome timestamp. This checks stored observations,
    not a new controlled gameplay session and not every biome in Minecraft.
    """
    start=time.perf_counter()
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        rows=db.execute('SELECT x,z,heights,biomes FROM surfaces WHERE dim=0 AND surface_version>=2 AND biomes IS NOT NULL ORDER BY x,z').fetchall()
    samples=[]
    for x,z,h,bs in rows:
        biomes=json.loads(bs)
        if not isinstance(biomes,list) or len(biomes)!=16:continue
        heights=np.frombuffer(zlib.decompress(h),dtype='<i2').reshape(16,16)
        for i,b in enumerate(biomes):
            lx=(i%4)*4;lz=(i//4)*4;y=int(heights[lz,lx])
            if b and y!=-32768:samples.append((x*16+lx,y,z*16+lz,canonical(b)))
    if len(samples)>limit:samples=[samples[int(i)] for i in np.linspace(0,len(samples)-1,limit)]
    counts={};differences=[];matched=0
    with SeedGenerator(seed) as generator:
        for x,y,z,observed in samples:
            predicted=generator.name(generator.grid(4,x//4,y//4,z//4,1)[0,0]);ok=predicted==observed;matched+=ok
            count=counts.setdefault(observed,{'samples':0,'matched':0});count['samples']+=1;count['matched']+=ok
            if not ok and len(differences)<30:differences.append({'x':x,'y':y,'z':z,'observed':observed,'predicted':predicted})
    return {'scope':'stored pack samples; 4-block biome grid at observed XYZ; no new real-game test','samples':len(samples),'matched':matched,
            'fraction':matched/len(samples) if samples else None,'by_biome':counts,'differences':differences,
            'sample_sha256':hashlib.sha256(json.dumps(samples,separators=(',',':')).encode()).hexdigest(),'wall_seconds':time.perf_counter()-start}

@lru_cache(maxsize=1)
def seed_palette():
    return json.loads((ROOT/'paleta.json').read_text(encoding='utf-8'))

def metadata(world):
    """Only level.dat metadata, never LevelDB. Called once per world selection."""
    try:
        import amulet_nbt
        path=Path(world)/'level.dat'
        if path.stat().st_size>16*1024*1024:raise ValueError('Metadados grandes demais')
        tag=amulet_nbt.load(path.read_bytes()[8:],compressed=False,little_endian=True).compound
        version=[int(n.py_int) for n in tag['lastOpenedWithVersion']][:4]
        if version[:2]!=[1,26] or not 50<=version[2]<=52:raise ValueError('Prévia disponível apenas para Bedrock 26.50–26.52')
        if int(tag['Generator'].py_int)!=1:raise ValueError('Prévia requer geração normal')
        seed=str(tag['RandomSeed'].py_int);seed_number(seed)
        manifest=json.loads((NATIVE/'manifest.json').read_text(encoding='utf-8'))
        if not (NATIVE/'seed-generator.dll').is_file():raise ValueError('Gerador não compilado')
        palette_hash=hashlib.sha256((ROOT/'paleta.json').read_bytes()).hexdigest()
        from antique_art import ART_VERSION
        version_id=hashlib.sha256((seed+str(version)+manifest['files']['seed-generator.dll']+palette_hash+ART_VERSION).encode()).hexdigest()[:24]
        return {'available':True,'experimental':True,'dimension':0,'seed':seed,'version':version,'revision':version_id,
                'description':'Biomas previstos em altura fixa; costas e fronteiras podem divergir. Não é terreno observado.'}
    except Exception as error:
        return {'available':False,'experimental':True,'description':str(error)}

def render_prediction(seed,level,x,z,y=64,style='paper',smooth=False):
    from PIL import Image
    if not 0<=level<=3 or style not in ('paper','minecraft','atlas') or not -64<=y<=320:raise ValueError('Prévia inválida')
    scale=4*4**level
    with SeedGenerator(seed) as generator:
        if style=='atlas':
            from antique_art import render_predicted
            ids=generator.grid(scale,x*64-4,y//4,z*64-4,72)
            unique,inverse=np.unique(ids,return_inverse=True)
            names=np.asarray([generator.name(int(n)) for n in unique],dtype=object)[inverse].reshape(72,72)
            image=render_predicted(np.repeat(np.repeat(names,4,axis=0),4,axis=1),x,z,step=4**level)
            out=io.BytesIO();image.save(out,format='WEBP',lossless=True,method=2);return out.getvalue()
        # A one-sample halo makes visual interpolation agree across tile edges.
        side=66 if smooth else 64;offset=-1 if smooth else 0
        ids=generator.grid(scale,x*64+offset,y//4,z*64+offset,side)
        table=seed_palette();colors=table['seed_biomes'];water=table['minecraft']['blocks']['minecraft:water'] if style=='minecraft' else table['identity']['water']
        lookup={}
        for number in np.unique(ids):
            name=generator.name(number)
            if 'ocean' in name or 'river' in name:color=water
            elif name in colors:color=colors[name]
            elif any(k in name for k in ('snow','frozen','ice','peak','grove')):color=colors['snow']
            elif any(k in name for k in ('desert','beach','badlands')):color=colors['sand']
            elif any(k in name for k in ('forest','taiga','jungle','swamp')):color=colors['forest']
            else:color=colors['plains']
            lookup[int(number)]=((207,203,193,255) if 'ocean' in name or 'river' in name else (240,237,227,255)) if style=='atlas' else tuple(bytes.fromhex(color[1:]))+(255,)
        unique,inverse=np.unique(ids,return_inverse=True)
        pixels=np.array([lookup[int(n)] for n in unique],dtype=np.uint8)[inverse].reshape(side,side,4)
    image=Image.fromarray(pixels)
    if smooth:image=image.resize((264,264),Image.Resampling.BILINEAR).crop((4,4,260,260))
    else:image=image.resize((256,256),Image.Resampling.NEAREST)
    out=io.BytesIO();image.save(out,format='WEBP',lossless=True,method=2);return out.getvalue()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--seed',required=True);parser.add_argument('--capture',required=True)
    args=parser.parse_args();print(json.dumps(validate_capture(args.seed,args.capture),indent=2,ensure_ascii=False))
