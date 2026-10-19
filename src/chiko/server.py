import asyncio
import hashlib
import hmac
import io
import ipaddress
import json
import logging
import multiprocessing
import os
import secrets
import time
import threading
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

from aiohttp import web, WSMsgType
import qrcode
from chiko.world.terrain import Terrain, run_terrain
from chiko.network.encryption import GameEncryption
from chiko.network.content_log import ContentLog
from chiko.storage.session_cache import SessionCache
from chiko.world.discovery import discover
from chiko.storage.surface_store import SurfaceStore,SurfaceQuotaExceeded
from chiko.world.terrain import relief_image
from chiko.cartography.render_queue import RenderQueue, RenderBusy, RenderClosed, background_call
from chiko.cartography.tile_pipeline import TileIndex,TilePipeline,TileChanged,MAX_LEVEL,TILE_SIZES,source_key
from chiko.cartography.seed_layer import metadata as seed_metadata,render_prediction
from chiko.storage.world_storage import WorldStorage
from chiko.storage.waypoints import WaypointStore,WaypointLimit
from chiko.storage.annotations import AnnotationStore,AnnotationConflict
from chiko.storage.history import MapHistory,render_overview,render_change
import numpy as np

from chiko.paths import ROOT, WEB, ASSETS
LOG = logging.getLogger('livemap')

def tile_delta(old,new):
    result={}
    for dim in old.keys()|new.keys():
        a={(x,z):h for x,z,h in old.get(dim,[])};b={(x,z):h for x,z,h in new.get(dim,[])}
        updates=[[x,z,h] for (x,z),h in b.items() if a.get((x,z))!=h]
        removed=[[x,z] for x,z in a.keys()-b.keys()]
        if updates or removed:result[dim]={'upsert':updates,'remove':removed}
    return result


def parse_targets(body, host_name=''):
    details = body.get('details', [])
    if isinstance(details, str):
        details = json.loads(details)
    if not isinstance(details, list):
        raise ValueError('querytarget.details deve ser uma lista')
    result = []
    for entry in details:
        pos = entry.get('position', {})
        if not all(k in pos for k in ('x', 'y', 'z')):
            continue
        uid = str(entry.get('uniqueId', entry.get('id', '')))
        name = entry.get('name', entry.get('nameTag', ''))
        dimension = entry.get('dimension', 0)
        dimension = {'overworld': 0, 'nether': 1, 'the_nether': 1, 'the_end': 2,
                     'minecraft:overworld': 0, 'minecraft:nether': 1,
                     'minecraft:the_nether': 1, 'minecraft:the_end': 2}.get(str(dimension), dimension)
        result.append({'id': uid, 'name': name or ('Jogador ' + uid[-6:]),
                       'dimension': int(dimension), **{k: float(pos[k]) for k in ('x', 'y', 'z')},
                       'host': bool(host_name and name == host_name),
                       'yaw':float(entry.get('yaw',0)),
                       'color': '#' + hashlib.sha256(uid.encode()).hexdigest()[:6]})
    return result


class LiveMap:
    def __init__(self, config):
        from chiko.settings import normalize
        config=normalize(config,ROOT,require_world=False)
        self.config = config
        self.open_world_storage()
        self.cache=SessionCache(ROOT/'data'/'sessions')
        self.terrain = self.make_terrain()
        self.worker=None
        self.stop_event=asyncio.Event()
        self.switch_lock=asyncio.Lock()
        self.host_token=secrets.token_urlsafe(32)
        self.entities=[]
        self.entity_update=0
        self.entity_frame=None
        self.entity_parts={}
        self.capabilities={}
        self.biome_results=[]
        self.live_surfaces={}
        self.render_queue=RenderQueue()
        self.saved_version_revision=None
        self.saved_versions={}
        self.open_capture_store()
        self.open_map_tiles()
        self.players = []
        self.connected = False
        self.last_update = 0
        self.error = None
        self.listeners = set()
        self.sessions = {}
        self.attempts = {}
        self.game_ws = None
        self.pending = {}
        self.host_name = config.get('host_name', '')
        self.names = {}
        self.content_log = ContentLog(config['content_log']) if config.get('content_log') and config['content_log']!='auto' else None
        self.player_source = 'websocket'

    def state(self):
        self.sync_tile_index()
        return {'players': self.players if time.time() - self.last_update < max(5, self.config['player_seconds'] * 4) else [],
                'minecraft_connected': self.connected, 'last_player_update': self.last_update,
                'player_error': self.error, 'terrain': self.terrain.manifest,
                'player_source':self.player_source,
                'entities':self.entities if time.time()-self.entity_update<5 else [],
                'capabilities':self.capabilities,'live_chunks':self.live_chunks(),
                'biome_results':self.biome_results,'world_id':self.world_id(),
                'session_id':self.cache.path.name,'texture_packs':0,
                'render_queue':self.render_queue.stats(),
                'tile_index':self.tile_index.manifest(),'tile_cache':self.web_tiles.stats(),'seed_layer':self.seed_info,
                'world_storage':self.storage.stats() if self.storage else {'persistent':False},
                'shared_waypoints':{**self.shared_store.snapshot,'pin_writes':bool(self.config.get('pin'))} if self.shared_store else {'available':False,'points':[]},
                'annotations':{'available':True,'revision':self.annotations.revision} if self.annotations else {'available':False},
                'history':self.history_summary(),
                'tile_options':{'sizes':list(TILE_SIZES),'max_level':MAX_LEVEL},
                'settings':{'terrain_seconds':self.config['terrain_seconds'],'capture_persistent':self.config.get('capture_persistent',False),'capture_limit_mb':self.config.get('capture_limit_mb',64)},
                'url': self.config['lan_url'], 'connect_command': '/connect '+self.config.get('connect_url','ws://localhost:'+str(self.config['minecraft_port'])),
                'pack_command':'/livemap:vincular '+self.world_id(),
                'world_name': (Path(self.config['world']) / 'levelname.txt').read_text(encoding='utf-8')}

    def world_id(self):
        return hashlib.sha256(str(Path(self.config['world']).resolve()).encode()).hexdigest()

    def open_world_storage(self):
        previous=getattr(self,'history_job',None)
        if previous:previous['cancel'].set()
        self.storage=WorldStorage(ROOT,self.config['world'],self.config.get('world_limit_mb',512)) if self.config.get('capture_persistent',False) and self.config.get('world_storage',True) else None
        self.shared_store=WaypointStore(self.storage.folder/'chiko.storage.waypoints.sqlite') if self.storage else None
        self.annotations=AnnotationStore(self.storage.folder/'anotacoes.sqlite') if self.storage else None
        self.history=MapHistory(self.storage.folder/'historico.sqlite') if self.storage else None
        self.history_error='';self.history_next_attempt=0

    def history_summary(self):
        if not self.history:return {'available':False}
        info=self.history.status();frames=info['frames'];job=getattr(self,'history_job',None)
        return {k:v for k,v in info.items() if k not in ('frames','recent')} | {'frame_count':len(frames),'latest':frames[0]['id'] if frames else None,
            'running':bool(job and job['world']==self.world_id() and not job['task'].done()),'error':self.history_error}

    def start_history_frame(self,dimension=0):
        if not self.history:raise ValueError('Ative o armazenamento por mundo.')
        job=getattr(self,'history_job',None)
        if job and not job['task'].done():raise ValueError('Já existe um quadro em preparação. Aguarde.')
        if self.storage.stats().get('quota_reached'):raise ValueError('A cota deste mundo foi atingida.')
        history=self.history;world=self.world_id();saved=self.terrain.store.path;live=self.live_store.path
        region=history.settings().get('primary_region')
        if not region:raise ValueError('Escolha uma região principal no histórico antes de registrar um quadro.')
        if region['dimension']!=dimension:raise ValueError('Escolha a dimensão da região principal.')
        cancel=threading.Event();self.history_error=''
        async def capture():
            try:
                result,_=await asyncio.to_thread(background_call,lambda:render_overview(saved,live,dimension,cancel,region=region))
                if cancel.is_set() or self.history is not history:return
                data,metadata=result
                await asyncio.to_thread(history.add_frame,dimension,data,metadata)
                if self.history is history:self.storage.last_stats=0
            except Exception as error:
                if not cancel.is_set() and self.history is history:self.history_error=str(error);LOG.warning('Quadro do histórico: %s',error)
        self.history_job={'world':world,'cancel':cancel,'task':asyncio.create_task(capture())}
        self.history_next_attempt=time.time()+history.settings()['interval_minutes']*60

    def history_tick(self):
        if not self.history:return
        info=self.history.status();options=info['settings'];now=time.time()
        region=options.get('primary_region')
        if not options['frames_enabled'] or not region:return
        last=max([f['at'] for f in info['frames'] if f['dimension']==region['dimension'] and all(f.get(k)==region[k] for k in ('min_x','min_z','max_x','max_z'))],default=options['started'])
        if now>=max(self.history_next_attempt,last+options['interval_minutes']*60):
            self.history_next_attempt=now+options['interval_minutes']*60
            try:self.start_history_frame(region['dimension'])
            except ValueError:pass

    def make_terrain(self):
        return Terrain(self.cache.path,self.config['world'],str(self.storage.saved_path) if self.storage else None,int(self.storage.limit_bytes*.75) if self.storage else None)

    def open_capture_store(self):
        persistent=self.config.get('capture_persistent',False)
        path=self.storage.capture_path if self.storage else ROOT/'data'/'captures'/self.world_id()/'surfaces.sqlite' if persistent else self.cache.path/'data'/'live.sqlite'
        limit=int(self.storage.limit_bytes*.25) if self.storage else int(self.config.get('capture_limit_mb',64))*1024*1024 if persistent else None
        self.live_store=SurfaceStore(path,limit,min_surface_version=2,preserve=bool(self.storage))
        self.live_surfaces=self.live_store.entries()
        self.capture_writes=0

    def open_map_tiles(self):
        self.seed_info=seed_metadata(self.config['world'])
        self.tile_index=TileIndex();self.tile_marker=None
        self.web_tiles=TilePipeline(self.tile_index,self.render_queue,self.terrain.store.path,self.live_store.path,
            self.cache.path/'data'/'map-tiles'/(self.world_id()+'.sqlite'),self.world_id(),refresh=self.sync_tile_index,
            saved_cutoff=lambda:self.terrain.manifest.get('updated',0))

    def sync_tile_index(self):
        marker=(self.terrain.manifest['revision'],self.capture_writes)
        if marker!=self.tile_marker:
            self.tile_index.sync(self.terrain.manifest.get('chunks',{}),self.live_surfaces.copy())
            self.tile_marker=marker

    def surface(self,dim,x,z):
        # The complete save surface is authoritative. Live data only fills gaps.
        for store in (self.terrain.store,self.live_store):
            surface=store.get(dim,x,z)
            if surface:return surface,store
        return None,None

    def surface_margin(self,dim,x,z,heights):
        margin=np.pad(heights,1,mode='edge').astype(float)
        for dx,dz in [(-1,0),(1,0),(0,-1),(0,1)]:
            neighbor,_=self.surface(dim,x+dx,z+dz)
            if not neighbor:continue
            h=neighbor[1]
            if dx==-1:margin[1:-1,0]=h[:,-1]
            if dx==1:margin[1:-1,-1]=h[:,0]
            if dz==-1:margin[0,1:-1]=h[-1,:]
            if dz==1:margin[-1,1:-1]=h[0,:]
        return margin

    def render_key(self,dim,x,z,exaggeration=1.5,intensity=.8):
        revision=(self.cache.path.name,self.terrain.manifest['revision'])
        if revision!=self.saved_version_revision:
            self.saved_versions={(int(d),cx,cz):h for d,chunks in self.terrain.manifest.get('chunks',{}).items() for cx,cz,h in chunks}
            self.saved_version_revision=revision
        # An unrelated saved chunk must not invalidate every rendered image.
        versions=tuple((self.saved_versions.get((dim,x+dx,z+dz)),self.live_surfaces.get((dim,x+dx,z+dz))) for dx,dz in [(0,0),(-1,0),(1,0),(0,-1),(0,1)])
        return (self.cache.path.name,dim,x,z,versions,exaggeration,intensity)

    def render_surface(self,dim,x,z,exaggeration=1.5,intensity=.8):
        surface,store=self.surface(dim,x,z)
        if surface is None:raise LookupError('Chunk sem superfície disponível')
        depth,biomes,_=store.extras(dim,x,z)
        image=relief_image(surface[0],surface[1],self.surface_margin(dim,x,z,surface[1]),exaggeration,intensity,depth,biomes or surface[2])
        buffer=io.BytesIO();image.save(buffer,format='PNG');return buffer.getvalue()

    def live_chunks(self):
        result={}
        for (dim,x,z),value in self.live_surfaces.items():
            result.setdefault(str(dim),[]).append([x,z,value])
        return result

    def auto_log(self):
        roots=[Path(os.environ.get('APPDATA',Path.home()/'AppData'/'Roaming'))/'Minecraft Bedrock'/'logs',
               Path(self.config['world']).parent.parent/'logs',
               Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'Packages'/'Microsoft.MinecraftUWP_8wekyb3d8bbwe'/'LocalState'/'logs']
        files=[p for root in roots if root.is_dir() for p in root.iterdir()
               if p.is_file() and 'contentlog' in p.name.lower() and p.suffix.lower() in ('.log','.txt')]
        if files:
            latest=max(files,key=lambda p:p.stat().st_mtime_ns)
            if not self.content_log or self.content_log.path!=latest:
                self.content_log=ContentLog(latest)
                LOG.info('Content Log selecionado: %s',latest)

    def accept_surface(self,packet):
        # Old getTopmostBlock captures can contain the seabed instead of water.
        # Keep them on disk for diagnosis, but never display/replay them.
        if packet.get('surfaceVersion')!=2:return
        dim,x,z=(int(packet[k]) for k in ('dimension','x','z'))
        palette=packet['palette'];ids=packet['ids'];heights=packet['heights']
        if dim not in (0,1,2) or len(ids)!=256 or len(heights)!=256 or not 0<len(palette)<=256:
            raise ValueError('Superfície inválida')
        if any(not isinstance(i,int) or not 0<=i<len(palette) for i in ids):raise ValueError('Paleta inválida')
        names=np.asarray(palette)[np.asarray(ids)].reshape(16,16)
        h=np.asarray(heights,dtype=np.int16).reshape(16,16)
        depth=packet.get('depth')
        if depth is not None and len(depth)!=256:raise ValueError('Profundidade inválida')
        try:self.live_store.put(dim,x,z,names,h,packet.get('biome'),depth=np.asarray(depth).reshape(16,16) if depth is not None else None,biomes=packet.get('biomes'),surface_version=2)
        except SurfaceQuotaExceeded:
            if self.storage:self.storage.quota_blocked=True;self.storage.last_stats=0
            return
        if (self.capture_writes+1)%64==0:self.live_surfaces=self.live_store.entries()
        # Tick and telemetry time are not terrain changes.
        self.live_surfaces[(dim,x,z)]=self.live_store.entry_hash(dim,x,z)
        self.capture_writes+=1

    async def ingest_packet(self,packet):
        async with self.switch_lock:
            await self._ingest_packet(packet)

    async def _ingest_packet(self,packet):
        if packet.get('worldId')!=self.world_id():
            if packet.get('kind')=='status' and not packet.get('worldId'):
                self.error='Pack universal sem vinculo: copie /livemap:vincular no site.'
            return
        kind=packet.get('kind')
        if kind=='status':
            self.players=parse_targets({'details':packet.get('players',[])},self.host_name)
            self.last_update=time.time();self.player_source='content_log';self.error=None
            self.capabilities=packet.get('capabilities',{})
        elif kind=='entities':
            if self.entity_frame!=packet['frame']:
                self.entity_frame=packet['frame'];self.entity_parts={}
            total=int(packet['total']);part=int(packet['part'])
            if not 1<=total<=32 or not 0<=part<total:return
            self.entity_parts[part]=packet['entities'][:24]
            if len(self.entity_parts)==total:
                self.entities=[e for i in range(total) for e in self.entity_parts[i]]
                self.entity_update=time.time()
        elif kind=='surface':
            await asyncio.to_thread(self.accept_surface,packet)
        elif kind=='biome':
            self.biome_results=[r for r in self.biome_results if r.get('biome')!=packet.get('biome')]+[packet]
            self.biome_results=self.biome_results[-100:]
        elif kind=='error':self.error=str(packet.get('message','Erro do pack'))

    def start_worker(self):
        self.worker=multiprocessing.Process(target=run_terrain,args=(str(self.cache.path),self.config['world'],self.config['terrain_seconds'],str(self.storage.saved_path) if self.storage else None,int(self.storage.limit_bytes*.75) if self.storage else None),daemon=True)
        self.worker.start()

    def stop_worker(self):
        if self.worker:
            if self.worker.is_alive():self.worker.terminate()
            self.worker.join(timeout=5)
            self.worker=None

    async def select_world(self,path):
        async with self.switch_lock:
            if self.game_ws:await self.game_ws.close()
            await self.web_tiles.aclose()
            self.stop_worker()
            self.cache.close()
            self.cache=SessionCache(ROOT/'data'/'sessions')
            self.cache.watch()
            self.config['world']=str(path)
            self.open_world_storage()
            self.terrain=self.make_terrain()
            self.open_capture_store()
            self.players=[];self.entities=[];self.biome_results=[]
            self.render_queue=RenderQueue();self.saved_version_revision=None;self.saved_versions={}
            self.open_map_tiles()
            self.last_update=0;self.names={};self.error=None
            self.capabilities={};self.entity_update=0;self.entity_frame=None;self.entity_parts={}
            self.start_worker()
            self.publish()

    def close(self):
        self.stop_worker()
        self.cache.close()

    def publish(self):
        payload = self.state()
        for queue in self.listeners:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(payload)

    async def heartbeat(self):
        while True:
            try:
                path = self.cache.path / 'data' / 'terrain-state.json'
                if path.exists():
                    candidate = json.loads(path.read_text(encoding='utf-8'))
                    expected = hashlib.sha256(str(Path(self.config['world']).resolve()).encode()).hexdigest()
                    if candidate.get('world_id') == expected:
                        self.terrain.manifest = candidate
            except (OSError, ValueError):
                pass
            if self.content_log:
                try:
                    packets=await asyncio.to_thread(self.content_log.read_packets)
                    for packet in packets:await self.ingest_packet(packet)
                except Exception as exc:
                    self.error = 'Content Log: ' + str(exc)
            if self.config.get('content_log')=='auto':self.auto_log()
            self.history_tick()
            self.publish()
            await asyncio.sleep(.25)

    async def minecraft(self, request):
        if not any(ipaddress.ip_address(request.remote or '::') in ipaddress.ip_network(n) for n in self.config.get('minecraft_allowed_networks',['127.0.0.0/8','::1/128'])):
            raise web.HTTPForbidden()
        if request.headers.get('Origin'):
            raise web.HTTPForbidden(text='Conexão exclusiva do jogo')
        if self.game_ws is not None:
            raise web.HTTPConflict(text='Minecraft já conectado')
        ws = web.WebSocketResponse(max_msg_size=1024 * 1024, heartbeat=20, decode_text=False,
                                   protocols=['com.microsoft.minecraft.wsencrypt'], compress=False)
        await ws.prepare(request)
        self.game_ws, self.connected = ws, True
        LOG.info('Minecraft conectado: %s', request.remote)
        crypto = GameEncryption() if ws.ws_protocol else None
        ready = asyncio.Event()

        async def command(line, kind):
            rid = str(uuid.uuid4())
            self.pending[rid] = (kind, time.time())
            packet = {'header': {'version': 1, 'requestId': rid, 'messageType':'commandRequest',
                                          'messagePurpose': 'commandRequest'},
                                'body': {'commandLine': line}}
            data = json.dumps(packet, ensure_ascii=False).encode('utf-8')
            await ws.send_frame(crypto.encode(data) if crypto else data, WSMsgType.TEXT)

        async def poll():
            await command(crypto.command() if crypto else 'getlocalplayername', 'encryption' if crypto else 'host')
            try:
                await asyncio.wait_for(ready.wait(), timeout=12)
            except asyncio.TimeoutError:
                self.error = 'Minecraft não concluiu a negociação WebSocket em 12 segundos'
                await ws.close()
                return
            if crypto:
                await command('getlocalplayername', 'host')
            next_names = 0
            while not ws.closed:
                self.pending = {k: v for k, v in self.pending.items() if time.time() - v[1] < 10}
                if not any(v[0] == 'targets' for v in self.pending.values()):
                    await command('querytarget @a', 'targets')
                if time.time() >= next_names:
                    await command('list', 'names')
                    next_names = time.time() + 5
                self.publish()
                await asyncio.sleep(max(.25, self.config['player_seconds']))

        task = asyncio.create_task(poll())
        try:
            while not ws.closed:
                msg = await ws.receive()
                if msg.type in (WSMsgType.CLOSE,WSMsgType.CLOSED,WSMsgType.ERROR):
                    LOG.warning('Minecraft encerrou conexão: tipo=%s código=%s motivo=%s',msg.type,msg.data,msg.extra)
                    break
                if msg.type not in (WSMsgType.TEXT, WSMsgType.BINARY):
                    continue
                try:
                    data = msg.data.encode() if isinstance(msg.data, str) else msg.data
                    packet = json.loads(crypto.decode(data) if crypto else data)
                    body, header = packet.get('body', {}), packet.get('header', {})
                    pending = self.pending.pop(header.get('requestId'), None)
                    if self.config.get('debug_packets'):
                        LOG.info('Resposta do Minecraft: %s',json.dumps(packet,ensure_ascii=False)[:8192])
                    if pending is None:
                        continue
                    if body.get('statusCode', 0) != 0:
                        self.error = str(body.get('statusMessage', body))
                    elif pending[0] == 'host':
                        self.host_name = body.get('localplayername', body.get('name', self.host_name))
                        if crypto and not crypto.encoder:
                            await command(crypto.command(), 'encryption')
                        else:
                            ready.set()
                    elif pending[0] == 'encryption':
                        crypto.accept(body['publicKey'])
                        ready.set()
                        LOG.info('Criptografia WebSocket estabelecida (P-384 / AES-CFB8)')
                    elif pending[0] == 'names':
                        names = body.get('players', [])
                        if isinstance(names, str):
                            names = [n.strip() for n in names.split(',') if n.strip()]
                        for name in names:
                            if isinstance(name, str):
                                await command('querytarget @a[name=' + json.dumps(name, ensure_ascii=False) + ']', 'name:' + name)
                    elif pending[0].startswith('name:'):
                        for player in parse_targets(body):
                            self.names[player['id']] = pending[0][5:]
                    elif pending[0] == 'targets':
                        self.player_source = 'websocket'
                        self.players = parse_targets(body, self.host_name)
                        for player in self.players:
                            if player['id'] in self.names:
                                player['name'] = self.names[player['id']]
                            player['host'] = player['name'] == self.host_name
                        self.last_update = time.time()
                        self.error = None
                        LOG.info('Posições recebidas: %s jogador(es)', len(self.players))
                    self.publish()
                except Exception as exc:
                    self.error = str(exc)
                    LOG.exception('Resposta do Minecraft inválida')
        finally:
            LOG.info('Minecraft desconectado: close_code=%s error=%s', ws.close_code, ws.exception())
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.connected = False
            self.game_ws = None
            self.players = []
            self.pending.clear()
            self.publish()
        return ws

    async def events(self, request):
        response = web.StreamResponse(headers={'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
        await response.prepare(request)
        queue = asyncio.Queue(maxsize=1)
        self.listeners.add(queue)
        queue.put_nowait(self.state())
        sent_revision = None
        previous=None
        try:
            while not self.stop_event.is_set():
                try:
                    state = await asyncio.wait_for(queue.get(), timeout=15)
                    full=state
                    state=dict(state)
                    revision = (state['world_id'],state['session_id'],state['terrain']['revision'], state['terrain'].get('error'))
                    if revision == sent_revision:
                        state = {k:v for k,v in state.items() if k != 'terrain'}
                    else:
                        sent_revision = revision
                        if previous and previous['world_id']==state['world_id'] and previous['session_id']==state['session_id']:
                            terrain=dict(state['terrain'])
                            for field in ('chunks','regions'):
                                old=previous['terrain'].get(field,{})
                                terrain[field+'_delta']=tile_delta(old,terrain.get(field,{}))
                                terrain.pop(field,None)
                            state['terrain']=terrain
                    if previous and previous['world_id']==state['world_id'] and previous['session_id']==state['session_id']:
                        state['live_chunks_delta']=tile_delta(previous['live_chunks'],state.pop('live_chunks'))
                        state['tile_index_delta']=tile_delta(previous['tile_index'],state.pop('tile_index'))
                        old={e['id']:e for e in previous['entities']};new={e['id']:e for e in state.pop('entities')}
                        state['entities_delta']={'upsert':[e for k,e in new.items() if old.get(k)!=e],'remove':[k for k in old if k not in new]}
                        if previous.get('shared_waypoints')==state.get('shared_waypoints'):state.pop('shared_waypoints',None)
                        if previous.get('history')==state.get('history'):state.pop('history',None)
                        if previous.get('annotations')==state.get('annotations'):state.pop('annotations',None)
                        for key in list(state):
                            if key not in ('terrain','live_chunks_delta','tile_index_delta','entities_delta','world_id','session_id','players') and previous.get(key)==state[key]:state.pop(key)
                    previous=full
                    await response.write(('data: ' + json.dumps(state) + '\n\n').encode())
                except asyncio.TimeoutError:
                    await response.write(b': heartbeat\n\n')
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            self.listeners.discard(queue)
        return response

    async def login(self, request):
        now = time.time()
        history = [t for t in self.attempts.get(request.remote, []) if now - t < 60]
        if len(history) >= 8:
            raise web.HTTPTooManyRequests(text='Aguarde um minuto')
        self.attempts[request.remote] = history + [now]
        body = await request.json()
        if not hmac.compare_digest(str(body.get('pin', '')), self.config.get('pin', '')):
            raise web.HTTPUnauthorized()
        token = secrets.token_urlsafe(32)
        self.sessions[token] = now + 43200
        response = web.json_response({'ok': True})
        response.set_cookie('session', token, httponly=True, samesite='Strict', max_age=43200)
        return response

    def app(self):
        networks = [ipaddress.ip_network(n) for n in self.config['allowed_networks']]
        @web.middleware
        async def guard(request, handler):
            peer = ipaddress.ip_address(request.remote or '0.0.0.0')
            if not any(peer in n for n in networks):
                raise web.HTTPForbidden(text='Somente rede local autorizada')
            if request.headers.get('Origin') and request.headers['Origin'] != f'{request.scheme}://{request.host}':
                raise web.HTTPForbidden(text='Origem não autorizada')
            public = request.path in ('/', '/app.js', '/style.css','/controls.css', '/api/login',
                                      '/components.html','/components.js','/chiko-design.css',
                                      '/locales.js','/i18n.js','/tile-source.js','/map-renderer.js','/pixel-avatars.js','/chiko.js','/timeline.js','/map-editor.js',
                                      '/assets/paper-frame.svg','/assets/Caveat.ttf','/assets/OFL-Caveat.txt',
                                      '/caderno.html','/caderno-preview.css','/caderno-preview.js','/assets/chiko-pixel-v1.png','/assets/doodleatlas-icon.png','/favicon.ico')
            if self.config.get('pin') and not public and self.sessions.get(request.cookies.get('session'), 0) < time.time():
                raise web.HTTPUnauthorized(text='PIN necessário')
            response = await handler(request)
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Referrer-Policy'] = 'no-referrer'
            response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
            return response
        app = web.Application(middlewares=[guard], client_max_size=4096)
        async def close_renders(app):
            job=getattr(self,'history_job',None)
            if job:
                job['cancel'].set()
                await job['task']
            await self.web_tiles.aclose()
        app.on_cleanup.append(close_renders)
        def host(request):
            if not ipaddress.ip_address(request.remote or '::').is_loopback:
                raise web.HTTPForbidden(text='Abra o endere?o local do mapa no PC do host')
            if request.method!='GET' and not hmac.compare_digest(request.headers.get('X-Host-Token',''),self.host_token):
                raise web.HTTPForbidden(text='Token do host necessário')
        async def host_info(request):
            if not ipaddress.ip_address(request.remote or '::').is_loopback:
                return web.json_response({'is_host':False})
            return web.json_response({'token':self.host_token})
        async def favicon(request):
            return web.FileResponse(ASSETS/'branding'/'doodleatlas-icon.png')
        async def worlds(request):
            return web.json_response([{'id':hashlib.sha256(str(Path(w['path']).resolve()).encode()).hexdigest(),'name':w['name']}
                                      for w in await asyncio.to_thread(discover)])
        async def select(request):
            host(request)
            body=await request.json()
            candidates=await asyncio.to_thread(discover)
            chosen=next((w for w in candidates if hashlib.sha256(str(Path(w['path']).resolve()).encode()).hexdigest()==body.get('id')),None)
            if not chosen:raise web.HTTPNotFound(text='Mundo não encontrado')
            await self.select_world(chosen['path'])
            return web.json_response({'ok':True})
        async def shutdown(request):
            host(request)
            self.stop_event.set()
            self.publish()
            return web.json_response({'ok':True})
        async def settings(request):
            host(request)
            body=await request.json()
            try:seconds=float(body['terrain_seconds'])
            except (KeyError,TypeError,ValueError):raise web.HTTPBadRequest(text='Intervalo inválido')
            if not np.isfinite(seconds) or not 2<=seconds<=600:raise web.HTTPBadRequest(text='Use entre 2 e 600 segundos')
            self.config['terrain_seconds']=seconds
            target=self.cache.path/'settings.json';temporary=target.with_suffix('.tmp')
            temporary.write_text(json.dumps({'terrain_seconds':seconds}));temporary.replace(target)
            self.publish()
            return web.json_response({'terrain_seconds':seconds,'scope':'intervalo mínimo entre inícios; duração da leitura pode ser maior'})
        async def file(request):
            name = request.match_info.get('file', 'index.html')
            if name == 'caderno.html':
                html = (WEB/'index.html').read_text(encoding='utf-8')
                return web.Response(text=html, content_type='text/html', headers={'Cache-Control':'no-store'})
            return web.FileResponse(WEB / name)
        async def asset(request):
            name = request.match_info['asset']
            folder = 'branding' if name == 'doodleatlas-icon.png' else ('chiko' if name == 'chiko-pixel-v1.png' else 'web')
            return web.FileResponse(ASSETS/folder/name)
        async def state(request):
            return web.json_response(self.state())
        def waypoint_writer(request):
            # The guard already validates PIN sessions and Origin. Without a PIN,
            # viewing the LAN map does not grant anonymous write permission.
            if not self.config.get('pin'):host(request)
        async def shared_points(request):
            if request.method=='GET':
                return web.json_response(self.state()['shared_waypoints'],headers={'Cache-Control':'no-store'})
            waypoint_writer(request)
            if request.method=='POST':
                if request.content_type!='application/json':raise web.HTTPBadRequest(text='Use JSON')
                try:body=await request.json()
                except (ValueError,UnicodeError):raise web.HTTPBadRequest(text='JSON inválido')
                if not isinstance(body,dict):raise web.HTTPBadRequest(text='Anotação inválida')
                world=body.get('world_id')
            else:body=None;world=request.query.get('world_id')
            async with self.switch_lock:
                if world!=self.world_id():raise web.HTTPConflict(text='O mundo mudou. Atualize o mapa antes de salvar.')
                store=self.shared_store
                if store is None:raise web.HTTPConflict(text='Ative o armazenamento por mundo para compartilhar pontos.')
                if body is not None:
                    stats=self.storage.stats()
                    if stats.get('quota_reached'):raise web.HTTPInsufficientStorage(text='Cota deste mundo atingida; pontos existentes preservados.')
                try:
                    if body is not None:await asyncio.to_thread(store.create,body)
                    else:await asyncio.to_thread(store.delete,request.match_info['point_id'])
                except WaypointLimit as exc:raise web.HTTPConflict(text=str(exc))
                except ValueError as exc:raise web.HTTPBadRequest(text=str(exc))
                except KeyError:raise web.HTTPNotFound(text='Este ponto já foi removido.')
                self.storage.last_stats=0
                self.publish()
                return web.json_response({**store.snapshot,'pin_writes':bool(self.config.get('pin'))},headers={'Cache-Control':'no-store'})
        async def annotation_document(request):
            world=self.world_id();store=self.annotations
            if request.method=='GET':
                result=await asyncio.to_thread(store.read) if store else {'available':False,'cells':[],'revision':0}
                if self.world_id()!=world:raise web.HTTPConflict(text='Mundo mudou')
                return web.json_response(result | {'world_id':world,'pin_writes':bool(self.config.get('pin'))},headers={'Cache-Control':'no-store'})
            waypoint_writer(request)
            if request.content_type!='application/json':raise web.HTTPBadRequest(text='Use JSON')
            # Only this endpoint accepts larger documents. Other APIs retain their 4 KiB limit.
            data=bytearray()
            async for part in request.content.iter_chunked(65536):
                data.extend(part)
                if len(data)>3*1024*1024:raise web.HTTPRequestEntityTooLarge(max_size=3*1024*1024,actual_size=len(data))
            try:body=json.loads(data)
            except (ValueError,UnicodeError):raise web.HTTPBadRequest(text='JSON inválido')
            async with self.switch_lock:
                if not isinstance(body,dict) or body.get('world_id')!=self.world_id() or self.world_id()!=world:raise web.HTTPConflict(text='Mundo mudou')
                if not store:raise web.HTTPConflict(text='Ative o armazenamento por mundo')
                if self.storage.stats().get('quota_reached'):raise web.HTTPInsufficientStorage(text='Cota do mundo atingida; edição anterior preservada')
                try:result=await asyncio.to_thread(store.save,body.get('revision'),body.get('cells'),body.get('structures'))
                except AnnotationConflict as error:raise web.HTTPConflict(text=str(error))
                except ValueError as error:raise web.HTTPBadRequest(text=str(error))
                self.storage.last_stats=0
                self.publish()
                return web.json_response(result,headers={'Cache-Control':'no-store'})
        async def history_info(request):
            if not self.history:return web.json_response({'available':False})
            history=self.history;world=self.world_id()
            info=await asyncio.to_thread(history.status,True)
            if self.world_id()!=world:raise web.HTTPConflict(text='Mundo mudou')
            return web.json_response(info | {'world_id':world},headers={'Cache-Control':'no-store'})
        async def history_settings(request):
            host(request)
            try:body=await request.json()
            except ValueError:raise web.HTTPBadRequest(text='JSON inválido')
            async with self.switch_lock:
                if not isinstance(body,dict) or body.get('world_id')!=self.world_id():raise web.HTTPConflict(text='Mundo mudou')
                if not self.history:raise web.HTTPConflict(text='Armazenamento persistente desativado')
                try:options=await asyncio.to_thread(self.history.configure,body.get('settings'))
                except ValueError as error:raise web.HTTPBadRequest(text=str(error))
                if not options['frames_enabled'] or 'primary_region' in body.get('settings',{}):
                    job=getattr(self,'history_job',None)
                    if job:job['cancel'].set()
                if 'primary_region' in body.get('settings',{}):self.history_error=''
                self.history_next_attempt=time.time()+options['interval_minutes']*60
                self.publish();return web.json_response({'ok':True})
        async def history_capture(request):
            waypoint_writer(request)
            try:body=await request.json()
            except ValueError:raise web.HTTPBadRequest(text='JSON inválido')
            async with self.switch_lock:
                if not isinstance(body,dict) or body.get('world_id')!=self.world_id():raise web.HTTPConflict(text='Mundo mudou')
                dimension=body.get('dimension',0)
                if type(dimension) is not int or dimension not in (0,1,2):raise web.HTTPBadRequest(text='Dimensão inválida')
                try:self.start_history_frame(dimension)
                except ValueError as error:raise web.HTTPConflict(text=str(error))
                self.publish();return web.json_response({'queued':True},status=202)
        async def history_image(request):
            world=self.world_id();history=self.history
            if request.query.get('world_id')!=world:raise web.HTTPConflict(text='Mundo mudou')
            if not history:raise web.HTTPNotFound()
            frame=await asyncio.to_thread(history.frame,int(request.match_info['frame_id']))
            if self.world_id()!=world:raise web.HTTPConflict(text='Mundo mudou')
            if not frame:raise web.HTTPNotFound(text='Quadro expirou ou foi removido pela cota')
            data,digest=frame;etag='"'+digest+'"';headers={'Cache-Control':'private, max-age=0, must-revalidate','ETag':etag}
            if request.headers.get('If-None-Match')==etag:return web.Response(status=304,headers=headers)
            return web.Response(body=data,content_type='image/webp',headers=headers)
        async def history_change(request):
            world=self.world_id();history=self.history
            if request.query.get('world_id')!=world:raise web.HTTPConflict(text='Mundo mudou')
            if not history:raise web.HTTPNotFound()
            row=await asyncio.to_thread(history.change,int(request.match_info['event_id']))
            if not row:raise web.HTTPNotFound(text='Versão expirada ou removida pela cota')
            try:result=await self.render_queue.request(('history',world,hashlib.sha256(row[0]).hexdigest()),lambda:render_change(row[0]))
            except (RenderBusy,RenderClosed):raise web.HTTPServiceUnavailable()
            if self.world_id()!=world:raise web.HTTPConflict(text='Mundo mudou')
            headers={'Cache-Control':'private, max-age=0, must-revalidate','ETag':result.etag}
            if request.headers.get('If-None-Match')==result.etag:return web.Response(status=304,headers=headers)
            return web.Response(body=result.data,content_type='image/webp',headers=headers)
        async def qr(request):
            buffer = io.BytesIO()
            qrcode.make(self.config['lan_url']).save(buffer, format='PNG')
            return web.Response(body=buffer.getvalue(), content_type='image/png')
        async def tile(request):
            dim, cx, cz = (int(request.match_info[k]) for k in ('dim', 'cx', 'cz'))
            if request.path.startswith('/live/'):
                return await queued_render(request,dim,cx,cz,1.5,.8)
            folder = self.terrain.folder if request.path.startswith('/tiles/') else self.cache.path/'data'/('live_tiles' if request.path.startswith('/live/') else 'regions')
            path = folder / str(dim) / f'{cx}_{cz}.png'
            if not path.is_file():
                raise web.HTTPNotFound()
            return web.FileResponse(path, headers={'Cache-Control': 'no-cache'})
        async def render(request):
            dim,cx,cz=(int(request.match_info[k]) for k in ('dim','cx','cz'))
            try:
                exaggeration=float(request.query.get('exaggeration',1.5));intensity=float(request.query.get('intensity',.8))
                if not 0<=exaggeration<=8 or not 0<=intensity<=1.5:raise ValueError()
            except ValueError:raise web.HTTPBadRequest(text='Relevo inválido')
            mode=request.query.get('mode','relief')
            if mode!='relief':raise web.HTTPBadRequest(text='Use mode=relief: o mapa usa cores planas, sem texturas')
            return await queued_render(request,dim,cx,cz,exaggeration,intensity)
        async def queued_render(request,dim,cx,cz,exaggeration,intensity):
            key=self.render_key(dim,cx,cz,exaggeration,intensity)
            try:
                result=await self.render_queue.request(key,lambda:self.render_surface(dim,cx,cz,exaggeration,intensity),
                    valid=lambda:key==self.render_key(dim,cx,cz,exaggeration,intensity))
            except LookupError:raise web.HTTPNotFound()
            except (RenderBusy,RenderClosed):raise web.HTTPServiceUnavailable(headers={'Retry-After':'1'},text='Fila ocupada; tente novamente')
            headers={'Cache-Control':'private, max-age=0, must-revalidate','ETag':result.etag}
            matches=[part.strip() for part in request.headers.get('If-None-Match','').split(',')]
            if result.etag in matches or '*' in matches:return web.Response(status=304,headers=headers)
            return web.Response(body=result.data,content_type='image/png',headers=headers)
        async def map_tile(request):
            style=request.query.get('palette','paper')
            if style not in ('paper','minecraft','atlas'):raise web.HTTPBadRequest(text='Paleta inválida')
            d,level,x,z=(int(request.match_info[k]) for k in ('dim','level','tx','tz'))
            if d not in (0,1,2) or not 0<=level<=MAX_LEVEL:raise web.HTTPBadRequest(text='Dimensão ou zoom inválido')
            if request.query.get('world')!=self.world_id():raise web.HTTPConflict(text='Mundo mudou; atualize o mapa')
            try:
                pixels=int(request.query.get('pixels','256'));native=source_key(d,level,x,z,pixels)
                exaggeration=float(request.query.get('exaggeration',1.5));intensity=float(request.query.get('intensity',.8))
                if not 0<=exaggeration<=8 or not 0<=intensity<=1.5:raise ValueError()
            except ValueError:raise web.HTTPBadRequest(text='Relevo inválido')
            self.sync_tile_index()
            version=self.tile_index.version(*native)
            if version is None:raise web.HTTPNotFound()
            if request.query.get('revision')!=version:raise web.HTTPConflict(headers={'Retry-After':'1'},text='Versão mudou; aguardando atualização')
            pipeline=self.web_tiles
            try:
                async with asyncio.timeout(10):
                    result=await pipeline.request_sized(d,level,x,z,pixels,exaggeration,intensity,style)
                self.sync_tile_index()
                if self.web_tiles is not pipeline or self.tile_index.version(*native)!=version:raise TileChanged()
            except LookupError:raise web.HTTPNotFound()
            except TileChanged:raise web.HTTPConflict(headers={'Retry-After':'1'},text='Terreno mudou; tente novamente')
            except (RenderBusy,RenderClosed,TimeoutError):raise web.HTTPServiceUnavailable(headers={'Retry-After':'1'},text='Preparando o mapa; tente novamente')
            headers={'Cache-Control':'private, max-age=0, must-revalidate','ETag':result.etag,'X-Tile-Version':version}
            matches=[p.strip().removeprefix('W/') for p in request.headers.get('If-None-Match','').split(',')]
            if result.etag in matches or '*' in matches:return web.Response(status=304,headers=headers)
            return web.Response(body=result.data,content_type='image/webp',headers=headers)
        async def seed_tile(request):
            d,level,x,z=(int(request.match_info[k]) for k in ('dim','level','tx','tz'))
            info=self.seed_info;world=self.world_id()
            if not info.get('available') or d!=0:raise web.HTTPNotFound(text='Prévia indisponível')
            if request.query.get('world')!=world or request.query.get('revision')!=info['revision']:raise web.HTTPConflict(text='Mundo ou previsão mudou')
            try:
                y=int(request.query.get('y','64'));style=request.query.get('palette','paper');smooth=request.query.get('smooth','0')
                if not 0<=level<=3 or not -64<=y<=320 or max(abs(x),abs(z))*64*(4*4**level)>30000000 or style not in ('paper','minecraft','atlas') or smooth not in ('0','1'):raise ValueError()
            except ValueError:raise web.HTTPBadRequest(text='Prévia inválida')
            queue=self.render_queue
            try:
                async with asyncio.timeout(10):
                    result=await queue.request(('seed',info['revision'],level,x,z,y,style,smooth),lambda:render_prediction(info['seed'],level,x,z,y,style,smooth=='1'),
                        valid=lambda:self.world_id()==world and self.seed_info==info)
                if self.world_id()!=world or self.seed_info!=info:raise web.HTTPConflict()
            except (RenderBusy,RenderClosed,TimeoutError):raise web.HTTPServiceUnavailable(headers={'Retry-After':'1'})
            headers={'Cache-Control':'private, max-age=0, must-revalidate','ETag':result.etag}
            matches=[p.strip().removeprefix('W/') for p in request.headers.get('If-None-Match','').split(',')]
            if result.etag in matches or '*' in matches:return web.Response(status=304,headers=headers)
            return web.Response(body=result.data,content_type='image/webp',headers=headers)
        async def biome_search(request):
            q=request.query.get('q','').strip().lower()[:128]
            dim=int(request.query.get('dimension','0'))
            saved=await asyncio.to_thread(self.terrain.store.search,q,dim)
            saved+=await asyncio.to_thread(self.live_store.search,q,dim)
            seed=[r for r in self.biome_results if q in r.get('biome','').lower() and r.get('dimension',0)==dim]
            return web.json_response({'saved':saved,'seed':seed,'seed_value':self.terrain.manifest.get('seed'),
                                      'instruction':'No chat do mundo com o pack: /livemap:bioma minecraft:cherry_grove. O resultado da seed aparecerá aqui.'})
        app.router.add_get('/', file)
        app.router.add_get('/{file:locales.js|i18n.js|app.js|style.css|controls.css|components.html|components.js|chiko-design.css|tile-source.js|map-renderer.js|pixel-avatars.js|chiko.js|timeline.js|map-editor.js|caderno.html|caderno-preview.css|caderno-preview.js}', file)
        app.router.add_get('/assets/{asset:paper-frame.svg|Caveat.ttf|OFL-Caveat.txt|chiko-pixel-v1.png|doodleatlas-icon.png}',asset)
        app.router.add_post('/api/login', self.login)
        app.router.add_get('/api/state', state)
        app.router.add_get('/api/waypoints',shared_points)
        app.router.add_get('/api/annotations',annotation_document)
        app.router.add_put('/api/annotations',annotation_document)
        app.router.add_post('/api/waypoints',shared_points)
        app.router.add_delete('/api/waypoints/{point_id:[a-f0-9]{32}}',shared_points)
        app.router.add_get('/api/history',history_info)
        app.router.add_post('/api/history/settings',history_settings)
        app.router.add_post('/api/history/capture',history_capture)
        app.router.add_get(r'/api/history/frames/{frame_id:\d+}.webp',history_image)
        app.router.add_get(r'/api/history/changes/{event_id:\d+}.webp',history_change)
        app.router.add_get('/api/host',host_info)
        app.router.add_get('/favicon.ico',favicon)
        app.router.add_get('/api/worlds',worlds)
        app.router.add_post('/api/worlds/select',select)
        app.router.add_post('/api/shutdown',shutdown)
        app.router.add_post('/api/settings',settings)
        app.router.add_get('/api/biomes',biome_search)
        app.router.add_get('/api/events', self.events)
        app.router.add_get('/qr.png', qr)
        app.router.add_get(r'/tiles/{dim:-?\d+}/{cx:-?\d+}/{cz:-?\d+}.png', tile)
        app.router.add_get(r'/regions/{dim:-?\d+}/{cx:-?\d+}/{cz:-?\d+}.png', tile)
        app.router.add_get(r'/render/{dim:-?\d+}/{cx:-?\d+}/{cz:-?\d+}.png',render)
        app.router.add_get(r'/live/{dim:-?\d+}/{cx:-?\d+}/{cz:-?\d+}.png',tile)
        app.router.add_get(r'/map/{dim:-?\d+}/{level:\d+}/{tx:-?\d+}/{tz:-?\d+}.webp',map_tile)
        app.router.add_get(r'/seed/{dim:-?\d+}/{level:\d+}/{tx:-?\d+}/{tz:-?\d+}.webp',seed_tile)
        return app


async def main(config=None):
    if config is None:
        from chiko.settings import load
        config=load()
    if config['http_port'] == config['minecraft_port']:
        raise ValueError('As portas HTTP e Minecraft devem ser diferentes')
    live = LiveMap(config)
    runner = web.AppRunner(live.app(),shutdown_timeout=2)
    await runner.setup()
    await web.TCPSite(runner, config['http_host'], config['http_port']).start()
    game = web.Application()
    game.router.add_get('/{tail:.*}', live.minecraft)
    game_runner = web.AppRunner(game)
    await game_runner.setup()
    await web.TCPSite(game_runner, config['minecraft_host'], config['minecraft_port']).start()
    (ROOT / 'data' / 'server.pid').write_text(str(os.getpid()), encoding='ascii')
    LOG.info('Caderno aberto em %s | LAN: %s',config['local_url'],config['lan_url'])
    LOG.info('Pack via Content Log; WebSocket opcional: %s',config['connect_url'])
    live.cache.watch()
    live.start_worker()
    (ROOT/'data'/'control.json').write_text(json.dumps({'url':config['local_url'],'port':config['http_port'],'token':live.host_token,'pid':os.getpid()}))
    heartbeat = asyncio.create_task(live.heartbeat())
    try:
        await live.stop_event.wait()
    finally:
        live.stop_worker()
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)
        await runner.cleanup()
        await game_runner.cleanup()
        live.cache.close()


if __name__ == '__main__':
    from chiko.__main__ import main as cli
    cli()
