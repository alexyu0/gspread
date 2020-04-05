import webbrowser
from time import sleep
import json
import os
import logging


import requests


import budgeting.utils.constants as constants


log = logging.getLogger(__name__)


AUTH_HEADER = None
SHEETS_BASE_URL = 'https://sheets.googleapis.com/v4/spreadsheets/{}'.format(
    constants.SPREADSHEET_ID)
SHEETS_URL_TEMPLATE = SHEETS_BASE_URL + ':{}'


class GSpread:
    def __init__(self):
        if constants.ACCESS_TOKEN is None:
            # token authorization flow
            if os.path.exists(constants.ACCESS_TOKEN_PATH):
                with open(constants.ACCESS_TOKEN_PATH, 'r') as f:
                    constants.ACCESS_TOKEN = json.load(f)
                    print(constants.ACCESS_TOKEN)
            else:
                self.__auth_loop()

        global AUTH_HEADER
        AUTH_HEADER =  {'Authorization': 'Bearer {}'.format(constants.ACCESS_TOKEN)}

    def __auth_loop(self, fn, args, kwargs, pass_fn):
        webbrowser.open('{}:{}/authorize'.format(constants.HOST, constants.PORT))
        stale_token = constants.ACCESS_TOKEN
        while True:
            print("in loop", stale_token, constants.ACCESS_TOKEN)
            sleep(60)
            if os.path.exists(constants.ACCESS_TOKEN_PATH):
                with open(constants.ACCESS_TOKEN_PATH, 'r') as f:
                    constants.ACCESS_TOKEN = json.load(f)
            if pass_fn(fn(*args, **kwargs)):
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
            resp = requests.post(SHEETS_URL_TEMPLATE.format('batchUpdate'), 
                headers=AUTH_HEADER,
                json=body)
            if not resp.ok:
                log.error(resp.json())
                if resp.status_code == 401:
                    # auth error so refresh token
                    self.__auth_loop(
                        requests.post, 
                        [SHEETS_URL_TEMPLATE.format('batchUpdate')],
                        {
                            'headers': AUTH_HEADER,
                            'json': body,
                        },
                        lambda resp: resp.ok,
                    )
            else:
                break

    def duplicate_sheet(self, id, title):
        body = {
            'requests': [
                {
                    'duplicateSheetRequest': {
                        'sourceSheetId': id,
                        'newSheetName': '{}_copy_{}'.format(title, datetime.now()),
                    },
                },
            ],
        }
        while True:
            resp = requests.post(SHEETS_URL_TEMPLATE.format('batchUpdate'), 
                headers=AUTH_HEADER,
                json=body)
            if not resp.ok:
                log.error(resp.json())
                if resp.status_code == 401:
                    # auth error so refresh token
                    self.__auth_loop()
            else:
                break
