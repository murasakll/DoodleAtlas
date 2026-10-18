"""Bounded observed history and small, opt-out overview frames. No game writes."""
from contextlib import contextmanager, closing
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import time
import zlib

DEFAULTS = {'enabled': True, 'frames_enabled': True, 'interval_minutes': 60,
            'limit_mb': 32, 'retention_days': 7}


class MapHistory:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.last_stats = 0
        self.cached_stats = {}
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS versions (hash TEXT PRIMARY KEY, payload BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, origin TEXT NOT NULL,
                    dim INTEGER NOT NULL,x INTEGER NOT NULL,z INTEGER NOT NULL,at REAL NOT NULL,hash TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS event_chunk ON events(origin,dim,x,z,id DESC);
                CREATE INDEX IF NOT EXISTS event_time ON events(at);
                CREATE INDEX IF NOT EXISTS event_hash ON events(hash);
                CREATE TABLE IF NOT EXISTS frames (id INTEGER PRIMARY KEY AUTOINCREMENT,dim INTEGER NOT NULL,
                    at REAL NOT NULL,hash TEXT NOT NULL,data BLOB NOT NULL,metadata TEXT NOT NULL);
            ''')
            db.execute('INSERT OR IGNORE INTO settings VALUES(1,?)', (json.dumps(DEFAULTS | {'started': time.time()}),))

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA journal_size_limit=1048576')
            try:limit=self.settings(db)['limit_mb']
            except sqlite3.OperationalError:limit=DEFAULTS['limit_mb']
            page=db.execute('PRAGMA page_size').fetchone()[0]
            db.execute('PRAGMA max_page_count='+str(int(limit*1048576*.7)//page))
            with db:
                yield db

    def settings(self, db=None):
        if db is not None:return DEFAULTS | json.loads(db.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])
        with self.connect() as db:return self.settings(db)

    def configure(self, values):
        if not isinstance(values, dict) or set(values)-set(DEFAULTS):raise ValueError('Opções de histórico inválidas')
        for key, value in values.items():
            if key in ('enabled', 'frames_enabled'):
                if type(value) is not bool:raise ValueError('Use verdadeiro ou falso')
            elif type(value) is not int or value not in ({'interval_minutes':(10,30,60,180,360,1440), 'limit_mb':(8,16,32,64), 'retention_days':(1,3,7,14,30)}[key]):
                raise ValueError('Escolha um valor disponível para '+key)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            value=self.settings(db) | values
            db.execute('UPDATE settings SET value=? WHERE id=1',(json.dumps(value),))
            self.prune(db,value)
        self.last_stats=0
        return value

    def record(self, origin, row):
        # Timestamp is deliberately outside the content digest. Identical revisits cost no history rows.
        dim,x,z,palette,ids,heights,biome,updated,depth,biomes,version=row
        packed=json.dumps([palette,ids.hex(),heights.hex(),biome,depth.hex() if depth else None,biomes,version],separators=(',',':')).encode()
        digest=hashlib.sha256(packed).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE');settings=self.settings(db)
            if not settings['enabled']:return False
            last=db.execute('SELECT hash FROM events WHERE origin=? AND dim=? AND x=? AND z=? ORDER BY id DESC LIMIT 1',(origin,dim,x,z)).fetchone()
            if last and last[0]==digest:return False
            db.execute('INSERT OR IGNORE INTO versions VALUES(?,?)',(digest,zlib.compress(packed)))
            db.execute('INSERT INTO events(origin,dim,x,z,at,hash) VALUES(?,?,?,?,?,?)',(origin,dim,x,z,time.time(),digest))
            self.prune(db,settings)
        self.last_stats=0
        return True

    @staticmethod
    def prune(db, settings):
        cutoff=time.time()-settings['retention_days']*86400
        db.execute('DELETE FROM events WHERE at<?',(cutoff,));db.execute('DELETE FROM frames WHERE at<?',(cutoff,))
        # Bound metadata too, even with very small, highly repetitive surfaces.
        db.execute('DELETE FROM events WHERE id IN (SELECT id FROM events ORDER BY id DESC LIMIT -1 OFFSET ?)',(min(20000,settings['limit_mb']*500),))
        db.execute('DELETE FROM frames WHERE id IN (SELECT id FROM frames ORDER BY id DESC LIMIT -1 OFFSET 168)')
        db.execute('DELETE FROM versions WHERE hash NOT IN (SELECT hash FROM events)')
        limit=settings['limit_mb']*1048576*.4
        used=db.execute('SELECT (SELECT COALESCE(sum(length(payload)),0) FROM versions)+(SELECT COALESCE(sum(length(data)),0) FROM frames)').fetchone()[0]
        while used>limit:
            old_event=db.execute('SELECT id,at,hash FROM events ORDER BY id LIMIT 1').fetchone()
            old_frame=db.execute('SELECT id,at,length(data) FROM frames ORDER BY id LIMIT 1').fetchone()
            if old_frame and (not old_event or old_frame[1]<=old_event[1]):
                db.execute('DELETE FROM frames WHERE id=?',(old_frame[0],));used-=old_frame[2]
            elif old_event:
                db.execute('DELETE FROM events WHERE id=?',(old_event[0],))
                if not db.execute('SELECT 1 FROM events WHERE hash=? LIMIT 1',(old_event[2],)).fetchone():
                    used-=db.execute('SELECT length(payload) FROM versions WHERE hash=?',(old_event[2],)).fetchone()[0]
                    db.execute('DELETE FROM versions WHERE hash=?',(old_event[2],))
            else:break

    def add_frame(self, dim, data, metadata):
        extent=[metadata.get(key) for key in ('min_x','min_z','max_x','max_z')]
        digest=hashlib.sha256(data+json.dumps(extent).encode()).hexdigest();now=time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            last=db.execute('SELECT id,hash FROM frames WHERE dim=? ORDER BY id DESC LIMIT 1',(dim,)).fetchone()
            if last and last[1]==digest:return last[0]
            cursor=db.execute('INSERT INTO frames(dim,at,hash,data,metadata) VALUES(?,?,?,?,?)',(dim,now,digest,data,json.dumps(metadata)))
            self.prune(db,self.settings(db));frame_id=cursor.lastrowid
        self.last_stats=0
        return frame_id

    def frame(self, frame_id):
        with self.connect() as db:return db.execute('SELECT data,hash FROM frames WHERE id=?',(frame_id,)).fetchone()

    def change(self, event_id):
        with self.connect() as db:
            return db.execute('SELECT v.payload FROM events e JOIN versions v ON e.hash=v.hash WHERE e.id=?',(event_id,)).fetchone()

    def status(self, force=False):
        if not force and time.monotonic()-self.last_stats<5:return self.cached_stats
        with self.connect() as db:
            settings=self.settings(db)
            frames=[{'id':i,'dimension':dim,'at':at,'bytes':size,**json.loads(meta)} for i,dim,at,size,meta in db.execute('SELECT id,dim,at,length(data),metadata FROM frames ORDER BY id DESC LIMIT 168')]
            count=db.execute('SELECT count(*) FROM events').fetchone()[0]
            recent=[{'id':i,'origin':o,'dimension':d,'x':x,'z':z,'at':at} for i,o,d,x,z,at in db.execute('SELECT id,origin,dim,x,z,at FROM events ORDER BY id DESC LIMIT 12')]
        disk=sum(p.stat().st_size for p in [self.path,Path(str(self.path)+'-wal'),Path(str(self.path)+'-shm')] if p.exists())
        self.cached_stats={'available':True,'settings':settings,'frames':frames,'events':count,'recent':recent,'bytes':disk,'near_limit':disk>=settings['limit_mb']*1048576*.8}
        self.last_stats=time.monotonic()
        return self.cached_stats


def render_change(payload):
    import numpy as np
    from PIL import Image
    from terrain import colour
    from relief import hillshade
    palette,ids,heights,biome,depth,biomes,version=json.loads(zlib.decompress(payload))
    indices=np.frombuffer(zlib.decompress(bytes.fromhex(ids)),dtype='<u2').reshape(16,16)
    rgba=np.asarray([colour(n) for n in json.loads(palette)],dtype=np.uint8)[indices].copy()
    h=np.frombuffer(zlib.decompress(bytes.fromhex(heights)),dtype='<i2').reshape(16,16)
    rgba[:,:,:3]=np.clip(rgba[:,:,:3]*hillshade(np.pad(h,1,mode='edge'),1.5,.8)[:,:,None],0,255).astype('uint8')
    out=io.BytesIO();Image.fromarray(rgba).save(out,format='WEBP',lossless=True,method=2)
    return out.getvalue()


def overview_rows(path,dim,minimum):
    # Release each read transaction between batches, allowing WAL checkpoints and live writes.
    last=(-9223372036854775808,-9223372036854775808)
    while True:
        with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=5)) as db:
            rows=db.execute('SELECT x,z,palette,ids,heights FROM surfaces WHERE dim=? AND surface_version>=? AND (x,z)>(?,?) ORDER BY x,z LIMIT 64',(dim,minimum,*last)).fetchall()
        if not rows:return
        yield from rows
        last=rows[-1][:2]


def render_overview(saved_path, live_path, dim, cancel, side=768):
    """One bounded low-resolution frame. Streaming, no giant intermediate map or seed."""
    import numpy as np
    from PIL import Image
    from terrain import colour
    from relief import hillshade
    paths=[(live_path,2),(saved_path,0)];bounds=[];started=time.time();deadline=time.monotonic()+30
    for path,minimum in paths:
        with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=5)) as db:
            b=db.execute('SELECT min(x),min(z),max(x),max(z) FROM surfaces WHERE dim=? AND surface_version>=?',(dim,minimum)).fetchone()
            if b[0] is not None:bounds.append(b)
    if not bounds:raise LookupError('Ainda não há terreno observado nesta dimensão.')
    minx=min(b[0] for b in bounds)*16;minz=min(b[1] for b in bounds)*16
    maxx=(max(b[2] for b in bounds)+1)*16;maxz=(max(b[3] for b in bounds)+1)*16
    scale=min(1,side/max(maxx-minx,maxz-minz));width=max(1,int((maxx-minx)*scale+.5));height=max(1,int((maxz-minz)*scale+.5))
    image=Image.new('RGBA',(width,height));chunks=0
    for path,minimum in paths:
        for x,z,palette,ids,heights in overview_rows(path,dim,minimum):
            if cancel.is_set():raise InterruptedError('Captura cancelada')
            if chunks>=50000 or time.monotonic()>deadline:raise TimeoutError('Mundo excedeu o orçamento do quadro automático (30 s / 50.000 chunks). Nenhum quadro parcial foi salvo.')
            # A concurrently expanding database may add a chunk beyond the bounds measured above.
            if not minx<=x*16<maxx or not minz<=z*16<maxz:continue
            names=json.loads(palette);indices=np.frombuffer(zlib.decompress(ids),dtype='<u2').reshape(16,16)
            rgba=np.asarray([colour(n) for n in names],dtype=np.uint8)[indices].copy()
            h=np.frombuffer(zlib.decompress(heights),dtype='<i2').reshape(16,16)
            rgba[:,:,:3]=np.clip(rgba[:,:,:3]*hillshade(np.pad(h,1,mode='edge'),1.5,.8)[:,:,None],0,255).astype('uint8')
            left=int((x*16-minx)*scale);top=int((z*16-minz)*scale)
            right=min(width,max(left+1,int(((x+1)*16-minx)*scale)));bottom=min(height,max(top+1,int(((z+1)*16-minz)*scale)))
            tile=Image.fromarray(rgba).resize((right-left,bottom-top),Image.Resampling.BOX)
            image.alpha_composite(tile,(left,top));chunks+=1
            if chunks%32==0:time.sleep(.02)  # Yield between small batches; this runs below normal priority.
    out=io.BytesIO();image.save(out,format='WEBP',lossless=True,method=2)
    return out.getvalue(),{'width':width,'height':height,'min_x':minx,'min_z':minz,'max_x':maxx,'max_z':maxz,
                          'chunks_read':chunks,'started':started,'finished':time.time(),'source':'observed','style':'paper',
                          'note':'Leituras sucessivas do save e captura; não é um snapshot atômico. Sem seed, jogadores ou entidades.'}
