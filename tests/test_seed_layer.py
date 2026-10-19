import asyncio
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from aiohttp import CookieJar
from aiohttp.test_utils import TestClient,TestServer
from chiko.cartography.seed_layer import SeedGenerator,seed_number,canonical,render_prediction,NATIVE,metadata

class SeedTests(unittest.TestCase):
    def test_atlas_uses_halo_and_keeps_pixel_art_without_smoothing(self):
        calls=[]
        class Field:
            def __init__(self,*args):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def grid(self,scale,x,y,z,side=64):
                calls.append((scale,x,z,side))
                return np.tile((np.arange(x,x+side)>=0).astype(np.int32),(side,1))
            def name(self,n):return 'forest' if n else 'ocean'
        with patch('chiko.cartography.seed_layer.SeedGenerator',Field):
            a=Image.open(io.BytesIO(render_prediction('1',0,-1,0,style='atlas',smooth=False))).convert('RGBA')
            b=Image.open(io.BytesIO(render_prediction('1',0,-1,0,style='atlas',smooth=True))).convert('RGBA')
        self.assertEqual((4,-68,-4,72),calls[0]);self.assertEqual((256,256),a.size)
        np.testing.assert_array_equal(a,b)

    def test_soft_prediction_interpolates_across_tile_boundary_with_shared_halo(self):
        from chiko.cartography.seed_layer import seed_palette
        class Field:
            def __init__(self,*args):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def grid(self,scale,x,y,z,side=64):return np.tile((np.arange(x,x+side)>=64).astype(np.int32),(side,1))
            def name(self,n):return 'plains' if n else 'ocean'
        with patch('chiko.cartography.seed_layer.SeedGenerator',Field):
            left=Image.open(io.BytesIO(render_prediction('1',0,0,0,smooth=True))).convert('RGB')
            right=Image.open(io.BytesIO(render_prediction('1',0,1,0,smooth=True))).convert('RGB')
            raw=Image.open(io.BytesIO(render_prediction('1',0,0,0,smooth=False))).convert('RGB')
        palette=seed_palette();water=np.array(tuple(bytes.fromhex(palette['identity']['water'][1:])))
        land=np.array(tuple(bytes.fromhex(palette['seed_biomes']['plains'][1:])))
        np.testing.assert_allclose(left.getpixel((255,128)),water*.625+land*.375,atol=1)
        np.testing.assert_allclose(right.getpixel((0,128)),water*.375+land*.625,atol=1)
        self.assertEqual(tuple(water),raw.getpixel((255,128)))
        self.assertEqual((256,256),left.size)

    def test_decimal_64_bits_and_invalid_input(self):
        self.assertEqual(9223372036854775783,seed_number('9223372036854775783'))
        self.assertEqual((1<<64)-1,seed_number('-1'))
        for bad in [True,1.5,'1.5',' 12','1e6','--1',str(1<<64)]:
            with self.assertRaises(ValueError):seed_number(bad)
        self.assertEqual('stony_shore',canonical('minecraft:stone_beach'))
        self.assertFalse(metadata(Path('does-not-exist'))['available'])

    @unittest.skipUnless((NATIVE/'seed-generator.dll').is_file(),'optional Windows seed DLL')
    def test_full_seed_and_native_lifetime(self):
        with SeedGenerator('-1') as negative,SeedGenerator(str((1<<64)-1)) as unsigned:
            np.testing.assert_array_equal(negative.grid(16,-32,16,-32),unsigned.grid(16,-32,16,-32))
        with self.assertRaises(RuntimeError):negative.biome(0,64,0)
        with SeedGenerator('9223372036854775783') as full,SeedGenerator(str(9223372036854775783&0xffffffff)) as low:
            self.assertFalse(np.array_equal(full.grid(16,0,16,0),low.grid(16,0,16,0)))

    @unittest.skipUnless((NATIVE/'seed-generator.dll').is_file(),'optional Windows seed DLL')
    def test_bounded_image_and_invalid_parameters(self):
        data=render_prediction('1234',1,-1,0,64,'paper')
        with Image.open(io.BytesIO(data)) as im:
            self.assertEqual((256,256),im.size);self.assertEqual('WEBP',im.format)
        for bad in [(-1,64,'paper'),(4,64,'paper'),(0,500,'paper'),(0,64,'invalid')]:
            with self.assertRaises(ValueError):render_prediction('1234',bad[0],0,0,bad[1],bad[2])

class SeedHTTP(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from chiko.server import LiveMap,ROOT
        from chiko.storage.session_cache import SessionCache
        self.scratch=tempfile.TemporaryDirectory(prefix='chiko-seed-http-');root=Path(self.scratch.name)
        world=root/'world';world.mkdir();(world/'levelname.txt').write_text('Seed HTTP test',encoding='utf-8')
        config=json.loads((Path(__file__).resolve().parents[1]/'config'/'settings.example.json').read_text(encoding='utf-8-sig'))
        config.update(world=str(world),pin='2468',capture_persistent=False)
        self.root_patch=patch('chiko.server.ROOT',root);self.root_patch.start()
        with patch('chiko.server.SessionCache',side_effect=lambda parent:SessionCache(root/'sessions')):self.live=LiveMap(config)
        self.live.seed_info={'available':True,'experimental':True,'seed':'1234','revision':'test-revision'}
        self.client=TestClient(TestServer(self.live.app()),cookie_jar=CookieJar(unsafe=True));await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close();self.live.close();self.root_patch.stop();self.scratch.cleanup()

    @unittest.skipUnless((NATIVE/'seed-generator.dll').is_file(),'optional Windows seed DLL')
    async def test_real_native_image_via_authenticated_route(self):
        await self.client.post('/api/login',json={'pin':'2468'})
        path='/seed/0/0/-1/0.webp?world='+self.live.world_id()+'&revision=test-revision&y=96'
        response=await self.client.get(path);self.assertEqual(200,response.status)
        with Image.open(io.BytesIO(await response.read())) as image:
            self.assertEqual((256,256),image.size);self.assertEqual('WEBP',image.format)

    async def test_pin_world_dimension_version_validation_and_cache(self):
        path='/seed/0/0/0/0.webp?world='+self.live.world_id()+'&revision=test-revision'
        self.assertEqual(401,(await self.client.get(path)).status)
        await self.client.post('/api/login',json={'pin':'2468'})
        self.assertEqual(409,(await self.client.get(path.replace('test-revision','wrong'))).status)
        self.assertEqual(404,(await self.client.get(path.replace('/seed/0/','/seed/1/'))).status)
        self.assertEqual(400,(await self.client.get(path+'&y=900')).status)
        self.assertEqual(400,(await self.client.get(path+'&palette=invalid')).status)
        self.assertEqual(400,(await self.client.get(path+'&smooth=invalid')).status)
        calls=[]
        def render(*args):calls.append(args);return b'simulated-webp'
        with patch('chiko.server.render_prediction',side_effect=render):
            first=await self.client.get(path);self.assertEqual(200,first.status);await first.read()
            self.assertEqual(1,len(calls));self.assertEqual('image/webp',first.content_type)
            second=await self.client.get(path,headers={'If-None-Match':first.headers['ETag']})
            self.assertEqual(304,second.status);self.assertEqual(1,len(calls))
            changed=await self.client.get(path+'&y=128');await changed.read();self.assertEqual(2,len(calls))
            changed=await self.client.get(path+'&palette=minecraft');await changed.read();self.assertEqual(3,len(calls))
            changed=await self.client.get(path+'&smooth=1');await changed.read();self.assertEqual(4,len(calls));self.assertTrue(calls[-1][-1])

if __name__=='__main__':unittest.main()
