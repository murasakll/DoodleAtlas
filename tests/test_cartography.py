import io
from pathlib import Path
import tempfile
import unittest
import json
import time
from unittest.mock import patch
import numpy as np
from PIL import Image
from chiko.cartography.atlas import draw_atlas,PAPER,INK,FAINT
from chiko.storage.surface_store import SurfaceStore
from chiko.cartography.tile_pipeline import render_base
from chiko.cartography.antique_art import render_observed,sheets,quarter_uv,ASSETS


def assert_ink_palette(test,pixels):
    test.assertTrue(np.all(pixels[:,:,3]==255))
    rgb=pixels[:,:,:3].astype(float)
    # Original PNG opacity is preserved: shades must remain on the ink/paper line.
    weight=(rgb[:,:,0]-INK[0])/(PAPER[0]-INK[0])
    test.assertTrue(np.all((weight>=0)&(weight<=1)))
    for channel in (1,2):
        expected=INK[channel]+weight*(PAPER[channel]-INK[channel])
        test.assertLessEqual(np.max(np.abs(rgb[:,:,channel]-expected)),1.5)


class CartographyTests(unittest.TestCase):
    def test_observed_roof_footprint_and_tile_seam(self):
        names=np.full((288,544),'minecraft:oak_leaves',dtype=object);heights=np.full(names.shape,80)
        names[100:120,250:280]='minecraft:oak_planks';heights[100:120,250:280]=84
        whole=np.asarray(render_observed(names,heights))
        self.assertTrue(np.all(whole[85:102,236:262,:3]==(224,217,201)))
        left=np.asarray(render_observed(names[:,:288],heights[:,:288]))
        right=np.asarray(render_observed(names[:,256:],heights[:,256:],1,0))
        np.testing.assert_array_equal(whole,np.concatenate((left,right),axis=1))

    def test_unknown_is_transparent_and_not_a_coast(self):
        names=np.full((258,258),'minecraft:air',dtype=object);heights=np.full((258,258),-32768)
        self.assertEqual(0,np.asarray(draw_atlas(names,heights))[:,:,3].sum())
        names[1:17,1:17]='minecraft:grass_block';heights[1:17,1:17]=64
        pixels=np.asarray(draw_atlas(names,heights))
        self.assertTrue(np.all(pixels[:16,:16]==PAPER))
        self.assertEqual(0,pixels[16:,:,3].sum())

    def test_ocean_coast_halo_and_monochrome(self):
        names=np.full((258,258),'minecraft:water',dtype=object);heights=np.full((258,258),62)
        names[:,:257]='minecraft:grass_block';heights[:,:257]=64
        pixels=np.asarray(draw_atlas(names,heights))
        self.assertTrue(np.all(pixels[:,-1]==INK))
        assert_ink_palette(self,pixels)

    def test_licensed_symbols_are_deterministic_and_require_data(self):
        names=np.full((258,258),'minecraft:oak_leaves',dtype=object);heights=np.full((258,258),80)
        a=np.asarray(draw_atlas(names,heights,-2,3));b=np.asarray(draw_atlas(names,heights,-2,3))
        np.testing.assert_array_equal(a,b);self.assertGreater(np.sum(a[:,:,0]<200),100)
        heights[:]=-32768;self.assertEqual(0,np.asarray(draw_atlas(names,heights,-2,3))[:,:,3].sum())

    def test_pipeline_save_priority_and_normal_mode_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);saved=SurfaceStore(root/'save.sqlite');live=SurfaceStore(root/'live.sqlite')
            live.put(0,0,0,np.full((16,16),'minecraft:stone'),np.full((16,16),140),surface_version=2)
            saved.put(0,0,0,np.full((16,16),'minecraft:water'),np.full((16,16),62))
            with Image.open(io.BytesIO(render_base(saved.path,live.path,0,0,0,1.5,.8,style='atlas'))) as image:
                pixels=np.asarray(image.convert('RGBA'));self.assertEqual((256,256),image.size)
                assert_ink_palette(self,pixels[:16,:16])
                self.assertEqual(0,pixels[20,20,3])
            with Image.open(io.BytesIO(render_base(saved.path,live.path,0,0,0,1.5,.8,style='minecraft'))) as image:
                r,g,b,a=image.convert('RGBA').getpixel((8,8));self.assertGreater(b,r);self.assertEqual(255,a)

    def test_assets_and_all_quarter_addresses(self):
        import itertools
        import hashlib
        manifest=json.loads((ASSETS/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(25,len(sheets()))
        for entry in manifest['files'].values():
            self.assertEqual(entry['sha256'],hashlib.sha256((ASSETS/entry['file']).read_bytes()).hexdigest())
        for qx,qz in itertools.product((0,1),repeat=2):
            for flags in itertools.product((False,True),repeat=5):
                u,v=quarter_uv(qx,qz,*flags);self.assertIn(u,range(4));self.assertIn(v,range(6))

    def test_neighbor_tiles_match_one_wide_render_with_negative_origin(self):
        names=np.full((288,544),'minecraft:oak_leaves',dtype=object)
        heights=np.full(names.shape,80,dtype=np.int16)
        names[:,240:320]='minecraft:water';heights[:,240:320]=62
        names[160:,:160]='minecraft:sand';heights[160:,:160]=64
        heights[200:220,350:390]=-32768
        whole=np.asarray(render_observed(names,heights,-1,2))
        left=np.asarray(render_observed(names[:,:288],heights[:,:288],-1,2))
        right=np.asarray(render_observed(names[:,256:],heights[:,256:],0,2))
        np.testing.assert_array_equal(whole,np.concatenate((left,right),axis=1))
        np.testing.assert_array_equal(whole[:,:,3]!=0,heights[16:-16,16:-16]!=-32768)

    def test_forest_biome_does_not_invent_trees_on_cleared_land(self):
        names=np.full((288,288),'minecraft:grass_block',dtype=object);heights=np.full(names.shape,64)
        with patch('chiko.cartography.antique_art._compose',return_value='captured') as compose:
            render_observed(names,heights,biomes=np.full(names.shape,'forest',dtype=object))
        self.assertEqual({'plains'},set(compose.call_args.args[0].flat))


class AtlasHTTP(unittest.IsolatedAsyncioTestCase):
    async def test_atlas_route_and_etag(self):
        import chiko.server as server
        from aiohttp.test_utils import TestClient,TestServer
        config=json.loads((Path(__file__).resolve().parents[1]/'config'/'settings.example.json').read_text(encoding='utf-8-sig'))
        with tempfile.TemporaryDirectory(prefix='chiko-atlas-http-') as directory:
            root=Path(directory);world=root/'world';world.mkdir();(world/'levelname.txt').write_text('Atlas test')
            config.update(world=str(world),capture_persistent=False,pin='',allowed_networks=['127.0.0.0/8'])
            with patch('chiko.server.ROOT',root):
                live=server.LiveMap(config);client=TestClient(TestServer(live.app()));await client.start_server()
                try:
                    live.terrain.store.put(0,0,0,np.full((16,16),'minecraft:water'),np.full((16,16),62))
                    version=live.terrain.store.entry_hash(0,0,0)
                    live.terrain.manifest.update(chunks={'0':[[0,0,version]]},revision=2,updated=time.time()+1)
                    tile=live.state()['tile_index']['0/0'][0]
                    url='/map/0/0/0/0.webp?world='+live.world_id()+'&revision='+tile[2]+'&palette=atlas'
                    response=await client.get(url);self.assertEqual(200,response.status)
                    with Image.open(io.BytesIO(await response.read())) as image:self.assertIn(image.convert('RGBA').getpixel((8,8)),(PAPER,INK,FAINT))
                    self.assertEqual(304,(await client.get(url,headers={'If-None-Match':response.headers['ETag']})).status)
                finally:await client.close();live.close()
