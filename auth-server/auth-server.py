from __future__ import print_function

import flask
import os
import re
import time
import subprocess

auth_server_dir = os.path.dirname(__file__)
app_dir = os.path.dirname(auth_server_dir)
bin_dir = os.path.join(app_dir, 'bin')
update_acls_bin = os.path.join(bin_dir, 'generate-acls.sh')
acl_dir = os.path.join(app_dir, 'var', 'acls')
acl_fn_prefix = 'acl-'
log_dir = os.path.join(app_dir, 'var', 'log')
access_log_fn_template = os.path.join(log_dir, 'access-%Y-%m.log')
access_log_ts_template = '%Y%m%dT%H%M%S.'
acl_update_log_fn = os.path.join(log_dir, 'acl-update.log')

re_acl_name = re.compile('^[a-z0-9_.-]+$')

def acl_fn(acl):
    if not re_acl_name.match(acl):
        raise Exception('Invalid ACL ID', acl)
    return os.path.join(acl_dir, acl_fn_prefix + acl)

def show_file(fn, template, **extra):
    try:
        with open(fn, 'rt') as f:
            content=f.read()
    except:
        content='Could not read log file'
    return flask.render_template(template, content=content, **extra)

update_acls_popen = None

def update_acls_start():
    global update_acls_popen
    if update_acls_popen:
        return 'Already running'
    try:
        with open(acl_update_log_fn, 'wt') as logf:
            update_acls_popen = subprocess.Popen([update_acls_bin, acl_dir],
                stdout=logf, stderr=logf)
        return None
    except Exception as e:
        return 'Could not start update process: ' + repr(e)

def update_acls_poll():
    global update_acls_popen
    if not update_acls_popen:
        return False
    update_acls_popen.poll()
    if update_acls_popen.returncode is not None:
        update_acls_popen = None
    return update_acls_popen is not None

def access_log_fn():
    return time.strftime(access_log_fn_template)

last_ts = None
ts_seq_num = 0
def gen_ts():
    global ts_seq_num
    global last_ts
    ts = time.strftime(access_log_ts_template)
    if ts == last_ts:
        ts_seq_num += 1
    else:
        ts_seq_num = 0
    last_ts = ts
    return ts + str(ts_seq_num)

app = flask.Flask(__name__)

@app.route('/')
def index():
    return flask.render_template('index.html')

@app.route('/ui/update-acls')
def ui_update_acls():
    update_acls_poll()
    message = update_acls_start()
    if message:
        return flask.render_template('ui-update-acls.html', message=message)
    else:
        return flask.redirect('/ui/view-acl-update-log', code=302)

@app.route('/ui/view-acl-update-log')
def ui_view_acl_update_log():
    running = update_acls_poll()
    return show_file(acl_update_log_fn, 'ui-view-acl-update-log.html', running=running)

@app.route('/ui/view-acls')
def ui_view_acls():
    fns = os.listdir(acl_dir)
    acls = [acl[len(acl_fn_prefix):] for acl in fns if acl.startswith(acl_fn_prefix)]
    return flask.render_template('ui-view-acls.html', acls=acls)

@app.route('/ui/view-acl/<acl>')
def ui_view_acl(acl):
    return show_file(acl_fn(acl), 'ui-view-acl.html', name=acl)

@app.route('/ui/view-access-check-log')
def ui_view_access_check_log():
    return show_file(access_log_fn(), 'ui-view-access-check-log.html')

@app.route('/api/check-access-0/<acl>/<rfid>')
def api_check_access_0(acl, rfid):
    result = False
    with open(acl_fn(acl), 'rt') as f:
        for l in f.readlines():
            if l.strip() == rfid:
                result = True
                break
    with open(access_log_fn(), 'at+') as f:
        print('%s,check,%s,%s,%s' % (gen_ts(), acl, rfid, repr(result)), file=f)
    return flask.Response(repr(result), mimetype='text/plain')

@app.route('/api/log-remote-access-check-0/<acl>/<rfid>/<result>')
def api_log_remote_access_check_0(acl, rfid, result):
    with open(access_log_fn(), 'at+') as f:
        print('%s,check,%s,%s,%s' % (gen_ts(), acl, rfid, result), file=f)

@app.route('/api/get-acl-0/<acl>')
def api_get_acl_0(acl):
    with open(acl_fn(acl), 'rt') as f:
        return flask.Response(f.read(), mimetype='text/plain')
