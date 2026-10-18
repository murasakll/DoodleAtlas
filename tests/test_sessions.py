import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from server import LiveMap, ROOT
from session_cache import SessionCache, remove_session
from textures import TextureCatalog


class Sessions(unittest.TestCase):
    def test_cleanup_excludes_unmarked_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            protected=root/'session-backup';protected.mkdir()
            with self.assertRaises(ValueError):remove_session(protected,root)
            cache=SessionCache(root);path=cache.path
            (path/'tile.png').write_bytes(b'generated')
            cache.close()
            self.assertFalse(path.exists())
            self.assertTrue(protected.exists())

    def test_force_close_watcher_removes_session(self):
        with tempfile.TemporaryDirectory() as folder:
            script='from session_cache import SessionCache; import time; c=SessionCache('+repr(folder)+'); c.watch(); print(c.path,flush=True); time.sleep(60)'
            p=subprocess.Popen([sys.executable,'-c',script],cwd=ROOT,stdout=subprocess.PIPE,text=True)
            path=Path(p.stdout.readline().strip())
            time.sleep(.5)
            p.kill();p.wait();p.stdout.close()
            deadline=time.monotonic()+8
            while path.exists() and time.monotonic()<deadline:time.sleep(.1)
            self.assertFalse(path.exists())

    def test_local_addon_texture_and_height_shading(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'textures').mkdir()
            (root/'blocks.json').write_text(json.dumps({'test:rock':{'textures':{'up':'custom'}}}))
            (root/'textures'/'terrain_texture.json').write_text(json.dumps({'texture_data':{'custom':{'textures':'textures/rock'}}}))
            Image.new('RGBA',(16,16),(200,100,50,255)).save(root/'textures'/'rock.png')
            catalog=TextureCatalog([root])
            names=np.full((16,16),'test:rock');heights=np.zeros((16,16),dtype=np.int16);heights[:,8:]=20
            render=catalog.render(names,heights)
            self.assertEqual((128,128),render.size)
            self.assertEqual((200,100,50,255),catalog.tile('test:rock').getpixel((0,0)))
            self.assertGreater(len(render.getcolors()),1)


class LivePackets(unittest.IsolatedAsyncioTestCase):
    async def test_world_isolation_surface_biome_and_entity_frames(self):
        config=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
        config['capture_persistent']=False
        live=LiveMap(config)
        try:
            surface={'worldId':'wrong','kind':'surface','surfaceVersion':2,'dimension':0,'x':-25,'z':1,'palette':['test:rock'],'ids':[0]*256,'heights':[65]*256,'biome':'test:forest'}
            await live.ingest_packet(surface)
            self.assertFalse(live.live_surfaces)
            surface['worldId']=live.world_id()
            legacy=dict(surface);legacy.pop('surfaceVersion')
            await live.ingest_packet(legacy)
            self.assertFalse(live.live_surfaces)
            await live.ingest_packet(surface)
            self.assertEqual(1,len(live.live_surfaces))
            first_hash=dict(live.live_surfaces)
            await live.ingest_packet({**surface,'tick':9999})
            self.assertEqual(first_hash,live.live_surfaces)
            self.assertEqual(-392,live.live_store.search('forest')[0]['x'])
            entity={'typeId':'addon:animal','category':'animal'}
            await live.ingest_packet({'worldId':live.world_id(),'kind':'entities','frame':1,'part':1,'total':2,'entities':[entity]})
            self.assertFalse(live.entities)
            await live.ingest_packet({'worldId':live.world_id(),'kind':'entities','frame':1,'part':0,'total':2,'entities':[entity]})
            self.assertEqual(2,len(live.entities))
            old=live.cache.path
            with tempfile.TemporaryDirectory() as folder:
                target=Path(folder);(target/'levelname.txt').write_text('Temporary test world')
                with patch.object(live,'start_worker'):
                    await live.select_world(target)
                self.assertFalse(old.exists())
                self.assertFalse(live.entities)
                self.assertFalse(live.live_surfaces)
                await live.ingest_packet(surface)
                self.assertFalse(live.live_surfaces)
        finally:live.close()
