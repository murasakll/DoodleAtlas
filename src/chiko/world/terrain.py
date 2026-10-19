"""Bedrock reader. Amulet and LevelDB only ever receive a disposable snapshot."""
import hashlib
import json
import logging
import shutil
import struct
import time
from functools import lru_cache
from pathlib import Path

import amulet
import numpy as np
from PIL import Image
from chiko.world.coverage import chunk_record, audit_records
from chiko.storage.snapshot_db import SnapshotInconsistent, snapshot  # noqa: F401 (snapshot is re-exported)
from chiko.storage.surface_store import SurfaceStore
from chiko.cartography.relief import hillshade,biome_tint
from chiko.storage.observed_points import ObservedPoints,extract_points,DETECTOR_VERSION

LOG = logging.getLogger(__name__)
DIMENSIONS = {"minecraft:overworld": 0, "minecraft:the_nether": 1, "minecraft:the_end": 2}

from chiko.paths import ASSETS
PALETTE_PATH = ASSETS / 'paleta.json'
PALETTE = json.loads(PALETTE_PATH.read_text(encoding='utf-8'))
PALETTE_ID = hashlib.sha256(PALETTE_PATH.read_bytes()).hexdigest()[:16]


def palette_colour(value):
    if not isinstance(value,str) or len(value)!=7 or not value.startswith('#'):
        raise ValueError('Cor inválida em paleta.json: use #RRGGBB')
    return tuple(bytes.fromhex(value[1:])) + (255,)


for _value in [PALETTE['fallback'], *PALETTE['identity'].values(), *PALETTE['blocks'].values(), *[r['color'] for r in PALETTE['rules']]]:
    palette_colour(_value)
for _value in [PALETTE['minecraft']['fallback'],*PALETTE['minecraft']['blocks'].values(),*[r['color'] for r in PALETTE['minecraft']['rules']]]:
    palette_colour(_value)


@lru_cache(maxsize=4096)
def colour(name,style='paper'):
    base = name.split(":")[-1]
    if base in ("air", "cave_air", "void_air"):
        return (0, 0, 0, 0)
    if style=='minecraft':
        table=PALETTE['minecraft']
        if name in table['blocks']:return palette_colour(table['blocks'][name])
        for rule in table['rules']:
            if any(k in base for k in rule['contains']):return palette_colour(rule['color'])
        return palette_colour(table['fallback'])
    if name in PALETTE['blocks']:
        return palette_colour(PALETTE['blocks'][name])
    for rule in PALETTE['rules']:
        if any(k in base for k in rule['contains']):
            return palette_colour(rule['color'])
    return palette_colour(PALETTE['fallback'])


def chunk_image(chunk):
    result = np.zeros((16, 16, 4), dtype=np.uint8)
    found = np.zeros((16, 16), dtype=bool)
    # Arrays are x,y,z; image is z,x. Skip air, including caves above terrain.
    palette = np.array([colour(b.namespaced_name) for b in chunk.block_palette], dtype=np.uint8)
    for sy in sorted(chunk.blocks.sub_chunks, reverse=True):
        blocks = chunk.blocks.get_sub_chunk(sy)
        rgba = palette[blocks]
        opaque = rgba[:, :, :, 3] != 0
        present = opaque.any(axis=1) & ~found
        top = 15 - opaque[:, ::-1, :].argmax(axis=1)
        xs, zs = np.where(present)
        result[zs, xs] = rgba[xs, top[xs, zs], zs]
        found |= present
        if found.all():
            break
    return Image.fromarray(result)


def native_chunk(wrapper, cx, cz, dimension):
    """Pinned Amulet 1.9.50 adapter: use its decoder and unpacker without universal translation."""
    raw = wrapper.get_raw_chunk_data(cx, cz, dimension)
    interface, translator, version = wrapper._get_interface_and_translator(raw)
    chunk, palette = wrapper._decode(interface, dimension, cx, cz, raw)
    return wrapper._unpack(translator, version, chunk, palette)


def surface_data(chunk,max_height=None):
    names=np.full((16,16),'minecraft:air',dtype=object)
    heights=np.full((16,16),-32768,dtype=np.int16)
    found=np.zeros((16,16),dtype=bool)
    palette=np.asarray([b.namespaced_name for b in chunk.block_palette],dtype=object)
    visible=np.asarray([colour(str(n))[3]!=0 for n in palette])
    for sy in sorted(chunk.blocks.sub_chunks,reverse=True):
        blocks=chunk.blocks.get_sub_chunk(sy)
        solid=visible[blocks]
        if max_height is not None:
            solid=solid & (np.arange(sy*16,sy*16+16)[None,:,None]<=max_height)
        present=solid.any(axis=1)&~found
        top=15-solid[:,::-1,:].argmax(axis=1)
        xs,zs=np.where(present)
        names[zs,xs]=palette[blocks[xs,top[xs,zs],zs]]
        heights[zs,xs]=sy*16+top[xs,zs]
        found|=present
        if found.all():break
    return names,heights


def shade_surface(heights,margin=None,exaggeration=1.5,intensity=.8):
    return hillshade(np.pad(heights,1,mode='edge') if margin is None else margin,exaggeration,intensity)


def relief_image(names,heights,margin=None,exaggeration=1.5,intensity=.8,depth=None,biome=None):
    image=np.asarray([[colour(str(name)) for name in row] for row in names],dtype=np.uint8)
    light=shade_surface(heights,margin,exaggeration,intensity)
    for z in range(16):
        for x in range(16):
            cell_biome=biome[(z//4)*4+x//4] if isinstance(biome,list) and len(biome)==16 else biome
            tint=biome_tint(str(names[z,x]),cell_biome)
            image[z,x,:3]=np.clip(image[z,x,:3].astype(float)*light[z,x]*tint,0,255).astype('uint8')
    return Image.fromarray(image)


def saved_biome(chunk):
    try:
        chunk.biomes.convert_to_2d()
        return str(chunk.biome_palette[int(chunk.biomes[8,8])])
    except (IndexError,KeyError,TypeError,ValueError,AttributeError):
        return None

def water_depth(chunk,names,heights):
    result=np.zeros((16,16),dtype=np.uint8)
    for z,x in np.argwhere(np.char.find(np.asarray(names,dtype=str),'water')>=0):
        top=int(heights[z,x]);bottom=top
        for y in range(top-1,max(top-64,-65),-1):
            try:name=chunk.block_palette[int(chunk.blocks[x,y,z])].namespaced_name
            except (IndexError,KeyError):break
            if 'water' not in name and name not in ('minecraft:air','minecraft:seagrass','minecraft:kelp'):break
            bottom=y
        result[z,x]=top-bottom+1
    return result


class Terrain:
    def __init__(self, root, world, store_path=None, store_limit=None):
        self.root, self.world = Path(root), Path(world)
        self.folder = self.root / "data" / "tiles"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.persistent_path=Path(store_path).parent if store_path else None
        self.store=SurfaceStore(store_path or self.root/'data'/'surfaces.sqlite',max_bytes=store_limit,preserve=bool(store_path))
        self.observed_points=ObservedPoints(self.store.path.parent/'pontos_observados.sqlite')
        self.hashes = {}
        self.region_images = {}
        self.region_versions = {}
        self.dirty_regions = set()
        self.manifest = {"revision": 0, "chunks": {}, "spawn": None, "error": None}
        cache = self.persistent_path/'leitor.json' if self.persistent_path else self.root/'data'/'cache.json'
        if cache.exists():
            try:
                content = json.loads(cache.read_text(encoding='utf-8'))
                if content.get('world') == str(self.world.resolve()) and content.get('renderer') == 2 and (content.get('palette') == PALETTE_ID or store_path):
                    self.hashes = content['hashes']
                    self.manifest = content['manifest']
                    self.region_versions = content.get('region_versions', {})
            except (ValueError, KeyError):
                LOG.warning('Cache inválido; será reconstruído')
        if store_path:
            known=self.store.entries();chunks={}
            for (d,x,z),version in known.items():chunks.setdefault(str(d),[]).append([x,z,self.hashes.get(f'{d}/{x}/{z}',version)])
            self.manifest={**self.manifest,'chunks':chunks,'regions':{},'updated':time.time()}
            self.manifest.pop('progress',None)
            # PNGs remain temporary, so the old atlas is never assumed present.
            self.region_versions={}
        self.manifest['observed_points']=self.observed_points.snapshot()

    def cache(self):
        target = self.root / 'data' / 'cache.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps({'world':str(self.world.resolve()), 'renderer':2,
                                         'hashes':self.hashes, 'manifest':self.manifest,
                                         'region_versions':self.region_versions,'palette':PALETTE_ID}), encoding='utf-8')
        temporary.replace(target)
        if self.persistent_path:
            from chiko.storage.world_storage import atomic_json
            atomic_json(self.persistent_path/'leitor.json',{'world':str(self.world.resolve()),'renderer':2,
                'hashes':self.hashes,'manifest':self.manifest,'region_versions':{},'palette':PALETTE_ID})

    def region_tile(self, dim, cx, cz, image):
        rx, rz = cx // 16, cz // 16
        key = f'{dim}/{rx}/{rz}'
        if key not in self.region_images:
            target = self.root / 'data' / 'regions' / str(dim) / f'{rx}_{rz}.png'
            if target.exists() and key in self.region_versions:
                with Image.open(target) as previous:
                    self.region_images[key] = previous.convert('RGBA')
            else:
                self.region_images[key] = Image.new('RGBA', (256,256))
                # A resumed checkpoint may already contain other chunks in this
                # atlas. Populate all of them before marking the atlas available.
                for local_x in range(16):
                    for local_z in range(16):
                        other_x, other_z = rx*16+local_x, rz*16+local_z
                        token = f'{dim}/{other_x}/{other_z}'
                        cached = self.folder/str(dim)/f'{other_x}_{other_z}.png'
                        if token in self.hashes and cached.is_file():
                            with Image.open(cached) as previous:
                                self.region_images[key].paste(previous.convert('RGBA'),(local_x*16,local_z*16))
        self.region_images[key].paste(image, ((cx % 16)*16, (cz % 16)*16))
        self.dirty_regions.add(key)
        # A boundary height also changes lighting in the adjacent atlas halo.
        for dx,dz in ((-1,0),(1,0),(0,-1),(0,1)):
            nx,nz=cx+dx,cz+dz
            neighbor=f'{dim}/{nx//16}/{nz//16}'
            if neighbor!=key and neighbor in self.region_versions:
                self.dirty_regions.add(neighbor)

    def flush_regions(self):
        for key in self.dirty_regions:
            dim, rx, rz = key.split('/')
            names,h,depth=self.store.region_arrays(int(dim),int(rx),int(rz))
            core=names[1:-1,1:-1]
            palette,ids=np.unique(np.asarray(core,dtype=str),return_inverse=True)
            pixels=np.asarray([colour(str(n)) for n in palette],dtype=np.uint8)[ids].reshape(256,256,4)
            light=hillshade(h)
            pixels[:,:,:3]=np.clip(pixels[:,:,:3]*light[:,:,None],0,255).astype('uint8')
            self.region_images[key]=Image.fromarray(pixels)
            target = self.root / 'data' / 'regions' / dim / f'{rx}_{rz}.png'
            target.parent.mkdir(exist_ok=True, parents=True)
            temporary = target.with_suffix('.tmp')
            self.region_images[key].save(temporary, format='PNG')
            temporary.replace(target)
            self.region_versions[key] = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
        self.dirty_regions.clear()
        # Bound decoded atlas memory; published PNGs can be reopened as needed.
        self.region_images.clear()
        regions = {}
        valid = set()
        for dim, chunks in self.manifest['chunks'].items():
            for cx, cz, *_ in chunks:
                valid.add(f'{dim}/{cx//16}/{cz//16}')
        for key in valid:
            if key in self.region_versions:
                dim, rx, rz = key.split('/')
                regions.setdefault(dim, []).append([int(rx),int(rz),self.region_versions[key]])
        self.manifest['regions'] = regions

    def publish(self):
        self.manifest['world_id'] = hashlib.sha256(str(self.world.resolve()).encode()).hexdigest()
        target = self.root / 'data' / 'terrain-state.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.manifest), encoding='utf-8')
        for attempt in range(10):
            try:
                temporary.replace(target)
                return
            except PermissionError:
                time.sleep(.05)
        raise RuntimeError('Não foi possível publicar manifesto')

    def refresh(self):
        from leveldb import LevelDB
        snap = self.root / "data" / "snapshots" / str(time.time_ns())
        level = None
        previous_full = bool(self.manifest['chunks']) and 'progress' not in self.manifest
        try:
            snapshot(self.world, snap)
            # Fingerprint raw chunk records before translation, so unchanged chunks aren't decoded.
            db = LevelDB(str(snap / "db"))
            groups = {}
            records = {}
            try:
                for key, value in db.iterate():
                    record = chunk_record(key)
                    if record is None:
                        continue
                    dim,cx,cz,tag=record
                    records.setdefault((dim,cx,cz),set()).add(tag)
                    groups.setdefault((dim, cx, cz), hashlib.sha256()).update(key + value)
            finally:
                db.close()
            level = amulet.load_level(str(snap))
            new_hashes, chunks, changed = {}, {}, 0
            failures = []
            spawn = None
            seed=None
            try:
                tag = level.level_wrapper.root_tag.compound
                spawn = {axis: int(tag['Spawn' + axis.upper()].py_int) for axis in ('x', 'y', 'z')}
                seed=str(tag['RandomSeed'].py_int) if 'RandomSeed' in tag else None
            except Exception:
                LOG.exception('Não foi possível ler spawn')
            total = sum(1 for d in level.dimensions for _ in level.all_chunk_coords(d))
            processed = 0
            indexed={(DIMENSIONS[d],cx,cz) for d in level.dimensions if d in DIMENSIONS
                     for cx,cz in level.all_chunk_coords(d)}
            coverage = audit_records(records,indexed)
            if coverage['omitted_block_record_chunks']:
                raise RuntimeError(f"Índice do Amulet omitiu {coverage['omitted_block_record_chunks']} chunks com blocos: {coverage['omitted_examples']}")
            empty_surfaces=set(self.manifest.get('empty_surface_chunks',[]))
            point_signatures=self.observed_points.signatures()
            points_processed=0
            self.manifest = {**self.manifest, 'progress': {'done':0, 'total':total}}
            for dimension in level.dimensions:
                dim = DIMENSIONS.get(dimension)
                if dim is None:
                    continue
                entries = []
                coords = list(level.all_chunk_coords(dimension))
                sx, sz = ((spawn['x'] // 16, spawn['z'] // 16) if spawn and dim == 0 else (0, 0))
                coords.sort(key=lambda p: (p[0]-sx)**2 + (p[1]-sz)**2)
                for cx, cz in coords:
                    token = f"{dim}/{cx}/{cz}"
                    raw = groups.get((dim, cx, cz))
                    signature = raw.hexdigest()[:16] if raw else ""
                    target = self.folder / str(dim) / f"{cx}_{cz}.png"
                    region_key = f'{dim}/{cx//16}/{cz//16}'
                    points_needed=point_signatures.get((dim,cx,cz))!=DETECTOR_VERSION+':'+signature
                    needs_surface=not signature or signature != self.hashes.get(token) or (not target.exists() and self.store.get(dim,cx,cz) is None)
                    if points_needed and not needs_surface:
                        try:
                            decoded=native_chunk(level.level_wrapper,cx,cz,dimension)
                            self.observed_points.put(dim,cx,cz,signature,extract_points(decoded,dim,cx,cz))
                            points_processed+=1
                            if points_processed%64==0:level.unload_unchanged()
                        except Exception as exc:
                            LOG.warning('Pontos do chunk %s: %s',token,exc);failures.append(token)
                    if needs_surface:
                        try:
                            decoded=native_chunk(level.level_wrapper,cx,cz,dimension)
                            if points_needed:
                                try:self.observed_points.put(dim,cx,cz,signature,extract_points(decoded,dim,cx,cz))
                                except Exception as exc:
                                    LOG.warning('Pontos do chunk %s: %s',token,exc);failures.append(token)
                            names,heights=surface_data(decoded,120 if dim==1 else None)
                            self.store.put(dim,cx,cz,names,heights,saved_biome(decoded))
                            image = relief_image(names,heights)
                            if image.getchannel('A').getbbox() is None:
                                empty_surfaces.add(token)
                            else:
                                empty_surfaces.discard(token)
                            target.parent.mkdir(exist_ok=True, parents=True)
                            temporary = target.with_suffix('.tmp')
                            image.save(temporary, format="PNG")
                            temporary.replace(target)
                            self.region_tile(dim, cx, cz, image)
                            changed += 1
                            if changed % 64 == 0:
                                level.unload_unchanged()
                        except Exception as exc:
                            LOG.warning("Chunk %s: %s", token, exc)
                            failures.append(token)
                            if not target.exists() and self.store.get(dim,cx,cz) is None:
                                continue
                            signature = self.hashes.get(token, "")
                    elif not target.exists():
                        surface=self.store.get(dim,cx,cz)
                        if surface is None:continue
                        image=relief_image(surface[0],surface[1])
                        target.parent.mkdir(exist_ok=True,parents=True);image.save(target,format='PNG');self.region_tile(dim,cx,cz,image)
                    elif region_key not in self.region_versions:
                        with Image.open(target) as cached_image:
                            self.region_tile(dim, cx, cz, cached_image.convert('RGBA'))
                    new_hashes[token] = signature
                    self.hashes[token] = signature
                    entries.append([cx, cz, signature[:16]])
                    processed += 1
                    if processed % 256 == 0 and not previous_full:
                        partial = dict(self.manifest['chunks'])
                        partial.update(chunks)
                        partial[str(dim)] = list(entries)
                        self.manifest = {'revision': self.manifest['revision'] + 1, 'chunks':partial,
                                         'spawn':spawn, 'updated':time.time(), 'changed':changed,
                                         'failed_chunks':list(failures), 'error':None,
                                         'progress':{'done':processed, 'total':total}}
                        self.manifest['observed_points']=self.observed_points.snapshot()
                        LOG.info('Terreno: %s/%s chunks processados', processed, total)
                        self.flush_regions()
                        self.cache()
                        self.publish()
                chunks[str(dim)] = entries
            for removed in self.hashes.keys() - new_hashes.keys():
                dim, cx, cz = map(int, removed.split('/'))
                self.region_tile(dim, cx, cz, Image.new('RGBA', (16,16)))
            self.hashes = new_hashes
            self.observed_points.prune(indexed)
            self.manifest = {"revision": self.manifest['revision'] + 1, "chunks": chunks,
                             "spawn": spawn, "updated": time.time(), "changed": changed,
                             "failed_chunks": failures, "error": None}
            self.manifest['observed_points']=self.observed_points.snapshot()
            self.manifest['coverage']=coverage
            self.manifest['snapshot']=json.loads((snap/'.snapshot.json').read_text())
            LOG.info('Snapshot concluído em %s tentativa(s)',self.manifest['snapshot']['attempts'])
            self.manifest['snapshot_time']=time.time()
            self.manifest['seed']=seed
            self.manifest['empty_surface_chunks']=sorted(empty_surfaces & new_hashes.keys())
            (self.root / 'data' / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
            self.flush_regions()
            self.cache()
            LOG.info("Terreno: %s chunks indexados, %s renderizados, %s erros de parser; cobertura: %s",
                     sum(map(len,chunks.values())),changed,len(failures),coverage)
            self.publish()
        except SnapshotInconsistent as exc:
            self.manifest['error'] = 'Terreno desatualizado: o jogo estava gravando no disco; nova tentativa no próximo ciclo'
            LOG.warning("Snapshot adiado (%s); preservando último mapa", exc)
            self.publish()
        except Exception as exc:
            self.manifest['error'] = str(exc)
            LOG.exception("Snapshot rejeitado; preservando último mapa")
            self.publish()
        finally:
            if level:
                level.close()
            if snap.exists():
                shutil.rmtree(snap)
        return self.manifest


def run_terrain(root, world, interval, store_path=None, store_limit=None):
    # A forced console close must not leave the decoder holding the session DB.
    import multiprocessing
    import threading
    import os
    parent = multiprocessing.parent_process()
    def monitor_parent():
        while parent is not None:
            if not parent.is_alive():
                os._exit(0)
            time.sleep(1)
    threading.Thread(target=monitor_parent, daemon=True).start()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', force=True,
                        handlers=[logging.StreamHandler()])
    terrain = Terrain(root, world,store_path,store_limit)
    while True:
        started=time.monotonic()
        terrain.refresh()
        while True:
            current=interval
            try:current=float(json.loads((Path(root)/'settings.json').read_text()).get('terrain_seconds',interval))
            except (OSError,ValueError,TypeError):pass
            if time.monotonic()-started>=max(2,current):break
            time.sleep(.25)
