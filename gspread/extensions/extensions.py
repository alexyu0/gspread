import traceback
import webbrowser
from time import sleep
import json
import os
import logging
from datetime import datetime
import random


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
            print('in loop', stale_token, self.access_token)
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

    def __request_loop(self, body):
        max_backoff=32
        i = 0
        while True:
            resp = requests.post(self.url_template.format('batchUpdate'),
                headers=self.auth_header,
                json=body)
            if resp.status_code == 429:
                # rate limited by the googs
                rand_ms = float(random.uniform(0, 1000))
                sleep_time = min(2**i + rand_ms/1000, max_backoff)
                for line in traceback.format_stack():
                    print(line.strip())
                log.info('Rate limited (error code 429), sleeping for {}'.format(sleep_time))
                sleep(sleep_time)
                i += 1
                continue
            elif not resp.ok:
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
                else:
                    raise Exception(resp.json())

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
        self.__request_loop(body)

    def duplicate_sheet(self, sheet_id, title, index):
        body = {
            'requests': [
                {
                    'duplicateSheet': {
                        'sourceSheetId': sheet_id,
                        'newSheetName': '{}_copy_{}'.format(title, datetime.now()),
                        'insertSheetIndex': index + 1,
                    },
                },
            ],
        }
        self.__request_loop(body)

    def clear_conditional_formatting(self, sheet_id):
        while True:
            try:
                self.__request_loop({
                    'requests': [
                        {
                            'deleteConditionalFormatRule': {
                                'index': 0,
                                'sheetId': sheet_id,
                            },
                        },
                    ],
                })
            except Exception as e:
                log.info('clearing done')
                break

    def color_conditional_format(self,
                                 sheet_id,
                                 start_col,
                                 start_row,
                                 end_col,
                                 end_row,
                                 threshold=None,
                                 rgb_tup=(255,255,255),
                                 lte=False,
                                 gte=False):
        # bool condition type
        cond_type = None
        if lte:
            cond_type = 'NUMBER_LESS_THAN_EQ'
        elif gte:
            cond_type = 'NUMBER_GREATER_THAN_EQ'
        else:
            raise 'Invalid condition, choose either lte or gte'

        body = {
            'requests': [
                {
                    'addConditionalFormatRule': {
                        'rule': {
                            'ranges': [
                                {
                                    'sheetId': sheet_id,
                                    'startColumnIndex': start_col,
                                    'startRowIndex': start_row,
                                    'endColumnIndex': end_col,
                                    'endRowIndex': end_row,
                                },
                            ],
                            'booleanRule': {
                                'condition': {
                                    'type': cond_type,
                                    'values': [
                                        {
                                            'userEnteredValue': threshold,
                                        }
                                    ]
                                },
                                'format': {
                                    'backgroundColor': {
                                        'red': rgb_tup[0]/255.0,
                                        'green': rgb_tup[1]/255.0,
                                        'blue': rgb_tup[2]/255.0,
                                    }
                                }
                            }
                        },
                        'index': 0
                    }
                }
            ]
        }
        self.__request_loop(body)

    def insert_cells(self, sheet_id, start_row, start_col, end_col, num_rows):
        body = {
            'requests': [
                {
                    'insertRange': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': start_row,
                            'endRowIndex': start_row + num_rows,
                            'startColumnIndex': start_col,
                            'endColumnIndex': end_col
                        },
                        'shiftDimension': 'ROWS'
                    }
                }
            ]
        }
        self.__request_loop(body)
