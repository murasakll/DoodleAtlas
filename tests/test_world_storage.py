import asyncio
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing

import numpy as np
from chiko.storage.surface_store import SurfaceStore,SurfaceQuotaExceeded
from chiko.storage.world_storage import WorldStorage,world_id,copy_verified
from chiko.storage.session_cache import SessionCache,preserve_legacy,LEGACY

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='chiko-storage-test-');self.root=Path(self.temp.name)
        self.world=self.root/'world-a';self.world.mkdir();(self.world/'levelname.txt').write_text('Same name')

    def tearDown(self):self.temp.cleanup()

    def put(self,path,name='minecraft:water',updated=1.,version=2,x=0):
        store=SurfaceStore(path);store.put(0,x,0,np.full((16,16),name),np.full((16,16),62),updated=updated,surface_version=version)
        return store

    def test_verified_copy_wal_and_source_preservation(self):
        path=self.root/'source.sqlite';store=self.put(path)
        db=sqlite3.connect(path);db.execute('PRAGMA journal_mode=WAL')
        db.execute('UPDATE surfaces SET biome=?',('minecraft:ocean',));db.commit()
        original=path.read_bytes()
        try:
            report=copy_verified(path,self.root/'copy.sqlite');self.assertEqual(1,report['count'])
            with closing(sqlite3.connect(self.root/'copy.sqlite')) as copied:self.assertEqual('minecraft:ocean',copied.execute('SELECT biome FROM surfaces').fetchone()[0])
            self.assertEqual(original,path.read_bytes())
        finally:db.close()

    def test_migrate_idempotent_newer_target_and_name_collision(self):
        path=self.root/'data/captures'/world_id(self.world)/'surfaces.sqlite';self.put(path,updated=10.)
        session=self.root/'data/sessions/session-old';(session/'data').mkdir(parents=True)
        (session/'data/cache.json').write_text(json.dumps({'world':str(self.world.resolve()),'renderer':2,'palette':'old','manifest':{},'hashes':{}}))
        save=self.put(session/'data/surfaces.sqlite','minecraft:stone',updated=20.)
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in [path,save.path]}
        world=WorldStorage(self.root,self.world);self.assertEqual('minecraft:water',SurfaceStore(world.capture_path).get(0,0,0)[0][0,0])
        self.assertEqual('minecraft:stone',SurfaceStore(world.saved_path).get(0,0,0)[0][0,0])
        report=json.loads((world.folder/'migracao.json').read_text());self.assertTrue(report['verified']);self.assertEqual(2,len(report['sources']))
        self.put(world.capture_path,'minecraft:sand',updated=1000.)
        WorldStorage(self.root,self.world)
        self.assertEqual('minecraft:sand',SurfaceStore(world.capture_path).get(0,0,0)[0][0,0])
        for p,h in before.items():self.assertEqual(h,hashlib.sha256(p.read_bytes()).hexdigest())
        other=self.root/'world-b';other.mkdir();(other/'levelname.txt').write_text('Same name')
        self.assertNotEqual(world.folder,WorldStorage(self.root,other).folder)

    def test_legacy_sessions_preserved_new_sessions_cleaned(self):
        parent=self.root/'sessions';old=parent/'session-old';old.mkdir(parents=True)
        marker=old/'.session.json';marker.write_text(json.dumps({'owner':LEGACY,'pid':99999999}));(old/'valuable').write_text('keep')
        fresh=SessionCache(parent);fresh.close()
        self.assertTrue((old/'valuable').is_file());self.assertNotEqual(LEGACY,json.loads(marker.read_text())['owner'])
        self.assertFalse(fresh.path.exists())

    def test_invalid_copy_does_not_mark_migration_ready(self):
        source=self.root/'data/captures'/world_id(self.world)/'surfaces.sqlite';source.parent.mkdir(parents=True);source.write_bytes(b'invalid sqlite')
        with self.assertRaises(sqlite3.DatabaseError):WorldStorage(self.root,self.world)
        self.assertEqual(b'invalid sqlite',source.read_bytes())
        self.assertFalse((self.root/'mapas'/world_id(self.world)/'metadados.json').exists())

    def test_quota_does_not_evict_existing_data(self):
        store=SurfaceStore(self.root/'limited.sqlite',max_bytes=65536,preserve=True)
        names=np.array(['minecraft:block_'+str(n) for n in range(256)]).reshape(16,16)
        store.put(0,0,0,names,np.arange(256).reshape(16,16))
        stopped=False
        for x in range(1,150):
            try:store.put(0,x,0,names,np.arange(256).reshape(16,16))
            except (SurfaceQuotaExceeded,sqlite3.OperationalError):stopped=True;break
        self.assertTrue(stopped);self.assertIsNotNone(store.get(0,0,0))

class PersistentAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_restart_survives_session_cleanup_and_rollback_keeps_new_data(self):
        import chiko.server as server
        config=json.loads((Path(__file__).resolve().parents[1]/'config'/'settings.example.json').read_text(encoding='utf-8-sig'))
        with tempfile.TemporaryDirectory(prefix='chiko-app-storage-') as directory:
            root=Path(directory);world=root/'world';world.mkdir();(world/'levelname.txt').write_text('Persistent test')
            config.update(world=str(world),capture_persistent=True)
            with patch('chiko.server.ROOT',root):
                first=server.LiveMap(config.copy())
                first.accept_surface({'surfaceVersion':2,'dimension':0,'x':0,'z':0,'palette':['minecraft:water'],'ids':[0]*256,'heights':[62]*256})
                first.terrain.store.put(0,1,0,np.full((16,16),'minecraft:stone'),np.full((16,16),70))
                session=first.cache.path;database=first.live_store.path
                await first.web_tiles.aclose();first.close()
                self.assertFalse(session.exists());self.assertTrue(database.exists())
                second=server.LiveMap(config.copy())
                self.assertTrue(second.state()['world_storage']['persistent']);self.assertEqual(1,len(second.live_surfaces));self.assertEqual(1,len(second.terrain.manifest['chunks']['0']))
                other=root/'other';other.mkdir();(other/'levelname.txt').write_text('Persistent test')
                with patch.object(second,'start_worker'),patch.object(SessionCache,'watch'):
                    await second.select_world(other)
                    self.assertEqual(0,len(second.live_surfaces));self.assertNotEqual(database,second.live_store.path)
                    await second.select_world(world)
                    self.assertEqual(database,second.live_store.path);self.assertEqual(1,len(second.live_surfaces))
                await second.web_tiles.aclose();second.close()
                config['world_storage']=False
                rollback=server.LiveMap(config.copy());self.assertIsNone(rollback.storage)
                self.assertNotEqual(database,rollback.live_store.path);self.assertTrue(database.exists())
                await rollback.web_tiles.aclose();rollback.close()

if __name__=='__main__':unittest.main()
