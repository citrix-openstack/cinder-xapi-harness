#!/bin/bash
virtualenv --no-site-packages .env
. .env/bin/activate
pip install -r harness-requires
./update_cinder.sh

coverage erase
coverage run nosetests
coverage report --show-missing --include=cinder.volume.drivers.xenap*
