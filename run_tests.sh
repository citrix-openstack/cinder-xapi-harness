#!/bin/bash
virtualenv --no-site-packages .env
. .env/bin/activate
pip install -r harness-requires
./update_cinder.sh

set -eux
coverage erase
coverage run .env/bin/nosetests -v -x "$@"
coverage report --show-missing --include=*xenapi*
