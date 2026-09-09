#!/usr/bin/env python
"""Reassemble the tategaki panel crops from the local volume scans.

The crops are git-ignored (see fixtures/README.md): copyrighted panels do not
go into a public repository. expected.json carries the page name and the crop
box for every entry, so the image set is reproducible byte-for-byte from a
local copy of the volume without shipping any artwork.

Usage:
    uv run python tests/gen_tategaki_panels.py [<volume-dir>]

<volume-dir> defaults to the single directory under fixtures/tategaki/ that
holds the page scans. Exits with result.py's SKIP (3) and a named reason when it is absent -- the
same exit-code contract check_tategaki.py uses, from the same one place, so a
machine without the scans reports SKIP rather than a mystery traceback.
"""

import glob
import io
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.result import PASS, SKIP  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TATEDIR = os.path.join(ROOT, "fixtures", "tategaki")
EXPECTED = os.path.join(TATEDIR, "expected.json")


def main() -> int:
    volume = sys.argv[1] if len(sys.argv) > 1 else None
    if volume is None:
        dirs = [p for p in glob.glob(os.path.join(TATEDIR, "*"))
                if os.path.isdir(p) and os.path.basename(p) != "panels"]
        if len(dirs) != 1:
            print(f"SKIP: expected exactly one volume directory under {TATEDIR}, "
                  f"found {len(dirs)} -- pass one explicitly. "
                  f"See fixtures/README.md", flush=True)
            return SKIP
        volume = dirs[0]
    if not os.path.isdir(volume):
        print(f"SKIP: volume directory absent: {volume} -- see fixtures/README.md",
              flush=True)
        return SKIP

    with io.open(EXPECTED, encoding="utf-8") as fh:
        entries = json.load(fh)

    out_dir = os.path.join(TATEDIR, "panels")
    os.makedirs(out_dir, exist_ok=True)
    written = 0
    for e in entries:
        src = os.path.join(volume, e["page"])
        if not os.path.exists(src):
            print(f"SKIP: page absent: {src} -- see fixtures/README.md", flush=True)
            return SKIP
        with Image.open(src) as im:
            im.load()
            im.crop(tuple(e["box"])).save(os.path.join(TATEDIR, e["file"]))
        written += 1
    print(f"wrote {written} panels to {out_dir}", flush=True)
    return PASS


sys.exit(main())
