import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from chiko.settings import normalize,load,lan_address,url
from chiko.tools.pack import build


class SettingsTests(unittest.TestCase):
    def test_relative_world_path_and_configurable_addresses(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);world=root/'worlds'/'demo';(world/'db').mkdir(parents=True);(world/'level.dat').write_bytes(b'fixture')
            settings=normalize({'world':'worlds/demo','http_port':9000,'minecraft_port':9001,'advertise_host':'map.example.test','minecraft_advertise_host':'game.example.test'},root)
            self.assertEqual(str(world.resolve()),settings['world'])
            self.assertEqual('http://map.example.test:9000',settings['lan_url'])
            self.assertEqual('ws://game.example.test:9001',settings['connect_url'])
            self.assertEqual('http://[::1]:9000',url('::1',9000))

    def test_invalid_ports_and_networks_are_rejected(self):
        for change in ({'http_port':0},{'http_port':True},{'http_port':8081},{'allowed_networks':['garbage']},{'http_host':'https://host/'},{'terrain_seconds':0}):
            with self.assertRaises(ValueError):normalize(change,require_world=False)

    def test_environment_overrides_file_and_no_username_in_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'settings.json';config.write_text(json.dumps({'http_port':9000}))
            with patch.dict(os.environ,{'CHIKO_HTTP_PORT':'9002','CHIKO_ADVERTISE_HOST':'lan.test'},clear=True):
                settings=load(config,require_world=False)
            self.assertEqual(9002,settings['http_port']);self.assertEqual('http://lan.test:9002',settings['lan_url'])

    def test_auto_address_ignores_loopback(self):
        with patch('chiko.settings.socket.getaddrinfo',return_value=[(None,None,None,None,('127.0.0.1',0)),(None,None,None,None,('10.23.45.6',0))]):
            self.assertEqual('10.23.45.6',lan_address())


class UniversalPackTests(unittest.TestCase):
    def test_generated_pack_has_no_world_binding_and_importable_root(self):
        with tempfile.TemporaryDirectory() as folder:
            target=build(output=Path(folder)/'Universal.mcpack')
            with zipfile.ZipFile(target) as archive:
                self.assertEqual('export const WORLD_ID = "";\n',archive.read('scripts/config.js').decode())
                manifest=json.loads(archive.read('manifest.json'))
                self.assertEqual([1,1,0],manifest['header']['version'])
                self.assertIn('scripts/main.js',archive.namelist())
                self.assertIn('world.setDynamicProperty',archive.read('scripts/main.js').decode())
                self.assertNotIn('level.dat',archive.namelist())

    def test_old_world_bound_builder_remains_available(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            world=Path(folder)/'abc=';world.mkdir()
            with patch('chiko.world.discovery.discover',return_value=[{'name':'Demo','path':str(world)}]):
                target=build('abc=',Path(folder)/'Bound.mcpack')
            with zipfile.ZipFile(target) as archive:
                self.assertIn(hashlib.sha256(str(world.resolve()).encode()).hexdigest(),archive.read('scripts/config.js').decode())
