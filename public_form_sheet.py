"""Read an explicitly configured form-response tab using its existing link access.

This adapter never changes Google sharing or submits data to Google. Private
sources continue to use the authenticated Google Sheets provider.
"""
import csv
import re
from io import StringIO
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


class PublicFormSheet:
    def __init__(self, file_id, profile, error, max_bytes=12*1024*1024):
        self.error, self.max_bytes, self.file_id = error, max_bytes, file_id
        required = {'gid', 'tab_name', 'title', 'locale', 'timezone'}
        if (not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', file_id) or not isinstance(profile, dict)
                or set(profile) != required or isinstance(profile.get('gid'), bool)
                or not isinstance(profile.get('gid'), int) or not 0 <= profile['gid'] <= 2147483647
                or any(not isinstance(profile.get(key), str) or not profile[key].strip() or len(profile[key]) > 200 for key in required - {'gid'})
                or not re.fullmatch(r'[a-z]{2}_[A-Z]{2}', profile['locale'])):
            raise error('Invalid existing-link form source configuration.')
        try:
            ZoneInfo(profile['timezone'])
        except (ZoneInfoNotFoundError, ValueError):
            raise error('Invalid response-sheet time zone.') from None
        self.profile = dict(profile)
        self.cached_rows = None

    def rows(self):
        if self.cached_rows is not None:
            return self.cached_rows
        url = 'https://docs.google.com/spreadsheets/d/' + self.file_id + '/export'
        try:
            with requests.get(url, params={'format':'csv', 'gid':self.profile['gid']}, timeout=(10,45), stream=True) as response:
                if response.status_code in (401,403,404):
                    raise self.error('The response sheet is no longer readable through its existing link. Use authenticated Google access or restore the intended source access. Saved CRM data is retained.',403)
                if response.status_code == 429:
                    raise self.error('Google is limiting requests. Wait and retry; saved data is retained.',503)
                if response.status_code != 200 or 'text/csv' not in response.headers.get('Content-Type','').lower():
                    raise self.error('Google did not return a readable response worksheet. Check the selected tab and access; saved data is retained.',502)
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise self.error('Response worksheet exceeds the 12 MB import limit.')
                    chunks.append(chunk)
            reader = csv.reader(StringIO(b''.join(chunks).decode('utf-8-sig')))
            rows = []
            for index, row in enumerate(reader):
                if index > 20000 or len(row) > 200:
                    raise self.error('Response worksheet exceeds 20,000 rows or 200 columns.')
                rows.append(row)
            if not rows or not any(rows[0]):
                raise self.error('Response worksheet has no readable column headers.')
            self.cached_rows = rows
            return rows
        except self.error:
            raise
        except (requests.RequestException, UnicodeError, csv.Error):
            raise self.error('Google response-sheet read failed or timed out. Saved CRM data is retained.',502) from None

    def inspect(self, file_id):
        if file_id != self.file_id:
            raise self.error('The response-sheet ID does not match the configured source.')
        self.rows()
        p = self.profile
        return {'id':file_id, 'name':p['title'], 'url':'https://docs.google.com/spreadsheets/d/'+file_id+'/edit',
                'tabs':[{'id':p['gid'], 'name':p['tab_name']}], 'locale':p['locale'], 'timezone':p['timezone']}

    def read(self, file_id, tabs, headers_only=False):
        if file_id != self.file_id or any(tab != self.profile['tab_name'] for tab in tabs):
            raise self.error('Select the configured response worksheet.')
        rows = self.rows()
        return [rows[:6] if headers_only else rows for _ in tabs]
