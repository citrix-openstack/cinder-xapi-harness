#!/bin/bash
virtualenv --no-site-packages .env
. .env/bin/activate
pip install -r harness-requires
nosetests -v -x --cover-html --cover-erase --with-coverage --cover-package=xenapi_nfs_driver
