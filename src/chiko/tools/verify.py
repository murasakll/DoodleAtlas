"""Read-only checks against the running HTTP service; no simulated players."""
import asyncio
import io
import json
import time
from pathlib import Path
from aiohttp import ClientSession, ClientTimeout
from PIL import Image

from chiko.paths import ROOT


async def verify():
    from chiko.settings import load
    config = load()
    evidence = {'time':time.time(), 'checks':[], 'simulated_players':False}
    async with ClientSession(timeout=ClientTimeout(total=15), read_bufsize=4*1024*1024) as client:
        for base in [config['local_url'], config['lan_url']]:
            for route in ['/', '/app.js', '/style.css', '/api/state', '/qr.png']:
                start = time.perf_counter()
                async with client.get(base + route) as response:
                    content = await response.read()
                    evidence['checks'].append({'url':base+route,'status':response.status,
                                               'bytes':len(content),'seconds':round(time.perf_counter()-start,4)})
                    if response.status != 200:
                        raise RuntimeError(f'{route}: HTTP {response.status}; o verificador sem PIN é apenas para configuração sem PIN')
                    if route == '/api/state':
                        state = json.loads(content)
                    if route == '/qr.png':
                        Image.open(io.BytesIO(content)).verify()
        regions = state['terrain'].get('regions', {})
        count = sum(len(c) for c in state['terrain']['chunks'].values())
        evidence['terrain'] = {k:v for k,v in state['terrain'].items() if k not in ('chunks','regions')}
        evidence['terrain']['chunks_count'] = count
        evidence['terrain']['regions_count'] = sum(map(len,regions.values()))
        evidence['real_game'] = {k:state[k] for k in ('minecraft_connected','players','last_player_update','player_error')}
        for dimension, coords in regions.items():
            if not coords:
                continue
            cx, cz, *_ = coords[0]
            async with client.get(config['lan_url'] + f'/regions/{dimension}/{cx}/{cz}.png') as response:
                content = await response.read()
                image = Image.open(io.BytesIO(content))
                image.verify()
                evidence['checks'].append({'atlas_dimension':dimension,'status':response.status,'pixels':image.size})
        async with client.get(config['lan_url'] + '/api/events') as response:
            frames = []
            while len(frames)<2:
                line = await response.content.readline()
                if line.startswith(b'data: '):
                    frames.append(json.loads(line[6:]))
            evidence['sse'] = {'status':response.status, 'frames':len(frames),
                               'first_has_terrain':'terrain' in frames[0], 'second_has_terrain':'terrain' in frames[1]}
    target = ROOT / 'logs' / 'http-verification.json'
    target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(evidence,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    asyncio.run(verify())
