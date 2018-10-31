#!/bin/bash

set -e
set -x

script_dir="$(dirname "$0")"
app_dir="$(cd "${script_dir}"/.. && pwd)"

cd "${app_dir}"

apt -y update
apt -y install build-essential python3-dev virtualenv postfix mailutils

groupadd --system gpio || true

useradd --system --home-dir "${app_dir}" fcchaccess || true

# Could be combined with useradd,
# but doing this separately works for upgrades too
usermod -a -G gpio fcchaccess || true
usermod -a -G dialout fcchaccess || true

if [ ! -d venv ]; then
  virtualenv -p python3 venv
fi
(. ./venv/bin/activate && pip install --upgrade -r etc/pip-requirements.txt)

mkdir -p "${app_dir}/.credentials"

chown -R root:fcchaccess "${app_dir}"
chmod -R u+rX,u-w,g+rX,g-w,o-rwx "${app_dir}"
chmod -R ug+w "${app_dir}/.credentials" "${app_dir}/var"

su -c "\"${app_dir}/bin/generate-acls.sh\" --auth-only" fcchaccess
set +x
cat <<ENDOFDOC

INSTRUCTIONS:

1) Open a web browser
2) Navigate to Google Drive
3) Open the folder containing the membership list:
   Fort Collins Creator Hub Public > Board Private > Membership List
4) Right-click (or Options-click) the "000 Membership List" document
5) In the popup menu, select Open With > FCCH Access Control
6) Your web browser will redirect to the FCCH website

NOTE: You only need to follow these instructions the very first time you run
this install script for a given Google account, or after you revoke the FCCH
Access Control application's access to the membership list document.

Once these actions are complete, press enter to continue:
ENDOFDOC
read dummy
set -x
su -c "\"${app_dir}/bin/generate-acls.sh\" \"${app_dir}/var/acls/\"" fcchaccess

sed -i -e "/ExecStart/s@=.*/@=${app_dir}/bin/@" "${app_dir}/etc/systemd/"*.service

systemctl enable \
  "${app_dir}/etc/systemd/fcch-access-control-auth-server.service"
systemctl start fcch-access-control-auth-server

systemctl enable \
  "${app_dir}/etc/systemd/fcch-access-control-door-controller.service"
systemctl start fcch-access-control-door-controller
