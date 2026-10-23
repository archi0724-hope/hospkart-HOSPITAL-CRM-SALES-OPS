"""Exercise one-tab form mapping/import/sync in independent Chrome and Edge profiles."""
import json
import os
import sys
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from playwright.sync_api import sync_playwright
from waitress import create_server
from test_form_responses import FormResponseTests, LINK, FORM_LINK


def check():
    reports = []
    for channel in os.getenv('BROWSER_CHANNELS', 'chrome,msedge').split(','):
        fixture = FormResponseTests('test_response_create_edit_reorder_and_repeat')
        fixture.setUp()
        server = create_server(app.app, host='127.0.0.1', port=0)
        Thread(target=server.run, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel=channel, headless=True)
                page = browser.new_page(accept_downloads=True)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.effective_port}/')
                page.wait_for_function('dashboardReady&&!document.body.inert&&sheetState!==null')
                page.evaluate('openSpreadsheetConnection()')
                page.locator('#sheetLinkInput').fill(LINK)
                page.locator('#sheetSourceMode').select_option('form_responses')
                page.locator('#sheetFormLinkInput').fill(FORM_LINK)
                page.get_by_role('button', name='Save form and source links', exact=True).click()
                page.wait_for_function('!sheetBusy&&sheetState.source!==null')
                assert page.locator('#leadQueryFormLink').get_attribute('href') == FORM_LINK
                assert 'still need' in page.locator('#leadQueryFormStatus').inner_text()
                page.get_by_role('button', name='Check link and access', exact=True).click()
                page.wait_for_function('!sheetBusy&&sheetInspection!==null')
                assert not page.locator('#sheetQueriesTab').is_visible()
                page.get_by_role('button', name='Load columns', exact=True).click()
                page.wait_for_function("!sheetBusy&&document.getElementById('sheetMap-responses-timestamp')!==null")
                assert page.locator('#sheetMap-responses-details').input_value() == 'Detailed Description of Lead or Query'
                page.get_by_role('button', name='Preview and validate', exact=True).click()
                page.wait_for_function('!sheetBusy&&sheetPreviewToken!==null')
                assert 'FORM-L:' in page.locator('#sheetPreviewRows').inner_text()
                assert 'Email placeholder omitted' in page.locator('#sheetPreviewReport').inner_text()
                assert page.evaluate('sectionRecords.leads.length') == 0
                page.locator('#sheetImportButton').click()
                page.wait_for_function('!sheetBusy&&sectionRecords.leads.length===2')
                assert page.evaluate('allQueryRecords().length') == 1
                assert '0012345678' in page.locator('#sheetLeadRows').inner_text()
                fixture.provider.rows[0][1][9] = 'Updated form query'
                page.locator('#sheetSyncButton').click()
                page.wait_for_function("!sheetBusy&&sheetState.queries[0].details==='Updated form query'")
                page.locator('#sheetSyncButton').click()
                page.wait_for_function('!sheetBusy')
                assert '2 unchanged' in page.locator('#sheetSyncReport').inner_text()
                page.reload()
                page.wait_for_function('dashboardReady&&!document.body.inert&&sheetState!==null')
                page.evaluate("navigate('leads')")
                assert page.locator('#leadQueryFormLink').get_attribute('href') == FORM_LINK
                assert page.locator('#sheetSourceMode').input_value() == 'form_responses'
                assert page.evaluate('sectionRecords.leads.length') == 2
                assert not errors, errors
                reports.append({'browser': channel, 'form_link_persisted': True, 'one_tab_mapping': True,
                                'preview_import': True, 'query_relationship': True, 'repeat_sync_no_duplicates': True,
                                'reload_persistence': True, 'javascript_errors': errors})
                browser.close()
        finally:
            server.close()
            fixture.doCleanups()
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    check()
