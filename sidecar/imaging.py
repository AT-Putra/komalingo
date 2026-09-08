"""Encode policy. The only place in the app that calls Image.save.

Pillow silently drops icc_profile and exif on save. A translated page that
comes back colour-shifted or stripped of its camera metadata is a data-loss
bug that no visual check catches, so both are carried explicitly here rather
than left to the caller to remember.
"""

from __future__ import annotations

import io
import os

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from . import atomic

# JPEG re-encode settings. subsampling=0 (4:4:4) because manga is line art:
# chroma subsampling smears the coloured edges of speech bubbles, and it is the
# one JPEG setting whose damage survives at quality=95.
JPEG_QUALITY = 95
JPEG_SUBSAMPLING = 0

# EXIF tag 0x8825 is the GPS IFD pointer. A translated page carries no reason
# to ship the photographer's coordinates onward.
GPS_IFD = 0x8825


def strip_gps(exif_bytes: bytes | None) -> bytes | None:
    """Drop the GPS IFD, keep every other tag byte-identical."""
    if not exif_bytes:
        return exif_bytes
    exif = Image.Exif()
    exif.load(exif_bytes)
    if GPS_IFD in exif:
        del exif[GPS_IFD]
    return exif.tobytes()


def _save_kwargs(fmt: str, src: Image.Image) -> dict:
    kw: dict = {}

    icc = src.info.get("icc_profile")
    if icc:
        kw["icc_profile"] = icc

    exif = strip_gps(src.info.get("exif"))
    if exif:
        kw["exif"] = exif

    if fmt == "JPEG":
        kw["quality"] = JPEG_QUALITY
        kw["subsampling"] = JPEG_SUBSAMPLING
    elif fmt == "PNG":
        # An empty PngInfo suppresses the tIME chunk, which otherwise stamps
        # the current time into the file and makes byte-identical output
        # impossible to assert.
        kw["pnginfo"] = PngInfo()
    elif fmt == "WEBP":
        kw["quality"] = JPEG_QUALITY
        kw["lossless"] = src.format == "WEBP" and src.info.get("lossless", False)

    return kw


def encode(img: Image.Image, fmt: str, src: Image.Image | None = None) -> bytes:
    """Encode to bytes in `fmt`, carrying metadata from `src` (default: img)."""
    buf = io.BytesIO()
    img.save(buf, format=fmt, **_save_kwargs(fmt, src if src is not None else img))
    return buf.getvalue()


def output_path(src_path, dest_dir, suffix: str = "_translated") -> str:
    """Destination path whose extension matches the SOURCE format.

    Named off the source extension rather than the decoded format so a .jpeg
    input does not silently become .jpg.
    """
    stem, ext = os.path.splitext(os.path.basename(os.fspath(src_path)))
    return os.path.join(os.fspath(dest_dir), f"{stem}{suffix}{ext}")


def save(img: Image.Image, src_path, dest_path, src: Image.Image | None = None) -> str:
    """Encode `img` in the source image's format and write it atomically.

    Format comes from the source image, not from the destination extension:
    the pipeline must never turn a user's PNG into a JPEG because a path
    string said so.
    """
    with Image.open(atomic.long_path(src_path)) as probe:
        fmt = probe.format
        meta = src if src is not None else probe
        payload = encode(img, fmt, meta)

    with atomic.atomic_write(dest_path) as fh:
        fh.write(payload)
    return atomic.long_path(dest_path)
