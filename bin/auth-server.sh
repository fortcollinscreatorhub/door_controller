#!/bin/bash

set -e

script_dir="$(dirname "$0")"
app_dir="$(cd "${script_dir}"/.. && pwd)"

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

. "${app_dir}/venv/bin/activate"
export FLASK_APP="${app_dir}/auth-server/auth-server.py"
#export FLASK_DEBUG=1
exec flask run --host=0.0.0.0 --port=8080
