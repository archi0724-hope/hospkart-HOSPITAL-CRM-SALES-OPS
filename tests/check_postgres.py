"""Full PostgreSQL integration against a disposable LOCAL test database only.

Set CRM_TEST_DATABASE_URL to localhost/hospkart_test. No production URLs accepted.
The test database must start empty. No customer messages are sent.
"""
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from threading import Barrier, Thread
from unittest.mock import patch
from urllib.parse import urlparse
from uuid import uuid4
import psycopg
from psycopg import sql

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['SCHEDULER_ENABLED']='false'
os.environ.pop('DATABASE_URL',None)
from crm_test_environment import app, login_browser_admin
import database
from migrate_database import migrate
from test_spreadsheet_sync import FakeSheets, connection_payload


def check():
    url=os.getenv('CRM_TEST_DATABASE_URL','')
    parsed=urlparse(url)
    if parsed.hostname not in ('localhost','127.0.0.1') or parsed.path!='/hospkart_test':
        raise ValueError('Use a disposable local PostgreSQL hospkart_test database.')
    test_database='hospkart_test_'+uuid4().hex[:12]
    with psycopg.connect(url,autocommit=True) as control:
        control.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(test_database)))
    url=parsed._replace(path='/'+test_database).geturl()
    report={}
    with tempfile.TemporaryDirectory() as temp:
        source=Path(temp)/'source.db'
        with patch.object(app,'DB_PATH',source),patch.object(app,'DATABASE_URL',''):
            app.init_db();client=app.app.test_client()
            response=client.post('/api/workspace',json={'revision':0,'values':{
                'hk_v2_clients':[{'id':'000C','name':'Migration Hospital','mobile':'0012345678','status':'New Lead'}],
                'hk_v2_leads':[{'id':'000L','name':'Migration Lead','status':'New Lead'}]}},headers={'X-CRM-Request':'1'})
            assert response.status_code==200,response.json
        assert migrate(source,url)['applied'] is False
        assert migrate(source,url,apply=True)['applied']
        try:migrate(source,url,apply=True)
        except ValueError:pass
        else:raise AssertionError('Nonempty target migration was not rejected.')
        report['sqlite_migration_preserved_and_repeat_rejected']=True
        with patch.object(app,'DATABASE_URL',url),patch.object(app,'DATA_DIR',Path(temp)):
            client=app.app.test_client();headers={'X-CRM-Request':'1'}
            def workspace():return client.get('/api/workspace').json['workspace']
            assert client.get('/api/health').json['database_engine']=='postgresql'
            assert workspace()['values']['hk_v2_clients'][0]['mobile']=='0012345678'
            current=workspace();barrier=Barrier(2)
            def concurrent_save(value):
                barrier.wait()
                return app.app.test_client().post('/api/workspace',json={'revision':current['revision'],'values':{'hk_v2_feedback':[{'text':value}]}},headers=headers).status_code
            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes=list(executor.map(concurrent_save,['first','second']))
            assert sorted(outcomes)==[200,409],outcomes
            report['concurrent_stale_edit_rejected']=True
            before=workspace()
            try:
                with app.db_conn() as conn:
                    conn.execute('BEGIN IMMEDIATE')
                    conn.execute('UPDATE crm_workspace SET revision=revision+100 WHERE id=1')
                    raise ValueError('rollback probe')
            except ValueError:pass
            assert workspace()==before
            report['atomic_rollback']=True
            provider=FakeSheets()
            with patch.object(app.sheet_sync,'provider',provider):
                preview=client.post('/api/spreadsheet/preview',json=connection_payload(),headers=headers)
                assert preview.status_code==200,preview.json
                imported=client.post('/api/spreadsheet/import',json={'token':preview.json['token']},headers=headers)
                assert imported.status_code==200,imported.json
                provider.rows[0][1][1]='Updated Sheet Hospital'
                updated=client.post('/api/spreadsheet/sync',json={},headers=headers)
                assert updated.status_code==200,updated.json
                repeated=client.post('/api/spreadsheet/sync',json={},headers=headers).json
                assert repeated['connection']['report']['counts']['leads']['unchanged']==1
                assert len(repeated['queries'])==1
                assert repeated['queries'][0]['lead_id']=='0001'
            report['sheet_add_edit_repeat_and_relationship']=True
            with app.db_conn() as conn:
                epoch=conn.execute('SELECT last_attempt_epoch FROM sheet_connection').fetchone()[0]
            assert abs(epoch-datetime.now().timestamp())<10
            report['sync_epoch_full_precision']=True
            timestamp=datetime.now(app.IST).isoformat(timespec='seconds')
            complaint={'id':'CMP-TEST','customer_name':'Migration Hospital','subject':'Replacement','details':'Needs replacement',
                'status':'Resolved','priority':'High','assigned_owner':'Service','resolution':'Replacement delivered',
                'created_at':timestamp,'updated_at':timestamp,'resolved_at':timestamp}
            response=client.post('/api/workspace',json={'revision':workspace()['revision'],'values':{'hk_v2_complaints':[complaint]}},headers=headers)
            assert response.status_code==200,response.json
            assert 'Replacement delivered' in client.post('/api/quotesaarthi/chat',json={'message':'Show resolved complaints'}).json['reply']
            report['complaints_and_live_knowledge']=True
            with patch.object(app,'whatsapp_configured',return_value=True):
                result=client.post('/api/whatsapp/schedule',json={'to':'919999999999','client_name':'Synthetic only','scheduled_at':(datetime.now(app.IST)+timedelta(days=30)).isoformat(),
                    'template_name':'test_only','parameters':[],'confirmed_opt_in':True})
            assert result.status_code==200,result.json
            assert isinstance(result.json['id'],int)
            with patch.object(app,'email_configured',return_value=True):
                result=client.post('/api/email/send',json={'confirmed_recipients':True,'subject':'Test {{name}}','message':'Test only',
                    'recipients':[{'email':'synthetic@example.test','name':'Synthetic'}]})
            assert result.status_code==202,result.json
            report['message_ids_and_email_batch_insert']=True
            from openpyxl import load_workbook
            exported=client.post('/api/spreadsheet/export',json={'leads':repeated['leads'],'queries':repeated['queries']},headers=headers)
            assert exported.status_code==200
            book=load_workbook(BytesIO(exported.data));assert book['Leads']['A2'].value=='0001';book.close();exported.close()
            report['xlsx_export']=True
            result=client.post('/api/drive-import/save',json={'label':'Synthetic Drive workbook','link':'https://drive.google.com/file/d/synthetic_workbook_123456/view','target':'clients'},headers=headers)
            assert result.status_code==200,result.json
            assert len(client.get('/api/drive-import').json['links'])==1
            from drive_workbook_fixture import fixture
            copied,name,_=fixture()
            item=result.json['links'][0]
            response=client.post('/api/drive-import/save-copy',data={'id':item['id'],'file':(copied,name)},headers=headers)
            assert response.status_code==200,response.json
            with patch.object(app.drive_import_provider,'download') as google:
                downloaded=client.post('/api/drive-import/download',json={'id':item['id'],'saved_copy':True},headers=headers)
                assert downloaded.status_code==200 and downloaded.data.startswith(b'PK')
                google.assert_not_called();downloaded.close()
            report['postgres_workbook_bytes_saved_and_reimportable_without_google']=True
            app.init_db();assert workspace()['values']['hk_v2_complaints'][0]['resolution']=='Replacement delivered'
            report['reinitialize_retains_records_and_links']=True
            if os.getenv('PG_BROWSER_CHECKS','true')=='true':
                from waitress import create_server
                from playwright.sync_api import sync_playwright
                from drive_workbook_fixture import fixture
                server=create_server(app.app,host='127.0.0.1',port=0);Thread(target=server.run,daemon=True).start()
                try:
                    with sync_playwright() as playwright:
                        for channel in os.getenv('BROWSER_CHANNELS','chrome,msedge').split(','):
                            browser=playwright.chromium.launch(**({} if channel=='chromium' else {'channel':channel}),headless=True)
                            page=browser.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                            page.on('dialog',lambda dialog:dialog.accept())
                            login_browser_admin(page.context, f'http://127.0.0.1:{server.effective_port}/')
                            page.goto(f'http://127.0.0.1:{server.effective_port}/');page.wait_for_function('dashboardReady&&!document.body.inert')
                            page.evaluate("navigate('clients')")
                            page.get_by_role('button',name='Import Excel',exact=True).click()
                            assert page.locator('#excelImportSourceDialog').is_visible()
                            page.locator('#excelDriveSourceLink').fill('https://drive.google.com/file/d/synthetic_workbook_123456/view')
                            with patch.object(app.drive_import_provider,'download',side_effect=fixture):
                                page.locator('#excelDriveSourceSubmit').click()
                                if channel==os.getenv('BROWSER_CHANNELS','chrome,msedge').split(',')[0]:
                                    page.locator('#importConfirm:not(.hidden)').wait_for();page.locator('#importConfirmAccept').click()
                                page.wait_for_function('!driveImportBusy')
                                page.wait_for_function("clients.some(row=>row.name==='Shared Drive Hospital')")
                            page.reload();page.wait_for_function('dashboardReady&&!document.body.inert')
                            assert page.evaluate("clients.some(row=>row.name==='Shared Drive Hospital')")
                            assert not errors,errors
                            report['browser_'+channel]=True;browser.close()
                finally:server.close()
    print(json.dumps(report,indent=2))


if __name__=='__main__':check()
