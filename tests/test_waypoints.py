import asyncio
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from aiohttp import CookieJar
from aiohttp.test_utils import TestClient, TestServer
from waypoints import WaypointStore, WaypointLimit


class Waypoints(unittest.TestCase):
    def test_persistence_validation_limit_and_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'one/waypoints.sqlite'
            store=WaypointStore(path)
            point=store.create(dict(name=' Ponte ',x=-16,z=32,dimension=0))
            self.assertEqual('Ponte',point['name'])
            self.assertEqual(store.snapshot,WaypointStore(path).snapshot)
            self.assertEqual([],WaypointStore(Path(directory)/'two/waypoints.sqlite').snapshot['points'])
            for change in [dict(name=' '),dict(name='a\n'),dict(x=float('nan')),dict(x=True),dict(z=30000001),dict(dimension=True),dict(dimension=3)]:
                with self.assertRaises(ValueError):store.create(dict(name='a',x=0,z=0,dimension=0)|change)
            store.limit=1
            with self.assertRaises(WaypointLimit):store.create(dict(name='a',x=0,z=0,dimension=0))
            store.delete(point['id'])
            self.assertEqual([],WaypointStore(path).snapshot['points'])
            self.assertEqual(2,store.snapshot['revision'])
            with self.assertRaises(KeyError):store.delete(point['id'])
            with closing(sqlite3.connect(path)) as db:self.assertEqual('ok',db.execute('PRAGMA integrity_check').fetchone()[0])

    def test_concurrent_creates_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            store=WaypointStore(Path(directory)/'points.sqlite');store.limit=10
            def create(n):
                try:store.create(dict(name=str(n),x=n,z=0,dimension=0));return True
                except WaypointLimit:return False
            with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(create,range(20)))
            self.assertEqual(10,sum(results));self.assertEqual(10,len(store.snapshot['points']))


class WaypointAPI(unittest.IsolatedAsyncioTestCase):
    async def test_auth_world_guard_sse_and_restart(self):
        import server
        config=json.loads((server.ROOT/'config.json').read_text(encoding='utf-8-sig'))
        with tempfile.TemporaryDirectory(prefix='chiko-waypoints-') as directory:
            root=Path(directory);world=root/'world';world.mkdir();(world/'levelname.txt').write_text('Test')
            config.update(world=str(world),capture_persistent=True,pin='123456',allowed_networks=['127.0.0.0/8'])
            with patch('server.ROOT',root):
                live=server.LiveMap(config.copy())
                first=TestClient(TestServer(live.app()),cookie_jar=CookieJar(unsafe=True))
                second=TestClient(TestServer(live.app()),cookie_jar=CookieJar(unsafe=True))
                await first.start_server();await second.start_server()
                try:
                    body=dict(world_id=live.world_id(),name='Shared bridge',x=1,z=-2,dimension=0)
                    self.assertEqual(401,(await first.post('/api/waypoints',json=body)).status)
                    for client in (first,second):self.assertEqual(200,(await client.post('/api/login',json={'pin':'123456'})).status)
                    events=await second.get('/api/events')
                    async def event():
                        while True:
                            line=await asyncio.wait_for(events.content.readline(),3)
                            if line.startswith(b'data:'):return json.loads(line[5:])
                    await event()
                    reply=await first.post('/api/waypoints',json=body);self.assertEqual(200,reply.status)
                    data=await reply.json();point=data['points'][0]
                    received=await event();self.assertEqual(point,received['shared_waypoints']['points'][0])
                    self.assertEqual(point,(await (await second.get('/api/state')).json())['shared_waypoints']['points'][0])
                    self.assertEqual(409,(await first.post('/api/waypoints',json=body|{'world_id':'stale'})).status)
                    self.assertEqual(400,(await first.post('/api/waypoints',json=body|{'x':True})).status)
                    self.assertEqual(403,(await first.post('/api/waypoints',json=body,headers={'Origin':'http://other.invalid'})).status)
                    events.close()
                    self.assertEqual(1,len(WaypointStore(live.shared_store.path).snapshot['points']))
                    self.assertEqual(200,(await second.delete('/api/waypoints/'+point['id'],params={'world_id':live.world_id()})).status)
                    self.assertEqual([],live.shared_store.snapshot['points'])
                    # No PIN: a LAN viewer cannot write without the loopback host token.
                    live.config['pin']=''
                    self.assertEqual(403,(await first.post('/api/waypoints',json=body)).status)
                    self.assertEqual(200,(await first.post('/api/waypoints',json=body,headers={'X-Host-Token':live.host_token})).status)
                finally:
                    await first.close();await second.close();live.close()
                restarted=server.LiveMap(config.copy())
                try:
                    self.assertEqual('Shared bridge',restarted.state()['shared_waypoints']['points'][0]['name'])
                    other=root/'other-world';other.mkdir();(other/'levelname.txt').write_text('Test')
                    with patch.object(restarted,'start_worker'),patch.object(server.SessionCache,'watch'):
                        await restarted.select_world(other)
                        self.assertEqual([],restarted.state()['shared_waypoints']['points'])
                        await restarted.select_world(world)
                        self.assertEqual(1,len(restarted.state()['shared_waypoints']['points']))
                finally:
                    await restarted.web_tiles.aclose();restarted.close()
