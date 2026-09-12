#!/usr/bin/env python
"""Reassemble the tategaki panel set, then PROVE it is the maintainer's.

    uv run --project sidecar python tests/fetch_fixtures.py [<volume-dir>]                # reassemble, verify
    uv run --project sidecar python tests/fetch_fixtures.py [<volume-dir>] --verify-only  # verify what is on disk
    uv run --project sidecar python tests/fetch_fixtures.py [<volume-dir>] --write        # record
    uv run --project sidecar python tests/fetch_fixtures.py [<volume-dir>] --write --force

<volume-dir> defaults the way gen_tategaki_panels.py's does: the single scan
directory under fixtures/tategaki/.

gen_tategaki_panels.py makes the panel crops reproducible from a local copy
of the volume. It cannot make them CORRECT: a second developer with a
different scan of the same volume -- another rip, another resolution, a
re-saved JPEG -- gets 24 panels with the right names and the wrong pixels,
and check_tategaki grades those against transcriptions that were read off
other pixels. Nothing in that path notices. The CER it prints is not a
measurement of the OCR; it is a measurement of how far the scan drifted.

fixtures/tategaki/MANIFEST.json closes that gap without shipping artwork: it
records sha256 and size for the 13 source pages expected.json references and
for every panel cropped from them, plus the sha256 of the expected.json those
hashes were written against. Section E of the build order cut this file in
iteration 2 and said it returns in v1.1 if a second person ever needs to
reproduce the quality gates. This is that return.

Default mode reassembles, then verifies. Every mismatch is printed with the
category it most likely belongs to, because the three causes call for three
different fixes:

  wrong scan     a source page's bytes differ from the manifest's. Nothing
                 cropped from it can match either, so its panels are reported
                 under this heading rather than as 24 separate mysteries.
                 Fix: obtain the scan the manifest was written from.
  wrong crop     a panel differs while its source page matches. The page is
                 right, so the box or the encoder is not: expected.json's box
                 changed, or the installed PIL writes a different PNG stream.
                 Fix: diff expected.json's box, then the PIL version.
  drifted truth  expected.json's bytes differ from what the manifest was
                 written against. The panel hashes are only meaningful
                 relative to the transcriptions authored for them, so a
                 changed expected.json means the manifest describes a set
                 that no longer exists. Fix: re-author deliberately, then
                 `--write --force`.

`--verify-only` skips the reassembly and hashes what is on disk. The default
mode cannot see a damaged panel: re-cropping from the scans repairs it before
the hash is taken, which is the right thing for a developer setting up but
the wrong thing for the question "is the set on this disk the one the manifest
vouches for?". That question is check_tategaki's, and this mode answers it
from the command line, source pages included.

Exit contract (tests/lib/result.py): 0 every file matches · 1 any mismatch,
every one named · 3 the scans are absent (see fixtures/README.md). A missing
MANIFEST.json is a broken checkout, exit 1: the file is committed, and its
absence describes the clone, not the machine.

`--write` regenerates the manifest from the set on this machine and REFUSES
when an existing manifest's expected.json hash differs from the current
file, unless `--force` is passed too. Re-authoring the ground truth must be
a deliberate act -- a --write that silently re-based the panel hashes onto a
changed expected.json would make the manifest vouch for whatever happened to
be on disk, which is the failure it exists to catch.

The manifest contains hashes and sizes only. No image data.
"""

import datetime
import hashlib
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from gen_tategaki_panels import EXPECTED, TATEDIR, find_volume, reassemble, scan_dirs  # noqa: E402
from lib.result import FAIL, PASS, SKIP, broken_checkout, skip  # noqa: E402

MANIFEST = os.path.join(TATEDIR, "MANIFEST.json")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def image_size(path):
    # PIL reads the header only; the pixels are never decoded here. The hash
    # is over the file bytes, which is what a second machine can compare.
    with Image.open(path) as im:
        return list(im.size)


def load_manifest():
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def build_manifest(volume, entries):
    pages = {}
    for page in sorted({e["page"] for e in entries}):
        src = os.path.join(volume, page)
        pages[page] = {"sha256": sha256_file(src), "size": image_size(src)}
    panels = {}
    for e in entries:
        path = os.path.join(TATEDIR, e["file"])
        panels[e["file"]] = {"sha256": sha256_file(path), "size": image_size(path),
                             "page": e["page"], "box": list(e["box"])}
    return {
        "provenance": {
            "volume": os.path.basename(volume),
            "written_by": "tests/fetch_fixtures.py --write",
            "date": datetime.date.today().isoformat(),
            "note": "sha256s only; no artwork",
        },
        "expected_json_sha256": sha256_file(EXPECTED),
        "pages": pages,
        "panels": panels,
    }


class Report:
    """What verify() found, split so a caller can assert on each part.

    `expected` is None or one line; `pages` and `panels` are lists of lines,
    one per mismatched or missing file, each already carrying its category.
    """

    def __init__(self):
        self.expected = None
        self.pages = []
        self.panels = []
        self.checked = 0

    @property
    def ok(self):
        return self.expected is None and not self.pages and not self.panels


def _compare(path, want, on_disk_root):
    """A mismatch line for one manifest entry, or None when the bytes match."""
    full = os.path.join(on_disk_root, path)
    if not os.path.exists(full):
        return f"{path}: missing (manifest sha256 {want['sha256'][:12]}...)"
    got = sha256_file(full)
    if got == want["sha256"]:
        return None
    return (f"{path}: sha256 {got[:12]}... size {image_size(full)}, manifest "
            f"{want['sha256'][:12]}... size {want['size']}")


def verify(manifest, volume=None):
    """Hash every file the manifest names and report what differs.

    With `volume`, the 13 source pages are checked first and a panel whose
    page already mismatched is filed under that page's "wrong scan" rather
    than reported as an independent crop failure. Without it (check_tategaki
    on a box that has panels but not the scans), panels and expected.json
    are checked alone and a panel mismatch cannot be categorised further
    than "not the pixels the ground truth was authored for".
    """
    rep = Report()

    got = sha256_file(EXPECTED)
    rep.checked += 1
    if got != manifest["expected_json_sha256"]:
        rep.expected = (f"expected.json: sha256 {got[:12]}..., manifest "
                        f"{manifest['expected_json_sha256'][:12]}... -- "
                        f"drifted ground truth: the manifest was written against "
                        f"other transcriptions; re-author deliberately, then "
                        f"--write --force")

    bad_pages = set()
    if volume is not None:
        for page, want in sorted(manifest["pages"].items()):
            rep.checked += 1
            line = _compare(page, want, volume)
            if line:
                bad_pages.add(page)
                rep.pages.append(f"{line} -- wrong scan: not the page the "
                                 f"manifest was written from")

    for path, want in sorted(manifest["panels"].items()):
        rep.checked += 1
        line = _compare(path, want, TATEDIR)
        if not line:
            continue
        if want["page"] in bad_pages:
            why = f"wrong scan: cropped from mismatched {want['page']}"
        elif volume is not None:
            why = (f"wrong crop or wrong PIL: {want['page']} matches, so the "
                   f"box {want['box']} or the PNG encoder differs")
        else:
            why = ("not the pixels the ground truth was authored for (the scans "
                   "were not consulted, so wrong scan and wrong crop cannot be "
                   "told apart -- run fetch_fixtures.py with the volume to find out)")
        rep.panels.append(f"{line} -- {why}")
    return rep


def print_report(rep):
    n_bad = (rep.expected is not None) + len(rep.pages) + len(rep.panels)
    for line in ([rep.expected] if rep.expected else []) + rep.pages + rep.panels:
        print(f"  MISMATCH {line}", flush=True)
    print(f"fetch_fixtures: {rep.checked - n_bad}/{rep.checked} files match "
          f"MANIFEST.json ({n_bad} mismatched)", flush=True)


def write_manifest(volume, force):
    with open(EXPECTED, encoding="utf-8") as fh:
        entries = json.load(fh)
    if os.path.exists(MANIFEST) and not force:
        existing = load_manifest()
        old = existing["expected_json_sha256"]
        now = sha256_file(EXPECTED)
        if old != now:
            print(f"REFUSED: expected.json sha256 changed ({old[:12]}... -> "
                  f"{now[:12]}...) since MANIFEST.json was written. The panel "
                  f"hashes are only meaningful relative to the transcriptions "
                  f"authored against them; pass --force if the re-authoring "
                  f"was deliberate.", flush=True)
            return FAIL
        # The same refusal for the SOURCE pages. Without it a maintainer with
        # a different rip who ran --write would re-vouch for the wrong pixels
        # in one step -- the hole the manifest exists to close, on the write
        # side (review, F1). A page that is new to the manifest is fine; one
        # the manifest already names must still hash the same.
        drifted = []
        for page, want in sorted(existing["pages"].items()):
            src = os.path.join(volume, page)
            if os.path.exists(src) and sha256_file(src) != want["sha256"]:
                drifted.append(page)
        if drifted:
            print(f"REFUSED: {len(drifted)} source page(s) differ from the ones "
                  f"MANIFEST.json was written from ({', '.join(drifted[:5])}"
                  f"{'...' if len(drifted) > 5 else ''}). This is a different "
                  f"scan of the volume; the transcriptions were authored against "
                  f"the other one. Pass --force only if the ground truth was "
                  f"re-read against THESE pages.", flush=True)
            return FAIL
    rc = reassemble(volume)
    if rc != PASS:
        return rc
    manifest = build_manifest(volume, entries)
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, sort_keys=True, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {MANIFEST}: {len(manifest['pages'])} pages, "
          f"{len(manifest['panels'])} panels, expected.json "
          f"{manifest['expected_json_sha256'][:12]}...", flush=True)
    return PASS


def main():
    args = sys.argv[1:]
    write = "--write" in args
    force = "--force" in args
    verify_only = "--verify-only" in args
    rest = [a for a in args if a not in ("--write", "--force", "--verify-only")]
    if len(rest) > 1 or (force and not write) or (write and verify_only):
        print(f"usage: {os.path.basename(__file__)} [<volume-dir>] "
              f"[--write [--force] | --verify-only]", flush=True)
        return FAIL

    if not os.path.exists(EXPECTED):
        return broken_checkout(f"ground truth absent: {EXPECTED} -- committed, "
                                f"see fixtures/README.md")
    if not write and not os.path.exists(MANIFEST):
        return broken_checkout(f"manifest absent: {MANIFEST} -- committed, "
                                f"see fixtures/README.md")

    if verify_only and not rest:
        # A box that holds the panels but not the scans -- a second developer
        # who was handed the crops -- can still verify what it has. verify()
        # has always accepted volume=None; the CLI just never offered it.
        dirs = scan_dirs()
        volume = dirs[0] if len(dirs) == 1 else None
    else:
        volume = rest[0] if rest else find_volume()
        if volume is None:
            # find_volume() already named the reason on its own SKIP line.
            return SKIP
        if not os.path.isdir(volume):
            return skip(f"volume directory absent: {volume} -- see fixtures/README.md")

    if write:
        return write_manifest(volume, force)

    if not verify_only:
        rc = reassemble(volume)
        if rc != PASS:
            return rc
    rep = verify(load_manifest(), volume)
    print_report(rep)
    return PASS if rep.ok else FAIL


if __name__ == "__main__":
    sys.exit(main())
