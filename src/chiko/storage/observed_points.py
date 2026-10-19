"""Persistent POIs extracted from already decoded save chunks, never from seed."""
import hashlib
import json
import sqlite3
from pathlib import Path
import numpy as np

DETECTOR_VERSION='blocks-1'
LABELS={'bed':'Cama','nether_portal':'Portal do Nether','end_portal':'Portal do End'}


def point_kind(name):
    namespace,_,name=str(name).partition(':')
    if namespace not in ('minecraft','universal_minecraft'):return None
    if name=='bed' or name.endswith('_bed'):return 'bed'
    if name in ('portal','nether_portal'):return 'nether_portal'
    if name=='end_portal':return 'end_portal'
    return None


def extract_points(chunk,dimension,cx,cz):
    kinds=[point_kind(b.namespaced_name) for b in chunk.block_palette]
    relevant=[i for i,kind in enumerate(kinds) if kind]
    if not relevant:return []
    result=[]
    for sy in sorted(chunk.blocks.sub_chunks):
        blocks=chunk.blocks.get_sub_chunk(sy)
        for x,y,z in np.argwhere(np.isin(blocks,relevant)):
            result.append([kinds[int(blocks[x,y,z])],dimension,cx*16+int(x),int(sy)*16+int(y),cz*16+int(z)])
            if len(result)>=512:return result
    return result


class ObservedPoints:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        db=self.connect()
        try:
            with db:db.execute('CREATE TABLE IF NOT EXISTS chunks(dim INTEGER,cx INTEGER,cz INTEGER,signature TEXT,points TEXT,PRIMARY KEY(dim,cx,cz))')
        finally:db.close()

    def connect(self):
        # A connection per short operation, explicitly closed by each method.
        db=sqlite3.connect(self.path,timeout=15)
        db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
        page=db.execute('PRAGMA page_size').fetchone()[0]
        db.execute('PRAGMA max_page_count='+str(32*1024*1024//page))
        return db

    def signatures(self):
        db=self.connect()
        try:return {(d,x,z):s for d,x,z,s in db.execute('SELECT dim,cx,cz,signature FROM chunks')}
        finally:db.close()

    def put(self,dimension,cx,cz,signature,points):
        db=self.connect()
        try:
            with db:db.execute('INSERT OR REPLACE INTO chunks VALUES(?,?,?,?,?)',(dimension,cx,cz,DETECTOR_VERSION+':'+signature,json.dumps(points,separators=(',',':'))))
        finally:db.close()

    def prune(self,coordinates):
        db=self.connect()
        try:
            removed=[row for row in db.execute('SELECT dim,cx,cz FROM chunks') if tuple(row) not in coordinates]
            with db:db.executemany('DELETE FROM chunks WHERE dim=? AND cx=? AND cz=?',removed)
        finally:db.close()

    def snapshot(self):
        db=self.connect();blocks=set();scanned=0;truncated=False
        try:
            for payload, in db.execute('SELECT points FROM chunks ORDER BY dim,cx,cz'):
                scanned+=1
                decoded=json.loads(payload)
                if len(decoded)>=512:truncated=True
                for point in decoded:
                    if len(blocks)>=20000:truncated=True;break
                    blocks.add(tuple(point))
        finally:db.close()
        points=[]
        while blocks:
            first=blocks.pop();stack=[first];group=[]
            while stack:
                p=stack.pop();group.append(p);kind,d,x,y,z=p
                for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                    neighbor=(kind,d,x+dx,y+dy,z+dz)
                    if neighbor in blocks:blocks.remove(neighbor);stack.append(neighbor)
            first=min(group);kind,d,_,_,_=first
            points.append({'id':'observed-'+hashlib.sha256(repr(first).encode()).hexdigest()[:20],
                'kind':kind,'name':LABELS[kind],'dimension':d,'x':sum(p[2]+.5 for p in group)/len(group),
                'y':sum(p[3] for p in group)/len(group),'z':sum(p[4]+.5 for p in group)/len(group),
                'source':'save','blocks':len(group)})
        points.sort(key=lambda p:p['id'])
        return {'points':points,'scanned_chunks':scanned,'truncated':truncated,'source':'save'}
