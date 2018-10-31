#!/usr/bin/env python3

import argparse
from filelock import FileLock
import httplib2
import os
import time

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/sheets.googleapis.com-python-quickstart.json
scopes = 'https://www.googleapis.com/auth/drive.file ' \
         'https://www.googleapis.com/auth/drive.install'
client_secret_fname = 'client_secret.json'
google_app_name = 'FCCH Access Control'

bin_dir = os.path.dirname(__file__)
app_dir = os.path.dirname(bin_dir)
client_secret_fpath = os.path.join(
    app_dir,
    'etc',
    client_secret_fname)

def get_credentials(flags):
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
        'fcch-access-control-google-oauth.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(client_secret_fpath, scopes)
        flow.user_agent = google_app_name
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def download_google_sheet(flags, debug, acl_dir, ts):
    credentials = get_credentials(flags)
    http = credentials.authorize(httplib2.Http())
    discoveryUrl = \
        'https://sheets.googleapis.com/$discovery/rest?version=v4'
    service = discovery.build('sheets', 'v4', http=http,
        discoveryServiceUrl=discoveryUrl)
    spreadsheetId = '1Yyh2_EYODBmzlVgj0tv-oQpPBWjPptk3kwTZ3CThrzc'
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheetId,
        range='Access Control Export'
    ).execute()
    values = result.get('values', [])
    if not values:
        raise Exception('No values found in Google Sheet')
        return

    headers = values[0]
    if headers[0] != 'RFID':
        raise Exception('Header[0] not RFID???')
    acls = headers[1:]

    def clean_rfid(rfid):
        try:
            return int(rfid.strip().lstrip('0'))
        except:
            return None

    acl_content = {acl: [] for acl in acls}
    for row in values[1:]:
        if debug: print()
        if debug: print('Values:', repr(row))
        if not len(row):
          continue
        rfids = row[0]
        if debug: print('Raw RFIDs:', repr(rfids))
        rfids = rfids.split(',')
        rfids = [clean_rfid(r) for r in rfids]
        rfids = [r for r in rfids if r]
        if debug: print('Clean RFIDs:', repr(rfids))
        if not rfids:
            continue
        for (i, acl) in enumerate(acls):
            col = 1 + i
            if col >= len(row):
                break
            access = row[col]
            if debug: print(acl, repr(access))
            if access != 'y':
                continue
            if debug: print(acl, "yes")
            acl_content[acl].extend(rfids)

    old_files = os.listdir(acl_dir)

    acl_fname_prefix = 'acl-'

    for acl in acls:
        fname = acl_fname_prefix + acl
        fpath = os.path.join(acl_dir, fname)
        try:
            old_files.remove(fname)
        except:
            pass
        fname_tmp = '.' + fname + '.tmp'
        fpath_tmp = os.path.join(acl_dir, fname_tmp)
        with open(fpath_tmp, 'wt') as f:
            print('# Generated at', ts, file=f)
            for rfid in sorted(acl_content[acl]):
                print(rfid, file=f)
        os.rename(fpath_tmp, fpath)

    for fname in old_files:
        if not fname.startswith(acl_fname_prefix):
            continue
        fpath = os.path.join(acl_dir, fname)
        os.unlink(fpath)

if __name__ == '__main__':
    ts = time.strftime('%Y%m%dT%H%M%S')
    parser = argparse.ArgumentParser(
        parents=[tools.argparser],
        description='Download Access Control info from Google Sheet')
    parser.add_argument(
        '--debug', action='store_true', help='Turn on debugging prints')
    parser.add_argument(
        '--auth-only', action='store_true',
        help='Set up authentication, but don\'t download data')
    parser.add_argument(
        'output_dir', nargs='?',
        help='Directory to write RFID lists to')
    args = parser.parse_args()
    if args.debug: print(args)
    if args.auth_only:
        get_credentials(args)
    else:
        if not args.output_dir:
            parser.error('output_dir required if --auth-only not specified')
        lock_fn = os.path.join(args.output_dir, ".lock")
        with FileLock(lock_fn):
            download_google_sheet(args, args.debug, args.output_dir, ts)
        print('RFID lists generated OK at', ts)
