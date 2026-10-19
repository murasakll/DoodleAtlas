import io
import tempfile
import unittest
from pathlib import Path
import numpy as np
from leveldb import LevelDB
from chiko.cartography.relief import hillshade
from chiko.storage.surface_store import SurfaceStore
from chiko.storage.snapshot_db import snapshot


class Revision(unittest.TestCase):
    def test_saved_surface_is_authoritative_even_against_new_capture(self):
        from chiko.server import LiveMap
        with tempfile.TemporaryDirectory() as folder:
            live=LiveMap.__new__(LiveMap)
            live.live_store=SurfaceStore(Path(folder)/'capture.sqlite')
            class Terrain:pass
            live.terrain=Terrain();live.terrain.store=SurfaceStore(Path(folder)/'saved.sqlite')
            names=np.full((16,16),'minecraft:stone');h=np.full((16,16),70)
            live.live_store.put(0,0,0,names,h,updated=10)
            live.terrain.store.put(0,0,0,names,h+1,updated=20)
            self.assertEqual(71,live.surface(0,0,0)[0][1][0,0])
            live.live_store.put(0,0,0,names,h+2,updated=30)
            self.assertEqual(71,live.surface(0,0,0)[0][1][0,0])

    def test_legacy_seabed_hidden_and_recapture_does_not_change_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'capture.sqlite'
            store=SurfaceStore(path,min_surface_version=2)
            names=np.full((16,16),'minecraft:gravel');h=np.full((16,16),53)
            store.put(0,0,0,names,h)
            self.assertIsNone(store.get(0,0,0));self.assertEqual({},store.entries())
            store.put(0,0,0,np.full((16,16),'minecraft:water'),h+9,surface_version=2,updated=10)
            first=store.entry_hash(0,0,0)
            store.put(0,0,0,np.full((16,16),'minecraft:water'),h+9,surface_version=2,updated=30)
            self.assertEqual(first,store.entries()[(0,0,0)])

    def test_surface_water_does_not_show_depth(self):
        from chiko.world.terrain import relief_image
        names=np.full((16,16),'minecraft:water');h=np.full((16,16),62)
        a=np.asarray(relief_image(names,h,depth=np.zeros((16,16))))
        b=np.asarray(relief_image(names,h,depth=np.full((16,16),60)))
        np.testing.assert_array_equal(a,b)

    def test_flat_and_unknown_have_no_false_cliffs(self):
        h=np.full((18,18),70.)
        np.testing.assert_allclose(hillshade(h),1)
        h[:,9:]=-32768
        np.testing.assert_allclose(hillshade(h),1)

    def test_adjacent_chunks_equal_joined_hillshade(self):
        z,x=np.indices((16,32));h=30+np.sin(x/3)*4+z*.7
        padded=np.pad(h,1,mode='edge')
        joined=hillshade(padded)
        a=hillshade(padded[:,:18]);b=hillshade(padded[:,16:])
        np.testing.assert_allclose(np.concatenate([a,b],axis=1),joined,atol=1e-12)

    def test_capture_reopen_preserves_depth_biomes_and_time(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'surfaces.sqlite';store=SurfaceStore(path,1024*1024)
            names=np.full((16,16),'minecraft:water');heights=np.full((16,16),63)
            store.put(0,-1,2,names,heights,'minecraft:ocean',depth=np.full((16,16),12),biomes=['minecraft:ocean']*16,updated=1234)
            reopened=SurfaceStore(path)
            np.testing.assert_array_equal(reopened.get(0,-1,2)[0],names)
            depth,biomes,stamp=reopened.extras(0,-1,2)
            self.assertEqual(12,depth[0,0]);self.assertEqual(16,len(biomes));self.assertEqual(1234,stamp)

    def test_region_halo_carries_neighbor_and_missing_data(self):
        with tempfile.TemporaryDirectory() as folder:
            store=SurfaceStore(Path(folder)/'test.sqlite')
            for x,height in [(15,70),(16,80)]:store.put(0,x,0,np.full((16,16),'minecraft:stone'),np.full((16,16),height))
            _,h,_=store.region_arrays(0,0,0)
            self.assertEqual(70,h[1,256]);self.assertEqual(80,h[1,257]);self.assertEqual(-32768,h[1,1])

    def test_actual_leveldb_recovers_copied_truncated_wal(self):
        # Real LevelDB engine; still not evidence about a live Minecraft writer.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);world=root/'world';world.mkdir()
            (world/'level.dat').write_bytes(b'test');(world/'levelname.txt').write_text('test')
            db=LevelDB(str(world/'db'),create_if_missing=True)
            try:
                db.put(b'first',b'committed-value')
                db.put(b'second',b'x'*1000)
                db.close();db=None
                copied=snapshot(world,root/'copy')
                wal=list((copied/'db').glob('*.log'))
                self.assertTrue(wal)
                last=wal[-1]
                with last.open('r+b') as stream:stream.truncate(max(0,last.stat().st_size-3))
                recovered=LevelDB(str(copied/'db'))
                try:self.assertEqual(b'committed-value',recovered.get(b'first'))
                finally:recovered.close()
            finally:
                if db is not None:db.close()
