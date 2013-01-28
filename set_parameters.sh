#!/bin/bash
set -u
git checkout -- params.py
sed -ie "s/XAPIPASS/$XAPIPASS/" params.py
sed -ie "s/XAPISERVER/$XAPISERVER/" params.py
sed -ie "s/NFSSERVER/$NFSSERVER/" params.py
sed -ie "s,NFSPATH,$NFSPATH," params.py
sed -ie "s,LOCALPATHTONFS,$LOCALPATHTONFS," params.py
