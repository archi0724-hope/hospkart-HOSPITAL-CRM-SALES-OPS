"""Source-independent Chrome/Edge checks through the actual Waitress WSGI server.

Install requirements-dev.txt and Chrome/Edge, then run this file from the project.
All workbooks, databases, admin hashes, and browser profiles are temporary.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from threading import Thread

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from openpyxl import Workbook
from playwright.sync_api import sync_playwright
from waitress import create_server
from production import server_options
from werkzeug.security import generate_password_hash


def make_workbook(path):
    workbook=Workbook();workbook.remove(workbook.active)
    invoices=[['2026-09-01','INV-1','Test Alpha','Jaipur',100,'Paid'],['2026-09-02','INV-2','Test Alpha','Jaipur',200,'Active'],['2026-09-03','INV-3','Test Beta','Delhi',300,'Part Paid']]
    headers=['Invoice Date','Invoice No.','Client / Hospital','Delivery City / Location','Invoice Total (₹)','Invoice Status']
    summary=workbook.create_sheet('Client Summary');summary.append(headers)
    for row in invoices:summary.append(row)
    detail=workbook.create_sheet('Client Call List');detail.append(headers+['Item Name','Category','Item Total incl. GST (₹)'])
    for row,item,amount in [(invoices[0],'Item A',40),(invoices[0],'Item B',60),(invoices[1],'Item C',200),(invoices[2],'Item D',300)]:detail.append(row+[item,'Test category',amount])
    cancelled=workbook.create_sheet('Cancelled Invoices');cancelled.append(headers);cancelled.append(['2026-09-04','INV-X','Test Cancelled','Delhi',50,'Canceled'])
    for name in ['Categorized Items','Verification Summary','Read Me']:
        sheet=workbook.create_sheet(name);sheet.append(['Label','Value']);sheet.append(['Synthetic test source',name])
        if name=='Read Me':
            for number in range(8):sheet.append([f'Storage capacity fixture {number}','x'*32000])
    workbook.save(path);workbook.close()


def check():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);app.DATA_DIR=root;app.DB_PATH=root/'test.db';app.ADMIN_PASSWORD_PATH=root/'admin.hash'
        app.admin_attempts.clear();app.init_db()
        if app.scheduler.running:app.scheduler.pause()
        password='production-browser-test-only'
        app.ADMIN_PASSWORD_PATH.write_text(generate_password_hash(password),encoding='utf-8')
        # Ignore any real environment hash: test authorization always uses temp data.
        previous_hash=os.environ.pop('ADMIN_PASSWORD_HASH',None)
        fixture=root/'test-invoices.xlsx';make_workbook(fixture)
        options=server_options();options.update(host='127.0.0.1',port=0)
        server=create_server(app.app,**options)
        Thread(target=server.run,daemon=True).start()
        address=f'http://127.0.0.1:{server.effective_port}/'
        transfer=None;reports=[]
        try:
            with sync_playwright() as playwright:
                for channel in os.getenv('BROWSER_CHANNELS','chrome,msedge').split(','):
                    browser=playwright.chromium.launch(channel=None if channel=='chromium' else channel)
                    context=browser.new_context(viewport={'width':1440,'height':1000})
                    page=context.new_page();errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(address)
                    assert page.locator('#navClients').inner_text()=='10'
                    page.click('button[onclick="loadInvoiceWorkbook(true)"]')
                    page.locator('#toast').get_by_text('No workbook is stored on this server. Use Import Excel to load your file.',exact=True).wait_for()
                    if transfer:
                        page.evaluate("navigate('data')")
                        page.set_input_files('#jsonCheckpointFile',str(transfer))
                        page.locator('#importConfirmAccept').click()
                        page.wait_for_function('invoiceWorkbook?.sheets.length===6')
                        assert page.evaluate('JSON.stringify({clients,calls,feedback,segmentData,invoiceWorkbook})')==expected_transfer
                    else:
                        page.set_input_files('#excelImportFile',str(fixture))
                        page.wait_for_function('invoiceWorkbook?.sheets.length===6')
                    assert page.locator('#invoiceDetailRows tr').count()==3
                    assert '₹600' in page.locator('#invoiceMetrics').inner_text()
                    assert page.locator('#servedTotal').inner_text()=='2'
                    for _ in range(20):page.evaluate('installInvoiceWorkbook(invoiceWorkbook,invoiceWorkbook.filename)')
                    assert 1<=page.evaluate('backups.length')<10, 'Large workbook fixture should exercise backup quota retention'
                    page.reload();page.wait_for_function('invoiceWorkbook?.sheets.length===6')
                    assert page.locator('#invoiceDetailRows tr').count()==3
                    # A write failure must roll back active data and its checkpoint.
                    rollback=page.evaluate("""()=>{
                      const keys=['hk_v2_clients','hk_v2_calls','hk_v2_feedback','hk_v2_segments','hk_v2_invoice_workbook','hk_v2_backups'];
                      const before=JSON.stringify(keys.map(key=>localStorage.getItem(key)));
                      const beforeState=JSON.stringify({clients,calls,feedback,segmentData,invoiceWorkbook,backups});
                      const original=Storage.prototype.setItem;let failed=false,message='';
                      Storage.prototype.setItem=function(key,value){if(key==='hk_v2_segments'&&!failed){failed=true;throw new DOMException('Test quota','QuotaExceededError')}return original.call(this,key,value)};
                      try{installInvoiceWorkbook(invoiceWorkbook,'failed-import.xlsx')}catch(error){message=error.message}finally{Storage.prototype.setItem=original}
                      return {message,same:before===JSON.stringify(keys.map(key=>localStorage.getItem(key))),sameState:beforeState===JSON.stringify({clients,calls,feedback,segmentData,invoiceWorkbook,backups})};
                    }""")
                    assert rollback['same'] and rollback['sameState'] and 'storage is full' in rollback['message'],rollback
                    page.evaluate("navigate('data')")
                    with page.expect_download() as download:page.click('button[onclick="prepareFullBackup()"]')
                    transfer=root/'transfer.json';download.value.save_as(transfer)
                    expected_transfer=page.evaluate('JSON.stringify({clients,calls,feedback,segmentData,invoiceWorkbook})')
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.locator('#mobileView').is_visible()
                    page.select_option('#mobileView','served');assert page.locator('#page-served').is_visible()
                    page.select_option('#mobileView','data');assert page.locator('#page-data').is_visible()
                    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                    row=page.locator('#importRemovalRows tr').filter(has=page.locator('td').get_by_text('Categorized Items',exact=True))
                    row.get_by_role('button',name='Remove',exact=True).click()
                    page.fill('#importRemovalPassword',password);page.fill('#importRemovalConfirmation','REMOVE Categorized Items');page.click('#importRemovalSubmit')
                    page.wait_for_function('invoiceWorkbook.sheets.length===5')
                    assert '₹600' in page.locator('#invoiceMetrics').inner_text()
                    assert not errors,errors
                    context.close()
                    # Old/corrupted state must not crash initialization or be erased.
                    for key,value in [('hk_v2_clients','{}'),('hk_v2_clients','null'),('hk_v2_clients','[null]'),('hk_v2_backups','[{}]'),('hk_v2_segments','{"served":[null]}'),('hk_v2_invoice_workbook','{"sheets":null}')]:
                        old=browser.new_context();old.add_init_script(f'localStorage.setItem({json.dumps(key)},{json.dumps(value)})')
                        p=old.new_page();failures=[];p.on('pageerror',lambda error:failures.append(str(error)));p.goto(address)
                        p.locator('#browserStorageNotice:not(.hidden)').wait_for()
                        assert not failures,(key,failures)
                        assert p.evaluate(f'localStorage.getItem({json.dumps(key)})')==value
                        old.close()
                    blocked=browser.new_context();blocked.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('Storage blocked','SecurityError')}})")
                    p=blocked.new_page();failures=[];p.on('pageerror',lambda error:failures.append(str(error)));p.goto(address)
                    assert p.locator('#browserStorageNotice').is_visible();assert not failures,failures
                    blocked.close();reports.append({'browser':channel,'passed':True,'repeated_imports':20,'corrupt_storage_cases':6,'blocked_storage':True,'transfer':True,'mobile':True,'admin_removal':True,'rollback':True})
                    browser.close()
            print(json.dumps({'server':'Waitress','fresh_setup_without_private_data':True,'results':reports}))
        finally:
            server.close()
            if app.scheduler.running:app.scheduler.shutdown(wait=False)
            if previous_hash is not None:os.environ['ADMIN_PASSWORD_HASH']=previous_hash


if __name__=='__main__':check()
