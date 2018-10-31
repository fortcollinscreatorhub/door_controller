Install OS
sudo bash
wpa_supplicant.conf, restart service or reboot to get wifi
Disable GUI VNC for security
raspi-config to enable SSH, can do the rest over SSH
apt update
apt dist-upgrade
apt install openssh-server postfix mailutils
# when asked about postfix, select XXX site
ssh restart
install SSH public keys
verify key access
install sshd_config
ssh restart
cp files in backup/ to correct location
newaliases
service postfix restart
echo test|mail -s test swarren@wwwdotorg.org
raspi-config to disable getty on serial, leave HW enabled
run bin/install.sh
reboot, test


Interacting with the web server from an SSH session:

    links http://127.0.0.1:8080/

    (arrows select links or scroll, enter follows a link, backspace goes back,
    q quits)

Note!

    This README is significantly out-of-date and needs to be re-written. Use at
    your own risk!

One-time setup:

    Ensure you're running from a terminal/shell in a GUI environment that can
    launch a web browser

    cd to root directory of this project
    virtualenv -p python3 venv
    . ./venv/bin/activate
    pip install -r etc/pip-requirements.txt

    To re-generate etc/pip-requirements.txt:
    (. ./venv/bin/activate && pip freeze) > etc/pip-requirements.txt

    ./bin/generate-acls.sh var/acls
    # 1) Log in to Google account in web browser if prompted
    # 2) Allow app to access/install-into Google driver in web browser if prompted
    # 3) Open Google drive in web browser, navigate to the FCCH Membership List
    #    folder, right-click the 000 Membership List file, select Open With ->
    #    FCCH Access Control, wait for browser to redirect to FCCH website

    To run:

    cd to root directory of this project
    ./bin/generate-acls.sh var/acls

    Result:
    View var/acls/acl-${aclname} e.g. acl-door, acl-big-laser-cutter

Debug logs:

    systemctl enable $(pwd)/etc/systemd/fcch-access-control-auth-server.service
    systemctl disable fcch-access-control-auth-server.service
    systemctl start/stop/restart fcch-access-control-auth-server
    journalctl -u fcch-access-control-auth-server

    systemctl enable $(pwd)/etc/systemd/fcch-access-control-door-controller.service
    systemctl disable fcch-access-control-door-controller.service
    systemctl start/stop/restart fcch-access-control-door-controller
    journalctl -u fcch-access-control-door-controller
