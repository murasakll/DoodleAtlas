"""Contract tests with a simulated game, never evidence of a real Minecraft connection."""
import asyncio
import json
import unittest
from pathlib import Path
from aiohttp import ClientSession, CookieJar, web
from aiohttp.test_utils import TestClient, TestServer
from server import LiveMap, ROOT, parse_targets
from terrain import chunk_image, snapshot


class Integration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
        self.config['pin'] = '2468'
        self.config['capture_persistent'] = False
        self.config['packet_log'] = 'minecraft-simulated.jsonl'
        self.live = LiveMap(self.config)
        self.client = TestClient(TestServer(self.live.app()), cookie_jar=CookieJar(unsafe=True), read_bufsize=4*1024*1024)
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.live.close()

    async def test_pin_and_readonly(self):
        self.assertEqual(200, (await self.client.get('/')).status)
        self.assertEqual(401, (await self.client.get('/api/state')).status)
        self.assertEqual(401, (await self.client.post('/api/login', json={'pin': 'bad'})).status)
        self.assertEqual(200, (await self.client.post('/api/login', json={'pin': '2468'})).status)
        self.assertEqual(200, (await self.client.get('/api/state')).status)
        self.assertEqual(405, (await self.client.post('/api/state')).status)
        self.assertEqual(403, (await self.client.get('/api/state', headers={'Origin':'http://evil.example'})).status)
        self.assertEqual(404, (await self.client.get('/tiles/0/999999/999999.png')).status)

    async def test_texture_mode_removed(self):
        self.assertFalse(hasattr(self.live,'textures'))
        await self.client.post('/api/login', json={'pin':'2468'})
        self.assertEqual(400,(await self.client.get('/render/0/0/0.png?mode=texture')).status)

    async def test_live_and_render_share_cache_etag_and_local_invalidation(self):
        import numpy as np
        await self.client.post('/api/login',json={'pin':'2468'})
        def capture(name):
            self.live.live_store.put(0,0,0,np.full((16,16),name),np.full((16,16),62),surface_version=2)
            self.live.live_surfaces[(0,0,0)]=self.live.live_store.entry_hash(0,0,0)
        capture('minecraft:water')
        first=await self.client.get('/live/0/0/0.png');data=await first.read()
        self.assertEqual(200,first.status);etag=first.headers['ETag']
        self.assertIn('private',first.headers['Cache-Control'])
        same=await self.client.get('/render/0/0/0.png?mode=relief',headers={'If-None-Match':etag})
        self.assertEqual(304,same.status);self.assertEqual(b'',await same.read())
        count=self.live.render_queue.completed
        self.live.terrain.manifest['revision']+=1
        self.live.terrain.manifest['chunks']={'0':[[900,900,'unrelated']]}
        same=await self.client.get('/live/0/0/0.png')
        self.assertEqual(data,await same.read());self.assertEqual(count,self.live.render_queue.completed)
        capture('minecraft:stone')
        changed=await self.client.get('/live/0/0/0.png')
        self.assertNotEqual(data,await changed.read());self.assertNotEqual(etag,changed.headers['ETag'])
        self.assertEqual(count+1,self.live.render_queue.completed)

    async def test_webp_route_version_world_etag_and_dirty_tile(self):
        import io
        import numpy as np
        from PIL import Image
        from urllib.parse import urlencode
        self.assertEqual(401,(await self.client.get('/map/0/0/0/0.webp')).status)
        await self.client.post('/api/login',json={'pin':'2468'})
        def capture(name):
            self.live.accept_surface({'surfaceVersion':2,'dimension':0,'x':0,'z':0,'palette':[name],'ids':[0]*256,'heights':[62]*256})
        def url():
            state=self.live.state();version=state['tile_index']['0/0'][0][2]
            return '/map/0/0/0/0.webp?'+urlencode({'world':state['world_id'],'revision':version})
        capture('minecraft:water');original=url()
        response=await self.client.get(original);data=await response.read()
        self.assertEqual(200,response.status);self.assertEqual('image/webp',response.content_type)
        with Image.open(io.BytesIO(data)) as raw:
            image=raw.convert('RGBA');self.assertEqual((256,256),image.size);self.assertEqual((168,230,245,255),image.getpixel((2,2)))
        etag=response.headers['ETag'];count=self.live.render_queue.completed
        cached=await self.client.get(original,headers={'If-None-Match':'W/'+etag})
        self.assertEqual(304,cached.status);self.assertEqual(count,self.live.render_queue.completed)
        self.assertGreater(self.live.web_tiles.cache.hits,0)
        capture('minecraft:stone')
        self.assertEqual(409,(await self.client.get(original)).status)
        changed=await self.client.get(url());self.assertNotEqual(etag,changed.headers['ETag']);await changed.read()
        self.assertEqual(409,(await self.client.get(url().replace('world=','world=wrong'))).status)
        self.assertEqual(400,(await self.client.get(original.replace('/map/0/0/','/map/0/99/'))).status)

    async def test_sse_tile_index_uses_deltas(self):
        await self.client.post('/api/login',json={'pin':'2468'})
        try:
            async with self.client.get('/api/events') as response:
                first=json.loads((await asyncio.wait_for(response.content.readline(),2))[6:])
                self.assertIn('tile_index',first)
                await response.content.readline()
                self.live.accept_surface({'surfaceVersion':2,'dimension':0,'x':0,'z':0,'palette':['minecraft:water'],'ids':[0]*256,'heights':[62]*256})
                self.live.publish()
                second=json.loads((await asyncio.wait_for(response.content.readline(),2))[6:])
                self.assertNotIn('tile_index',second)
                self.assertIn('0/0',second['tile_index_delta'])
                self.assertEqual(1,len(second['tile_index_delta']['0/0']['upsert']))
                self.live.stop_event.set();self.live.publish()
        finally:self.live.stop_event.set();self.live.publish()

    async def test_component_gallery_and_local_assets_without_game_data(self):
        # The public demo contains sample data only; protected APIs stay protected.
        for path in ('/components.html','/components.js','/chiko-design.css',
                     '/tile-source.js','/map-renderer.js','/pixel-avatars.js','/chiko.js',
                     '/assets/paper-frame.svg','/assets/Caveat.ttf','/assets/OFL-Caveat.txt'):
            response=await self.client.get(path)
            self.assertEqual(200,response.status,path)
            self.assertTrue(await response.read(),path)
            self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
        self.assertEqual(401,(await self.client.get('/api/state')).status)
        self.assertEqual(401,(await self.client.get('/assets/config.json')).status)
        await self.client.post('/api/login',json={'pin':'2468'})
        self.assertEqual(404,(await self.client.get('/assets/config.json')).status)

    async def test_network_rejected(self):
        self.live.config['allowed_networks'] = ['192.168.99.0/24']
        async with TestClient(TestServer(self.live.app())) as client:
            self.assertEqual(403, (await client.get('/')).status)

    async def test_host_settings_bounds_and_pin_rate_limit(self):
        for _ in range(8):self.assertEqual(401,(await self.client.post('/api/login',json={'pin':'bad'})).status)
        self.assertEqual(429,(await self.client.post('/api/login',json={'pin':'2468'})).status)
        self.live.attempts.clear()
        await self.client.post('/api/login',json={'pin':'2468'})
        self.assertEqual(403,(await self.client.post('/api/settings',json={'terrain_seconds':4})).status)
        headers={'X-Host-Token':self.live.host_token}
        self.assertEqual(400,(await self.client.post('/api/settings',json={'terrain_seconds':.5},headers=headers)).status)
        self.assertEqual(200,(await self.client.post('/api/settings',json={'terrain_seconds':4},headers=headers)).status)
        self.assertEqual(4,json.loads((self.live.cache.path/'settings.json').read_text())['terrain_seconds'])

    async def test_sse_and_stale_players(self):
        await self.client.post('/api/login', json={'pin':'2468'})
        async with self.client.get('/api/events') as response:
            line = await asyncio.wait_for(response.content.readline(), 2)
            self.assertTrue(line.startswith(b'data: '))
            payload = json.loads(line[6:])
            self.assertIn('terrain', payload)
            self.live.players = [{'id':'stale'}]
            self.live.last_update = 0
            self.live.publish()
            await response.content.readline()
            data = json.loads((await response.content.readline())[6:])
            self.assertEqual([], data['players'])

    async def test_game_protocol_simulated(self):
        game = web.Application()
        game.router.add_get('/{tail:.*}', self.live.minecraft)
        async with TestClient(TestServer(game)) as client:
            socket = await client.ws_connect('////')
            seen = set()
            for _ in range(3):
                packet = await asyncio.wait_for(socket.receive_json(), 3)
                command = packet['body']['commandLine']
                seen.add(command)
                body = {'statusCode':0}
                if command == 'getlocalplayername':
                    body['localplayername'] = 'Host Teste'
                elif command == 'querytarget @a':
                    body['details'] = json.dumps([{'uniqueId':'123','dimension':1,'position':{'x':12.5,'y':64,'z':-9},'name':'Host Teste'}])
                elif command == 'list':
                    body['players'] = []
                await socket.send_json({'header':{'requestId':packet['header']['requestId']},'body':body})
            for _ in range(20):
                if self.live.players:
                    break
                await asyncio.sleep(.01)
            self.assertEqual({'getlocalplayername','querytarget @a','list'}, seen)
            self.assertEqual(12.5, self.live.players[0]['x'])
            self.assertTrue(self.live.players[0]['host'])
            self.assertEqual(1, self.live.players[0]['dimension'])
            await socket.close()

    async def test_game_encrypted_protocol_simulated(self):
        import base64
        import hashlib
        import shlex
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        from cryptography.hazmat.decrepit.ciphers.modes import CFB8
        game = web.Application()
        game.router.add_get('/{tail:.*}', self.live.minecraft)
        async with TestClient(TestServer(game)) as client:
            socket = await client.ws_connect('/ws',protocols=['com.microsoft.minecraft.wsencrypt'],decode_text=False)
            packet = await socket.receive_json()
            parts = shlex.split(packet['body']['commandLine'])
            self.assertEqual('enableencryption',parts[0])
            decode = lambda value: base64.b64decode(value+'='*(-len(value)%4))
            public = serialization.load_der_public_key(decode(parts[1]))
            private = ec.generate_private_key(ec.SECP384R1())
            shared = private.exchange(ec.ECDH(),public).lstrip(b'\x00')
            key = hashlib.sha256(decode(parts[2])+shared).digest()
            cipher = Cipher(algorithms.AES(key),CFB8(key[:16]))
            encrypt, decrypt = cipher.encryptor(), cipher.decryptor()
            encoded = private.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
            await socket.send_json({'header':{'requestId':packet['header']['requestId']},
                                    'body':{'statusCode':0,'publicKey':base64.b64encode(encoded).decode()}})
            message = await socket.receive()
            packet = json.loads(decrypt.update(message.data))
            self.assertEqual('getlocalplayername',packet['body']['commandLine'])
            response = {'header':{'requestId':packet['header']['requestId']},'body':{'statusCode':0,'localplayername':'Encrypted Host'}}
            await socket.send_frame(encrypt.update(json.dumps(response).encode()),1)
            message = await socket.receive()
            packet = json.loads(decrypt.update(message.data))
            self.assertEqual('querytarget @a',packet['body']['commandLine'])
            response = {'header':{'requestId':packet['header']['requestId']},'body':{'statusCode':0,
                         'details':json.dumps([{'uniqueId':'secure','name':'Encrypted Host','dimension':0,
                                               'position':{'x':33,'y':70,'z':-20}}])}}
            await socket.send_frame(encrypt.update(json.dumps(response).encode()),1)
            for _ in range(50):
                if self.live.players:
                    break
                await asyncio.sleep(.01)
            self.assertEqual(33,self.live.players[0]['x'])
            self.assertTrue(self.live.players[0]['host'])
            await socket.close()


class Parser(unittest.TestCase):
    def test_coverage_detects_blocks_missing_from_library_index(self):
        from coverage import audit_records,chunk_record
        import struct
        records={(0,1,2):{44,47},(0,3,4):{47},(0,8,9):{49}}
        result=audit_records(records,{(0,1,2)})
        self.assertEqual(1,result['omitted_block_record_chunks'])
        self.assertEqual([[0,3,4]],result['omitted_examples'])
        self.assertEqual(1,result['metadata_only_chunks'])
        self.assertIsNone(chunk_record(b'globalkey'))
        self.assertEqual((0,1,2,47),chunk_record(struct.pack('<ii',1,2)+b'/\xff'))

    def test_content_log_no_replay_partial_lines_and_rotation(self):
        import tempfile
        from content_log import ContentLog
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
            path = Path(directory)/'test.log'
            path.write_text('[BEDROCK_LIVE_MAP]{"players":[{"old":true}]}\n',encoding='utf-8')
            reader = ContentLog(path)
            self.assertIsNone(reader.read())
            with path.open('ab') as output:
                output.write(b'[Scripting][warning]-[BEDROCK_LIVE_MAP]{"players":[')
            self.assertIsNone(reader.read())
            with path.open('ab') as output:
                output.write('{"name":"João"}]}\n'.encode())
            self.assertEqual([{'name':'João'}],reader.read())
            path.write_text('[BEDROCK_LIVE_MAP]{"players":[]}\n',encoding='utf-8')
            self.assertEqual([],reader.read())

    def test_encryption_ecdh_and_continuous_stream(self):
        import base64
        import hashlib
        from encryption import GameEncryption
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        from cryptography.hazmat.decrepit.ciphers.modes import CFB8
        server = GameEncryption()
        client = ec.generate_private_key(ec.SECP384R1())
        encoded = client.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
        server.accept(base64.b64encode(encoded).decode())
        shared = client.exchange(ec.ECDH(),server.private.public_key()).lstrip(b'\x00')
        key = hashlib.sha256(server.salt+shared).digest()
        cipher = Cipher(algorithms.AES(key),CFB8(key[:16]))
        client_send, client_receive = cipher.encryptor(), cipher.decryptor()
        for data in [b'{"first":1}', b'{"second":2}', b'{"third":3}']:
            self.assertEqual(data,server.decode(client_send.update(data)))
            self.assertEqual(data,client_receive.update(server.encode(data)))

    def test_top_column_negative_height_and_image_axes(self):
        from amulet.api.chunk import Chunk
        from amulet.api.block import Block
        from terrain import colour
        import numpy as np
        chunk = Chunk(-1, 3)
        air = chunk.block_palette.get_add_block(Block('minecraft','air'))
        stone = chunk.block_palette.get_add_block(Block('minecraft','stone'))
        water = chunk.block_palette.get_add_block(Block('minecraft','water'))
        low = np.full((16,16,16), air, dtype=np.uint32)
        low[2,5,7] = stone
        chunk.blocks.add_sub_chunk(-1, low)
        high = np.full((16,16,16), air, dtype=np.uint32)
        high[2,3,7] = water
        chunk.blocks.add_sub_chunk(0, high)
        image = chunk_image(chunk)
        self.assertEqual(colour('water'), image.getpixel((2,7)))
        self.assertEqual(0, image.getpixel((7,2))[3])
        high[2,3,7] = air
        chunk.blocks.add_sub_chunk(0, high)
        self.assertEqual(colour('stone'), chunk_image(chunk).getpixel((2,7)))

    def test_query_details_without_name(self):
        players = parse_targets({'details':'[{"uniqueId":"42","dimension":2,"position":{"x":-1,"y":90,"z":5}}]'})
        self.assertEqual('Jogador 42', players[0]['name'])
        self.assertEqual(2, players[0]['dimension'])

    def test_snapshot_refuses_source(self):
        with self.assertRaises(ValueError):
            snapshot(ROOT, ROOT / 'data' / 'unsafe')


if __name__ == '__main__':
    unittest.main(verbosity=2)
