#!/bin/bash

git pull
sudo -u edxapp /edx/bin/pip.edxapp uninstall -y edx-sga
sudo -u edxapp /edx/bin/pip.edxapp install edx-sga 
