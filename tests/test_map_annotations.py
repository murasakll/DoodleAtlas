import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from map_annotations import AnnotationStore,AnnotationConflict,validate

CELL=dict(kind='road',dimension=0,grid=4,x=-4,z=8,color='#484238',label='Estrada norte')
BUILDING=dict(id='hall',name='Hall',dimension=0,grid=4,display='detailed',icon='house',color='#484238')
PART=CELL|dict(kind='part_floor',buildingId='hall')


class AnnotationTests(unittest.TestCase):
    def test_additive_legacy_migration(self):
        import sqlite3
        from contextlib import closing
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'anotacoes.sqlite';encoded=json.dumps([CELL])
            with closing(sqlite3.connect(path)) as db,db:
                db.execute('CREATE TABLE document(id INTEGER PRIMARY KEY,revision INTEGER NOT NULL,data TEXT NOT NULL)')
                db.execute('INSERT INTO document VALUES(1,7,?)',(encoded,))
            store=AnnotationStore(path);data=store.read()
            self.assertEqual((7,[CELL],[]),(data['revision'],data['cells'],data['structures']))
            with closing(sqlite3.connect(path)) as db:self.assertEqual(encoded,db.execute('SELECT data FROM document').fetchone()[0])
            self.assertEqual(7,AnnotationStore(path).read()['revision'])

    def test_modular_layers_and_view_persistence(self):
        parts=[PART|{'kind':kind} for kind in ('part_floor','part_wall','part_roof','part_table')]
        self.assertEqual(parts,validate(parts,[BUILDING]))
        with self.assertRaises(ValueError):validate(parts)
        with self.assertRaises(ValueError):validate(parts+[PART|{'kind':'part_door'}],[BUILDING])
        for change in [{'buildingId':'missing'},{'grid':8},{'dimension':2}]:
            with self.assertRaises(ValueError):validate([PART|change],[BUILDING])
        with tempfile.TemporaryDirectory() as directory:
            store=AnnotationStore(Path(directory)/'anotacoes.sqlite')
            store.save(0,parts,[BUILDING]);store.save(1,parts,[BUILDING|{'display':'icon'}])
            current=AnnotationStore(store.path).read()
            self.assertEqual(parts,current['cells']);self.assertEqual('icon',current['structures'][0]['display'])
            with self.assertRaises(AnnotationConflict):store.save(2,[CELL])
            with self.assertRaises(ValueError):store.save(2,[PART|{'buildingId':'missing'}],[BUILDING])
            self.assertEqual(current,store.read())

    def test_restart_conflict_and_world_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'a/anotacoes.sqlite';store=AnnotationStore(path)
            self.assertEqual(1,store.save(0,[CELL])['revision'])
            self.assertEqual([CELL],AnnotationStore(path).read()['cells'])
            self.assertEqual(1,store.save(1,[CELL])['revision'])
            with self.assertRaises(AnnotationConflict):store.save(0,[])
            self.assertEqual([CELL],store.read()['cells'])
            self.assertEqual([],AnnotationStore(Path(directory)/'b/anotacoes.sqlite').read()['cells'])

    def test_village_stamps_round_trip_and_layer(self):
        from map_annotations import STAMP_KINDS
        cells=[CELL|{'kind':kind,'x':n*16} for n,kind in enumerate(sorted(STAMP_KINDS))]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'anotacoes.sqlite'
            AnnotationStore(path).save(0,cells)
            self.assertEqual(cells,AnnotationStore(path).read()['cells'])
        with self.assertRaises(ValueError):validate([CELL|{'kind':'well'},CELL|{'kind':'windmill'}])
        self.assertEqual(2,len(validate([CELL,CELL|{'kind':'well'}])))

    def test_background_layer_round_trip(self):
        cells=[CELL,CELL|{'kind':'house'},CELL|{'kind':'background','color':'#c4d8dc'}]
        self.assertEqual(cells,validate(cells))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'anotacoes.sqlite';AnnotationStore(path).save(0,cells)
            self.assertEqual(cells,AnnotationStore(path).read()['cells'])
        with self.assertRaises(ValueError):validate([cells[-1],cells[-1]|{'color':'#ccd0b8'}])
        with self.assertRaises(ValueError):validate([CELL|{'kind':'eraseBackground'}])

    def test_invalid_cells_and_layer_overlap(self):
        for fields in [dict(kind=[]),dict(kind='unknown'),dict(grid=True),dict(dimension=True),dict(x=-3),dict(x=float('nan')),dict(color='red'),dict(label='x\n')]:
            with self.assertRaises(ValueError):validate([CELL|fields])
        with self.assertRaises(ValueError):validate([CELL,CELL|{'kind':'fence'}])
        self.assertEqual(2,len(validate([CELL,CELL|{'kind':'house'}])))


class AnnotationHTTP(unittest.IsolatedAsyncioTestCase):
    async def test_permissions_large_document_and_stale_world(self):
        import server
        from aiohttp.test_utils import TestClient,TestServer
        config=json.loads((server.ROOT/'config.json').read_text(encoding='utf-8-sig'))
        with tempfile.TemporaryDirectory(prefix='chiko-editor-') as directory:
            root=Path(directory);world=root/'world';world.mkdir();(world/'levelname.txt').write_text('Editor test')
            config.update(world=str(world),capture_persistent=True,pin='',allowed_networks=['127.0.0.0/8'])
            with patch('server.ROOT',root):
                live=server.LiveMap(config);client=TestClient(TestServer(live.app()));await client.start_server()
                try:
                    body={'world_id':live.world_id(),'revision':0,'cells':[CELL|{'x':n*4} for n in range(100)]};headers={'X-Host-Token':live.host_token}
                    self.assertEqual(403,(await client.put('/api/annotations',json=body)).status)
                    self.assertEqual(409,(await client.put('/api/annotations',json=body|{'world_id':'old'},headers=headers)).status)
                    self.assertEqual(200,(await client.put('/api/annotations',json=body,headers=headers)).status)
                    result=await (await client.get('/api/annotations')).json();self.assertEqual(100,len(result['cells']))
                    self.assertEqual(409,(await client.put('/api/annotations',json=body,headers=headers)).status)
                    self.assertEqual(400,(await client.put('/api/annotations',json=body|{'revision':1,'cells':[CELL|{'kind':[]}]},headers=headers)).status)
                    self.assertEqual(100,len(live.annotations.read()['cells']))
                    self.assertEqual(403,(await client.put('/api/annotations',json=body,headers=headers|{'Origin':'https://example.invalid'})).status)
                    modular=body|{'revision':1,'structures':[BUILDING],'cells':body['cells']+[PART]}
                    self.assertEqual(200,(await client.put('/api/annotations',json=modular,headers=headers)).status)
                    result=await (await client.get('/api/annotations')).json()
                    self.assertEqual([BUILDING],result['structures']);self.assertEqual(PART,result['cells'][-1])
                    self.assertEqual(409,(await client.put('/api/annotations',json=body|{'revision':2},headers=headers)).status)
                finally:await client.close();live.close()
