from __future__ import print_function, absolute_import

import pickle
import os
import sys
import json


from gspread import authorize as gspread_authorize
from gspread.cell import Cell
from google.oauth2 import credentials as oauth2_creds, service_account as oauth2_sa
import google_auth_oauthlib.flow
from oauth2client.service_account import ServiceAccountCredentials
import flask
import requests
import pprint


import budgeting.utils.constants as constants


pp = pprint.PrettyPrinter(indent=4)

utils_bp = flask.Blueprint('utils_api', __name__)


###################################
# OAuth2 Flask routes and helpers #
###################################
def _credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }


def _print_index_table():
    return ('<table>' +
            '<tr><td><a href="/test">Test an API request</a></td>' +
            '<td>Submit an API request and see a formatted JSON response. ' +
            '        Go through the authorization flow if there are no stored ' +
            '        credentials for the user.</td></tr>' +
            '<tr><td><a href="/authorize">Test the auth flow directly</a></td>' +
            '<td>Go directly to the authorization flow. If there are stored ' +
            '        credentials, you still might not be prompted to reauthorize ' +
            '        the application.</td></tr>' +
            '<tr><td><a href="/revoke">Revoke current credentials</a></td>' +
            '<td>Revoke the access token associated with the current user ' +
            '        session. After revoking credentials, if you go to the test ' +
            '        page, you should see an <code>invalid_grant</code> error.' +
            '</td></tr>' +
            '<tr><td><a href="/clear">Clear Flask session credentials</a></td>' +
            '<td>Clear the access token currently stored in the user session. ' +
            '        After clearing the token, if you <a href="/test">test the ' +
            '        API request</a> again, you should go back to the auth flow.' +
            '</td></tr></table>')


@utils_bp.route('/test')
def test_api_request():
    if 'credentials' not in flask.session:
        return flask.redirect('authorize')

    # Load credentials from the session.
    credentials = oauth2_creds.Credentials(**flask.session['credentials'])
    credentials = _credentials_to_dict(credentials)

    # TODO maybe save these credentials in a persistent database instead.
    flask.session['credentials'] = credentials
    pp.pprint(credentials)

    return flask.jsonify(credentials)


@utils_bp.route('/authorize')
def authorize():
    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        constants.CLIENT_SECRETS_FILE, scopes=constants.SCOPES)
    # flow = oauth2_sa.Credentials.from_service_account_file(
    #     constants.CLIENT_SECRETS_FILE, scopes=constants.SCOPES)

    # The URI created here must exactly match one of the authorized redirect URIs
    # for the OAuth 2.0 client, which you configured in the API Console. If this
    # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
    # error.
    flow.redirect_uri = flask.url_for('utils_api.oauth2callback', _external=True)

    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')

    # Store the state so the callback can verify the auth server response.
    flask.session['state'] = state

    return flask.redirect(authorization_url)


@utils_bp.route('/oauth2callback')
def oauth2callback():
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = flask.session['state']

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        constants.CLIENT_SECRETS_FILE, scopes=constants.SCOPES, state=state)
    flow.redirect_uri = flask.url_for('utils_api.oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #                            credentials in a persistent database instead.
    credentials = flow.credentials
    flask.session['credentials'] = _credentials_to_dict(credentials)
    print('new token is {}'.format(credentials.to_json))
    constants.ACCESS_TOKEN = str(credentials.to_json)
    with open(constants.ACCESS_TOKEN_PATH, 'w') as f:
        json.dump(credentials.token, f)
        f.flush()

    return flask.redirect(flask.url_for('utils_api.test_api_request'))


@utils_bp.route('/revoke')
def revoke():
    if 'credentials' not in flask.session:
        return ('You need to <a href="/authorize">authorize</a> before ' +
                'testing the code to revoke credentials.')

    credentials = oauth2_creds.Credentials(**flask.session.pop('credentials'))

    revoke = requests.post('https://oauth2.googleapis.com/revoke',
        params={'token': credentials.token},
        headers = {'content-type': 'application/x-www-form-urlencoded'})

    status_code = getattr(revoke, 'status_code')
    if status_code == 200:
        return('Credentials successfully revoked.' + _print_index_table())
    else:
        return('An error occurred.' + _print_index_table())


@utils_bp.route('/clear')
def clear_credentials():
    if 'credentials' in flask.session:
        del flask.session['credentials']
    return ('Credentials have been cleared.<br><br>' +
            _print_index_table())


@utils_bp.route('/')
def index():
    return _print_index_table()


#########
# other #
#########
def auth():
    """
    Authenticates user for gspread
    """
    # use creds to create a client to interact with the Google Drive API
    scope = ['https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        constants.SERVICE_ACCOUNT_FILE, scope)
    return gspread_authorize(creds)


def tuples_to_cells(tuples, row_offset=0, col_offset=0):
    # (tuple, int, int) -> List[Cell]
    cells = []
    for row in range(0, len(tuples)):
        for col in range(0, len(tuples[row])):
            cells.append(Cell(row + row_offset + 1, col + col_offset + 1, tuples[row][col]))

    return cells
