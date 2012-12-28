#!/bin/bash
virtualenv --no-site-packages .env
. .env/bin/activate
pip install -r harness-requires
./update_cinder.sh
nosetests -v -x --cover-html --cover-erase --with-coverage --cover-package=cinder.volume.drivers.xenapi
