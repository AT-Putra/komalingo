r"""Read-only CBZ page enumeration. No repack, no safety budget, no other format.

Phase 3 needs one real multi-page item in hand, because the cache contract it
freezes -- placement on `(item_id, ordinal)`, two identical pages sharing a
hash -- is only testable against an archive that actually contains a repeated
page. A directory of loose files would have let the placement bug through.

**Read-only is a boundary, not an omission.** Phase 6's ingest has to enforce a
decompression budget, reject traversal members, and repack; those checks belong
on the path that accepts an untrusted archive from the user's disk into the
library. This path re-opens an item the user already ingested, to draw a page.
Sharing one function between them would mean either the editor pays for the
budget accounting on every page turn, or the ingest quietly inherits an opener
written without it. `pages()` opens the zip in "r" and holds no other mode.

Natural sort on the FULL member path, not on the basename. `ch2/p9.png` before
`ch2/p10.png` is the obvious half; the half that bites is `ch10/p1.png`, which
sorts before `ch2/p1.png` under any comparison that looks at the filename
alone, and before it lexicographically even on the full path. Segment-wise
digit-aware comparison is what puts chapter 2 before chapter 10 and page 9
before page 10 in the same ordering.
"""

from __future__ import annotations

import io
import os
import re
import sys
import zipfile

from PIL import Image, UnidentifiedImageError

from .. import atomic

# What PIL is asked to decode. Deliberately a fixed list rather than "whatever
# PIL registered": a CBZ carrying a .txt credits file or a .nfo should be
# skipped silently, and a reader that tries every member and catches the error
# reports a warning per junk file on an ordinary archive.
PAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff")

_DIGITS = re.compile(r"(\d+)")


def _natural_key(member: str):
    """Sort key for a full archive member path, digit-aware and segment-wise.

    Segments first, so a directory boundary always outranks anything inside it:
    comparing the flat string lets `ch2/p10.png` lose to `ch2-extra/p1.png`
    because '-' sorts below '/'. Within a segment, runs of digits compare as
    integers and everything else casefolded, so `p9` precedes `p10`.

    The (0, int) / (1, str) pairs keep a digit run and a text run from ever
    being compared to each other, which in Python 3 is a TypeError rather than
    an arbitrary order -- and it would be raised on the user's archive, not in
    any test written against tidy fixtures.
    """
    parts = member.replace("\\", "/").split("/")
    return [
        tuple(
            (0, int(tok), "") if tok.isdigit() else (1, 0, tok.casefold())
            for tok in _DIGITS.split(part)
            if tok
        )
        for part in parts
    ]


def _is_page(info: zipfile.ZipInfo) -> bool:
    """A member that should be decoded as a page.

    Directory entries, macOS resource forks and Windows thumbnail caches are
    skipped by NAME rather than by failing to decode, because "skipped without
    raising" and "skipped after a decode attempt and a warning" look the same
    to the caller and different to anyone reading the log.
    """
    name = info.filename.replace("\\", "/")
    if info.is_dir() or name.endswith("/"):
        return False
    base = name.rsplit("/", 1)[-1]
    if name.startswith("__MACOSX/") or base.startswith("._") or base == "Thumbs.db":
        return False
    return os.path.splitext(base)[1].lower() in PAGE_SUFFIXES


def _sorted_members(zf: zipfile.ZipFile) -> list[str]:
    """Page-candidate members of an OPEN archive, in yield order.

    One implementation, because `members` and `pages` must agree: a reader
    whose listing and whose enumeration sort differently would report a page
    order the editor then does not deliver, and the two expressions would drift
    the first time one of them was tuned.
    """
    return sorted((i.filename for i in zf.infolist() if _is_page(i)), key=_natural_key)


def members(path) -> list[str]:
    """The page-candidate member names of `path`, in the order `pages` uses.

    CANDIDATES, selected by extension. Nothing is decoded here, so a member
    named `.png` that is not a PNG is on this list and is not a page -- `pages`
    is what finds that out, and it skips without leaving an ordinal hole.
    """
    with zipfile.ZipFile(atomic.long_path(path), "r") as zf:
        return _sorted_members(zf)


def pages(path):
    """Yield `(ordinal, member, image)` for every decodable page, 1-based.

    Streamed through `ZipFile.open(member)`: nothing is extracted to disk, and
    the member is never `read()` whole into one bytes object first. PIL needs a
    seekable stream, and a zip member stream is seekable on 3.7+ for a stored
    or deflated entry -- when it is not, the member is buffered into memory for
    that page alone rather than for the archive.

    The image is fully loaded before it is yielded, so the caller may keep it
    after the stream closes. A generator that yielded a lazy Image would hand
    back a picture that decodes to an error one line after the `with` block.

    Ordinal counts PAGES YIELDED, not archive members. A junk file or an
    undecodable member does not leave a hole: placement keys on this number and
    a hole would mean "page 7" naming different pages before and after a
    corrupt member was repaired.

    The member NAME is yielded alongside because the delivered file is named
    after it. The alternative -- synthesising `{item}_{ordinal}` -- renames
    every page of every archive the user opens, so a translated page can no
    longer be matched to its source by eye or by a glob.
    """
    ordinal = 0
    with zipfile.ZipFile(atomic.long_path(path), "r") as zf:
        for name in _sorted_members(zf):
            with zf.open(name, "r") as stream:
                try:
                    raw = stream if stream.seekable() else io.BytesIO(stream.read())
                    with Image.open(raw) as img:
                        img.load()
                        fmt = img.format
                        page = img.convert("RGB")
                    # convert() copies info -- icc_profile and exif survive --
                    # but drops `format`, which is None on any derived image.
                    # The caller encodes the delivered page in the SOURCE
                    # format, so losing it here would silently turn a JPEG
                    # archive into PNG output.
                    page.format = fmt
                except (UnidentifiedImageError, OSError, ValueError,
                        Image.DecompressionBombError) as e:
                    # DecompressionBombError derives from Exception, not from
                    # OSError or ValueError, so the first tuple let it through
                    # -- and one pixel-bomb member, a few hundred KB compressed,
                    # aborted the whole archive as a 500. That contradicted the
                    # comment below in as many words. Phase 6 owns the ingest
                    # budget that REJECTS such an archive; here, where the
                    # archive is already the user's, it is one skipped page.
                    # Named, and on stderr rather than stdout: stdout is the
                    # progress pipe and Tauri parses every line of it as JSON.
                    # One bad member must not abort the other two hundred --
                    # the editor showing 199 pages and saying which one failed
                    # beats a dialog saying the archive is unreadable.
                    print(
                        f"read_cbz: skipping undecodable member {name!r}: "
                        f"{type(e).__name__}: {e}",
                        file=sys.stderr,
                        flush=True,
                    )
                    continue
            ordinal += 1
            yield ordinal, name, page
