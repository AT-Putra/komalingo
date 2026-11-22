r"""A chapter of loose page images, read the way an archive is read.

A folder of PNGs is the most common way a chapter arrives, and until this
module each image was its own item: its own Queue row, no page cache, no
placement, no skip path and no Editor (plan 1.1, critic B1). Now the images
that share a folder are ONE item, of kind `images`, and they go through
pipeline.run_item and _run_cached_page like the pages of a .cbz: cached by
their pixels, placed by ordinal, skipped one page at a time when a model
refuses them.

The item holds its files explicitly (job.Item.members). A group can be a
SUBSET of its folder -- the user picked three images out of thirty -- so
nothing here ever lists the folder itself.

There is no archive to repack. The translated pages are the output, in the
item's directory, under the names the user knows (`p01_translated.png`).
"""

from __future__ import annotations

import io
import os

from .. import atomic, safety
from . import archive

IMAGES = "images"

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")


def is_image(path) -> bool:
    return os.path.splitext(os.fspath(path))[1].lower() in IMAGE_SUFFIXES


def pages(paths):
    """Yield `(ordinal, member, image)` for every decodable image, 1-based.

    The archive readers' contract, so _run_pages cannot tell the difference:
    `member` is the file name (where the page is delivered), the image is
    RGB with `.format` set to the source format, and the ordinal counts
    pages YIELDED -- an undecodable file is skipped on stderr and leaves no
    hole, exactly as archive.pages does with a junk member.

    The bytes are read whole and decoded through archive._decode, so a
    decompression bomb or a truncated file is the same one-skipped-page it
    is inside a .cbz rather than a second policy.
    """
    ordinal = 0
    for path in paths:
        name = os.path.basename(os.fspath(path))
        try:
            # The archive budget's per-file cap, so a loose file is held to
            # the same bound as a member (review: folder.pages bypassed it).
            if os.path.getsize(atomic.long_path(os.fspath(path))) > safety.MAX_FILE_BYTES:
                raise OSError(f"larger than {safety.MAX_FILE_BYTES // (1024 * 1024)} MB")
            with atomic.open_retry(atomic.long_path(os.fspath(path)), "rb") as fh:
                payload = io.BytesIO(fh.read())
        except OSError as e:
            import sys  # noqa: PLC0415 -- the error path only

            print(f"images: skipping unreadable file {name!r}: {type(e).__name__}: {e}",
                  file=sys.stderr, flush=True)
            continue
        page = archive._decode(name, payload)
        if page is None:
            continue
        ordinal += 1
        yield ordinal, name, page
