# eugeo — Geografia europea

Work in progress; see docs/superpowers/specs.

## Data

`data.js` is generated from Natural Earth 1:10m (public domain) by `tools/build_data.py`; do not edit it by hand.
Rebuild with `.venv/bin/python tools/build_data.py`.

Known limitation: country outlines are simplified one by one (4 km), without shared topology,
so neighbouring borders may show slivers or small overlaps.
