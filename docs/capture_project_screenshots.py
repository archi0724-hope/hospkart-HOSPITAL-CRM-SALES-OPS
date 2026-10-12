"""Capture documentation screenshots with synthetic data on an isolated server.

Run: .venv/Scripts/python.exe docs/capture_project_screenshots.py
Requires requirements-dev.txt and installed Chrome (or DOC_BROWSER=chromium).
Never connects to the live dashboard or uses its customer catalogue/database.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from threading import Thread

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))


def capture():
    from playwright.sync_api import sync_playwright
    from waitress import create_server
    with tempfile.TemporaryDirectory() as temporary:
        directory=Path(temporary)
        for key in ['OPENAI_API_KEY','WHATSAPP_ACCESS_TOKEN','WHATSAPP_PHONE_NUMBER_ID','WHATSAPP_BUSINESS_ACCOUNT_ID','SMTP_HOST','SMTP_USERNAME','SMTP_PASSWORD','EMAIL_FROM','ADMIN_PASSWORD_HASH']:
            os.environ[key]=''
        for key in ['SCHEDULER_ENABLED','WHATSAPP_AUTOMATION_ENABLED','WHATSAPP_AUTO_REPLY_ENABLED','EMAIL_AUTOMATION_ENABLED','QUOTESAARTHI_USE_OLLAMA']:
            os.environ[key]='false'
        os.environ['CRM_DATA_DIR']=str(directory)
        os.environ['QUOTESAARTHI_CATALOG_PATH']=str(directory/'products.csv')
        import app
        from production import server_options
        from test_quotesaarthi import make_catalogue
        from check_production_browsers import make_workbook
        make_catalogue(directory/'products.csv')
        fixture=directory/'documentation-demo.xlsx';make_workbook(fixture)
        options=server_options();options.update(host='127.0.0.1',port=0)
        server=create_server(app.app,**options)
        Thread(target=server.run,daemon=True).start()
        screenshots=ROOT/'docs'/'screenshots';screenshots.mkdir(parents=True,exist_ok=True)
        manifest=[]
        try:
            with sync_playwright() as playwright:
                channel=os.getenv('DOC_BROWSER','chrome')
                browser=playwright.chromium.launch(headless=True,**({} if channel=='chromium' else {'channel':channel}))
                context=browser.new_context(viewport={'width':1600,'height':1000},device_scale_factor=1)
                page=context.new_page();errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.effective_port}/')
                page.wait_for_function("document.getElementById('navClients').innerText==='10'")
                page.set_input_files('#excelImportFile',str(fixture))
                page.wait_for_function('invoiceWorkbook?.sheets.length===6')
                page.evaluate("""async()=>{
                  const seed=originalClients[0];
                  sectionRecords.rghs=[{...seed,id:'DOC-RGHS',name:'Demo RGHS Hospital',mobile:'98XXXXXX11',email:'rghs@example.org',type:'RGHS Empanelled',remark:'Synthetic RGHS example'}];
                  sectionRecords.doctors=[{...seed,id:'DOC-DOCTOR',name:'Dr. Demo Contact',mobile:'98XXXXXX12',email:'doctor@example.org',type:'Doctor',status:'New Lead',remark:'Synthetic doctor contact'}];
                  sectionRecords.potential=[{...seed,id:'DOC-POTENTIAL',sourceRecordId:seed.id,workColor:'green',remark:'Synthetic completed outreach; independent potential copy'}];
                  segmentData.doctors=sectionRecords.doctors;segmentData.potential=sectionRecords.potential;
                  await Promise.all([persistRghs(),persistSegments()]);refreshDuplicateWorkRecords();renderAll();
                  const label=document.createElement('div');label.id='documentationLabel';label.textContent='DOCUMENTATION DEMO · SYNTHETIC DATA · NO MESSAGES SENT';
                  label.style.cssText='position:fixed;bottom:0;left:0;right:0;z-index:9999;background:#15284d;color:white;text-align:center;font:11px Arial;padding:6px;pointer-events:none';document.body.appendChild(label);
                }""")

                def shot(name, description):
                    page.wait_for_timeout(250)
                    page.screenshot(path=str(screenshots/name),full_page=False)
                    manifest.append({'file':name,'description':description,'data':'synthetic demonstration'})

                page.evaluate("navigate('dashboard');setNavigationOpen(true)")
                shot('01-navigation.png','Yellow HOSPkart wordmark and workspace menu')
                page.evaluate('closeNavigation()')
                views=[('dashboard','02-dashboard.png'),('clients','03-clients.png'),('rghs','04-rghs.png'),('served','05-served.png'),('doctors','06-doctors.png'),('potential','07-potential.png'),('leads','08-leads.png'),('quotes','09-quotations.png'),('orders','10-orders.png'),('calling','11-calling.png'),('feedback','12-feedback.png'),('whatsapp','13-whatsapp.png'),('email','14-email.png'),('reports','15-reports.png'),('data','18-backups.png')]
                for view,name in views:
                    page.evaluate('(view)=>navigate(view)',view)
                    if view=='data':
                        page.evaluate("document.querySelector('button[onclick=\"prepareFullBackup()\"]').closest('.card').scrollIntoView();window.scrollBy(0,-85)")
                    shot(name,'Workspace: '+view)
                page.evaluate("navigate('reports');document.getElementById('invoiceDashboard').scrollIntoView()")
                shot('16-invoice-analysis.png','Invoice metrics: 3 valid invoices, 2 clients, INR 600; synthetic workbook')
                page.locator('#invoiceDetailSheet').select_option('Client Call List')
                page.evaluate("document.getElementById('invoiceDetailRows').closest('table').scrollIntoView()")
                shot('17-workbook-details.png','Original columns and four item rows from Client Call List')
                page.evaluate("navigate('data');openImportRemoval({scope:'worksheet',name:'Client Call List',label:'Client Call List',count:4})")
                shot('19-admin-removal.png','Admin confirmation for one worksheet; no removal submitted')
                page.evaluate("closeImportRemoval();navigate('dashboard');toggleChat(true)")
                page.locator('#chatInput').fill('IV Set vendor listing');page.locator('.chat-send').click()
                page.wait_for_function('!quoteSaarthiSubmitting')
                shot('20-quotesaarthi-search.png','Actual local search against four synthetic offers')
                page.locator('#chatInput').fill('Quote IV Set 10 units with 5% discount and GST 18%');page.locator('.chat-send').click()
                page.wait_for_function('!quoteSaarthiSubmitting')
                page.locator('.quotation-downloads').wait_for()
                page.evaluate("const chat=document.getElementById('chatBody');chat.scrollTop=chat.scrollHeight")
                shot('21-quotesaarthi-draft.png','Actual draft quotation INR 89.68 with JSON/PDF export controls')
                page.evaluate('toggleChat(false)')
                page.set_viewport_size({'width':390,'height':844})
                shot('22-mobile.png','Mobile dashboard overview')
                page.evaluate('setNavigationOpen(true)')
                shot('23-mobile-navigation.png','Mobile workspace menu')
                assert not errors,errors
                manifest_data={'source':'Synthetic built-in CRM examples, synthetic invoice workbook and synthetic four-offer catalogue. No production records or credentials.','views':manifest,'invoice_fixture':{'served_entries':4,'distinct_clients':2,'valid_invoices':3,'valid_invoice_value':600,'cancelled_invoices':1},'quote_fixture':{'quantity':10,'unit_price':8,'discount_percent':5,'gst_percent':18,'total':89.68},'page_errors':errors}
                (screenshots/'manifest.json').write_text(json.dumps(manifest_data,indent=2),encoding='utf-8')
                context.close();browser.close()
                print(json.dumps({'screenshots':len(manifest),'page_errors':errors,'output':str(screenshots)}))
        finally:
            server.close()
            if app.scheduler.running:app.scheduler.shutdown(wait=False)


if __name__=='__main__':capture()
