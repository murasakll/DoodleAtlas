"""Read local packs; missing vanilla PNGs may use a small disposable Mojang cache."""
import json
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image,ImageEnhance
import hashlib
import urllib.request
import threading


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):
        return {}


def resource_packs(world,game_roots=()):
    packs=[]
    for root in game_roots:
        root=Path(root)
        def order(p):
            import re
            return tuple(int(n) for n in re.findall(r'\d+',p.name))
        if root.is_dir():
            packs.extend(sorted((p for p in root.iterdir() if p.is_dir() and p.name.startswith('vanilla')),key=order))
    world=Path(world)
    references=read_json(world/'world_resource_packs.json')
    references=references if isinstance(references,list) else []
    available={}
    for base in [world/'resource_packs',world.parent.parent/'resource_packs',world.parent.parent/'development_resource_packs']:
        if base.is_dir():
            for pack in base.iterdir():
                manifest=read_json(pack/'manifest.json')
                identifier=manifest.get('header',{}).get('uuid')
                if identifier:
                    available[identifier]=pack
    for reference in reversed(references):
        if reference.get('pack_id') in available:
            packs.append(available[reference['pack_id']])
    return packs


class TextureCatalog:
    def __init__(self,packs=(),download_cache=None):
        self.aliases={}
        self.blocks={}
        self.packs=list(packs)
        self.download_cache=Path(download_cache) if download_cache else None
        self.download_lock=threading.Lock()
        self.missing=set()
        for pack in self.packs:
            for alias,data in read_json(pack/'textures'/'terrain_texture.json').get('texture_data',{}).items():
                self.aliases[alias]=(pack,data.get('textures'))
            for name,data in read_json(pack/'blocks.json').items():
                if isinstance(data,dict) and 'textures' in data:
                    self.blocks[name]=data['textures']

    @lru_cache(maxsize=1024)
    def tile(self,name,size=16):
        from terrain import colour
        base=name.split(':')[-1]
        texture=self.blocks.get(name,self.blocks.get(base,base))
        if isinstance(texture,dict):
            texture=texture.get('up',texture.get('all',next(iter(texture.values()),base)))
        aliases={'grass_block':'grass_top','grass':'grass_top','snow_layer':'snow','water':'water_still','lava':'lava_still',
                 'oak_log':'log_oak_top','spruce_log':'log_spruce_top','birch_log':'log_birch_top'}
        candidate=self.aliases.get(str(texture),self.aliases.get(aliases.get(base,base)))
        if candidate:
            pack,value=candidate
            if isinstance(value,list):
                value=value[0] if value else None
            tint=None
            if isinstance(value,dict):
                tint=value.get('overlay_color')
                value=value.get('path')
            if isinstance(value,str):
                path=(pack/value).resolve()
                if pack.resolve() in path.parents:
                    for ext in ('','.png','.tga'):
                        target=Path(str(path)+ext)
                        if target.is_file():
                            try:
                                with Image.open(target) as source:
                                    image=source.convert('RGBA').crop((0,0,source.width,min(source.height,source.width)))
                                    image=image.resize((size,size),Image.Resampling.NEAREST)
                                if base in ('grass','grass_block') or 'leaves' in base:
                                    a=np.array(image).copy()
                                    a[:,:,:3]=(a[:,:,:3].astype(float)*np.array([.55,.78,.38])).astype('uint8')
                                    image=Image.fromarray(a)
                                return image
                            except OSError:
                                pass
                # New Bedrock distributions keep vanilla PNGs inside .brarchive.
                # Fetch only a requested vanilla PNG from Mojang's official samples,
                # into this disposable session; never download entire asset archives.
                if self.download_cache and name.startswith('minecraft:') and value.startswith('textures/blocks/') and '..' not in value:
                    with self.download_lock:
                        target=self.download_cache/(hashlib.sha256(value.encode()).hexdigest()+'.png')
                        if value not in self.missing and not target.exists():
                            try:
                                self.download_cache.mkdir(parents=True,exist_ok=True)
                                total=sum(p.stat().st_size for p in self.download_cache.glob('*.png'))
                                if total>8*1024*1024:raise OSError('Limite de 8 MB de texturas')
                                url='https://raw.githubusercontent.com/Mojang/bedrock-samples/main/resource_pack/'+value+'.png'
                                with urllib.request.urlopen(url,timeout=4) as response:data=response.read(1024*1024)
                                import io
                                with Image.open(io.BytesIO(data)) as check:check.verify()
                                target.write_bytes(data)
                            except (OSError,ValueError):self.missing.add(value)
                        if target.exists():
                            with Image.open(target) as source:
                                image=source.convert('RGBA').crop((0,0,source.width,min(source.height,source.width))).resize((size,size),Image.Resampling.NEAREST)
                            if base in ('grass','grass_block') or 'leaves' in base:
                                a=np.array(image).copy();a[:,:,:3]=(a[:,:,:3].astype(float)*np.array([.55,.78,.38])).astype('uint8');image=Image.fromarray(a)
                            return image
        return Image.new('RGBA',(size,size),colour(name))

    def render(self,names,heights,size=8,margin=None,exaggeration=1.5,intensity=.8,depth=None,biome=None):
        from terrain import shade_surface
        from relief import biome_tint
        out=Image.new('RGBA',(16*size,16*size))
        light=shade_surface(heights,margin,exaggeration,intensity)
        for z in range(16):
            for x in range(16):
                tile=self.tile(str(names[z,x]),size)
                cell_biome=biome[(z//4)*4+x//4] if isinstance(biome,list) and len(biome)==16 else biome
                tint=biome_tint(str(names[z,x]),cell_biome)
                if not np.all(tint==1):
                    a=np.array(tile).copy();a[:,:,:3]=np.clip(a[:,:,:3]*tint,0,255).astype('uint8');tile=Image.fromarray(a)
                if light[z,x]!=1:
                    tile=ImageEnhance.Brightness(tile).enhance(float(light[z,x]))
                out.paste(tile,(x*size,z*size),tile)
        return out
