"""Additive, verified migration of derived surfaces, never Minecraft LevelDB."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
from contextlib import closing

from chiko.storage.surface_store import SurfaceStore

COLUMNS=('dim','x','z','palette','ids','heights','biome','updated','depth','biomes','surface_version')
DEFAULTS={'updated':0.,'depth':None,'biomes':None,'surface_version':1}

def world_id(world):return hashlib.sha256(str(Path(world).resolve()).encode()).hexdigest()

def atomic_json(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temporary.replace(path)

def row_hash(row):
    h=hashlib.sha256()
    for value in row:
        if isinstance(value,bytes):data=b'b'+value
        else:data=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()
        h.update(len(data).to_bytes(8,'little'));h.update(data)
    return h.hexdigest()

def fingerprint(db,columns):
    result={}
    sql='SELECT '+','.join('"'+c.replace('"','""')+'"' for c in columns)+' FROM surfaces ORDER BY dim,x,z'
    for row in db.execute(sql):result[tuple(row[:3])]=row_hash(row)
    return result

def digest_rows(rows):
    h=hashlib.sha256()
    for key,value in sorted(rows.items()):h.update((str(key)+':'+value+'\n').encode())
    return {'count':len(rows),'sha256':h.hexdigest()}

def copy_verified(source,target):
    """SQLite backup with source snapshot held through count/checksum verification."""
    with closing(sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True,timeout=15)) as src,closing(sqlite3.connect(target)) as dst:
        src.execute('BEGIN');src.execute('SELECT count(*) FROM surfaces').fetchone()
        columns=[r[1] for r in src.execute('PRAGMA table_info(surfaces)')]
        if not set(columns)<=set(COLUMNS):raise ValueError('Colunas de captura desconhecidas: migração interrompida')
        src.backup(dst,pages=128,sleep=.01)
        if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Cópia SQLite inconsistente')
        before=digest_rows(fingerprint(src,columns));after=digest_rows(fingerprint(dst,columns))
        if before!=after:raise ValueError('Contagem/checksum divergentes na cópia')
        src.rollback()
        return before

def merge_verified(source,target,kind):
    """Merge a verified scratch copy. Newer target records are never rolled back."""
    store=SurfaceStore(target,preserve=True)
    with closing(sqlite3.connect(source)) as incoming:
        present=[r[1] for r in incoming.execute('PRAGMA table_info(surfaces)')]
        rows=[]
        for record in incoming.execute('SELECT * FROM surfaces'):
            values=dict(zip(present,record));rows.append(tuple(values.get(c,DEFAULTS.get(c)) for c in COLUMNS))
    with store.connect() as dst:
        expected=fingerprint(dst,COLUMNS)
        ranks={tuple(r[:3]):((int(r[4] or 1) if kind=='capture' else 0),float(r[3] or 0)) for r in dst.execute('SELECT dim,x,z,updated,surface_version FROM surfaces')}
        for row in rows:
            key=tuple(row[:3]);rank=((int(row[10] or 1) if kind=='capture' else 0),float(row[7] or 0))
            if key in ranks and rank<ranks[key]:continue
            dst.execute('INSERT OR REPLACE INTO surfaces ('+','.join(COLUMNS)+') VALUES ('+','.join('?' for _ in COLUMNS)+')',row)
            ranks[key]=rank;expected[key]=row_hash(row)
        actual=fingerprint(dst,COLUMNS)
        if digest_rows(actual)!=digest_rows(expected):raise ValueError('Verificação do banco migrado falhou')
        if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Integridade do banco migrado falhou')
        return digest_rows(actual)

class WorldStorage:
    def __init__(self,project,world,limit_mb=512):
        self.project=Path(project).resolve();self.world=Path(world).resolve();self.id=world_id(world)
        self.folder=self.project/'mapas'/self.id;self.folder.mkdir(parents=True,exist_ok=True)
        self.saved_path=self.folder/'superficie.sqlite';self.capture_path=self.folder/'capturas.sqlite'
        self.limit_bytes=max(32,int(limit_mb))*1024*1024
        try:
            previous=json.loads((self.folder/'metadados.json').read_text(encoding='utf-8'))
            quota=previous.get('quota_bytes')
            if isinstance(quota,int) and 32*1024*1024<=quota<=8192*1024*1024:self.limit_bytes=quota
        except (OSError,ValueError):pass
        self.last_stats=0.;self.cached_stats={}
        self.quota_blocked=False
        self.prepare()

    def legacy_sources(self):
        capture=self.project/'data'/'captures'/self.id/'surfaces.sqlite'
        if capture.is_file():yield 'capture',capture
        roots=[self.project]+sorted((self.project/'data'/'sessions').glob('session-*'))
        for root in roots:
            cache=root/'data'/'cache.json';state=root/'data'/'terrain-state.json'
            belongs=False
            try:belongs=json.loads(cache.read_text(encoding='utf-8')).get('world')==str(self.world)
            except (OSError,ValueError):pass
            try:belongs|=json.loads(state.read_text(encoding='utf-8')).get('world_id')==self.id
            except (OSError,ValueError):pass
            if not belongs:continue
            for kind,name in [('save','surfaces.sqlite'),('capture','live.sqlite')]:
                path=root/'data'/name
                if path.is_file():yield kind,path

    def prepare(self):
        reports=[]
        for path in [self.saved_path,self.capture_path]:SurfaceStore(path,preserve=True)
        for kind,source in self.legacy_sources():
            # Temporary SQLite copy only; old databases/sessions stay at their paths.
            with tempfile.TemporaryDirectory(prefix='migration-',dir=self.folder) as scratch:
                stage=Path(scratch).resolve()
                assert stage.parent==self.folder.resolve()
                snapshot=stage/'source.sqlite'
                verified=copy_verified(source,snapshot)
                merged=merge_verified(snapshot,self.capture_path if kind=='capture' else self.saved_path,kind)
                reports.append({'source':str(source),'kind':kind,'verified_copy':verified,'merged_database':merged})
        atomic_json(self.folder/'migracao.json',{'verified':True,'time':time.time(),'sources_preserved':True,'sources':reports})
        meta_path=self.folder/'metadados.json'
        try:meta=json.loads(meta_path.read_text(encoding='utf-8'))
        except (OSError,ValueError):meta={}
        try:
            import amulet_nbt
            tag=amulet_nbt.load((self.world/'level.dat').read_bytes()[8:],compressed=False,little_endian=True).compound
            seed=str(tag['RandomSeed'].py_int);version=[int(v.py_int) for v in tag['lastOpenedWithVersion']][:4]
        except Exception:seed=None;version=None
        try:name=(self.world/'levelname.txt').read_text(encoding='utf-8').strip()
        except OSError:name=self.world.name
        meta.update(id=self.id,name=name,seed=seed,edition='Bedrock',version=version,world_path=str(self.world),created=meta.get('created',time.time()),updated=time.time(),
                    quota_bytes=self.limit_bytes,ready=True,tiles='Temporary session cache; rebuilt on demand',waypoints='chiko.storage.waypoints.sqlite; shared annotations, WAL + FULL; personal annotations remain in browser')
        atomic_json(meta_path,meta)
        # Reader metadata is small. Do not copy old PNGs, snapshots or game files.
        if not (self.folder/'leitor.json').exists():
            candidates=[]
            for _,source in self.legacy_sources():
                if source.name!='surfaces.sqlite' or source.parent.parent.name=='captures':continue
                cache=source.parent/'cache.json'
                try:
                    value=json.loads(cache.read_text(encoding='utf-8'))
                    if value.get('world')==str(self.world):candidates.append((cache.stat().st_mtime,value))
                except (OSError,ValueError):pass
            if candidates:atomic_json(self.folder/'leitor.json',max(candidates,key=lambda v:v[0])[1])

    def stats(self):
        if time.monotonic()-self.last_stats<5:return self.cached_stats
        files=[p for p in self.folder.iterdir() if p.is_file()]
        size=0
        for p in files:
            try:size+=p.stat().st_size
            except FileNotFoundError:pass
        saved=self.saved_path.stat().st_size;capture=self.capture_path.stat().st_size
        pressure=max(size/(self.limit_bytes*.65),saved/(self.limit_bytes*.75*.65),capture/(self.limit_bytes*.25*.65))
        self.cached_stats={'persistent':True,'world_id':self.id,'folder':'mapas/'+self.id,'bytes':size,'limit_bytes':self.limit_bytes,
                           'near_limit':pressure>=.8,'quota_reached':self.quota_blocked or pressure>=1}
        self.last_stats=time.monotonic();return self.cached_stats
