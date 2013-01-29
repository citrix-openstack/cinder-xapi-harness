#!/bin/bash
set -exu
cat params.py.template |
sed -e "s/XAPIPASS/$XAPIPASS/" \
-e "s/XAPISERVER/$XAPISERVER/" \
-e "s/NFSSERVER/$NFSSERVER/" \
-e "s,NFSPATH,$NFSPATH," \
-e "s,LOCALPATHTONFS,$LOCALPATHTONFS," > params.py
