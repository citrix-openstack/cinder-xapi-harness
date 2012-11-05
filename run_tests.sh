#!/bin/bash
virtualenv --no-site-packages .env
. .env/bin/activate
rm -rf cinder
pip install -r harness-requires
[ -e cinder-master ] && (
    cd cinder-master
    git pull
) || git clone git://github.com/citrix-openstack/cinder.git cinder-master
mkdir -p cinder/volume
touch cinder/__init__.py
touch cinder/volume/__init__.py
cp -R cinder-master/cinder/volume/xenapi cinder/volume/
nosetests -v -x --cover-html --cover-erase --with-coverage --cover-package=xenapi_nfs_driver
