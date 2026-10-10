"""Real QuoteSaarthi widget/download checks using temporary catalogue and Waitress."""
import json
import os
import sys
import tempfile
from pathlib import Path
from threading import Thread
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from playwright.sync_api import sync_playwright
from waitress import create_server
from production import server_options
from test_quotesaarthi import make_catalogue


def check():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);app.DATA_DIR=root;app.DB_PATH=root/'test.db';app.init_db()
        if app.scheduler.running:app.scheduler.pause()
        catalogue=root/'products.csv';make_catalogue(catalogue)
        with patch.dict(os.environ,{'QUOTESAARTHI_CATALOG_PATH':str(catalogue),'QUOTESAARTHI_USE_OLLAMA':'false'}):
            options=server_options();options.update(host='127.0.0.1',port=0)
            server=create_server(app.app,**options);Thread(target=server.run,daemon=True).start()
            reports=[]
            try:
                with sync_playwright() as playwright:
                    for channel in os.getenv('BROWSER_CHANNELS','chrome,msedge').split(','):
                        browser=playwright.chromium.launch(**({} if channel=='chromium' else {'channel':channel}),headless=True)
                        context=browser.new_context(accept_downloads=True);page=context.new_page();errors=[]
                        page.on('pageerror',lambda error:errors.append(str(error)))
                        page.goto(f'http://127.0.0.1:{server.effective_port}/')
                        page.wait_for_function("typeof dashboardStorage!=='undefined' && document.getElementById('navClients').innerText==='10'")
                        before=page.evaluate('JSON.stringify({clients,sectionRecords})')
                        page.get_by_role('button',name='Open QuoteSaarthi',exact=True).click()

                        def send(message):
                            page.locator('#chatInput').fill(message);page.locator('.chat-send').click()
                            page.wait_for_function('!quoteSaarthiSubmitting')
                            return page.locator('#chatBody .bot').last.inner_text()

                        assert 'Vendor A' in send('IV Set vendor listing')
                        assert 'GST rate confirm' in send('Quote IV Set 10 units with 5% discount')
                        assert 'INR 89.68' in send('GST 18%')
                        token=page.evaluate('quoteSaarthiSession')
                        for extension in ['JSON','PDF']:
                            with page.expect_download() as event:
                                page.get_by_role('button',name='Download '+extension,exact=True).click()
                            target=root/(channel+'.'+extension.lower());event.value.save_as(target)
                            if extension=='JSON':
                                quote=json.loads(target.read_text());assert quote['final_amount']==89.68 and quote['draft']
                            else:assert target.read_bytes().startswith(b'%PDF')
                        isolated=browser.new_context();other=isolated.new_page();other.goto(page.url)
                        assert other.evaluate('quoteSaarthiSession') is None
                        isolated.close()
                        page.reload();page.wait_for_function('quoteSaarthiSession!==null')
                        assert page.evaluate('quoteSaarthiSession')==token
                        page.evaluate('toggleChat(true)')
                        page.get_by_role('button',name='New QuoteSaarthi conversation',exact=True).click()
                        assert page.evaluate('quoteSaarthiSession') is None
                        assert 'Vendor A' in send('Hospital Bed vendor listing')
                        assert page.evaluate('quoteSaarthiSession')!=token
                        assert page.evaluate('JSON.stringify({clients,sectionRecords})')==before
                        page.set_viewport_size({'width':390,'height':844})
                        box=page.locator('#chatWidget').bounding_box();assert box and box['x']>=0 and box['x']+box['width']<=390
                        assert page.get_by_role('button',name='New QuoteSaarthi conversation',exact=True).is_visible()
                        assert not errors,errors
                        reports.append({'browser':channel,'passed':True,'real_catalogue_search':True,'gst_clarification':True,'json_pdf_downloads':True,'session_isolation':True,'crm_preserved':True,'mobile':True})
                        context.close();browser.close()
                print(json.dumps({'server':'Waitress','results':reports}))
            finally:
                server.close()
                if app.scheduler.running:app.scheduler.shutdown(wait=False)


if __name__=='__main__':check()
