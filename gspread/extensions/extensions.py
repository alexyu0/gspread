import webbrowser
from time import sleep
import json
import os
import logging
from datetime import datetime


import requests


log = logging.getLogger(__name__)


class GSpread:
    def __init__(self, access_token, access_token_path, spreadsheet_id, host, port):
        self.access_token = access_token
        self.access_token_path = access_token_path
        self.spreadsheet_id = spreadsheet_id
        self.host = host
        self.port = port

        if self.access_token is None:
            # token authorization flow
            if os.path.exists(self.access_token_path):
                with open(self.access_token_path, 'r') as f:
                    self.access_token = json.load(f)
                    print(self.access_token)
            else:
                self.__auth_loop(None, None, None, None)

        self.base_url = 'https://sheets.googleapis.com/v4/spreadsheets/{}'.format(
            self.spreadsheet_id)
        self.url_template = self.base_url + ':{}'

    @property
    def auth_header(self):
        return {'Authorization': 'Bearer {}'.format(self.access_token)}

    def __auth_loop(self, fn, args, kwargs, pass_fn):
        webbrowser.open('{}:{}/authorize'.format(self.host, self.port))
        stale_token = self.access_token
        while True:
            print("in loop", stale_token, self.access_token)
            if os.path.exists(self.access_token_path):
                with open(self.access_token_path, 'r') as f:
                    self.access_token = json.load(f)

            if fn is None:
                sleep(1)
                if self.access_token != stale_token:
                    print('tokens are different, breaking loop')
                    break
            else:
                sleep(1)
                if 'headers' in kwargs:
                    kwargs['headers'] = self.auth_header
                print('auth pass fn kwargs is {}'.format(kwargs))
                result = fn(*args, **kwargs)
                print(result, result.ok)
                if pass_fn and pass_fn(result):
                    print('pass_fn {} passed, breaking loop'.format(pass_fn))
                    break

    def create_sheet_at_index(self, title, index, rows, cols):
        body = {
            'requests': [
                {
                    'addSheet': {
                        'properties': {
                            'title': title,
                            'sheetType': 'GRID',
                            'gridProperties': {
                                'rowCount': rows,
                                'columnCount': cols,
                            },
                            'index': index,
                        },
                    },
                },
            ],
        }
        while True:
            resp = requests.post(self.url_template.format('batchUpdate'), 
                headers=self.auth_header,
                json=body)
            if not resp.ok:
                log.error(resp.json())
                if resp.status_code == 401:
                    # auth error so refresh token then break since auth loop will do the work
                    self.__auth_loop(
                        requests.post, 
                        [self.url_template.format('batchUpdate')],
                        {
                            'headers': self.auth_header,
                            'json': body,
                        },
                        lambda resp: resp.ok,
                    )

            break

    def duplicate_sheet(self, id, title, index):
        body = {
            'requests': [
                {
                    'duplicateSheet': {
                        'sourceSheetId': id,
                        'newSheetName': '{}_copy_{}'.format(title, datetime.now()),
                        'insertSheetIndex': index + 1,
                    },
                },
            ],
        }
        while True:
            resp = requests.post(self.url_template.format('batchUpdate'), 
                headers=self.auth_header,
                json=body)
            if not resp.ok:
                log.error(resp.json())
                if resp.status_code == 401:
                    # auth error so refresh token then break since auth loop will do the work
                    self.__auth_loop(
                        requests.post, 
                        [self.url_template.format('batchUpdate')],
                        {
                            'headers': self.auth_header,
                            'json': body,
                        },
                        lambda resp: resp.ok,
                    )

            break
