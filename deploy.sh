#!/bin/bash

git pull
sudo -u edxapp /edx/bin/pip.edxapp uninstall -y .
sudo -u edxapp /edx/bin/pip.edxapp install . 
sudo /edx/bin/supervisorctl -c /edx/etc/supervisord.conf restart edxapp:
