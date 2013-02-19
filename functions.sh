#!/bin/bash

function set_parameters_from_environment
{
cat params.py.template |
sed -e "s/XAPIPASS/$XAPIPASS/" \
-e "s/XAPISERVER/$XAPISERVER/" \
-e "s/NFSSERVER/$NFSSERVER/" \
-e "s,NFSPATH,$NFSPATH," \
-e "s,LOCALPATHTONFS,$LOCALPATHTONFS," > params.py
}

function setup_virtualenv
{
(
virtualenv --no-site-packages "$1"
set +u
. "$1/bin/activate"
set -u
pip install -r harness-requires
)
}

function clone_cinder_repo_to
{
[ -e "$1" ] || git clone "$REPO" "$1"

(
cd "$1"
git checkout "${BRANCH-master}"
git pull
)

}

function extract_xapi_code_from
{
rm -rf cinder
mkdir -p cinder/volume/drivers
touch cinder/__init__.py
touch cinder/volume/__init__.py
touch cinder/volume/drivers/__init__.py
cp -R $1/cinder/volume/drivers/xenapi cinder/volume/drivers/
}

function run_tests
{
(
set +u
. "$1/bin/activate"
set -u
coverage erase
shift
coverage run .env/bin/nosetests -v -x "$@"
coverage report --show-missing --include=*xenapi*
)
}

