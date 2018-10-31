#!/bin/bash

set -e

script_dir="$(dirname "$0")"
app_dir="$(cd "${script_dir}"/.. && pwd)"

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

. "${app_dir}/venv/bin/activate"
exec python "${app_dir}/door-controller/door-controller.py"
