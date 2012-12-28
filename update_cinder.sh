#!/bin/bash
[ -e cinder-master ] && (
    cd cinder-master
    git pull
) || git clone git://github.com/citrix-openstack/cinder.git cinder-master
rm -rf cinder
mkdir -p cinder/volume/driver
touch cinder/__init__.py
touch cinder/volume/__init__.py
touch cinder/volume/driver/__init__.py
cp -R cinder-master/cinder/volume/driver/xenapi cinder/volume/driver/
