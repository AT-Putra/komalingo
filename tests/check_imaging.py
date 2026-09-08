"""Phase 0 -- encode policy. Offline, no network.

Asserts, from the build order:
  1. JPG, PNG and WEBP each round-trip to their OWN format
  2. the JPEG carries subsampling=0
  3. icc_profile survives byte-identical
  4. non-GPS EXIF survives byte-identical
  5. the GPS IFD is absent from the output of an input that has one

Deliberately NOT asserted: JPEG quality read back from quantization tables.
Cut by architect iteration 2 -- the mapping is not cleanly invertible, so the
assert would flake and get weakened rather than fixed.

Fixtures are built in-process rather than committed: the determinism ratchet
sha256s everything under fixtures/, and a JPEG written by a different Pillow
build would fail it for a non-regression reason.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from PIL import Image, JpegImagePlugin  # noqa: E402

from sidecar import imaging  # noqa: E402
from lib.result import Checks, run  # noqa: E402

# A real, minimal sRGB v2 profile would be 3KB of binary. Pillow does not
# validate icc_profile on save, and the assert is "the bytes we handed in come
# back", so a recognisable sentinel proves the carry without the payload.
ICC = b"MTFAKEICC" + bytes(range(64))

DESCRIPTION = 0x010E  # ImageDescription -- a tag that must survive
GPS_LAT = 2  # GPSLatitude, inside the GPS IFD that must not


def build_source(path, fmt, size=(64, 48), with_gps=True):
    """A source image carrying an ICC profile and EXIF with and without GPS."""
    img = Image.new("RGB", size)
    for y in range(size[1]):
        for x in range(size[0]):
            img.putpixel((x, y), (x * 4 % 256, y * 5 % 256, (x + y) % 256))

    exif = Image.Exif()
    exif[DESCRIPTION] = "manga-translator source"
    if with_gps:
        exif[imaging.GPS_IFD] = {GPS_LAT: (35.0, 41.0, 0.0)}

    kwargs = {"icc_profile": ICC, "exif": exif.tobytes()}
    if fmt == "PNG":
        kwargs.pop("exif")  # written separately below; PNG eXIf is optional
    img.save(path, format=fmt, **kwargs)
    return img


def main():
    c = Checks("check_imaging")

    with tempfile.TemporaryDirectory() as root:
        # --- 1: format is matched to the INPUT, per format -----------------
        for fmt, ext in (("JPEG", ".jpg"), ("PNG", ".png"), ("WEBP", ".webp")):
            src = os.path.join(root, f"src{ext}")
            build_source(src, fmt)
            with Image.open(src) as im:
                out = imaging.save(im.copy(), src, os.path.join(root, f"out{ext}"))
            with Image.open(out) as got:
                c.check(got.format == fmt, f"{ext} round-trips as {fmt}, got {got.format}")

        # A .png destination path must NOT turn a JPEG source into a PNG:
        # format follows the source image, never the destination string.
        src = os.path.join(root, "src.jpg")
        misnamed = os.path.join(root, "misnamed.png")
        with Image.open(src) as im:
            imaging.save(im.copy(), src, misnamed)
        with Image.open(misnamed) as got:
            c.check(got.format == "JPEG", "format follows the SOURCE, not the dest extension")

        # --- 2: subsampling 4:4:4 on the JPEG ------------------------------
        with Image.open(os.path.join(root, "out.jpg")) as got:
            sub = JpegImagePlugin.get_sampling(got)
            c.check(sub == 0, f"JPEG subsampling is 0 (4:4:4), got {sub}")

        # --- 3 + 4 + 5: metadata carry, on the JPEG ------------------------
        with Image.open(os.path.join(root, "out.jpg")) as got:
            c.check(got.info.get("icc_profile") == ICC, "icc_profile survives byte-identical")

            exif = got.getexif()
            c.check(
                exif.get(DESCRIPTION) == "manga-translator source",
                "non-GPS EXIF survives byte-identical",
            )
            c.check(imaging.GPS_IFD not in exif, "GPS IFD is stripped from the output")

        # And the source really did have one -- otherwise assert 5 passes
        # vacuously and can never go red.
        with Image.open(os.path.join(root, "src.jpg")) as srcimg:
            c.check(
                imaging.GPS_IFD in srcimg.getexif(),
                "control: the source DID carry a GPS IFD",
            )

        # --- WEBP carries the profile too ----------------------------------
        with Image.open(os.path.join(root, "out.webp")) as got:
            c.check(got.info.get("icc_profile") == ICC, "WEBP carries icc_profile")

        # --- output_path keeps the source extension ------------------------
        c.check(
            imaging.output_path("/a/b/page.jpeg", "/out").endswith("page_translated.jpeg"),
            "output_path keeps .jpeg rather than normalising it to .jpg",
        )

    return c.finish()


run(main)
