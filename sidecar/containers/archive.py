r"""AC-6 / AC-11 / AC-12: the ingest path for every archive format.

One module, because the three ACs are one code path. Streaming extraction is
simultaneously what bounds memory (AC-12) and where the safety rules have the
only thing worth checking -- bytes that actually came out of the decompressor
(AC-11) -- and both are properties of the same loop that reads an archive to
translate it (AC-6).

**Format comes from the signature, never from the extension.** A `.cbz` that is
really a 7z is common enough that every comic reader handles it, and dispatching
on the name means such a file is handed to `zipfile`, raises `BadZipFile`, and
is reported to the user as a corrupt archive it is not.

**`extractall` is never called, and neither is any other whole-archive
extraction.** That is AC-12's mechanism, not a style preference: `extractall`
decompresses the entire archive to disk before the first page is translated,
which on a 200-page volume is the peak RSS the gate exists to prevent and a
directory of attacker-named files the safety rules were supposed to prevent
being created. `zipfile` and `tarfile` are driven member-by-member. py7zr has
no member-level read API in 1.x -- `extract` is the only door -- so it is
called with an in-memory `WriterFactory` that feeds every decompressed chunk
straight into the budget and never touches the filesystem. `check_archives`
asserts on both halves: the source carries no `extractall`, and a 7z read
leaves no file behind.

**A compressed tar is read in one forward pass, and it has to be.** Listing a
`.tar.gz` means decompressing all of it, so admission cannot run before
streaming the way it does for every other format -- it runs DURING it, against
a `_CountingReader` that charges the container's expansion to the budget as it
is produced. Two consequences are stated rather than discovered: the page
payloads of such an archive are held across the pass (encoded, not decoded --
see `_tar_single_pass`), and its non-page members are NOT carried through the
repack, because keeping them would mean holding the whole container. A plain
`.tar` has neither limitation; it is seekable and is read one member at a time.

**Read order is the editor's order.** `read_cbz._natural_key` is imported
rather than re-implemented -- a page spot-fixed at ordinal 7 must be the page
delivered at ordinal 7, and two sort implementations drift the first time one
is tuned.
"""

from __future__ import annotations

import io
import os
import re
import sys
import tarfile
import zipfile

from PIL import Image, UnidentifiedImageError

from .. import atomic, safety
from .read_cbz import PAGE_SUFFIXES, _natural_key

ZIP, SEVENZIP, TAR, RAR = "zip", "sevenzip", "tar", "rar"

# What AC-6 names, and nothing else. The value is the container family; the
# extension is kept separately because the OUTPUT keeps the input's extension
# (a .cbz does not come back as a .zip) while the reader only cares about the
# family.
EXTENSIONS = {
    ".cbz": ZIP, ".zip": ZIP,
    ".cb7": SEVENZIP, ".7z": SEVENZIP,
    ".cbt": TAR, ".tar": TAR,
    ".cbr": RAR, ".rar": RAR,
}

# What each input family is WRITTEN back as. Every format round-trips to itself
# except RAR, which is read-only for us and comes back as CBZ with a warning --
# AC-6's one deliberate format change, and the reason no part of this build
# compresses RAR.
OUTPUT_FORMAT = {ZIP: ZIP, SEVENZIP: SEVENZIP, TAR: TAR, RAR: ZIP}

CBR_WARNING = ("RAR archives are read-only: this item was written as .cbz. "
               "RAR compression is proprietary, so nothing here creates one.")

# The 7z epoch pin, in 7z's own unit: 100ns ticks since 1601-01-01. This value
# is 1970-01-01. Written into every member py7zr emits, because py7zr stamps
# the wall clock otherwise and the determinism gate reads these bytes.
SEVENZIP_EPOCH = 116444736000000000

# Pinned zip and tar stamps, matching gen_fixtures' own pinning. A repacked
# archive whose member times are the wall clock is not reproducible, and the
# round-trip assert compares archives written on two different seconds.
ZIP_DATE = (1980, 1, 1, 0, 0, 0)
TAR_MTIME = 0

_CHUNK = 1 << 16


class UnsupportedArchive(Exception):
    """The file is not an archive this build reads. Carries a reason string."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class LibarchiveMissing(Exception):
    """No usable libarchive, so the RAR read path cannot run.

    A named exception rather than the `ctypes` `TypeError` the binding raises
    when it finds no library: the UI has to tell the user their `.cbr` needs a
    component this install does not have, and "argument of type 'NoneType' is
    not iterable" is not that sentence.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


# --------------------------------------------------------------------------
# format detection
# --------------------------------------------------------------------------

_SIGNATURES = (
    (b"PK\x03\x04", ZIP), (b"PK\x05\x06", ZIP), (b"PK\x07\x08", ZIP),
    (b"7z\xbc\xaf\x27\x1c", SEVENZIP),
    (b"Rar!\x1a\x07\x00", RAR),        # RAR4
    (b"Rar!\x1a\x07\x01\x00", RAR),    # RAR5
    (b"\x1f\x8b", TAR),                # gzip -- a .tar.gz, read as tar
    (b"BZh", TAR),
    (b"\xfd7zXZ\x00", TAR),
)


def _head(path, n: int = 512) -> bytes:
    with open(atomic.long_path(path), "rb") as fh:
        return fh.read(n)


def detect_format(path) -> str:
    """The container family of `path`, from its bytes.

    The tar test is last and is positional rather than a prefix: tar has no
    leading magic at all, only `ustar` at offset 257, and a file shorter than
    that cannot be one. A tar written by a pre-POSIX tool carries no magic
    either; such a file is reported unsupported rather than guessed at, because
    "no signature anywhere" is also what every non-archive looks like.
    """
    head = _head(path)
    if not head:
        raise UnsupportedArchive(f"empty file: {os.path.basename(os.fspath(path))}")
    for sig, fmt in _SIGNATURES:
        if head.startswith(sig):
            return fmt
    if len(head) >= 262 and head[257:262] == b"ustar":
        return TAR
    raise UnsupportedArchive(
        f"unrecognised archive signature: {head[:8]!r}"
    )


def rar_generation(path) -> int:
    """4 or 5 for a RAR file, by signature. Raises for anything else.

    The `.cbr` fixture is pinned to RAR4 and this is what pins it: libarchive's
    RAR5 reader is a separate and less widely enabled code path, so a fixture
    that silently drifted to RAR5 would turn the PATH-emptied read assert --
    the one that makes "bundled and self-contained" a fact -- into a skip on
    builds that carry RAR4 support only.
    """
    head = _head(path, 16)
    if head.startswith(b"Rar!\x1a\x07\x01\x00"):
        return 5
    if head.startswith(b"Rar!\x1a\x07\x00"):
        return 4
    raise UnsupportedArchive(f"not a RAR file: {head[:8]!r}")


def is_archive(path) -> bool:
    """Whether `path` has an extension AC-6 covers. Cheap, name-only.

    Used to decide whether a directory entry is an item at all, which is a
    listing decision and must not open every file on the user's disk.
    """
    return os.path.splitext(os.fspath(path))[1].lower() in EXTENSIONS


def _is_page_name(name: str) -> bool:
    """Whether a member name is a page CANDIDATE. Identical rule to read_cbz."""
    clean = name.replace("\\", "/")
    if clean.endswith("/"):
        return False
    base = clean.rsplit("/", 1)[-1]
    if clean.startswith("__MACOSX/") or base.startswith("._") or base == "Thumbs.db":
        return False
    return os.path.splitext(base)[1].lower() in PAGE_SUFFIXES


# --------------------------------------------------------------------------
# libarchive resolution (RAR read)
# --------------------------------------------------------------------------

BUNDLED_LIBARCHIVE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "build", "libarchive",
)


def libarchive_path() -> str | None:
    r"""Where the bundled libarchive lives, or None to let the loader search.

    Order: `MT_LIBARCHIVE` (an explicit path, which is what a test or a
    developer with a system build uses), then the bundled `build\libarchive`
    directory beside the sidecar, then nothing -- and "nothing" means the
    binding falls back to the platform loader, which on a clean Windows box
    finds none and is exactly the case `LibarchiveMissing` names.
    """
    override = os.environ.get("MT_LIBARCHIVE", "").strip()
    if override:
        return override if os.path.isfile(override) else None
    # The packaged exe first. PyInstaller unpacks a one-file build into
    # sys._MEIPASS and __file__ no longer sits under the repository, so the
    # source-tree path below names a directory that does not exist inside the
    # bundle. build/sidecar.spec places the closure at <_MEIPASS>/libarchive,
    # and check_package proves the exe reads a .cbr -- this is the line that
    # assert depends on.
    frozen = getattr(sys, "_MEIPASS", None)
    roots = ([os.path.join(frozen, "libarchive")] if frozen else []) + [BUNDLED_LIBARCHIVE]
    for root in roots:
        for name in ("archive.dll", "libarchive.dll", "libarchive.so",
                     "libarchive.so.13", "libarchive.dylib"):
            candidate = os.path.join(root, name)
            if os.path.isfile(candidate):
                return candidate
    return None


def _libarchive():
    """Import the binding with the resolved library, or raise LibarchiveMissing.

    The binding reads `LIBARCHIVE` from the environment at IMPORT time, so the
    variable is set before the import rather than after it. The bundled
    directory is also put on the DLL search path: libarchive links zlib, bz2,
    lzma, zstd, iconv and libxml2, and a DLL whose dependencies cannot be found
    fails to load with the same FileNotFoundError as a DLL that is not there.
    """
    resolved = libarchive_path()
    if resolved:
        os.environ["LIBARCHIVE"] = resolved
        if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(os.path.dirname(resolved))
            except OSError:
                pass
    try:
        import libarchive  # noqa: PLC0415 -- deliberately lazy; see docstring
    except Exception as e:
        if resolved:
            # A library WAS found and would not load. Here the binding's own
            # error IS the diagnosis: a dependency DLL missing beside it fails
            # exactly like an absent file, and the type name is the only thing
            # that separates the two.
            reason = (f"libarchive at {resolved} could not be loaded "
                      f"({type(e).__name__}: {e}) -- a dependency DLL beside "
                      f"it may be missing")
        else:
            # Nothing resolved, and the platform loader found nothing either.
            # The binding reports that as "argument of type 'NoneType' is not
            # iterable", which is the exact sentence this class's docstring
            # exists to keep away from a reader -- so it does not go in the
            # message. It reached one anyway, as check_archives' skip reason,
            # because the message pasted it back in.
            # Two audiences, in that order. job.py puts this string on the
            # item as its SKIPPED reason and the Job view shows it, so the
            # first sentence is the one a reader who has just dropped a .cbr
            # on the app needs; the paths follow for whoever has to fix it.
            reason = ("this install cannot read RAR (.cbr) archives -- no "
                      "libarchive is bundled. Every other format is "
                      "unaffected: zip, 7z and tar need none of it. "
                      "(MT_LIBARCHIVE unset; "
                      f"{BUNDLED_LIBARCHIVE} carries no archive.dll, "
                      "libarchive.dll or libarchive.so; the platform loader "
                      "found none)")
        raise LibarchiveMissing(reason) from e
    return libarchive


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def _zip_entries(path):
    """(name, safety.Member) for every zip entry, in archive order."""
    with zipfile.ZipFile(atomic.long_path(path), "r") as zf:
        for info in zf.infolist():
            # The high 16 bits of external_attr are the Unix st_mode when the
            # archive was made on a Unix host. A zip CAN carry a symlink and
            # several packers do; the mode is the only place it says so.
            mode = info.external_attr >> 16
            yield info.filename, safety.Member(
                name=info.filename,
                is_dir=info.is_dir(),
                is_link=bool(mode & 0o170000) and (mode & 0o170000) != 0o100000
                and not info.is_dir(),
                declared_compressed=info.compress_size,
            )


def _tar_compression(path) -> str:
    """"gz" | "bz2" | "xz" for a whole-file-compressed tar, "" for a plain one.

    This distinction decides how the archive is READ, not merely how it is
    decoded, so it is a signature test rather than a guess from the name: a
    plain tar can be listed by reading 512-byte headers and seeking over the
    data, and a compressed one cannot be listed at all without decompressing
    every byte of it.
    """
    head = _head(path, 8)
    for sig, name in ((b"\x1f\x8b", "gz"), (b"BZh", "bz2"),
                      (b"\xfd7zXZ\x00", "xz")):
        if head.startswith(sig):
            return name
    return ""


class _CountingReader:
    """A read-only stream that charges every byte it produces to a Budget.

    This is the whole fix for the compressed-tar hole. `tarfile.open(..., "r:*")`
    on a `.tar.gz` calls `getmembers()`, which decompresses the ENTIRE archive
    to walk its headers -- and that happened inside the listing pass, before
    `_admit` ran a single rule and outside `account()` entirely. Measured on the
    first draft: an 11.94MB `.cbt` declaring 12GB was ACCEPTED after 14 seconds
    with the budget counting zero bytes, past a 200:1 rule, an 8GB total cap and
    a per-file cap. Every rule was live and none of them ran.

    So the decompressor is owned here rather than by `tarfile`: the gzip, bz2 or
    lzma object is wrapped in this, and tarfile is handed a plain stream. Now
    the bytes the container expands to are counted as they are produced, and
    `account_raw` refuses at the archive-level ratio or the total cap -- while
    the archive is still being read, not after.
    """

    def __init__(self, inner, budget: safety.Budget):
        self._inner = inner
        self._budget = budget

    def read(self, size=-1):
        chunk = self._inner.read(size)
        if chunk:
            self._budget.account_raw(len(chunk))
        return chunk

    def close(self):
        return self._inner.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _tar_entries(path):
    """Plain tar only. A compressed one goes through `_tar_single_pass`.

    `"r:"`, never `"r:*"`: the wildcard silently accepts a compressed stream and
    listing one means decompressing all of it. Naming the mode makes a
    compressed tar an error here rather than a hole.
    """
    with tarfile.open(atomic.long_path(path), "r:") as tf:
        for info in tf.getmembers():
            yield info.name, safety.Member(
                name=info.name,
                is_dir=info.isdir(),
                # Anything that is not a regular file or a directory: symlink,
                # hardlink, fifo, character and block device. tarfile is the
                # one format here that can carry all of them.
                is_link=not (info.isfile() or info.isdir()),
                # ZERO, deliberately, and this is the same decision the RAR
                # reader documents. A tar member is not individually
                # compressed -- the container is, or nothing is -- so there is
                # no denominator for a per-member ratio. Passing `info.size`
                # (which is the UNCOMPRESSED size) made every ratio exactly
                # 1:1, which does not disable the rule, it makes it look live
                # and never fire. Zero disables it in one place, on purpose,
                # and the byte caps plus the container-level ratio in
                # `account_raw` are what bound this format.
                declared_compressed=0,
            )


def _sevenzip_entries(path):
    import py7zr  # noqa: PLC0415 -- optional-format import, kept off startup
    with py7zr.SevenZipFile(atomic.long_path(path), "r") as sz:
        for f in sz.list():
            yield f.filename, safety.Member(
                name=f.filename,
                is_dir=bool(f.is_directory),
                # py7zr reports these as attributes on the listing entry. A 7z
                # symlink is stored as a regular member whose payload is the
                # target, with the flag in the attributes -- so the flag is the
                # only thing that distinguishes it from a tiny text file.
                is_link=bool(getattr(f, "is_symlink", False)
                             or getattr(f, "is_junction", False)),
                # `compressed` is the size of the SOLID BLOCK's first member and
                # None for every other member of that block, so on a typical 7z
                # this is 0 for all but one entry. Read as-is rather than
                # substituted: an approximation here would be a ratio rule that
                # fires on the block's boundaries instead of on a bomb.
                declared_compressed=int(getattr(f, "compressed", 0) or 0),
            )


def _rar_entries(path):
    la = _libarchive()
    with la.file_reader(atomic.long_path(path)) as archive:
        for entry in archive:
            yield str(entry.pathname), safety.Member(
                name=str(entry.pathname),
                is_dir=bool(entry.isdir),
                is_link=bool(entry.issym or entry.islnk),
                # libarchive reports the uncompressed size only. Passing it as
                # the compressed size would make every ratio 1:1 and disable
                # the rule; 0 disables the ratio rule explicitly instead, and
                # the absolute byte caps -- which are fed by streamed bytes --
                # are what bound a RAR bomb. Stated rather than accidental.
                declared_compressed=0,
            )


_ENTRY_READERS = {
    ZIP: _zip_entries, TAR: _tar_entries,
    SEVENZIP: _sevenzip_entries, RAR: _rar_entries,
}


def _admit(path, fmt: str, budget: safety.Budget):
    """Run every member past the budget; return the page candidates to stream.

    Every entry is checked, not only the pages: the member-count rule is about
    the archive and the traversal rules are about what a repack would create.
    Filtering to pages first would let an archive carrying 5000 pages and 500
    hostile non-image members through both.

    Returns `(names in read order, name -> Member)`. The Member goes back to
    the caller because the streaming pass has to hand it to `budget.begin` --
    admission and accounting are two passes over two different orders, and the
    per-file counters belong to the second one.
    """
    names, members = [], {}
    for name, member in _ENTRY_READERS[fmt](path):
        budget.check_member(member)
        members[name] = member
        if not member.is_dir and not member.is_link and _is_page_name(name):
            names.append(name)
    return sorted(names, key=_natural_key), members


def _decode(name: str, payload):
    """Decode one member's bytes to an RGB page, or None if it is not an image.

    Takes the buffer rather than `bytes`: the reader already holds the member in
    a BytesIO, and `getvalue()` would make a second full copy of it at the exact
    moment the per-file cap is meant to be a floor under peak RSS.

    Mirrors read_cbz's skip policy exactly, down to the message: an undecodable
    member is one skipped page on stderr, never a failed archive. stdout is the
    progress pipe and Tauri parses every line of it as JSON.
    """
    try:
        payload.seek(0)
        with Image.open(payload) as img:
            img.load()
            fmt = img.format
            page = img.convert("RGB")
        page.format = fmt
        return page
    except (UnidentifiedImageError, OSError, ValueError,
            Image.DecompressionBombError) as e:
        print(f"archive: skipping undecodable member {name!r}: "
              f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)
        return None


def _drain(stream, budget) -> io.BytesIO:
    """One member's bytes, counted per chunk on the way in."""
    buf = io.BytesIO()
    while True:
        chunk = stream.read(_CHUNK)
        if not chunk:
            break
        budget.account(len(chunk))
        buf.write(chunk)
    return buf


def _zip_payloads(path, names, members, budget):
    with zipfile.ZipFile(atomic.long_path(path), "r") as zf:
        for name in names:
            budget.begin(members[name])
            with zf.open(name, "r") as stream:
                yield name, _drain(stream, budget)


def _tar_payloads(path, names, members, budget):
    """Plain tar. Seekable, so one member is read at a time and none is held."""
    with tarfile.open(atomic.long_path(path), "r:") as tf:
        for name in names:
            budget.begin(members[name])
            stream = tf.extractfile(name)
            if stream is None:          # a directory or a link slipped through
                continue
            with stream:
                yield name, _drain(stream, budget)


def _tar_single_pass(path, budget):
    """Compressed tar: admit and read in ONE forward pass over the stream.

    Two properties make this necessary rather than tidy. Listing a compressed
    tar decompresses all of it, so admission cannot precede streaming -- it has
    to happen DURING it, which is what `"r|"` over a `_CountingReader` gives.
    And the stream is forward-only, so there is no seeking back to a member by
    name: a page's bytes are either kept as they go past or they are gone.

    What is held: the ENCODED bytes of the page candidates, not decoded
    rasters. A page is a few hundred KB as PNG and twenty megabytes decoded, so
    this costs roughly the archive's uncompressed size in encoded form rather
    than AC-12's budget -- and it is bounded above by the same total cap every
    other rule answers to. The CBZ path, which is the one AC-12 gates, still
    streams one page at a time and holds nothing. A `.cbt.gz` is a
    compatibility read; a `.cbz` is the product's own format.

    Returns `(names in natural order, name -> Member, name -> BytesIO)`.
    """
    comp = _tar_compression(path)
    raw = open(atomic.long_path(path), "rb")
    try:
        budget.begin_stream(os.path.getsize(atomic.long_path(path)))
        if comp == "gz":
            import gzip  # noqa: PLC0415 -- one of three, chosen by signature
            inner = gzip.GzipFile(fileobj=raw, mode="rb")
        elif comp == "bz2":
            import bz2  # noqa: PLC0415
            inner = bz2.BZ2File(raw, "rb")
        else:
            import lzma  # noqa: PLC0415
            inner = lzma.LZMAFile(raw, "rb")

        counting = _CountingReader(inner, budget)
        names, members, payloads = [], {}, {}
        with tarfile.open(fileobj=counting, mode="r|") as tf:
            for info in tf:
                member = safety.Member(
                    name=info.name,
                    is_dir=info.isdir(),
                    is_link=not (info.isfile() or info.isdir()),
                    declared_compressed=0,
                )
                budget.check_member(member)
                members[info.name] = member
                if member.is_dir or member.is_link:
                    continue
                if not (_is_page_name(info.name)
                        or safety.is_comicinfo(info.name)):
                    continue
                stream = tf.extractfile(info)
                if stream is None:
                    continue
                # begin() resets the per-member counters; the bytes are ALSO
                # counted as container bytes by _CountingReader on the way out
                # of the decompressor. That double count is deliberate: the
                # per-member cap and the container ratio are different rules
                # asking different questions, and a member read must answer
                # both.
                budget.begin(member)
                with stream:
                    payloads[info.name] = _drain(stream, budget)
                if _is_page_name(info.name):
                    names.append(info.name)
        return sorted(names, key=_natural_key), members, payloads
    finally:
        raw.close()


def _sevenzip_payloads(path, names, members, budget):
    """Every named member in ONE extract pass, into memory, budget-fed.

    py7zr 1.x has no member-level read: `extract` is the whole API. It does
    take a `WriterFactory`, and a factory that hands back a sink instead of a
    file is what keeps this off the filesystem -- so the rule "`extractall` is
    never called" holds in substance as well as in spelling, and the budget
    sees every decompressed chunk as it is produced rather than after the
    member is whole.

    ONE pass, not one per member. 7z compresses in solid blocks, so
    `reset()` + `extract([one name])` per member re-decompresses the whole
    block every time: measured at 0.01s for 3 members and 0.73s for 30, which
    extrapolates to about half a minute of pure re-decompression on a 200-page
    volume. The cost of the single pass is that the named members are resident
    together, as ENCODED bytes -- the same trade the compressed-tar and RAR
    readers make, and bounded by the same caps.
    """
    import py7zr  # noqa: PLC0415
    from py7zr.io import Py7zIO, WriterFactory  # noqa: PLC0415

    wanted = list(names)
    if not wanted:
        return

    class _BudgetIO(Py7zIO):
        def __init__(self, filename):
            self.filename = filename
            self._buf = io.BytesIO()
            budget.begin(members[filename])

        def write(self, s):
            budget.account(len(s))
            return self._buf.write(s)

        def read(self, size=None):
            return self._buf.read(size)

        def seek(self, offset, whence=0):
            return self._buf.seek(offset, whence)

        def flush(self):
            return self._buf.flush()

        def size(self):
            return self._buf.getbuffer().nbytes

        def buffer(self):
            return self._buf

    class _Factory(WriterFactory):
        def __init__(self):
            self.products = {}

        def create(self, filename):
            sink = _BudgetIO(filename)
            self.products[filename] = sink
            return sink

        def get(self, filename):
            return self.products[filename]

    factory = _Factory()
    with py7zr.SevenZipFile(atomic.long_path(path), "r") as sz:
        sz.extract(targets=wanted, factory=factory)
    for name in wanted:
        sink = factory.products.get(name)
        if sink is not None:
            yield name, sink.buffer()


def _rar_payloads(path, names, members, budget):
    """RAR members, read once in ARCHIVE order and yielded in NATURAL order.

    libarchive's reader is forward-only -- there is no seek to a named entry --
    so a second pass per member is not available and the encoded payloads are
    held across the pass. What is held is the DECOMPRESSED bytes of each page,
    not a decoded raster: a page is a few hundred KB as PNG and 20MB decoded,
    so this costs roughly the archive's own size rather than AC-12's budget.
    The CBZ path, which is the one AC-12 gates, streams one page at a time and
    holds nothing.
    """
    la = _libarchive()
    wanted = set(names)
    payloads = {}
    with la.file_reader(atomic.long_path(path)) as archive:
        for entry in archive:
            name = str(entry.pathname)
            if name not in wanted:
                continue
            budget.begin(members[name])
            buf = io.BytesIO()
            for block in entry.get_blocks():
                budget.account(len(block))
                buf.write(block)
            payloads[name] = buf
    for name in names:
        if name in payloads:
            yield name, payloads[name]


_PAYLOAD_READERS = {
    ZIP: _zip_payloads, TAR: _tar_payloads,
    SEVENZIP: _sevenzip_payloads, RAR: _rar_payloads,
}


def _scan(path, fmt: str, budget: safety.Budget):
    """`(page names in natural order, name -> Member, payload source)`.

    The one place the compressed-tar special case lives. Every other format
    admits first and streams second; a compressed tar has to do both at once,
    and every caller below wants the same three things regardless. The payload
    source is an iterable of `(name, buffer)` in the order given.
    """
    if fmt == TAR and _tar_compression(path):
        names, entries, payloads = _tar_single_pass(path, budget)
        return names, entries, [(n, payloads[n]) for n in names if n in payloads]
    names, entries = _admit(path, fmt, budget)
    return names, entries, _PAYLOAD_READERS[fmt](path, names, entries, budget)


def members(path, budget: safety.Budget | None = None) -> list[str]:
    """Page-candidate member names of `path`, in the order `pages` uses.

    CANDIDATES, selected by extension, exactly as read_cbz defines them: a
    member named `.png` that is not one is on this list and is not a page.
    """
    fmt = detect_format(path)
    budget = budget or safety.Budget(os.path.dirname(os.fspath(path)))
    names, _entries, _payloads = _scan(path, fmt, budget)
    return names


def pages(path, budget: safety.Budget | None = None):
    """Yield `(ordinal, member, image)` for every decodable page, 1-based.

    Same contract as `read_cbz.pages`, over every format AC-6 names, with the
    AC-11 budget enforced on the way past. The ordinal counts PAGES YIELDED,
    not members: a junk file or an undecodable member leaves no hole, because
    placement keys on this number and a hole would rename every page after a
    corrupt member was repaired.
    """
    fmt = detect_format(path)
    budget = budget or safety.Budget(os.path.dirname(os.fspath(path)))
    _names, _entries, source = _scan(path, fmt, budget)
    ordinal = 0
    for name, payload in source:
        page = _decode(name, payload)
        if page is None:
            continue
        ordinal += 1
        yield ordinal, name, page


# --------------------------------------------------------------------------
# ComicInfo.xml
# --------------------------------------------------------------------------

_LANGUAGE_RE = re.compile(rb"(<LanguageISO(?:\s[^>]*)?>)(.*?)(</LanguageISO\s*>)",
                          re.DOTALL)
_EMPTY_LANGUAGE_RE = re.compile(rb"<LanguageISO(\s[^>]*)?/>")
_CLOSE_RE = re.compile(rb"</ComicInfo\s*>")


def comicinfo(path, budget: safety.Budget | None = None) -> tuple[str, bytes] | None:
    """`(member name, raw bytes)` of the archive's ComicInfo.xml, or None.

    RAW bytes, and they stay raw through the repack. Parsing and re-serialising
    the file would normalise attribute order, self-closing tags, the XML
    declaration and the line endings -- all of which AC-6 requires to survive
    verbatim, and none of which any XML library preserves.

    Every member goes past the budget first, exactly as `pages` does, even
    though only one is read. The first draft filtered to the ComicInfo member
    and streamed it without admitting anything -- which is a public entry point
    into an untrusted archive with no AC-11 enforcement on it. In the product
    it is only ever called on an archive `pages` has already admitted, so
    nothing was reachable through it; a safety boundary that holds only because
    of the order its callers happen to run in is not one.
    """
    fmt = detect_format(path)
    budget = budget or safety.Budget(os.path.dirname(os.fspath(path)))
    if fmt == TAR and _tar_compression(path):
        # The single pass already holds it: re-reading would mean decompressing
        # the whole container a second time.
        _names, _entries, payloads = _tar_single_pass(path, budget)
        picks = [n for n in payloads if safety.is_comicinfo(n)]
        if not picks:
            return None
        name = sorted(picks, key=_natural_key)[0]
        return name, payloads[name].getvalue()

    _pages, entries = _admit(path, fmt, budget)
    picks = [n for n in entries if safety.is_comicinfo(n)]
    if not picks:
        return None
    name = sorted(picks, key=_natural_key)[0]
    for got, payload in _PAYLOAD_READERS[fmt](path, [name], entries, budget):
        return got, payload.getvalue()
    return None


def repack_extras(path, budget: safety.Budget | None = None):
    """`(comicinfo_entry, extra_entries)` -- everything a repack needs, ONE pass.

    This exists because two passes over one budget is a defect, not an
    inefficiency. `Budget.check_member` counts members, and it counts them per
    CALL: the repack used to fetch the ComicInfo and the other non-page members
    through two separate functions, each running its own `_admit`, so one
    budget across both counted every member twice and refused `member-count`
    at half the advertised cap. The damage was not a spurious
    error message -- `run_item` had already detected, OCR'd, translated and
    rendered every page by then, `job.run_item` reported the item SKIPPED as
    an unsafe archive, and `_discard_output` deleted the lot. A 3000-page
    box-set is inside what the 5000 cap was written to allow; measured, it was
    refused at member 5001 of a 3002-member archive after paying the full
    translation cost.

    One pass also halves the repack's I/O, which matters most on exactly the
    archives that used to trip it.
    """
    fmt = detect_format(path)
    budget = budget or safety.Budget(os.path.dirname(os.fspath(path)))

    if fmt == TAR and _tar_compression(path):
        # The single pass already holds what it kept; re-reading would mean
        # decompressing the whole container again. Non-page members are not
        # among them, which is the documented limit of the compressed-tar
        # reader -- see the module docstring.
        _names, _entries, payloads = _tar_single_pass(path, budget)
        picks = sorted((n for n in payloads if safety.is_comicinfo(n)),
                       key=_natural_key)
        info = (picks[0], payloads[picks[0]].getvalue()) if picks else None
        return info, []

    _pages, entries = _admit(path, fmt, budget)
    comic = sorted((n for n in entries if safety.is_comicinfo(n)),
                   key=_natural_key)
    chosen = comic[0] if comic else None
    # Excludes the CHOSEN ComicInfo, not every member that looks like one. An
    # archive carrying both `ComicInfo.xml` and `sub/ComicInfo.xml` had the
    # second land in neither list and vanish from the repack -- one shape for
    # which AC-6's member-set clause was simply false. A ComicInfo further down
    # the tree is an ordinary member; only the one the language rewrite targets
    # is handled separately.
    keep = sorted((n for n, m in entries.items()
                   if not m.is_dir and not m.is_link
                   and not _is_page_name(n) and n != chosen),
                  key=_natural_key)
    wanted = ([chosen] if chosen else []) + keep
    if not wanted:
        return None, []

    # LAZY, deliberately. Materialising the extras would hold every non-page
    # member at once -- bounded by max_total_bytes (8GB) rather than by
    # max_file_bytes (128MB) -- and `write_archive` promises its entries are
    # consumed one payload at a time. The ComicInfo is pulled off the front
    # because the writer needs it before the first entry, and `wanted` puts it
    # first; everything after it stays a generator, so admission is still ONE
    # pass and residency is still one member.
    stream = _PAYLOAD_READERS[fmt](path, wanted, entries, budget)
    info = None
    if chosen is not None:
        for name, payload in stream:
            if safety.is_comicinfo(name):
                info = (name, payload.getvalue())
            else:
                # The reader skipped the ComicInfo member (a tar link, say).
                # This one is an extra, and it must not be lost to the pull.
                return None, _lazy(name, payload.getvalue(), stream)
            break

    def rest():
        for name, payload in stream:
            yield name, payload.getvalue()

    return info, rest()


def _lazy(name, payload, stream):
    """`(name, payload)` followed by the rest of `stream`, still lazily."""
    yield name, payload
    for got, buf in stream:
        yield got, buf.getvalue()


def rewrite_language(xml: bytes, lang: str) -> bytes:
    """ComicInfo.xml with LanguageISO set to `lang` and nothing else touched.

    A byte-level substitution, for the reason in `comicinfo`. Three shapes are
    handled: an element with text, a self-closing `<LanguageISO/>`, and no
    element at all -- in which case one is inserted immediately before the
    closing tag, because AC-6 says the output declares its language and an
    input that never did still has to.
    """
    value = lang.encode("utf-8")
    if _LANGUAGE_RE.search(xml):
        return _LANGUAGE_RE.sub(lambda m: m.group(1) + value + m.group(3), xml, count=1)
    if _EMPTY_LANGUAGE_RE.search(xml):
        return _EMPTY_LANGUAGE_RE.sub(b"<LanguageISO>" + value + b"</LanguageISO>",
                                      xml, count=1)
    inserted = b"  <LanguageISO>" + value + b"</LanguageISO>\n"
    if _CLOSE_RE.search(xml):
        return _CLOSE_RE.sub(lambda m: inserted + m.group(0), xml, count=1)
    return xml


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------

def output_path(src_path, dest_dir, suffix: str = "_translated") -> str:
    """Where the repacked archive lands. Same extension, except RAR -> .cbz.

    The extension is preserved rather than normalised so a `.cbz` does not come
    back as a `.zip`: they are the same container and different things to every
    reader app the user has.
    """
    stem, ext = os.path.splitext(os.path.basename(os.fspath(src_path)))
    fmt = OUTPUT_FORMAT[detect_format(src_path)]
    if EXTENSIONS.get(ext.lower()) != fmt:
        ext = ".cbz" if fmt == ZIP else {SEVENZIP: ".cb7", TAR: ".cbt"}[fmt]
    return os.path.join(os.fspath(dest_dir), f"{stem}{suffix}{ext}")


def _write_zip(fh, entries):
    with zipfile.ZipFile(fh, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries:
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, payload)


def _write_tar(fh, entries):
    # format=GNU_FORMAT, not the default PAX: PAX writes an extended header
    # holding the mtime at full precision, which makes the output differ
    # between runs even with mtime pinned, because the pax record also carries
    # the archive's own creation context on some tar versions.
    with tarfile.open(fileobj=fh, mode="w", format=tarfile.GNU_FORMAT) as tf:
        for name, payload in entries:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mtime = TAR_MTIME
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tf.addfile(info, io.BytesIO(payload))


def _write_sevenzip(fh, entries):
    import py7zr  # noqa: PLC0415
    from py7zr.helpers import ArchiveTimestamp  # noqa: PLC0415

    with py7zr.SevenZipFile(fh, "w") as sz:
        for name, payload in entries:
            sz.writef(io.BytesIO(payload), name)
        # py7zr stamps the wall clock on every member and offers no argument
        # for it. The header is not written until close(), so pinning the
        # collected entries here is both the only hook there is and early
        # enough to matter. Creation and access times are dropped outright --
        # 7z stores each independently and an absent field is reproducible
        # where a pinned one is merely constant.
        for f in sz.files:
            f._file_info["lastwritetime"] = ArchiveTimestamp(SEVENZIP_EPOCH)
            for key in ("creationtime", "lastaccesstime"):
                f._file_info.pop(key, None)


_WRITERS = {ZIP: _write_zip, TAR: _write_tar, SEVENZIP: _write_sevenzip}


def write_archive(dest, entries, fmt: str, comicinfo_entry=None,
                  lang: str | None = None, extra_entries=None) -> str:
    """Repack `entries` -- an iterable of `(member name, bytes)` -- at `dest`.

    Through `atomic.atomic_write`, so a crash or a cancel mid-repack leaves no
    half-written archive where the user's reader would find one. `entries` is
    consumed lazily and one payload at a time; the caller streams pages off
    disk rather than holding two hundred of them.

    `comicinfo_entry` is `(member name, raw bytes)` as `comicinfo()` returned
    it. It is written FIRST, which is where every comic reader looks for it,
    and its bytes are the input's with only LanguageISO rewritten.

    `extra_entries` is every member of the input that is not a page and not the
    ComicInfo -- `credits.txt`, a `.nfo`, a cover thumbnail. They are written
    verbatim. Without them the output's member set is a subset of the input's
    and AC-6's round-trip clause is false in a way no page-order assert can
    see, because both sides of that comparison list pages.
    """
    writer = _WRITERS[fmt]

    def stream():
        if comicinfo_entry is not None:
            name, payload = comicinfo_entry
            yield name, (rewrite_language(payload, lang) if lang else payload)
        yield from entries
        yield from (extra_entries or ())

    with atomic.atomic_write(dest) as fh:
        writer(fh, stream())
    return atomic.long_path(dest)
