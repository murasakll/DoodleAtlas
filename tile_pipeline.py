"""On-demand 256px WebP pyramid. Only derived images go to a session SQLite."""
import asyncio
import hashlib
import io
import json
import sqlite3
import time
import zlib
from pathlib import Path

import numpy as np
from PIL import Image,features
from relief import hillshade,biome_tint
from terrain import colour,PALETTE_ID
from render_queue import Rendered,RenderClosed
from surface_store import SurfaceStore
from cartography import draw_atlas,VERSION as CARTOGRAPHY_VERSION

MAX_LEVEL=8
TILE_SIZES=(64,128,256,512,1024,2048)

def source_key(d,level,x,z,pixels=256):
    if pixels not in TILE_SIZES or not 0<=level<=MAX_LEVEL:raise ValueError('Tamanho ou zoom inválido')
    if pixels<=256:
        factor=256//pixels
        return d,level,x//factor,z//factor
    shift=(pixels//256).bit_length()-1
    if level+shift>MAX_LEVEL:raise ValueError('Zoom incompatível com tamanho do tile')
    return d,level+shift,x,z

def render_sized(children,pixels,crop=None):
    if crop is not None:
        with Image.open(io.BytesIO(children[0][2])) as child:return encode(child.convert('RGBA').crop(crop))
    image=Image.new('RGBA',(pixels,pixels))
    for dx,dz,data in children:
        with Image.open(io.BytesIO(data)) as child:image.paste(child.convert('RGBA'),(dx*256,dz*256))
    return encode(image)


def digest(value):
    return hashlib.sha256(json.dumps(value,separators=(',',':'),sort_keys=True).encode()).hexdigest()[:24]


class TileChanged(RuntimeError):
    pass


class TileIndex:
    def __init__(self):
        self.saved={};self.live={};self.versions={};self._manifest={}

    def sync(self,saved_chunks,live):
        saved={(int(d),x,z):v for d,items in saved_chunks.items() for x,z,v in items}
        dirty=set()
        for before,after in [(self.saved,saved),(self.live,live)]:
            for d,x,z in before.keys()|after.keys():
                if before.get((d,x,z))==after.get((d,x,z)):continue
                xs={x//16};zs={z//16}
                if x%16==0:xs.add(x//16-1)
                if x%16==15:xs.add(x//16+1)
                if z%16==0:zs.add(z//16-1)
                if z%16==15:zs.add(z//16+1)
                dirty.update((d,0,rx,rz) for rx in xs for rz in zs)
        self.saved=saved;self.live=live.copy()
        if not dirty:return False
        for d,level,rx,rz in dirty:
            rows=[];present=False
            for z in range(rz*16-1,rz*16+17):
                for x in range(rx*16-1,rx*16+17):
                    key=(d,x,z);s=saved.get(key);l=live.get(key)
                    if s is None and l is None:continue
                    rows.append((x,z,s,l))
                    if rx*16<=x<rx*16+16 and rz*16<=z<rz*16+16:present=True
            key=(d,0,rx,rz)
            if present:self.versions[key]=digest((PALETTE_ID,rows))
            else:self.versions.pop(key,None)
        for level in range(1,MAX_LEVEL+1):
            dirty={(d,level,x//2,z//2) for d,_,x,z in dirty}
            for d,_,x,z in dirty:
                children=[self.versions.get((d,level-1,x*2+dx,z*2+dz)) for dz in range(2) for dx in range(2)]
                if any(children):self.versions[(d,level,x,z)]=digest((PALETTE_ID,level,children))
                else:self.versions.pop((d,level,x,z),None)
        result={}
        for (d,level,x,z),v in sorted(self.versions.items()):result.setdefault(f'{d}/{level}',[]).append([x,z,v])
        self._manifest=result
        return True

    def manifest(self):return self._manifest
    def version(self,d,level,x,z):return self.versions.get((d,level,x,z))


class TileCache:
    def __init__(self,path,limit=64*1024*1024):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.limit=limit;self.hits=0;self.used=0;self.entries=0;self.quota_reached=False
        db=self.connect()
        try:
            db.execute('PRAGMA journal_mode=WAL')
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS tiles(key TEXT PRIMARY KEY,data BLOB,etag TEXT,size INTEGER,used REAL)')
                db.execute('CREATE INDEX IF NOT EXISTS tiles_lru ON tiles(used)')
                db.execute('CREATE TABLE IF NOT EXISTS totals(id INTEGER PRIMARY KEY,bytes INTEGER,entries INTEGER)')
                # This is a generated session cache, never an existing real-data database.
                db.execute('INSERT OR IGNORE INTO totals VALUES(1,0,0)')
                self.used,self.entries=db.execute('SELECT bytes,entries FROM totals WHERE id=1').fetchone()
        finally:db.close()

    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.execute('PRAGMA synchronous=NORMAL');return db

    def get(self,key):
        db=self.connect()
        try:
            with db:
                row=db.execute('SELECT data,etag FROM tiles WHERE key=?',(key,)).fetchone()
                if row:db.execute('UPDATE tiles SET used=? WHERE key=?',(time.time(),key))
            if row:self.hits+=1;return Rendered(*row)
        finally:db.close()

    def disk_bytes(self):
        total=0
        for p in [self.path,Path(str(self.path)+'-wal'),Path(str(self.path)+'-shm')]:
            try:total+=p.stat().st_size
            except FileNotFoundError:pass
        return total

    def put(self,key,result):
        if self.disk_bytes()>self.limit:
            self.quota_reached=True;return
        size=len(result.data)
        if size>self.limit*.6:return
        db=self.connect()
        try:
            with db:
                used,count=db.execute('SELECT bytes,entries FROM totals WHERE id=1').fetchone()
                old=db.execute('SELECT size FROM tiles WHERE key=?',(key,)).fetchone()
                used+=size-(old[0] if old else 0);count+=0 if old else 1
                db.execute('INSERT OR REPLACE INTO tiles VALUES(?,?,?,?,?)',(key,result.data,result.etag,size,time.time()))
                while used>self.limit*.6:
                    rows=db.execute('SELECT key,size FROM tiles ORDER BY used LIMIT 16').fetchall()
                    if not rows:break
                    db.executemany('DELETE FROM tiles WHERE key=?',[(r[0],) for r in rows]);used-=sum(r[1] for r in rows);count-=len(rows)
                db.execute('UPDATE totals SET bytes=?,entries=? WHERE id=1',(used,count))
            self.used=used;self.entries=count
        finally:db.close()

    def stats(self):
        disk=self.disk_bytes()
        return {'entries':self.entries,'payload_bytes':self.used,'disk_bytes':disk,'limit_bytes':self.limit,'hits':self.hits,'near_limit':disk>=self.limit*.8,'quota_reached':self.quota_reached}


def _rows(path,d,rx,rz,minimum):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=10)
    try:
        return db.execute('SELECT x,z,palette,ids,heights,biome,biomes,updated FROM surfaces WHERE dim=? AND x BETWEEN ? AND ? AND z BETWEEN ? AND ? AND surface_version>=?',
            (d,rx*16-1,rx*16+16,rz*16-1,rz*16+16,minimum)).fetchall()
    finally:db.close()


def encode(image):
    out=io.BytesIO();image.save(out,format='WEBP',lossless=True,quality=75,method=2,exact=True);return out.getvalue()


def render_base(saved_path,live_path,d,rx,rz,exaggeration,intensity,expected_live=None,expected_saved=None,saved_cutoff=None,style='paper'):
    padding=16 if style=='atlas' else 1;side=256+padding*2
    pixels=np.zeros((side,side,4),dtype=np.uint8);heights=np.full((side,side),-32768,dtype=np.int16)
    ink_names=np.full((side,side),'minecraft:air',dtype=object) if style=='atlas' else None
    ink_biomes=np.full((side,side),'',dtype=object) if style=='atlas' else None
    # Captures fill gaps; known saved columns replace them. Air/unknown do not hide water.
    for path,minimum in [(live_path,2),(saved_path,0)]:
        seen=set()
        for x,z,palette,ids,h,biome,biomes,updated in _rows(path,d,rx,rz,minimum):
            coord=(d,x,z);seen.add(coord)
            if minimum==2 and expected_live is not None and SurfaceStore.content_hash(palette,ids,h,biome,biomes)!=expected_live.get(coord):
                raise TileChanged('Captura ainda não publicada no índice')
            if minimum==0:
                if expected_saved is not None and coord not in expected_saved:continue
                if saved_cutoff is not None and updated>saved_cutoff:raise TileChanged('Leitura do save ainda em publicação')
            names=np.asarray(json.loads(palette))[np.frombuffer(zlib.decompress(ids),dtype='<u2')].reshape(16,16)
            ph=np.frombuffer(zlib.decompress(h),dtype='<i2').reshape(16,16)
            unique,inverse=np.unique(names,return_inverse=True)
            rgba=np.asarray([colour(str(n),style) for n in unique],dtype=np.uint8)[inverse].reshape(16,16,4)
            green=[str(n) for n in unique if any(k in str(n) for k in ('grass','leaves','fern','vine'))]
            samples=json.loads(biomes) if biomes else None
            grid=np.repeat(np.repeat(np.asarray(samples).reshape(4,4),4,axis=0),4,axis=1) if isinstance(samples,list) and len(samples)==16 else None
            if green:
                for n in green:
                    name_mask=names==n
                    for b in np.unique(grid[name_mask]) if grid is not None else [biome]:
                        tint=biome_tint(n,b)
                        if not np.all(tint==1):
                            mask=name_mask&(grid==b) if grid is not None else name_mask
                            rgba[mask,:3]=np.clip(rgba[mask,:3]*tint,0,255).astype('uint8')
            xx=(x-rx*16)*16+padding;zz=(z-rz*16)*16+padding
            x0=max(0,xx);z0=max(0,zz);x1=min(side,xx+16);z1=min(side,zz+16)
            src=np.s_[z0-zz:z1-zz,x0-xx:x1-xx];dst=np.s_[z0:z1,x0:x1]
            valid=(rgba[src][:,:,3]!=0)&(ph[src]!=-32768)
            pixels[dst][valid]=rgba[src][valid];heights[dst][valid]=ph[src][valid]
            if ink_names is not None:
                ink_names[dst][valid]=names[src][valid]
                ink_biomes[dst][valid]=grid[src][valid] if grid is not None else (biome or '')
        if minimum==2 and expected_live is not None:
            expected={c for c in expected_live if c[0]==d and rx*16-1<=c[1]<=rx*16+16 and rz*16-1<=c[2]<=rz*16+16}
            if not expected.issubset(seen):raise TileChanged('Captura removida; aguardando índice')
    if style=='atlas':return encode(draw_atlas(ink_names,heights,rx,rz,ink_biomes))
    core=pixels[1:-1,1:-1].copy();core[:,:,:3]=np.clip(core[:,:,:3]*hillshade(heights,exaggeration,intensity)[:,:,None],0,255).astype('uint8')
    return encode(Image.fromarray(core))


def render_parent(children):
    image=Image.new('RGBA',(256,256))
    for dx,dz,data in children:
        with Image.open(io.BytesIO(data)) as child:
            image.paste(child.convert('RGBA').resize((128,128),Image.Resampling.BOX),(dx*128,dz*128))
    return encode(image)


class TilePipeline:
    def __init__(self,index,queue,saved_path,live_path,cache_path,world_id,refresh=lambda:None,saved_cutoff=lambda:None):
        if not features.check('webp'):raise RuntimeError('Pillow sem suporte WebP')
        self.index=index;self.queue=queue;self.saved_path=str(saved_path);self.live_path=str(live_path)
        self.world_id=world_id;self.cache=TileCache(cache_path);self.refresh=refresh;self.saved_cutoff=saved_cutoff
        self.closed=False;self.jobs={};self.io=set();self.io_lock=asyncio.Lock()

    async def _io(self,function,*args):
        async def run():
            async with self.io_lock:return await asyncio.to_thread(function,*args)
        task=asyncio.create_task(run());self.io.add(task)
        def done(t):
            self.io.discard(t)
            if not t.cancelled():t.exception()
        task.add_done_callback(done)
        return await asyncio.shield(task)

    async def request(self,d,level,x,z,exaggeration=1.5,intensity=.8,style='paper'):
        if style not in ('paper','minecraft','atlas'):raise ValueError('Paleta inválida')
        if self.closed:raise RenderClosed('Pipeline encerrado')
        version=self.index.version(d,level,x,z)
        if version is None:raise LookupError('Tile sem dados')
        spec=(d,level,x,z,exaggeration,intensity,style)
        key=digest((self.world_id,PALETTE_ID,CARTOGRAPHY_VERSION,spec,version))
        cached=await self._io(self.cache.get,key)
        if cached is not None:
            if self.closed:raise RenderClosed('Pipeline encerrado')
            self.refresh()
            if self.index.version(d,level,x,z)!=version:raise TileChanged()
            return cached
        if self.closed:raise RenderClosed('Pipeline encerrado')
        return await self._join(key,lambda:self._build(key,spec,version))

    async def _join(self,key,build):
        job=self.jobs.get(key)
        if job is None:
            if len(self.jobs)>=128:raise RenderClosed('Muitos pedidos; tente novamente')
            job={'task':asyncio.create_task(build()),'waiters':0};self.jobs[key]=job
        job['waiters']+=1
        try:return await asyncio.shield(job['task'])
        finally:
            job['waiters']-=1
            if not job['waiters']:
                self.jobs.pop(key,None)
                if not job['task'].done():job['task'].cancel()
                job['task'].add_done_callback(lambda t:None if t.cancelled() else t.exception())

    async def request_sized(self,d,level,x,z,pixels=256,exaggeration=1.5,intensity=.8,style='paper'):
        native=source_key(d,level,x,z,pixels)
        if pixels==256:return await self.request(d,level,x,z,exaggeration,intensity,style)
        if self.closed:raise RenderClosed('Pipeline encerrado')
        if style not in ('paper','minecraft','atlas'):raise ValueError('Paleta inválida')
        version=self.index.version(*native)
        if version is None:raise LookupError('Tile sem dados')
        key=digest(('sized-v1',self.world_id,PALETTE_ID,CARTOGRAPHY_VERSION,d,level,x,z,pixels,exaggeration,intensity,style,version))
        def current():
            self.refresh()
            return not self.closed and self.index.version(*native)==version
        cached=await self._io(self.cache.get,key)
        if cached is not None:
            if not current():raise TileChanged()
            return cached
        if self.closed:raise RenderClosed('Pipeline encerrado')
        async def build():
            children=[];crop=None
            if pixels<256:
                factor=256//pixels
                child=await self.request(*native,exaggeration,intensity,style)
                left=(x%factor)*pixels;top=(z%factor)*pixels
                crop=(left,top,left+pixels,top+pixels);children.append((0,0,child.data))
            else:
                factor=pixels//256
                for dz in range(factor):
                    for dx in range(factor):
                        cx=x*factor+dx;cz=z*factor+dz
                        if self.index.version(d,level,cx,cz) is None:continue
                        child=await self.request(d,level,cx,cz,exaggeration,intensity,style)
                        children.append((dx,dz,child.data))
            if not current():raise TileChanged()
            result=await self.queue.request(('sized',key),lambda:render_sized(children,pixels,crop),valid=current)
            if not current():raise TileChanged()
            await self._io(self.cache.put,key,result)
            return result
        return await self._join(key,build)

    async def _build(self,key,spec,version):
        d,level,x,z,exaggeration,intensity,style=spec
        def current():
            self.refresh()
            return not self.closed and self.index.version(d,level,x,z)==version
        if level==0:
            expected_live=self.index.live;expected_saved=self.index.saved;cutoff=self.saved_cutoff()
            render=lambda:render_base(self.saved_path,self.live_path,d,x,z,exaggeration,intensity,expected_live,expected_saved,cutoff,style)
        else:
            children=[]
            # Sequential dependency traversal bounds active renders and intermediate bytes.
            for dz in range(2):
                for dx in range(2):
                    if self.index.version(d,level-1,x*2+dx,z*2+dz) is not None:
                        child=await self.request(d,level-1,x*2+dx,z*2+dz,exaggeration,intensity,style)
                        children.append((dx,dz,child.data))
            render=lambda:render_parent(children)
        if not current():raise TileChanged()
        result=await self.queue.request(('webp',key),render,valid=current)
        if not current():raise TileChanged()
        await self._io(self.cache.put,key,result)
        return result

    async def aclose(self):
        self.closed=True
        tasks=[j['task'] for j in list(self.jobs.values())]
        for task in tasks:task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        await self.queue.aclose()
        if self.io:await asyncio.gather(*list(self.io),return_exceptions=True)

    def stats(self):return self.cache.stats()
