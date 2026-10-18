import json
import sqlite3
import zlib
import time
import hashlib
import logging
from contextlib import contextmanager
from pathlib import Path
import numpy as np


class SurfaceQuotaExceeded(RuntimeError):
    pass

class SurfaceStore:
    def __init__(self,path,max_bytes=None,min_surface_version=0,preserve=False):
        self.path=Path(path)
        self.max_bytes=max_bytes
        self.min_surface_version=min_surface_version
        self.preserve=preserve
        self.history=None;self.history_warned=False
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS surfaces (dim INTEGER,x INTEGER,z INTEGER,palette TEXT,ids BLOB,heights BLOB,biome TEXT,PRIMARY KEY(dim,x,z))')
            columns={r[1] for r in db.execute('PRAGMA table_info(surfaces)')}
            for name,kind in [('updated','REAL DEFAULT 0'),('depth','BLOB'),('biomes','TEXT'),('surface_version','INTEGER DEFAULT 1')]:
                if name not in columns:db.execute(f'ALTER TABLE surfaces ADD COLUMN {name} {kind}')
        if preserve:
            from map_history import MapHistory
            self.history=MapHistory(self.path.parent/'historico.sqlite')

    @contextmanager
    def connect(self):
        connection=sqlite3.connect(self.path,timeout=15)
        try:
            if self.preserve:
                connection.execute('PRAGMA journal_mode=WAL')
                connection.execute('PRAGMA synchronous=FULL')
                if self.max_bytes:
                    page=connection.execute('PRAGMA page_size').fetchone()[0]
                    connection.execute('PRAGMA max_page_count='+str(max(16,int(self.max_bytes*.65)//page)))
            with connection:
                yield connection
        except sqlite3.OperationalError as error:
            if self.preserve and getattr(error,'sqlite_errorcode',None)==sqlite3.SQLITE_FULL:
                raise SurfaceQuotaExceeded('Cota do mundo atingida; dados antigos preservados') from error
            raise
        finally:
            connection.close()

    def put(self,dim,x,z,names,heights,biome=None,depth=None,biomes=None,updated=None,surface_version=1):
        palette,ids=np.unique(np.asarray(names,dtype=str),return_inverse=True)
        if self.preserve and self.max_bytes and self.path.stat().st_size>=self.max_bytes*.65:
            raise SurfaceQuotaExceeded('Limite de dados do mundo atingido; nenhum registro antigo foi apagado')
        with self.connect() as db:
            row=(dim,x,z,json.dumps(palette.tolist()),zlib.compress(ids.astype('<u2').tobytes()),
                 zlib.compress(np.asarray(heights,dtype='<i2').tobytes()),biome,time.time() if updated is None else updated,
                 zlib.compress(np.asarray(depth,dtype='u1').tobytes()) if depth is not None else None,
                 json.dumps(biomes) if biomes is not None else None,surface_version)
            db.execute('INSERT OR REPLACE INTO surfaces (dim,x,z,palette,ids,heights,biome,updated,depth,biomes,surface_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       row)
            if self.max_bytes and not self.preserve:
                # Reserve space for SQLite indexes/pages; evict oldest captures, never worlds.
                used=db.execute('SELECT COALESCE(SUM(length(palette)+length(ids)+length(heights)+COALESCE(length(depth),0)+COALESCE(length(biomes),0)+128),0) FROM surfaces').fetchone()[0]
                while used>self.max_bytes*.65:
                    rows=db.execute('SELECT dim,x,z FROM surfaces ORDER BY updated LIMIT 32').fetchall()
                    if not rows:break
                    db.executemany('DELETE FROM surfaces WHERE dim=? AND x=? AND z=?',rows)
                    used=db.execute('SELECT COALESCE(SUM(length(palette)+length(ids)+length(heights)+COALESCE(length(depth),0)+COALESCE(length(biomes),0)+128),0) FROM surfaces').fetchone()[0]
        if self.history:
            try:self.history.record('save' if self.path.name=='superficie.sqlite' else 'capture',row)
            except (sqlite3.Error,OSError,ValueError) as error:
                # History is secondary. Never roll back or drop the authoritative surface for it.
                if not self.history_warned:logging.getLogger(__name__).warning('Histórico indisponível; superfície preservada: %s',error);self.history_warned=True
        if self.max_bytes and not self.preserve and self.path.stat().st_size>self.max_bytes:
            with self.connect() as db:db.execute('VACUUM')

    def entries(self):
        with self.connect() as db:
            rows=db.execute('SELECT dim,x,z,palette,ids,heights,biome,biomes FROM surfaces WHERE surface_version>=?',(self.min_surface_version,)).fetchall()
        return {(d,x,z):self.content_hash(p,ids,h,b,bs) for d,x,z,p,ids,h,b,bs in rows}

    @staticmethod
    def content_hash(palette,ids,heights,biome,biomes):
        return hashlib.sha256((palette+'\0'+(biome or '')+'\0'+(biomes or '')).encode()+ids+heights).hexdigest()[:16]

    def entry_hash(self,dim,x,z):
        with self.connect() as db:
            row=db.execute('SELECT palette,ids,heights,biome,biomes FROM surfaces WHERE dim=? AND x=? AND z=? AND surface_version>=?',(dim,x,z,self.min_surface_version)).fetchone()
        return self.content_hash(*row) if row else None

    def extras(self,dim,x,z):
        with self.connect() as db:row=db.execute('SELECT depth,biomes,updated FROM surfaces WHERE dim=? AND x=? AND z=?',(dim,x,z)).fetchone()
        if not row:return None,None,0
        return (np.frombuffer(zlib.decompress(row[0]),dtype='u1').reshape(16,16) if row[0] else None,
                json.loads(row[1]) if row[1] else None,row[2])

    def height_margin(self,dim,x,z):
        surface=self.get(dim,x,z)
        if not surface:return None
        out=np.pad(surface[1],1,mode='edge').astype(float)
        for dx,dz in [(-1,0),(1,0),(0,-1),(0,1)]:
            neighbor=self.get(dim,x+dx,z+dz)
            if neighbor is None:continue
            if dx==-1:out[1:-1,0]=neighbor[1][:,-1]
            if dx==1:out[1:-1,-1]=neighbor[1][:,0]
            if dz==-1:out[0,1:-1]=neighbor[1][-1,:]
            if dz==1:out[-1,1:-1]=neighbor[1][0,:]
        return out

    def region_arrays(self,dim,rx,rz):
        names=np.full((258,258),'minecraft:air',dtype=object)
        heights=np.full((258,258),-32768,dtype=np.int16)
        depth=np.zeros((258,258),dtype=np.uint8)
        with self.connect() as db:
            rows=db.execute('SELECT x,z,palette,ids,heights,depth FROM surfaces WHERE dim=? AND x BETWEEN ? AND ? AND z BETWEEN ? AND ?',
                            (dim,rx*16-1,rx*16+16,rz*16-1,rz*16+16)).fetchall()
        for x,z,palette,ids,h,d in rows:
            xx=(x-rx*16)*16+1;zz=(z-rz*16)*16+1
            x0=max(0,xx);z0=max(0,zz);x1=min(258,xx+16);z1=min(258,zz+16)
            if x0>=x1 or z0>=z1:continue
            source=np.s_[z0-zz:z1-zz,x0-xx:x1-xx];target=np.s_[z0:z1,x0:x1]
            tile=np.asarray(json.loads(palette))[np.frombuffer(zlib.decompress(ids),dtype='<u2')].reshape(16,16)
            names[target]=tile[source];heights[target]=np.frombuffer(zlib.decompress(h),dtype='<i2').reshape(16,16)[source]
            if d:depth[target]=np.frombuffer(zlib.decompress(d),dtype='u1').reshape(16,16)[source]
        return names,heights,depth

    def get(self,dim,x,z):
        with self.connect() as db:
            row=db.execute('SELECT palette,ids,heights,biome FROM surfaces WHERE dim=? AND x=? AND z=? AND surface_version>=?',(dim,x,z,self.min_surface_version)).fetchone()
        if not row:
            return None
        names=np.asarray(json.loads(row[0]))[np.frombuffer(zlib.decompress(row[1]),dtype='<u2')].reshape(16,16)
        heights=np.frombuffer(zlib.decompress(row[2]),dtype='<i2').reshape(16,16)
        return names,heights,row[3]

    def search(self,query,dimension=0,limit=100):
        with self.connect() as db:
            return [{'x':x*16+8,'z':z*16+8,'biome':biome,'source':'saved'}
                    for x,z,biome in db.execute('SELECT x,z,biome FROM surfaces WHERE dim=? AND biome LIKE ? AND surface_version>=? LIMIT ?',
                                                (dimension,'%'+query+'%',self.min_surface_version,limit))]
