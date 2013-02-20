#!/bin/bash

CINDER_DIR="$HOME/cinder"
HARNESS_DIR="$HOME/cinder-xapi-harness"

function wait_for_change
{
echo "Waiting for filesystem changes"
inotifywait -q -r -e close_write --exclude '.*sw.$' "$CINDER_DIR/cinder/volume/drivers/xenapi" "$HARNESS_DIR/test_xenapi_nfs_driver.py"
}

function run_tests
{
echo "packing files"
TEMPDIR=$(mktemp -d)

(
cd "$TEMPDIR"
mkdir -p cinder/volume/drivers
touch cinder/__init__.py
touch cinder/volume/__init__.py
touch cinder/volume/drivers/__init__.py
cp -R "$CINDER_DIR/cinder/volume/drivers/xenapi" cinder/volume/drivers/
cp "$HARNESS_DIR/test_xenapi_nfs_driver.py" ./
)

echo $(tput setaf 3)
echo "Pushing files, and running tests on remote machine"
OUTPUT=$(mktemp)
tar -czf - -C "$TEMPDIR" ./ |
ssh -q ubuntu@10.219.2.171 "cd cinderdriver && rm -rf cinder && tar -xzf - && . .env/bin/activate && coverage erase && coverage run .env/bin/nosetests -v -x $@ && coverage report --show-missing --include=*xenapi*" >"$OUTPUT" 2>&1
if [ "$?" != "0" ]
then
        echo $(tput setaf 1)
else
        echo $(tput setaf 2)
fi
cat "$OUTPUT"
echo $(tput setaf 7)
rm -rf "$TEMPDIR"
rm "$OUTPUT"
}

while true;
do
    wait_for_change
    run_tests "$@";
done

