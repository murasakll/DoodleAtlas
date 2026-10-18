import asyncio
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zlib

from aiohttp.test_utils import TestClient,TestServer
import numpy as np
from PIL import Image
from map_history import MapHistory,render_overview
from surface_store import SurfaceStore


def row(name='minecraft:water'):
    return (0,0,0,json.dumps([name]),zlib.compress(bytes(512)),zlib.compress(np.full((16,16),62,dtype='<i2').tobytes()),None,time.time(),None,None,2)


class HistoryTests(unittest.TestCase):
    def test_content_dedup_revert_and_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            history=MapHistory(Path(directory)/'history.sqlite')
            self.assertTrue(history.record('capture',row()))
            self.assertFalse(history.record('capture',row()))
            history.record('capture',row('minecraft:stone'));history.record('capture',row())
            self.assertEqual(3,history.status(True)['events'])
            with history.connect() as db:self.assertEqual(2,db.execute('SELECT count(*) FROM versions').fetchone()[0])
            history.configure({'enabled':False})
            self.assertFalse(history.record('capture',row('minecraft:sand')))
            with history.connect() as db:db.execute('UPDATE events SET at=?',(time.time()-86400*8,))
            history.configure({'retention_days':1})
            self.assertEqual(0,history.status(True)['events'])
            with history.connect() as db:self.assertEqual(0,db.execute('SELECT count(*) FROM versions').fetchone()[0])
            with self.assertRaises(ValueError):history.configure({'limit_mb':1024})

    def test_frame_dedup_and_payload_quota(self):
        with tempfile.TemporaryDirectory() as directory:
            history=MapHistory(Path(directory)/'history.sqlite');history.configure({'limit_mb':8})
            first=history.add_frame(0,b'a'*1500000,{'width':768,'height':768})
            self.assertEqual(first,history.add_frame(0,b'a'*1500000,{}))
            history.add_frame(0,b'b'*1500000,{});history.add_frame(0,b'c'*1500000,{})
            self.assertIsNone(history.frame(first))
            self.assertLessEqual(len(history.status(True)['frames']),2)
            with history.connect() as db:self.assertEqual('ok',db.execute('PRAGMA integrity_check').fetchone()[0])

    def test_identical_pixels_with_changed_extent_are_new_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            history=MapHistory(Path(directory)/'history.sqlite')
            first=history.add_frame(0,b'ocean',{'min_x':0,'max_x':16,'min_z':0,'max_z':16})
            second=history.add_frame(0,b'ocean',{'min_x':1000,'max_x':1016,'min_z':0,'max_z':16})
            self.assertNotEqual(first,second)

    def test_overview_bounds_saved_priority_water_and_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);saved=SurfaceStore(root/'saved.sqlite');live=SurfaceStore(root/'live.sqlite')
            live.put(0,-1,0,np.full((16,16),'minecraft:stone'),np.full((16,16),62),surface_version=2)
            saved.put(0,-1,0,np.full((16,16),'minecraft:water'),np.full((16,16),62))
            data,meta=render_overview(saved.path,live.path,0,threading.Event())
            with Image.open(io.BytesIO(data)) as image:
                self.assertEqual((16,16),image.size);r,g,b,a=image.convert('RGBA').getpixel((8,8));self.assertGreater(g,r);self.assertGreater(b,r);self.assertEqual(255,a)
            self.assertEqual(-16,meta['min_x']);self.assertEqual(0,meta['max_x'])
            cancel=threading.Event();cancel.set()
            with self.assertRaises(InterruptedError):render_overview(saved.path,live.path,0,cancel)
            with self.assertRaises(LookupError):render_overview(saved.path,live.path,1,threading.Event())

    def test_history_failure_preserves_current_surface(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            store=SurfaceStore(Path(directory)/'superficie.sqlite',preserve=True)
            with patch.object(store.history,'record',side_effect=sqlite3.OperationalError('disk full')):
                with self.assertLogs('surface_store',level='WARNING'):
                    store.put(0,0,0,np.full((16,16),'minecraft:water'),np.full((16,16),62))
            self.assertEqual('minecraft:water',store.get(0,0,0)[0][0,0])


class HistoryAPI(unittest.IsolatedAsyncioTestCase):
    async def test_capture_permissions_world_and_image(self):
        import server
        config=json.loads((server.ROOT/'config.json').read_text(encoding='utf-8-sig'))
        with tempfile.TemporaryDirectory(prefix='chiko-history-') as directory:
            root=Path(directory);world=root/'world';world.mkdir();(world/'levelname.txt').write_text('Test')
            config.update(world=str(world),capture_persistent=True,pin='',allowed_networks=['127.0.0.0/8'])
            with patch('server.ROOT',root):
                live=server.LiveMap(config);client=TestClient(TestServer(live.app()));await client.start_server()
                try:
                    live.terrain.store.put(0,0,0,np.full((16,16),'minecraft:water'),np.full((16,16),62))
                    self.assertEqual(1,live.history.status(True)['events'])
                    live.history_tick();self.assertIsNone(getattr(live,'history_job',None))
                    world_id=live.world_id();headers={'X-Host-Token':live.host_token};body={'world_id':world_id,'dimension':0}
                    self.assertEqual(403,(await client.post('/api/history/capture',json=body)).status)
                    self.assertEqual(409,(await client.post('/api/history/capture',json=body|{'world_id':'old'},headers=headers)).status)
                    self.assertEqual(202,(await client.post('/api/history/capture',json=body,headers=headers)).status)
                    await asyncio.wait_for(live.history_job['task'],5)
                    data=await (await client.get('/api/history')).json();self.assertEqual(1,len(data['frames']))
                    url='/api/history/frames/'+str(data['frames'][0]['id'])+'.webp?world_id='+world_id
                    response=await client.get(url);self.assertEqual(200,response.status)
                    with Image.open(io.BytesIO(await response.read())) as image:self.assertEqual((16,16),image.size)
                    self.assertEqual(304,(await client.get(url,headers={'If-None-Match':response.headers['ETag']})).status)
                    self.assertEqual(403,(await client.post('/api/history/settings',json={'world_id':world_id,'settings':{'enabled':False}})).status)
                    self.assertEqual(200,(await client.post('/api/history/settings',json={'world_id':world_id,'settings':{'enabled':False}},headers=headers)).status)
                    live.terrain.store.put(0,0,0,np.full((16,16),'minecraft:stone'),np.full((16,16),62))
                    self.assertEqual(1,live.history.status(True)['events'])
                    change=await client.get('/api/history/changes/1.webp?world_id='+world_id)
                    self.assertEqual(200,change.status)
                    with Image.open(io.BytesIO(await change.read())) as image:
                        r,g,b,a=image.convert('RGBA').getpixel((8,8));self.assertGreater(b,r);self.assertEqual(255,a)
                finally:await client.close();live.close()
