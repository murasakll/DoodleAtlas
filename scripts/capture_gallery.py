"""Screenshots of the real UI with synthetic data. Never opens a Minecraft save."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
if (PROJECT / 'runtime/gallery-tools').exists():
    sys.path.insert(0, str(PROJECT / 'runtime/gallery-tools'))
if (PROJECT / 'runtime/gallery-browsers').exists():
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(PROJECT / 'runtime/gallery-browsers'))

import numpy as np
from aiohttp import web
from playwright.async_api import async_playwright
from chiko import server
from chiko.storage.history import render_overview
import threading


def fixture(live):
    z, x = np.mgrid[0:512, 0:768]
    height = 70 + 32*np.sin(x/83)*np.cos(z/109) + 18*np.sin((x+z)/61)
    river = np.abs(x-(365+65*np.sin(z/88))) < 22
    lake = ((x-110)/95)**2 + ((z-350)/65)**2 < 1
    names = np.full(x.shape, 'minecraft:grass_block', dtype='<U32')
    names[height > 96] = 'minecraft:stone'
    names[height > 110] = 'minecraft:snow'
    names[np.abs(x-(365+65*np.sin(z/88))) < 29] = 'minecraft:sand'
    names[river | lake] = 'minecraft:water'
    height[river | lake] = 62
    height = height.astype('<i2')
    for cz in range(32):
        for cx in range(48):
            cut = np.s_[cz*16:(cz+1)*16, cx*16:(cx+1)*16]
            biome = 'minecraft:forest' if cx < 18 else 'minecraft:plains'
            live.terrain.store.put(0,cx,cz,names[cut],height[cut],biome=biome,surface_version=2)
    chunks = [[cx,cz,digest] for (dim,cx,cz),digest in live.terrain.store.entries().items() if dim == 0]
    live.terrain.manifest.update(revision=1,chunks={'0':chunks},regions={},updated=time.time(),spawn={'x':256,'z':256})
    for name,px,pz in [('Vila do Caderno',280,245),('Ponte do Rio',355,270),('Trilha da Serra',460,160)]:
        live.shared_store.create({'name':name,'x':px,'z':pz,'dimension':0})
    cells=[]
    def cell(kind,px,pz,label=''):
        return dict(dimension=0,grid=4,x=px,z=pz,kind=kind,color='#484238',label=label)
    for px in range(240,332,4):cells.append(cell('road',px,256))
    for pz in range(216,292,4):cells.append(cell('road',284,pz))
    for kind,px,pz in [('house',252,236),('house',308,236),('tavern',296,272),('well',276,248),('garden',252,276),('windmill',324,268)]:
        cells.append(cell(kind,px,pz))
    cells=list({(cell['kind'],cell['x'],cell['z']):cell for cell in cells}.values())
    live.annotations.save(0,cells,[])
    region={'dimension':0,'min_x':192,'min_z':160,'max_x':384,'max_z':352}
    live.history.configure({'frames_enabled':False,'primary_region':region})
    data,meta=render_overview(live.terrain.store.path,live.live_store.path,0,threading.Event(),region=region)
    live.history.add_frame(0,data,meta)


async def main():
    out=PROJECT/'docs/images'
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chiko-public-gallery-') as folder:
        root=Path(folder);world=root/'synthetic-world';world.mkdir()
        (world/'levelname.txt').write_text('Mundo de exemplo',encoding='utf-8')
        config=json.loads((PROJECT/'config/settings.example.json').read_text(encoding='utf-8'))
        config.update(world=str(world),pin='',capture_persistent=True,content_log='',http_host='127.0.0.1')
        with patch.object(server,'ROOT',root),patch.object(server,'discover',return_value=[{'path':str(world),'name':'Mundo de exemplo'}]):
            live=server.LiveMap(config)
            await asyncio.to_thread(fixture,live)
            runner=web.AppRunner(live.app());await runner.setup()
            site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
            port=site._server.sockets[0].getsockname()[1]
            async def heartbeat():
                while True:
                    live.connected=True;live.player_source='content_log';live.last_update=time.time()
                    live.players=[dict(id='demo-explorer',name='Explorador',host=True,x=280,y=72,z=244,dimension=0,yaw=40,color='#df9c48')]
                    live.publish();await asyncio.sleep(1)
            task=asyncio.create_task(heartbeat())
            try:
                async with async_playwright() as p:
                    browser=await p.chromium.launch(headless=True)
                    context=await browser.new_context(viewport={'width':1440,'height':900},device_scale_factor=1,reduced_motion='reduce')
                    page=await context.new_page();errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    await page.goto(f'http://127.0.0.1:{port}/?x=300&z=256&scale=2.4&dimension=0')
                    await page.wait_for_function("() => document.querySelector('.book-tabs') && document.querySelector('#worldSelect').options.length")
                    await page.evaluate('() => document.fonts.ready')
                    await page.wait_for_function("() => typeof tileSource !== 'undefined' && tileSource.stats().entries > 0 && tileSource.stats().loading === 0 && tileSource.stats().queued === 0",timeout=60000)
                    await page.wait_for_timeout(1000)
                    async def capture(name):
                        await page.screenshot(path=str(out/name),animations='disabled')
                    await capture('01-atlas.png')
                    await page.locator('.book-tabs [data-book-panel="editorPanel"]').click()
                    await page.locator('#editObjectPalette').scroll_into_view_if_needed()
                    await capture('02-editor.png')
                    await page.locator('.book-tabs [data-book-panel="waypointsPanel"]').click()
                    await capture('03-lugares.png')
                    await page.locator('#viewMode').evaluate("e => {e.value='plain'; e.dispatchEvent(new Event('change',{bubbles:true}));}")
                    await page.locator('.book-tabs [data-book-panel="waypointsPanel"]').click()
                    await page.wait_for_timeout(1500)
                    await capture('04-minecraft.png')
                    await page.locator('#openHistory').evaluate('e => e.click()')
                    await page.wait_for_function("() => document.querySelector('#historyImage').naturalWidth > 0")
                    await page.locator('#historyRegionStatus').scroll_into_view_if_needed()
                    await capture('05-historico.png')
                    await page.locator('#closeHistory').click()
                    await page.locator('#themeMode').evaluate("e => {e.value='dark'; e.dispatchEvent(new Event('change',{bubbles:true}));}")
                    await page.wait_for_timeout(700)
                    await capture('06-noturno.png')
                    await context.close();await browser.close()
                    if errors:raise RuntimeError('Browser errors: '+'; '.join(errors))
                    print('Six UI screenshots captured. Synthetic data; no Minecraft world opened.')
            finally:
                task.cancel()
                try:await task
                except asyncio.CancelledError:pass
                await runner.cleanup();live.close()


if __name__=='__main__':asyncio.run(main())
