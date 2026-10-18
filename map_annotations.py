"""User cartography, independent from observed terrain and Minecraft saves."""
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3

STAMP_KINDS={'campfire', 'windmill', 'bench', 'tent', 'house', 'tree', 'banner', 'well', 'shop', 'flowers', 'stable', 'boulder', 'wagon', 'watchtower', 'townhall', 'garden', 'market', 'library', 'tavern', 'forge', 'bakery', 'dock', 'warehouse', 'animal', 'bridge', 'boat', 'mine', 'pine', 'fountain', 'barn', 'square', 'temple', 'castle', 'lamp'}
PART_LAYERS={'part_floor':'floor','part_wall':'building-wall','part_door':'building-wall','part_window':'building-wall','part_roof':'roof','part_table':'furniture','part_bed':'furniture','part_chest':'furniture','part_chair':'furniture','part_stairs':'furniture'}
KINDS={'ink','road','fence','wall','field','crops','territory','background'}|STAMP_KINDS|PART_LAYERS.keys()
GRIDS={1,2,4,8,16}
LIMIT=20000


def layer(kind):
    return PART_LAYERS.get(kind) or ('line' if kind in ('road','fence','wall') else 'stamp' if kind in STAMP_KINDS else kind)


def validate_structures(structures):
    if not isinstance(structures,list) or len(structures)>256:raise ValueError('Limite de 256 construções por mundo')
    result=[];seen=set()
    for item in structures:
        if not isinstance(item,dict):raise ValueError('Construção inválida')
        ident=item.get('id');name=item.get('name','');dimension=item.get('dimension');grid=item.get('grid');display=item.get('display','detailed');icon=item.get('icon','house');color=item.get('color','#484238')
        if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',ident) or ident in seen:raise ValueError('ID de construção inválido ou repetido')
        if not isinstance(name,str) or len(name)>60 or any(ord(c)<32 for c in name):raise ValueError('Nome de construção inválido')
        if type(dimension) is not int or dimension not in (0,1,2) or type(grid) is not int or grid not in GRIDS:raise ValueError('Dimensão ou grade da construção inválida')
        if not isinstance(display,str) or display not in ('detailed','icon','auto') or not isinstance(icon,str) or icon not in STAMP_KINDS:raise ValueError('Visão ou ícone inválido')
        if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):raise ValueError('Cor inválida')
        seen.add(ident);result.append(dict(id=ident,name=name.strip(),dimension=dimension,grid=grid,display=display,icon=icon,color=color))
    return result


def validate(cells,structures=None):
    if not isinstance(cells,list) or len(cells)>LIMIT:raise ValueError('Limite de 20.000 células por mundo')
    result=[];seen=set();buildings={s['id']:s for s in validate_structures([] if structures is None else structures)}
    for cell in cells:
        if not isinstance(cell,dict):raise ValueError('Célula inválida')
        kind=cell.get('kind');grid=cell.get('grid');d=cell.get('dimension');x=cell.get('x');z=cell.get('z')
        if not isinstance(kind,str) or kind not in KINDS or type(grid) is not int or grid not in GRIDS or type(d) is not int or d not in (0,1,2):raise ValueError('Elemento, grade ou dimensão inválida')
        if any(type(v) is not int or abs(v)>29999900 or v%grid for v in (x,z)):raise ValueError('Coordenada inválida ou fora da grade')
        color=cell.get('color','#484238');label=cell.get('label','')
        if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):raise ValueError('Cor inválida')
        if not isinstance(label,str) or len(label)>60 or any(ord(c)<32 for c in label):raise ValueError('Nome inválido')
        building=cell.get('buildingId')
        if kind in PART_LAYERS:
            if not isinstance(building,str) or building not in buildings:raise ValueError('Peça sem construção válida')
            if buildings[building]['dimension']!=d or buildings[building]['grid']!=grid:raise ValueError('Peça fora da dimensão ou grade da construção')
        elif building is not None:raise ValueError('Somente peças modulares pertencem a construções')
        key=(d,grid,x,z,layer(kind),building)
        if key in seen:raise ValueError('Célula repetida na mesma camada')
        seen.add(key);item=dict(dimension=d,grid=grid,x=x,z=z,kind=kind,color=color,label=label.strip())
        if building is not None:item['buildingId']=building
        result.append(item)
    return result


class AnnotationConflict(Exception):pass


class AnnotationStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(self.connect()) as db,db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS document(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL,data TEXT NOT NULL)')
            if 'structures' not in {row[1] for row in db.execute('PRAGMA table_info(document)')}:db.execute("ALTER TABLE document ADD COLUMN structures TEXT NOT NULL DEFAULT '[]'")
            db.execute("INSERT OR IGNORE INTO document(id,revision,data) VALUES(1,0,'[]')")
            self.revision=db.execute('SELECT revision FROM document WHERE id=1').fetchone()[0]

    def connect(self):
        db=sqlite3.connect(self.path,timeout=5);db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA max_page_count=4096');db.execute('PRAGMA journal_size_limit=1048576');return db

    def read(self):
        with closing(self.connect()) as db:revision,data,structures=db.execute('SELECT revision,data,structures FROM document WHERE id=1').fetchone()
        self.revision=max(self.revision,revision)
        return {'available':True,'version':2,'revision':revision,'cells':json.loads(data),'structures':json.loads(structures),'limit':LIMIT}

    def save(self,revision,cells,structures=None):
        if type(revision) is not int or revision<0:raise ValueError('Revisão inválida')
        normalized=validate_structures([] if structures is None else structures)
        cells=validate(cells,normalized);encoded=json.dumps(cells,ensure_ascii=False,separators=(',',':'));encoded_structures=json.dumps(normalized,ensure_ascii=False,separators=(',',':'))
        if len(encoded.encode())+len(encoded_structures.encode())>3*1024*1024:raise ValueError('Edição ultrapassa 3 MiB')
        with closing(self.connect()) as db,db:
            db.execute('BEGIN IMMEDIATE')
            current,data,old_structures=db.execute('SELECT revision,data,structures FROM document WHERE id=1').fetchone()
            if current!=revision:raise AnnotationConflict('Outro navegador salvou uma edição. Exporte seu JSON antes de descartar e recarregar.')
            if structures is None and old_structures!='[]':raise AnnotationConflict('Atualize a página antes de salvar construções modulares.')
            if data!=encoded or old_structures!=encoded_structures:
                current+=1;db.execute('UPDATE document SET revision=?,data=?,structures=? WHERE id=1',(current,encoded,encoded_structures))
        self.revision=current
        return {'revision':current,'count':len(cells)}
