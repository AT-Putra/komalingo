#!/usr/bin/env python3
r"""Phase 6 -- AC-6 (archives), AC-11 (safety), AC-12 (memory). Offline.

    uv run --project sidecar python tests/check_archives.py

Exit-code contract, uniform across every check here:
    0  pass
    1  fail
    2  inconclusive -- the RSS measurement could not be trusted on this box
    3  skip         -- benign.cbr or libarchive is absent, so the .cbr clause
                       cannot be exercised (see fixtures/README.md)

Four groups of asserts, and they are deliberately different in kind:

  SAFETY (AC-11) is asserted by REASON, not by "something raised". A hostile
  fixture rejected for the wrong rule is a rule that is not doing its job while
  a neighbouring one covers for it, and a check that only asserts "rejected"
  cannot see that. Every reason in `safety.REASONS` must be observed by the end
  of the run -- except the documented backstop, which no input can reach and
  which is asserted through `Budget.escapes` directly.

  A RED-CHECK follows: the same hostile fixtures, read through a Budget with
  `enforce=False`, must be ACCEPTED. A safety assert that cannot be made to
  fail is not evidence, and the enforcement flag is the documented hook that
  makes it fail on demand.

  ROUND-TRIP (AC-6) compares member sets, page order and ComicInfo bytes. The
  ComicInfo assert is byte-level on purpose: the fixture carries CRLF, an XML
  declaration, an attribute and a self-closing tag, all of which survive a
  substitution and none of which survive a parse-and-reserialise.

  MEMORY (AC-12) follows section E's procedure exactly: baseline sampled before
  the archive is opened, peak sampled on a 250ms background thread during
  ingest, gate `peak - baseline < 400MB`, and the in-memory LRU tier warmed to
  its byte cap FIRST so the measurement includes the residency the bound has to
  coexist with. All three numbers are printed so a failure can be attributed
  before anyone starts tuning.
"""

import bz2
import contextlib
import gzip
import hashlib
import io
import json
import json as _json
import lzma
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import psutil  # noqa: E402
from PIL import Image  # noqa: E402

from sidecar import atomic, cache, job, pipeline, safety  # noqa: E402
from sidecar.containers import archive, read_cbz  # noqa: E402
from lib.result import Checks, run, skip  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVES = os.path.join(ROOT, "fixtures", "archives")
SAMPLE_CBZ = os.path.join(ROOT, "fixtures", "cbz", "sample.cbz")

BENIGN = ["benign.cbz", "benign.zip", "benign.cb7", "benign.7z",
          "benign.cbt", "benign.tar"]

# fixture -> the rule that must refuse it. Asserted by reason, not by raising.
HOSTILE = {
    "slip.cbz": safety.PARENT_TRAVERSAL,
    "absolute.cbz": safety.ABSOLUTE_PATH,
    "drive.cbz": safety.DRIVE_LETTER,
    "symlink.cbt": safety.LINK_ENTRY,
    "bomb.cbz": safety.RATIO_CAP,
    # The container-level bomb. Listing a compressed tar decompresses all of
    # it, so this one is refused by account_raw during the listing pass rather
    # than by any per-member rule -- which is the hole the first draft had.
    "bomb.cbt": safety.RATIO_CAP,
    "members.cbz": safety.MEMBER_COUNT,
}

# The 7z blind spot, asserted rather than commented. Its bomb is the SECOND
# member of a solid block, so py7zr reports no compressed size for it and the
# per-member ratio rule cannot fire; at the default 128MB per-file cap an 8MB
# member is legitimate and the archive is ACCEPTED. Only the tightened cap
# refuses it, and that is what makes "the byte caps are the general bound"
# a tested claim instead of a hope.
BLIND_7Z = "bomb.cb7"

BIG = "big.cbz"
RSS_BUDGET = 400 * 1024 * 1024
TIER_WARM_BYTES = 144 * 1024 * 1024   # just under cache.MAX_TIER_BYTES (150MB)
SAMPLE_INTERVAL = 0.25                # section E's 250ms

TARGET_LANG = "id"

# The fixture's ComicInfo.xml bytes, read back from the fixture in main() rather
# than re-declared here: the generator owns them, and a second copy in the check
# would round-trip against a file neither the app nor the generator wrote.
GEN_COMICINFO = b""


def fixture(name):
    return os.path.join(ARCHIVES, name)


def drain(path, budget=None):
    """Read every page of `path`, returning (ordinals, members)."""
    out = [(o, m) for o, m, _img in archive.pages(path, budget)]
    return [o for o, _m in out], [m for _o, m in out]


# --------------------------------------------------------------------------
# AC-11
# --------------------------------------------------------------------------

def check_safety(c, observed):
    for name, reason in HOSTILE.items():
        path = fixture(name)
        if not os.path.isfile(path):
            c.check(False, f"{name} is missing -- run tests/gen_fixtures.py")
            continue
        try:
            drain(path, safety.Budget(os.path.join(ROOT, "out")))
            c.check(False, f"{name} was ACCEPTED; expected {reason}")
        except safety.UnsafeArchive as e:
            observed.add(e.reason)
            c.check(e.reason == reason,
                    f"{name} rejected with {e.reason!r} (expected {reason!r})")

    # The two byte caps, on a tightened Budget rather than on a quarter-gigabyte
    # fixture. Same rules, same code path, three orders of magnitude less I/O.
    try:
        drain(fixture("bomb.cbz"),
              safety.Budget(ROOT, max_ratio=10**9, max_file_bytes=64 * 1024))
        c.check(False, "per-file cap did not fire on 8MB through a 64KB cap")
    except safety.UnsafeArchive as e:
        observed.add(e.reason)
        c.check(e.reason == safety.FILE_SIZE_CAP,
                f"per-file byte cap fires on streamed bytes ({e.reason})")

    try:
        drain(fixture("bomb.cbz"),
              safety.Budget(ROOT, max_ratio=10**9, max_total_bytes=64 * 1024))
        c.check(False, "running-total cap did not fire on 8MB through a 64KB cap")
    except safety.UnsafeArchive as e:
        observed.add(e.reason)
        c.check(e.reason == safety.TOTAL_SIZE_CAP,
                f"running-total byte cap fires on streamed bytes ({e.reason})")

    # The container bomb must be refused FAST -- while it is being listed, not
    # after. An archive-level rule that fires only once the whole container is
    # in memory is a rule that has already lost.
    started = time.perf_counter()
    try:
        drain(fixture("bomb.cbt"), safety.Budget(os.path.join(ROOT, "out")))
        c.check(False, "bomb.cbt was accepted")
    except safety.UnsafeArchive:
        pass
    elapsed = time.perf_counter() - started
    c.check(elapsed < 5.0,
            f"the compressed-tar bomb is refused during the listing pass "
            f"({elapsed:.2f}s; the first draft accepted it after 14s)")

    # The 7z solid-block blind spot, both halves.
    default_ok = True
    try:
        drain(fixture(BLIND_7Z), safety.Budget(os.path.join(ROOT, "out")))
    except safety.UnsafeArchive as e:
        default_ok = False
        c.check(False, f"{BLIND_7Z} was refused at default caps with {e.reason}; "
                       f"an 8MB member is legitimate")
    c.check(default_ok,
            f"{BLIND_7Z}: a solid-block member py7zr reports no compressed size "
            f"for is NOT caught by the ratio rule -- the documented blind spot")
    try:
        drain(fixture(BLIND_7Z),
              safety.Budget(ROOT, max_file_bytes=64 * 1024))
        c.check(False, f"{BLIND_7Z} passed a 64KB per-file cap")
    except safety.UnsafeArchive as e:
        observed.add(e.reason)
        c.check(e.reason == safety.FILE_SIZE_CAP,
                f"{BLIND_7Z}: the absolute byte cap is what answers where the "
                f"ratio rule cannot ({e.reason})")

    # The metadata-lie case, stated directly because no archive format lets a
    # fixture carry it: zipfile and tarfile both TRUNCATE a read at the size the
    # header declares, so a fixture whose header understates its payload cannot
    # even be streamed past the lie. What can be built is the Member the reader
    # would construct from such a header -- one declaring a compressed size so
    # large that the ratio rule reads 8MB as 1:1 -- and the assert is that the
    # byte caps, which are fed by streamed bytes alone, still refuse it.
    budget = safety.Budget(ROOT, max_file_bytes=64 * 1024)
    budget.check_member(safety.Member("ch1/p1.png", declared_compressed=1 << 40))
    try:
        for _ in range(4):
            budget.account(32 * 1024)
        c.check(False, "a lying compressed size defeated the per-file cap")
    except safety.UnsafeArchive as e:
        observed.add(e.reason)
        c.check(e.reason == safety.FILE_SIZE_CAP,
                "a member declaring a 1TB compressed size is still refused on "
                "streamed bytes")

    # The backstop. Unreachable through check_member because the three named
    # path rules fire first on every input that could reach it -- so it is
    # asserted on the predicate, which is why the predicate is public.
    escape_budget = safety.Budget(os.path.join(ROOT, "out"))
    for name in ("../evil.png", "..\\evil.png", "/evil.png", "C:evil.png"):
        c.check(escape_budget.escapes(name),
                f"commonpath backstop would refuse {name!r} independently")
    c.check(not escape_budget.escapes("ch1/p1.png"),
            "commonpath backstop admits an ordinary member")

    # comicinfo() is a second public door into an untrusted archive, and it
    # has to be the same door. Asserted on a hostile fixture rather than by
    # reading the source: a reader that admitted members and then streamed the
    # ComicInfo member through a DIFFERENT path would pass a source scan.
    try:
        archive.comicinfo(fixture("slip.cbz"),
                          safety.Budget(os.path.join(ROOT, "out")))
        c.check(False, "comicinfo() read a hostile archive without refusing it")
    except safety.UnsafeArchive as e:
        observed.add(e.reason)
        c.check(e.reason == safety.PARENT_TRAVERSAL,
                f"comicinfo() enforces the same budget as pages() ({e.reason})")

    missing = safety.REASONS - safety.BACKSTOP_REASONS - observed
    c.check(not missing,
            f"every non-backstop AC-11 reason was observed (missing: {sorted(missing)})")


def check_red(c):
    """The hostile fixtures must be ACCEPTED once enforcement is off.

    Without this the safety asserts above prove only that SOMETHING refuses the
    fixtures -- a decoder that happened to choke on `C:evil.png` would pass
    them. With it, the refusal is pinned to `Budget`.
    """
    # Every hostile fixture, not the three cheapest. The argument the first
    # draft made for the three path fixtures -- "a decoder that happened to
    # choke on C:evil.png would pass" -- applies just as well to tarfile's
    # opinions about link members and to the 5001-member listing, and not at
    # all to the byte rules, which is why they are covered separately below.
    targets = sorted(HOSTILE)
    accepted = 0
    for name in targets:
        budget = safety.Budget(os.path.join(ROOT, "out"), enforce=False)
        try:
            drain(fixture(name), budget)
            accepted += 1
        except safety.UnsafeArchive as e:
            c.check(False, f"red-check: {name} still refused with {e.reason} "
                           f"when enforcement was off")
        except Exception as e:  # noqa: BLE001 -- reporting, not swallowing
            c.check(False, f"red-check: {name} raised {type(e).__name__}: {e}")
    c.check(accepted == len(targets),
            f"red-check: {accepted}/{len(targets)} hostile archives accepted "
            f"with enforcement off, so the rejections above are Budget's doing")

    # The byte rules, which no fixture in that set exercises: a tightened cap
    # with enforcement off must not refuse what the same cap refuses with it on.
    try:
        drain(fixture("bomb.cbz"),
              safety.Budget(ROOT, max_file_bytes=64 * 1024, enforce=False))
        c.check(True, "red-check: the per-file byte cap is inert when "
                      "enforcement is off")
    except safety.UnsafeArchive as e:
        c.check(False, f"red-check: the byte cap still fired ({e.reason}) with "
                       f"enforcement off")


# --------------------------------------------------------------------------
# AC-6
# --------------------------------------------------------------------------

def check_round_trip(c, tmp):
    expected_pages = ["ch1/p1.png", "ch1/p2.png", "ch1/p10.png"]

    for name in BENIGN:
        path = fixture(name)
        if not os.path.isfile(path):
            c.check(False, f"{name} is missing -- run tests/gen_fixtures.py")
            continue

        src_fmt = archive.detect_format(path)
        _ordinals, members = drain(path)
        c.check(members == expected_pages,
                f"{name}: natural page order {members}")

        # Through repack_extras, which is what pipeline._repack calls: an
        # assert that read the input a different way from the product would
        # pass on a repack the product could not perform.
        info, extra = archive.repack_extras(path)
        c.check(info is not None and info[1] == GEN_COMICINFO,
                f"{name}: ComicInfo.xml read back byte-identical")

        # Repack through the product's writer, with the language rewritten.
        dest = os.path.join(tmp, f"rt_{name}")
        payloads = []
        for _o, member, img in archive.pages(path):
            buf = _encode_like(img, member)
            payloads.append((member, buf))
        out = archive.write_archive(
            dest, payloads, archive.OUTPUT_FORMAT[src_fmt], info, TARGET_LANG,
            extra_entries=list(extra),
        )

        c.check(archive.detect_format(out) == src_fmt,
                f"{name}: output container family is {src_fmt}, same as input")
        _o2, members_out = drain(out)
        c.check(members_out == members,
                f"{name}: repacked page order identical")

        # The member SET, not the page list. Both sides of the comparison
        # above come from archive.members(), which lists page candidates -- so
        # it cannot go red on a repack that silently drops credits.txt, and the
        # first draft's did exactly that. This reads the raw entry list.
        c.check(sorted(_all_members(out)) == sorted(_all_members(path)),
                f"{name}: member SET identical, non-page members included "
                f"({sorted(_all_members(out))})")

        info_out = archive.comicinfo(out)
        c.check(info_out is not None and info_out[0] == info[0],
                f"{name}: ComicInfo.xml kept its member name")
        c.check(info_out[1] == archive.rewrite_language(GEN_COMICINFO, TARGET_LANG),
                f"{name}: ComicInfo.xml byte-identical except LanguageISO")
        c.check(b"<LanguageISO>id</LanguageISO>" in info_out[1]
                and b"<LanguageISO>ja</LanguageISO>" not in info_out[1],
                f"{name}: LanguageISO rewritten to the target")
        c.check(info_out[1].count(b"\r\n") == GEN_COMICINFO.count(b"\r\n")
                and b"<Series/>" in info_out[1],
                f"{name}: CRLF and the self-closing tag survived the repack")


def _all_members(path):
    """Every member name an archive carries, pages and non-pages alike.

    Reads the entry list directly rather than through `members()`, which filters
    to page candidates -- the filtering is the reason the round-trip assert
    could not see a dropped `credits.txt`.
    """
    fmt = archive.detect_format(path)
    return [n for n, m in archive._ENTRY_READERS[fmt](path) if not m.is_dir]


def _encode_like(img, member):
    """Re-encode a decoded page in its member's own format.

    The round-trip assert is about the CONTAINER, so the payload only has to be
    a real image of the right format; the pipeline's own encode policy is
    check_imaging's subject and is not re-tested here.
    """
    fmt = os.path.splitext(member)[1].lstrip(".").upper()
    fmt = {"JPG": "JPEG", "TIF": "TIFF"}.get(fmt, fmt)
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def check_signatures(c):
    """Format comes from the bytes. A .cbz that is really a 7z reads as 7z."""
    c.check(archive.detect_format(fixture("benign.cbz")) == archive.ZIP,
            "benign.cbz detected as zip")
    c.check(archive.detect_format(fixture("benign.cb7")) == archive.SEVENZIP,
            "benign.cb7 detected as sevenzip by signature, not extension")
    c.check(archive.detect_format(fixture("benign.cbt")) == archive.TAR,
            "benign.cbt detected as tar (ustar at offset 257)")

    # The mislabelled-archive case, built here rather than committed: it is the
    # same bytes as benign.7z under a .cbz name, so it proves dispatch without
    # a second fixture to keep in step.
    with tempfile.TemporaryDirectory() as td:
        liar = os.path.join(td, "actually_7z.cbz")
        shutil.copyfile(fixture("benign.7z"), liar)
        c.check(archive.detect_format(liar) == archive.SEVENZIP,
                "a 7z named .cbz is read as a 7z, not reported as corrupt")
        _o, members = drain(liar)
        c.check(len(members) == 3, "and all three of its pages decode")


def check_compressed_tar(c, tmp):
    """The one-forward-pass reader, on archives it must ACCEPT.

    `bomb.cbt.gz` proves the path refuses; nothing proved it delivers. And the
    reader branches three ways on the container's compression -- gzip, bzip2,
    lzma -- of which a single fixture exercises one. Two of the three decoders
    were reachable only from a user's disk, which is the definition of a branch
    nothing tests.

    Built here rather than committed: three benign compressed tars would be
    three more files in the determinism sweep for one assert each, and their
    contents are `benign.cbz`'s own pages, so there is nothing a fixture would
    pin that this does not.
    """
    payloads = {}
    for _o, member, img in archive.pages(fixture("benign.cbz")):
        payloads[member] = _encode_like(img, member)
    info = archive.comicinfo(fixture("benign.cbz"))

    openers = {
        "gz": lambda path: gzip.GzipFile(filename="", mode="wb",
                                         fileobj=open(path, "wb"), mtime=0),
        "bz2": lambda path: bz2.BZ2File(path, "wb"),
        "xz": lambda path: lzma.LZMAFile(path, "wb"),
    }
    for label, opener in openers.items():
        path = os.path.join(tmp, f"benign_{label}.cbt")
        with opener(path) as stream:
            with tarfile.open(fileobj=stream, mode="w|",
                              format=tarfile.GNU_FORMAT) as tf:
                for name, payload in sorted(list(payloads.items()) + [info]):
                    entry = tarfile.TarInfo(name)
                    entry.size = len(payload)
                    entry.mtime = 0
                    entry.mode = 0o644
                    entry.uid = entry.gid = 0
                    entry.uname = entry.gname = ""
                    tf.addfile(entry, io.BytesIO(payload))

        c.check(archive.detect_format(path) == archive.TAR
                and archive._tar_compression(path) == label,
                f"a {label}-compressed tar is detected as tar/{label}")
        _ordinals, members = drain(path, safety.Budget(tmp))
        c.check(members == ["ch1/p1.png", "ch1/p2.png", "ch1/p10.png"],
                f"{label}: all three pages decode in natural order ({members})")
        got = archive.comicinfo(path, safety.Budget(tmp))
        c.check(got is not None and got[1] == info[1],
                f"{label}: ComicInfo.xml comes back byte-identical")
        _comic, extra = archive.repack_extras(path, safety.Budget(tmp))
        c.check(list(extra) == [],
                f"{label}: non-page members are NOT carried -- the documented "
                f"limit of the single-pass reader, not an accident")

    # And the whole way through, once: a `.cbt` that is gzip INSIDE is the
    # file a user double-clicks, and until this ran, no compressed container
    # had ever reached the repack. It is also the only path on which
    # `repack_extras` takes its single-pass branch.
    named = os.path.join(tmp, "volume.cbt")
    shutil.copyfile(os.path.join(tmp, "benign_gz.cbt"), named)
    item = job.run_item(job.classify(named), os.path.join(tmp, "cbt_out"),
                        "cbt-job")
    c.check(item.status == job.OK and item.pages == 3,
            f"a gzip-compressed .cbt completes a full run_item "
            f"({item.status}, {item.pages} pages, {item.reason!r})")
    c.check(item.output and archive.detect_format(item.output) == archive.TAR
            and archive._tar_compression(item.output) == "",
            f"and comes back as an UNCOMPRESSED tar -- the container is read "
            f"compressed and written plain, which AC-6's format list allows "
            f"because it names .cbt, not .cbt.gz ({item.output})")
    out_info = archive.comicinfo(item.output)
    c.check(out_info is not None
            and b"<LanguageISO>en</LanguageISO>" in out_info[1],
            "with its ComicInfo.xml carried through and LanguageISO rewritten")


def check_reader_agreement(c):
    """archive.pages and read_cbz.pages must not have drifted.

    Phase 3's editor reads a page through read_cbz and Phase 6's ingest reads
    the same page through archive; if their ordering or their skip policy
    differ, the page spot-fixed at ordinal 7 is not the page delivered at
    ordinal 7 -- and nothing else in the suite would notice.
    """
    a_ord, a_mem = drain(SAMPLE_CBZ)
    b = [(o, m) for o, m, _i in read_cbz.pages(SAMPLE_CBZ)]
    c.check(a_ord == [o for o, _m in b] and a_mem == [m for _o, m in b],
            "archive.pages and read_cbz.pages agree ordinal-for-ordinal on "
            "sample.cbz (junk skipped, no ordinal holes)")
    c.check(archive.members(SAMPLE_CBZ) == read_cbz.members(SAMPLE_CBZ),
            "and their candidate member listings agree")


def check_no_extractall(c):
    """AC-12's mechanism, asserted on the source and on the filesystem."""
    src = open(os.path.join(ROOT, "sidecar", "containers", "archive.py"),
               encoding="utf-8").read()
    # Calls, not mentions: the module docstring explains at length why
    # extractall is never used, and a bare substring search reads its own
    # explanation as the violation.
    calls = [line.strip() for line in src.splitlines()
             if "extractall(" in line or ".extract(" in line]
    c.check(not any("extractall(" in line for line in calls),
            f"archive.py calls no extractall ({calls})")
    c.check(all(line.startswith("sz.extract(") for line in calls),
            f"the only member extraction is py7zr's, through the in-memory "
            f"factory ({calls})")

    # py7zr's only read API is `extract`; the assert that matters is that it
    # wrote nothing, which is what the in-memory WriterFactory buys.
    with tempfile.TemporaryDirectory() as td:
        before = set(os.listdir(td))
        cwd = os.getcwd()
        os.chdir(td)
        try:
            drain(fixture("benign.7z"))
        finally:
            os.chdir(cwd)
        c.check(set(os.listdir(td)) == before,
                "reading a 7z left no file on disk")


def check_item_boundary(c, tmp):
    """US-603: one hostile item does not take the benign one with it."""
    hostile = fixture("slip.cbz")
    unsupported = os.path.join(tmp, "notes.txt")
    with open(unsupported, "w", encoding="utf-8") as fh:
        fh.write("not an item\n")

    items = [job.classify(p) for p in (hostile, unsupported)]
    results = [job.run_item(i, tmp, "check-archives-job") for i in items]

    c.check(all(r.status != job.OK for r in results),
            "a hostile archive and a text file are both refused")
    c.check(results[0].status == job.SKIPPED
            and safety.PARENT_TRAVERSAL in results[0].reason,
            f"the hostile item carries the rule that refused it "
            f"({results[0].reason!r})")
    c.check(results[1].status == job.SKIPPED and results[1].reason,
            f"the unsupported file carries a per-item reason "
            f"({results[1].reason!r})")
    # US-603's progress criterion, asserted on what was actually PRINTED.
    # Comparing job.ITEM_STAGES to a literal -- which is what the first draft
    # did -- stays green with both emit() calls deleted, which is the exact
    # class of assert this phase's red-check discipline exists to catch.
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        job.run_job([hostile, unsupported], tmp, "check-archives-emit")
    events = []
    for line in captured.getvalue().splitlines():
        try:
            events.append(_json.loads(line))
        except ValueError:
            continue
    item_events = [e for e in events if e.get("stage") in job.ITEM_STAGES]
    starts = [e for e in item_events if e["stage"] == "item_start"]
    dones = [e for e in item_events if e["stage"] == "item_done"]
    c.check(len(starts) == 2 and len(dones) == 2,
            f"exactly one item_start and one item_done per item "
            f"({len(starts)} starts, {len(dones)} dones over 2 items)")
    c.check({e["item"] for e in starts}
            == {os.path.basename(hostile), os.path.basename(unsupported)},
            f"each item-level event names its own item "
            f"({sorted(e['item'] for e in starts)})")
    c.check(all(set(e) == {"stage", "item", "page", "pct"} for e in item_events),
            "and carries pipeline.emit's four keys and no others")

    # The boundary's real claim: one bad item does not take the good one with
    # it. Asserted on a MIXED job rather than on two bad items, because "both
    # were refused" is also what a job that aborted on the first one looks
    # like. This runs the full pipeline on three pages, so it is the slowest
    # assert here and the only one that needs the OCR models resident -- a
    # model that is missing shows up as FAILED with its reason, which is the
    # honest outcome rather than a skip.
    mixed = job.run_job([fixture("benign.cbz"), hostile], tmp, "check-archives-mixed")
    good, bad = mixed["items"]
    c.check(good["status"] == job.OK and good["pages"] == 3,
            f"a benign archive beside a hostile one completes "
            f"({good['status']}, {good['pages']} pages, {good['reason']!r})")
    c.check(bad["status"] == job.SKIPPED and bad["reason"],
            f"and the hostile one is skipped with its reason ({bad['reason']!r})")
    c.check(good["output"] and archive.detect_format(good["output"]) == archive.ZIP,
            f"the benign item's output is a repacked archive ({good['output']})")
    c.check(archive.members(good["output"])
            == ["ch1/p1.png", "ch1/p2.png", "ch1/p10.png"],
            "the repacked archive keeps the input's member names and order")
    info = archive.comicinfo(good["output"])
    c.check(info is not None and b"<LanguageISO>en</LanguageISO>" in info[1]
            and b"<Series/>" in info[1],
            "and its ComicInfo.xml is the input's, with LanguageISO rewritten")

    check_collisions(c, tmp)
    check_refused_cleanup(c, tmp)
    check_high_member_round_trip(c, tmp)
    check_second_comicinfo(c, tmp)


def check_second_comicinfo(c, tmp):
    """A ComicInfo.xml further down the tree is an ordinary member.

    `repack_extras` picks ONE ComicInfo to rewrite -- the language rewrite has
    one target -- and the first draft then excluded every comicinfo-named
    member from the extras, so `sub/ComicInfo.xml` landed in neither list and
    vanished. One shape for which AC-6's member-set clause was false, while
    `extras`' own docstring named that exact file as something it carries.
    """
    pages_in = []
    for _o, member, img in archive.pages(fixture("benign.cbz")):
        pages_in.append((member, _encode_like(img, member)))
    primary = archive.comicinfo(fixture("benign.cbz"))
    second = b"<ComicInfo><Title>sub</Title></ComicInfo>"

    src = os.path.join(tmp, "two_comicinfo.cbz")
    archive.write_archive(src, sorted(pages_in + [
        ("ComicInfo.xml", primary[1]),
        ("sub/ComicInfo.xml", second),
        ("credits.txt", b"x"),
    ]), archive.ZIP)

    budget = safety.Budget(tmp)
    info, extra = archive.repack_extras(src, budget)
    extra = list(extra)
    c.check(info is not None and info[0] == "ComicInfo.xml",
            f"the root ComicInfo.xml is the one chosen for the rewrite "
            f"({info[0] if info else None})")
    c.check(("sub/ComicInfo.xml", second) in extra,
            f"and a second ComicInfo further down is carried as an ordinary "
            f"member ({[n for n, _p in extra]})")
    c.check(budget.members == len(_all_members(src)),
            f"still one admission pass ({budget.members} counted over "
            f"{len(_all_members(src))} members)")

    out = os.path.join(tmp, "two_comicinfo_out.cbz")
    archive.write_archive(out, pages_in, archive.ZIP, info, TARGET_LANG,
                          extra_entries=iter(extra))
    c.check(sorted(_all_members(out)) == sorted(_all_members(src)),
            f"and the member set round-trips ({sorted(_all_members(out))})")


def check_high_member_round_trip(c, tmp):
    """A LEGAL archive just under the member cap must survive a full run_item.

    The regime nothing covered: `members.cbz` sits at 5001 and is refused on
    the first pass, so it never reaches the repack, and every other fixture has
    four members. Between those two lies the case that broke -- the repack ran
    two admission passes over one budget, counted every member twice, and
    refused `member-count` at half the advertised cap. Not as an error message:
    every page had already been detected, OCR'd, translated and rendered, the
    item was reported SKIPPED as unsafe, and its whole output directory was
    deleted. A 3000-member box-set is inside what the cap was written to allow.

    Built here rather than committed: 3002 members of one byte each are a
    5-second generation and have no business in git. The pages are real (the
    translation path must actually run); the other 2999 members are the junk a
    real box-set carries -- per-chapter notes -- and they are what pushes the
    count past half the cap.
    """
    payloads = []
    for _o, member, img in archive.pages(fixture("benign.cbz")):
        payloads.append((member, _encode_like(img, member)))
    filler = 3002 - len(payloads) - 1          # -1 for ComicInfo.xml
    for i in range(filler):
        payloads.append((f"notes/n{i:05d}.txt", b"x"))

    src = os.path.join(tmp, "boxset.cbz")
    archive.write_archive(src, sorted(payloads), archive.ZIP,
                          archive.comicinfo(fixture("benign.cbz")))
    total = len(_all_members(src))
    c.check(safety.MAX_MEMBERS / 2 < total < safety.MAX_MEMBERS,
            f"the fixture sits between half the member cap and the cap "
            f"({total} members, cap {safety.MAX_MEMBERS})")

    # The shape of the defect, guarded directly: the repack must run ONE
    # admission pass. Counting members is what the cap reads, so two passes
    # over one budget halve it -- and an assert on the outcome alone would go
    # green again the moment someone picks a fixture below the doubled cap.
    counted = safety.Budget(tmp)
    archive.repack_extras(src, counted)
    c.check(counted.members == total,
            f"the repack admits every member once, not twice "
            f"({counted.members} counted over {total} members)")

    out_dir = os.path.join(tmp, "boxset_out")
    item = job.run_item(job.classify(src), out_dir, "boxset-job")
    c.check(item.status == job.OK,
            f"a {total}-member archive completes ({item.status}: {item.reason!r})")
    c.check(item.pages == 3, f"all three of its pages translated ({item.pages})")
    c.check(item.output and os.path.isfile(atomic.long_path(item.output)),
            f"and the repacked archive exists ({item.output})")
    c.check(os.path.isdir(atomic.long_path(pipeline.item_dir(out_dir, item.item_id))),
            "and its output directory was NOT deleted as an unsafe archive's")
    if item.output and os.path.isfile(atomic.long_path(item.output)):
        c.check(len(_all_members(item.output)) == total,
                f"every member round-trips, junk included "
                f"({len(_all_members(item.output))} of {total})")


def check_collisions(c, tmp):
    """Two items with the same basename must not write over each other.

    A folder holding `art/vol1.cbz` and `text/vol1.cbz` is ordinary, and both
    output names were keyed on the basename alone: the same
    `vol1_translated.cbz`, and -- because most archives carry `ch1/p1.png` --
    the same loose page files too. The second item destroyed the first's output
    AND left the cache's placement records pointing at files it had rewritten,
    which corrupts AC-13's resume as well.
    """
    src = fixture("benign.cbz")
    root = os.path.join(tmp, "collide")
    paths = []
    for folder in ("art", "text"):
        d = os.path.join(root, folder)
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, "vol1.cbz")
        shutil.copyfile(src, dst)
        paths.append(dst)

    items = job.disambiguate([job.classify(x) for x in paths])
    ids = [i.item_id for i in items]
    c.check(len(set(ids)) == 2,
            f"two items sharing a basename get distinct item_ids ({ids})")
    dirs = [pipeline.item_dir(root, i) for i in ids]
    c.check(len(set(dirs)) == 2,
            f"and distinct output directories ({[os.path.basename(d) for d in dirs]})")

    out_dir = os.path.join(root, "out")
    record = job.run_job(paths, out_dir, "collide-job")
    outputs = [i["output"] for i in record["items"]]
    c.check(all(outputs) and len(set(outputs)) == 2,
            f"a job over both writes two archives, not one ({outputs})")
    c.check(all(os.path.isfile(atomic.long_path(o)) for o in outputs),
            "and both survive the run -- neither overwrote the other")
    pages = []
    for item in record["items"]:
        d = pipeline.item_dir(out_dir, item["item_id"])
        pages.append(sorted(
            os.path.relpath(os.path.join(dp, f), d)
            for dp, _dn, fn in os.walk(d) for f in fn))
    c.check(pages[0] == pages[1] and pages[0],
            f"each item's loose pages live under its own directory ({pages[0]})")


def check_refused_cleanup(c, tmp):
    """An archive refused HALFWAY must not leave its translated pages behind.

    The three byte rules can only fire mid-stream, so by then pages 1..k are
    already delivered. Built here rather than as a fixture because it needs a
    GOOD page followed by a bomb -- the committed `bomb.cbz` is one member and
    is refused before anything is written, which would make this assert vacuous.
    """
    src = os.path.join(tmp, "halfway.cbz")
    good = None
    for _o, member, img in archive.pages(fixture("benign.cbz")):
        if member.endswith("p1.png"):
            good = _encode_like(img, member)
            break
    archive.write_archive(
        src,
        [("ch1/p1.png", good), ("ch1/p2.png", bytes(8 * 1024 * 1024))],
        archive.ZIP,
    )

    out_dir = os.path.join(tmp, "halfway_out")
    item = job.classify(src)
    result = job.run_item(item, out_dir, "halfway-job")
    c.check(result.status == job.SKIPPED and "ratio-cap" in result.reason,
            f"an archive whose second member is a bomb is refused "
            f"({result.status}: {result.reason!r})")
    left = pipeline.item_dir(out_dir, result.item_id)
    c.check(not os.path.isdir(atomic.long_path(left)),
            f"and the pages it had already written are gone ({left})")


def check_cbr(c, tmp):
    """AC-6's .cbr clause. Returns False when it could not be exercised."""
    path = fixture("benign.cbr")
    if not os.path.isfile(path):
        return False, "fixtures/archives/benign.cbr is absent (see fixtures/README.md)"
    if archive.libarchive_path() is None:
        try:
            archive._libarchive()
        except archive.LibarchiveMissing as e:
            return False, e.reason

    c.check(archive.rar_generation(path) == 4,
            "benign.cbr is RAR4 (-ma4), not RAR5")
    c.check(archive.detect_format(path) == archive.RAR,
            "benign.cbr detected as rar by signature")

    _ordinals, members = drain(path)
    c.check(len(members) == 3, f"all three .cbr pages decode ({len(members)})")

    out = archive.output_path(path, tmp)
    c.check(out.lower().endswith(".cbz"), f"a .cbr writes a .cbz ({out})")

    # The warning is per JOB. Two .cbr items, one warning.
    record = job.run_job([path, path], tmp, "cbr-job")
    c.check(len(record["warnings"]) == 1,
            f"the cbr->cbz warning is surfaced once per job, not per item "
            f"({len(record['warnings'])})")

    # PATH emptied: the read must still work, which is what makes "bundled and
    # self-contained" a fact rather than a claim.
    env = dict(os.environ, PATH="")
    probe = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, r'%s');"
         "from sidecar.containers import archive;"
         "print(len([m for _o,m,_i in archive.pages(r'%s')]))" % (ROOT, path)],
        capture_output=True, encoding="utf-8", errors="replace", env=env, cwd=ROOT,
    )
    c.check(probe.returncode == 0 and probe.stdout.strip() == "3",
            f"the .cbr still reads with PATH emptied -- libarchive is bundled, "
            f"not found on PATH (rc={probe.returncode} out={probe.stdout.strip()!r})")
    return True, ""


# --------------------------------------------------------------------------
# AC-12
# --------------------------------------------------------------------------

def warm_tier():
    """Fill cache's in-memory LRU tier to its byte cap and return its size.

    Section E requires the measurement to include the residency AC-12's bound
    must coexist with. Iteration 1 measured ingest with the tier cold, so the
    gate never observed the two budgets overlapping -- and in a real job they
    always do. The rasters are sized so three of them land just under the
    150MB cap: warming with page-sized rasters would leave the tier at 9MB and
    reintroduce exactly the accident this replaces.
    """
    cache.clear_tier()
    each = TIER_WARM_BYTES // cache.MAX_RASTERS
    side = int((each / 3) ** 0.5)
    for i in range(cache.MAX_RASTERS):
        cache._tier.put(f"warm-{i}", Image.new("RGB", (side, side), (i, 40, 90)))
    return cache.tier_bytes()


def _big_variants(tmp):
    """`big.cbz`'s 200 pages, repacked as 7z and as a gzipped tar.

    AC-12 is measured on the zip, which streams one page at a time and holds
    nothing. The other two readers do NOT: 7z extracts every named member in
    one pass (the fix for a quadratic per-member one) and a compressed tar
    holds every page candidate across its single forward pass, because both
    formats are forward-only and a second seek is not available. Those are
    deliberate trades and the docstrings say so -- but a trade nobody measures
    is a claim, and their residency scales with the ARCHIVE where the zip's
    scales with one page. So the same sampler runs over all three and prints
    all three numbers.

    Built rather than committed: repacking 200 pages costs under a second in
    each format, and two more 2MB archives in the determinism sweep buy
    nothing the zip does not already pin.
    """
    with zipfile.ZipFile(fixture(BIG)) as zf:
        entries = [(i.filename, zf.read(i.filename))
                   for i in zf.infolist() if not i.is_dir()]

    sevenzip = os.path.join(tmp, "big.cb7")
    archive.write_archive(sevenzip, entries, archive.SEVENZIP)

    tar_gz = os.path.join(tmp, "big.cbt")
    with gzip.GzipFile(filename="", mode="wb", fileobj=open(tar_gz, "wb"),
                       mtime=0) as stream:
        with tarfile.open(fileobj=stream, mode="w|",
                          format=tarfile.GNU_FORMAT) as tf:
            for name, payload in entries:
                entry = tarfile.TarInfo(name)
                entry.size = len(payload)
                entry.mtime = 0
                entry.mode = 0o644
                entry.uid = entry.gid = 0
                entry.uname = entry.gname = ""
                tf.addfile(entry, io.BytesIO(payload))

    return [("big.cbz", fixture(BIG)), ("big.cb7", sevenzip),
            ("big.cbt", tar_gz)]


def _measure(path, proc):
    """`(pages, peak - baseline, elapsed)` for one full ingest of `path`.

    Section E's procedure: baseline after residency is in place and before the
    input is opened, peak on a 250ms background thread during ingest.
    """
    baseline = proc.memory_info().rss
    peak = baseline
    done = threading.Event()

    def sample():
        nonlocal peak
        while not done.is_set():
            peak = max(peak, proc.memory_info().rss)
            done.wait(SAMPLE_INTERVAL)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    started = time.perf_counter()
    pages = 0
    try:
        for _o, _m, _img in archive.pages(path):
            pages += 1
            peak = max(peak, proc.memory_info().rss)
    finally:
        done.set()
        sampler.join(timeout=5)
    return pages, peak - baseline, time.perf_counter() - started


def check_memory(c, tmp):
    path = fixture(BIG)
    if not os.path.isfile(path):
        c.check(False, f"{BIG} is missing -- run tests/gen_fixtures.py")
        return

    proc = psutil.Process()
    tier = warm_tier()
    mb = 1024 * 1024

    with zipfile.ZipFile(path) as zf:
        declared = sum(1 for i in zf.infolist() if not i.is_dir())

    c.check(tier >= 100 * mb,
            f"the in-memory tier was warm before sampling ({tier / mb:.0f}MB)")

    zip_delta = None
    for label, target in _big_variants(tmp):
        pages, delta, elapsed = _measure(target, proc)
        # ASCII separators on purpose: run_all forces PYTHONIOENCODING=utf-8 on
        # its children, but a developer running this check directly gets the
        # console codepage, and a middot in cp1252 is the byte that killed a
        # reader thread once already (see run_all.run_check).
        print(f"  RSS {label:<11} delta {delta / mb:6.1f}MB | "
              f"warm tier {tier / mb:.1f}MB | {pages} pages in {elapsed:.1f}s",
              flush=True)
        c.check(pages == declared and pages == 200,
                f"{label}: all {pages} pages streamed (archive declares {declared})")
        c.check(delta < RSS_BUDGET,
                f"{label}: peak - baseline {delta / mb:.1f}MB < "
                f"{RSS_BUDGET / mb:.0f}MB")
        if label == "big.cbz":
            zip_delta = delta

    cache.clear_tier()
    return round(zip_delta / mb, 1)


def main():
    if not os.path.isdir(ARCHIVES):
        return skip("fixtures/archives/ is absent -- run tests/gen_fixtures.py")

    global GEN_COMICINFO
    with open(os.path.join(ARCHIVES, "expected.json"), encoding="utf-8") as fh:
        expected = json.load(fh)
    # Read back from the fixture itself rather than re-declared here: the
    # generator owns the bytes, and a second copy in the check would pass a
    # round-trip assert against a file neither the app nor the generator wrote.
    GEN_COMICINFO = archive.comicinfo(fixture("benign.cbz"))[1]
    if hashlib.sha256(GEN_COMICINFO).hexdigest() != expected["_comicinfo_sha256"]:
        print("FAIL: benign.cbz's ComicInfo.xml does not match expected.json")
        return 1

    c = Checks("check_archives")
    observed = set()
    with tempfile.TemporaryDirectory() as tmp:
        check_signatures(c)
        check_compressed_tar(c, tmp)
        check_reader_agreement(c)
        check_no_extractall(c)
        check_safety(c, observed)
        check_red(c)
        check_round_trip(c, tmp)
        check_item_boundary(c, tmp)
        peak_mb = check_memory(c, tmp)
        ran_cbr, why = check_cbr(c, tmp)

    # The named channel run_all.py ratchets on. hostile_rejected is a count
    # that should be 6 and stay 6; peak_rss_mb is RECORDED and not ratcheted,
    # for the reason id_chrf is not: it is a whole-process RSS reading, it
    # moves with the interpreter, the allocator and whatever else the box is
    # doing, and a ratchet that reads a 5MB swing as a regression goes red on
    # the weather. The 400MB gate above is the floor; this is the history.
    print("METRICS " + json.dumps({
        "archive_peak_rss_mb": peak_mb,
        "archive_hostile_rejected": len(observed & set(HOSTILE.values())),
    }), flush=True)

    result = c.finish()
    if result == 0 and not ran_cbr:
        # Not a pass. AC-6's .cbr clause is the one thing here that cannot be
        # verified without an artifact no free tool can author, and reporting
        # green would be reporting that it was checked.
        return skip(f"AC-6's .cbr clause not exercised: {why}")
    return result


if __name__ == "__main__":
    run(main)
