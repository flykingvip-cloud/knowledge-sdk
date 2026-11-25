"""Reproducible headless L4 script; NOT executed by the implementation executor.

Only the parent-dispatched sanctioned browser/computerUse agent may execute this
through its supported browser surface. Never execute via Shell/CDP/Puppeteer.
Manual computerUse evidence must be labelled visible/manual, not headless.
JWT input files are mode 0600, outside the repository and absent from screenshots.
"""
from __future__ import annotations
import asyncio,json
from pathlib import Path

async def verify(browser,base,token_file):
    context=await browser.new_context()
    page=await context.new_page();errors=[];page_errors=[]
    page.on('console',lambda message:errors.append(message.text) if message.type=='error' else None)
    page.on('pageerror',lambda error:page_errors.append(str(error)))
    try:
        await page.goto(base+'/ui',wait_until='networkidle')
        assert await page.locator('#identity-form').count()==0
        assert await page.locator('#preset').count()==0
        assert 'Demo' not in await page.locator('body').inner_text()
        await page.locator('#token-file').set_input_files(token_file)
        await page.wait_for_function("document.querySelector('#status').textContent.startsWith('Authenticated.')")
        assert await page.locator('#bearer').input_value()==''
        assert await page.locator('#token-file').input_value()==''
        await page.get_by_role('button',name='Load authorized documents').click()
        await page.wait_for_function("document.querySelector('#documents').textContent.includes('doc-published')")
        await page.get_by_role('button',name='Search evidence',exact=True).click()
        await page.wait_for_function("document.querySelector('#search-results').textContent.includes('APPROVED_PUBLIC_MARKER')")
        await page.locator('#citation').fill('kb://org/m4-browser/doc/doc-published@1')
        await page.get_by_role('button',name='Verify citation',exact=True).click()
        await page.wait_for_function("document.querySelector('#citation-result').textContent.length>0")
        citation=json.loads(await page.locator('#citation-result').inner_text())
        assert citation['result']['structuredContent']['valid'] is True
        assert citation['result']['structuredContent']['current_status']=='valid'
        await page.locator('#pack-id').fill('browser-pack');await page.get_by_role('button',name='Read pack',exact=True).click()
        await page.wait_for_function("document.querySelector('#pack-result').textContent.includes('browser-pack')")
        sealed=json.loads(await page.locator('#pack-result').inner_text())
        assert sealed['status']=='sealed' and len(sealed['pack_sha256'])==64
        await page.get_by_role('button',name='Load alerts',exact=True).click()
        await page.wait_for_function("document.querySelector('#alerts').textContent.includes('access_revoked')")
        dom=await page.locator('body').inner_text()
        for marker in ('DRAFT_NEVER_LEAK_MARKER','FOREIGN_NEVER_LEAK_MARKER'):assert marker not in dom
        # Request-level negative probes are not page console events. Record their
        # statuses separately; never silently discard unexpected browser errors.
        negative=await context.request.get(base+'/ui/demo/sign')
        assert negative.status in (403,404)
        assert not errors and not page_errors,{'console_errors':errors,'page_errors':page_errors}
        return {'base':base,'passed':True,'console_errors':errors,'page_errors':page_errors,'demo_sign_status':negative.status,'dom':dom,'modality':'headless only if browser launched headless by sanctioned browser agent'}
    finally:await context.close()

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(headless=True)
        try:
            results=[]
            for port,engine in ((18474,'sqlite'),(18475,'postgres')):
                results.append(await verify(browser,'http://127.0.0.1:'+str(port)+'/kb-prod','/workspace/knowledge-sdk-q2m4-artifacts/l4-'+engine+'.jwt'))
            print(json.dumps(results,indent=2))
        finally:await browser.close()
if __name__=='__main__':asyncio.run(main())
