"""Optional real-browser language checks; synthetic data, no game save access.

Uses the same optional Playwright installation as scripts/capture_gallery.py.
Run: python tests/i18n_browser.py
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import capture_gallery as gallery
import asyncio
import json
import tempfile
from unittest.mock import patch
from aiohttp import web
from playwright.async_api import async_playwright


async def main():
    with tempfile.TemporaryDirectory(prefix='doodleatlas-language-') as temporary:
        root=Path(temporary);world=root/'world';world.mkdir()
        (world/'levelname.txt').write_text('Casa',encoding='utf-8')
        config=json.loads((gallery.PROJECT/'config/settings.example.json').read_text(encoding='utf-8'))
        config.update(world=str(world),pin='',capture_persistent=True,content_log='',http_host='127.0.0.1')
        with patch.object(gallery.server,'ROOT',root),patch.object(gallery.server,'discover',return_value=[{'path':str(world),'name':'Casa'}]):
            live=gallery.server.LiveMap(config)
            await asyncio.to_thread(gallery.fixture,live)
            runner=web.AppRunner(live.app());await runner.setup()
            site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
            port=site._server.sockets[0].getsockname()[1]
            try:
                async with async_playwright() as p:
                    browser=await p.chromium.launch()
                    context=await browser.new_context(viewport={'width':1280,'height':800},locale='pt-BR',reduced_motion='reduce')
                    page=await context.new_page();errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    await page.goto(f'http://127.0.0.1:{port}/?x=300&z=256&scale=2.4')
                    await page.wait_for_function("() => document.querySelector('#languageSelect') && document.querySelector('#worldSelect').options.length")
                    await page.locator('.book-tabs [data-book-panel="layersPanel"]').click()
                    await page.locator('#languageSelect').select_option('en')
                    await page.wait_for_function("() => document.documentElement.lang === 'en' && document.querySelector('#fit').textContent.trim() === 'Fit map'")
                    translations=await page.evaluate("""() => [
                        DoodleAtlasI18n.t('Construir · Casa'),
                        DoodleAtlasI18n.t('Casa · 2 × 2 células'),
                        DoodleAtlasI18n.t('Seguindo Casa'),
                        DoodleAtlasI18n.t('3 / 20.000 células · salvo'),
                        DoodleAtlasI18n.t('256 px por tile · cache de imagens: 16 MiB. O tamanho muda a área coberta, não o detalhe do mapa.')
                    ]""")
                    assert translations==['Build · House','House · 2 × 2 cells','Following Casa','3 / 20,000 cells · saved','256 px per tile · image cache: 16 MiB. Size changes the area covered, not map detail.'],translations
                    assert await page.title()=='DoodleAtlas · your world in doodles'
                    tabs=await page.locator('.book-tabs > button').all_text_contents()
                    assert all(any(name in text for text in tabs) for name in ['Map','People','Places','Draw','Build','Biomes','Settings','History','Focus']),tabs
                    assert await page.locator('#worldSelect option:checked').text_content()=='Casa'
                    assert await page.locator('#viewMode').input_value()=='cartographer'
                    await page.evaluate("() => {document.querySelector('#connection').textContent='● Conectado pelo pack';document.querySelector('#waypoints').firstElementChild.querySelector('button').textContent='⚑ Compartilhado · Casa';}")
                    await page.wait_for_function("() => document.querySelector('#connection').textContent.includes('Connected through the pack')")
                    assert 'Shared · Casa' in await page.locator('#waypoints').text_content()
                    await page.locator('.book-tabs [data-book-panel="editorPanel"]').click()
                    await page.locator('#editObjectSearch').fill('windmill')
                    await page.wait_for_function("() => [...document.querySelectorAll('#editObjectPalette button')].filter(b=>!b.hidden).length===1")
                    assert await page.locator('#editObjectPalette button:not([hidden])').get_attribute('data-kind')=='windmill'
                    await page.locator('.book-tabs [data-book-panel="layersPanel"]').click()
                    await page.locator('#languageSelect').select_option('pt-BR')
                    await page.wait_for_function("() => document.querySelector('#fit').textContent.trim()==='Ver mapa'")
                    assert 'Compartilhado · Casa' in await page.locator('#waypoints').text_content()
                    assert await page.locator('#languageSelect').input_value()=='pt-BR'
                    await page.locator('#languageSelect').select_option('en')
                    await page.reload()
                    await page.wait_for_function("() => document.documentElement.lang==='en' && document.querySelector('#languageSelect')?.value==='en'")
                    await page.wait_for_function("() => tileSource.stats().entries > 0 && tileSource.stats().loading===0 && tileSource.stats().queued===0")
                    if '--screenshot' in sys.argv:
                        await page.locator('.book-tabs [data-book-panel="layersPanel"]').click()
                        await page.screenshot(path=str(gallery.PROJECT/'docs/images/07-english.png'),animations='disabled')
                        await page.locator('.book-tabs [data-book-panel="layersPanel"]').click()
                    await page.set_viewport_size({'width':390,'height':844})
                    await page.locator('.book-tabs [data-book-panel="layersPanel"]').click()
                    assert await page.locator('#languageSelect').is_visible()
                    assert await page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
                    assert not errors,errors
                    await browser.close()
                    print('Language checks passed: switching, persistence, dynamic updates, search, custom names and mobile width.')
            finally:
                await runner.cleanup();live.close()


if __name__=='__main__':asyncio.run(main())
