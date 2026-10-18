import asyncio
import io
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from surface_store import SurfaceStore
from render_queue import RenderQueue,Rendered
from tile_pipeline import TileIndex,TileCache,TilePipeline,TileChanged,render_base,MAX_LEVEL,TILE_SIZES,source_key


class IndexTests(unittest.TestCase):
    def test_boundary_negative_coordinates_and_unchanged_versions(self):
        index=TileIndex();index.sync({'0':[[15,0,'a'],[16,0,'b'],[-1,-1,'negative']]},{})
        a=index.version(0,0,0,0);b=index.version(0,0,1,0)
        self.assertIsNotNone(index.version(0,0,-1,-1))
        self.assertIsNotNone(index.version(0,MAX_LEVEL,-1,-1))
        self.assertFalse(index.sync({'0':[[15,0,'a'],[16,0,'b'],[-1,-1,'negative']]},{}))
        index.sync({'0':[[15,0,'changed'],[16,0,'b'],[-1,-1,'negative'],[900,900,'far']]},{})
        self.assertNotEqual(a,index.version(0,0,0,0));self.assertNotEqual(b,index.version(0,0,1,0))
        stable=index.version(0,0,0,0)
        index.sync({'0':[[15,0,'changed'],[16,0,'b'],[-1,-1,'negative'],[900,900,'far2']]},{})
        self.assertEqual(stable,index.version(0,0,0,0))
        index.sync({},{});self.assertEqual({},index.manifest())

    def test_cache_reopen_and_accounting_after_eviction(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'tiles.sqlite';cache=TileCache(path,limit=256*1024)
            for i in range(10):cache.put(str(i),Rendered(bytes([i])*20000,str(i)))
            self.assertLessEqual(cache.used,cache.limit*.6)
            again=TileCache(path,limit=256*1024)
            self.assertEqual(cache.used,again.used);self.assertEqual(cache.entries,again.entries)
            self.assertEqual('9',again.get('9').etag)
            db=sqlite3.connect(path)
            try:
                self.assertEqual('ok',db.execute('PRAGMA integrity_check').fetchone()[0])
                total,count=db.execute('SELECT SUM(size),COUNT(*) FROM tiles').fetchone()
                self.assertEqual((again.used,again.entries),(total,count))
            finally:db.close()


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.saved=SurfaceStore(self.root/'save.sqlite');self.live=SurfaceStore(self.root/'live.sqlite',min_surface_version=2)
        self.index=TileIndex();self.queue=RenderQueue(budget_seconds=1,cycle_seconds=.001)
        self.pipeline=TilePipeline(self.index,self.queue,self.saved.path,self.live.path,self.root/'tiles.sqlite','world-a')

    async def asyncTearDown(self):
        await self.pipeline.aclose();self.temp.cleanup()

    def put(self,store,x,z,name,h=62,biome=None):
        store.put(0,x,z,np.full((16,16),name),np.full((16,16),h),biome,surface_version=2)

    def sync(self):
        self.index.sync({'0':[[x,z,h] for (d,x,z),h in self.saved.entries().items()]},self.live.entries())

    async def test_surface_water_transparency_and_save_precedence(self):
        self.put(self.live,0,0,'minecraft:water');self.put(self.saved,1,0,'minecraft:stone',70)
        self.put(self.live,1,0,'minecraft:water');self.put(self.saved,0,0,'minecraft:air',-32768)
        self.sync();result=await self.pipeline.request(0,0,0,0,intensity=0)
        with Image.open(io.BytesIO(result.data)) as raw:im=raw.convert('RGBA')
        self.assertEqual((256,256),im.size)
        self.assertEqual((168,230,245,255),im.getpixel((5,5)))
        self.assertEqual(0,im.getpixel((100,100))[3])
        self.assertNotEqual(im.getpixel((5,5)),im.getpixel((20,5)))
        self.assertEqual(255,im.getpixel((20,5))[3])
        completed=self.queue.completed
        self.assertEqual(result.data,(await self.pipeline.request(0,0,0,0,intensity=0)).data)
        self.assertEqual(completed,self.queue.completed)

    async def test_all_tile_sizes_resolution_negatives_and_cache(self):
        self.put(self.live,-1,-1,'minecraft:water');self.put(self.saved,0,0,'minecraft:stone',70);self.sync()
        for size in TILE_SIZES:
            with self.subTest(size=size):
                result=await self.pipeline.request_sized(0,0,-1,-1,size,intensity=0)
                with Image.open(io.BytesIO(result.data)) as raw:
                    image=raw.convert('RGBA');self.assertEqual((size,size),image.size)
                    self.assertEqual((168,230,245,255),image.getpixel((size-1,size-1)))
                    self.assertEqual(0,image.getpixel((0,0))[3])
                count=self.queue.completed
                again=await self.pipeline.request_sized(0,0,-1,-1,size,intensity=0)
                self.assertEqual(result,again);self.assertEqual(count,self.queue.completed)
        small=await self.pipeline.request_sized(0,0,0,0,64,intensity=0)
        with Image.open(io.BytesIO(small.data)) as raw:self.assertEqual((154,159,159,255),raw.convert('RGBA').getpixel((0,0)))
        with self.assertRaises(ValueError):await self.pipeline.request_sized(0,0,0,0,4096)
        with self.assertRaises(ValueError):source_key(0,MAX_LEVEL,0,0,2048)

    async def test_sized_tile_update_invalidates_region_not_unrelated_region(self):
        self.put(self.live,0,0,'minecraft:water');self.put(self.live,40,0,'minecraft:stone');self.sync()
        first=await self.pipeline.request_sized(0,0,0,0,512,intensity=0)
        distant=await self.pipeline.request_sized(0,0,1,0,512,intensity=0)
        self.put(self.live,0,0,'minecraft:sand');self.sync()
        changed=await self.pipeline.request_sized(0,0,0,0,512,intensity=0)
        self.assertNotEqual(first.etag,changed.etag)
        self.assertEqual(distant.etag,(await self.pipeline.request_sized(0,0,1,0,512,intensity=0)).etag)

    async def test_parent_composition_has_correct_quadrants_and_no_extra_requests(self):
        for x,z,name in [(0,0,'minecraft:water'),(16,0,'minecraft:stone'),(0,16,'minecraft:sand')]:self.put(self.live,x,z,name)
        self.sync();results=await asyncio.gather(self.pipeline.request(0,1,0,0,intensity=0),self.pipeline.request(0,1,0,0,intensity=0))
        self.assertEqual(results[0],results[1]);self.assertEqual(4,self.queue.completed)
        with Image.open(io.BytesIO(results[0].data)) as raw:im=raw.convert('RGBA')
        self.assertEqual((168,230,245,255),im.getpixel((2,2)))
        self.assertEqual(255,im.getpixel((130,2))[3]);self.assertEqual(255,im.getpixel((2,130))[3])
        self.assertEqual(0,im.getpixel((130,130))[3])

    async def test_minecraft_palette_isolated_through_pyramid_and_disk_cache(self):
        self.put(self.live,0,0,'minecraft:water');self.sync()
        paper=await self.pipeline.request(0,1,0,0,intensity=0)
        minecraft=await self.pipeline.request(0,1,0,0,intensity=0,style='minecraft')
        with Image.open(io.BytesIO(paper.data)) as im:self.assertEqual((168,230,245,255),im.convert('RGBA').getpixel((2,2)))
        with Image.open(io.BytesIO(minecraft.data)) as im:
            self.assertEqual((63,118,228,255),im.convert('RGBA').getpixel((2,2)))
            self.assertEqual(0,im.convert('RGBA').getpixel((200,200))[3])
        self.assertNotEqual(paper.etag,minecraft.etag)
        completed=self.queue.completed
        self.assertEqual(minecraft.data,(await self.pipeline.request(0,1,0,0,intensity=0,style='minecraft')).data)
        self.assertEqual(paper.data,(await self.pipeline.request(0,1,0,0,intensity=0)).data)
        self.assertEqual(completed,self.queue.completed)
        with self.assertRaises(ValueError):await self.pipeline.request(0,0,0,0,style='invalid')

    async def test_actual_tint_relief_and_dirty_parent_refresh(self):
        self.put(self.live,0,0,'minecraft:grass_block',70,'minecraft:savanna');self.sync()
        first=await self.pipeline.request(0,1,0,0)
        flat=render_base(self.saved.path,self.live.path,0,0,0,1.5,0)
        with Image.open(io.BytesIO(flat)) as raw:
            self.assertNotEqual((166,181,172),raw.convert('RGBA').getpixel((5,5))[:3])
        self.put(self.live,0,0,'minecraft:water');self.sync()
        changed=await self.pipeline.request(0,1,0,0)
        self.assertNotEqual(first.etag,changed.etag)
        self.assertEqual(4,self.queue.completed)

    async def test_disk_cache_reuse_without_memory_cache(self):
        self.put(self.live,-1,-1,'minecraft:water');self.sync()
        first=await self.pipeline.request(0,0,-1,-1)
        self.queue.cache.clear();self.queue.bytes=0
        again=await self.pipeline.request(0,0,-1,-1)
        self.assertEqual(first,again);self.assertEqual(1,self.queue.completed)

    async def test_change_during_read_is_not_cached_as_old_version(self):
        self.put(self.live,0,0,'minecraft:water');self.sync()
        started=threading.Event();gate=threading.Event()
        def slow(*args):started.set();gate.wait(2);return render_base(*args)
        with patch('tile_pipeline.render_base',side_effect=slow):
            pending=asyncio.create_task(self.pipeline.request(0,0,0,0))
            try:
                for _ in range(100):
                    if started.is_set():break
                    await asyncio.sleep(.005)
                self.assertTrue(started.is_set())
                self.put(self.live,0,0,'minecraft:stone');self.sync();gate.set()
                with self.assertRaises(TileChanged):await pending
                self.assertEqual(0,self.pipeline.cache.entries)
                self.assertFalse(self.queue.cache)
            finally:gate.set();await asyncio.gather(pending,return_exceptions=True)

    async def test_close_waits_for_active_source_reader(self):
        self.put(self.live,0,0,'minecraft:water');self.sync()
        started=threading.Event();gate=threading.Event()
        def slow(*args):started.set();gate.wait(2);return render_base(*args)
        with patch('tile_pipeline.render_base',side_effect=slow):
            pending=asyncio.create_task(self.pipeline.request(0,1,0,0))
            closing=None
            try:
                for _ in range(100):
                    if started.is_set():break
                    await asyncio.sleep(.005)
                self.assertTrue(started.is_set())
                closing=asyncio.create_task(self.pipeline.aclose());await asyncio.sleep(.01)
                self.assertFalse(closing.done());gate.set();await asyncio.wait_for(closing,1)
                self.assertFalse(self.pipeline.jobs);self.assertFalse(self.pipeline.io)
            finally:
                gate.set();await asyncio.gather(pending,*([closing] if closing else []),return_exceptions=True)
