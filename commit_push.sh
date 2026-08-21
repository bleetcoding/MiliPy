#!/bin/bash
set -e
cd /home/ubuntu/milipy
git add -A
git -c user.name="MiliPy CI" -c user.email="ci@milipy.local" commit -m 'v0.2.0: protocol extension (action ids/acks, rich capability states, capture tuning),
coordinate calibration, perception architecture interfaces, device-validation and
android-compatibility docs, bridge id-echo on acks and errors' -q
git push origin main -q
echo "PUSH_OK"
git log -1 --format="%H" | cat
