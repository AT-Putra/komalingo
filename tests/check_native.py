r"""The native bundle libarchive needs (AC-6's .cbr clause). OFFLINE.

    uv run --project sidecar python tests\check_native.py

`sidecar/native.py` fetches nine DLLs from conda-forge with pinned sha256s.
Three of its claims are the kind that rot silently, so none of them is read
out of a comment here -- each is re-derived from the bytes on disk:

  [closure]   every non-system DLL that anything in build/libarchive imports
              is also in build/libarchive. This is the assert that would have
              caught the first attempt, where libxml2 pulled icuuc78.dll and
              archive.dll then failed to load with a FileNotFoundError naming
              nothing in particular.
  [no-icu]    libxml2 is the no-ICU variant. conda-forge ships both at the
              same version and the default costs 16.8MB plus data for a XAR
              reader this project never opens, so the pin is load-bearing and
              a re-pin could lose it without any other assert noticing.
  [no-openssl] nothing in the closure imports libcrypto or libssl. conda's
              metadata for libarchive DECLARES openssl; the binary imports
              Windows CNG (bcrypt.dll) instead. Bundling a stale OpenSSL is
              worse than bundling none, and the difference between the
              declared list and the real one is 3MB of security surface.
  [pins]      every package is pinned to an exact build with a 64-hex sha256.
              A range or a "latest" would make the closure above reproducible
              on one machine and not the next.

Exit contract: 0 pass, 3 skip (the bundle is not installed -- a clean clone
that has not run `python -m sidecar.native` yet).
"""

from __future__ import annotations

import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.result import Checks, run, skip  # noqa: E402
from sidecar import native  # noqa: E402

# Imports resolved by Windows itself. Anything not matching these has to be in
# the bundle, or the DLL that needs it will not load.
SYSTEM_PREFIXES = (
    "api-ms-", "kernel32", "advapi32", "user32", "bcrypt", "crypt32",
    "ucrtbase", "vcruntime", "msvcp", "msvcrt", "ole32", "oleaut32",
    "shell32", "ws2_32", "normaliz", "wldap32", "dnsapi", "secur32",
    "iphlpapi", "winmm", "gdi32", "ntdll", "bcryptprimitives", "shlwapi",
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def pe_imports(path: str) -> list[str]:
    """The DLL names in `path`'s PE import directory.

    Hand-rolled rather than a dependency: reading one table is forty lines,
    and a check that verifies the bundle should not need something outside
    the bundle to do it.
    """
    with open(path, "rb") as fh:
        b = fh.read()

    pe = struct.unpack_from("<I", b, 0x3C)[0]
    if b[pe:pe + 4] != b"PE\0\0":
        raise ValueError(f"{os.path.basename(path)} is not a PE image")
    nsec, = struct.unpack_from("<H", b, pe + 6)
    opt_size, = struct.unpack_from("<H", b, pe + 20)
    opt = pe + 24
    magic, = struct.unpack_from("<H", b, opt)
    # 0x20b is PE32+, whose optional header puts the data directories 16 bytes
    # further along than PE32's.
    directories = opt + (112 if magic == 0x20B else 96)
    imports_rva, _size = struct.unpack_from("<II", b, directories + 8)
    if not imports_rva:
        return []

    sections = []
    for i in range(nsec):
        o = opt + opt_size + i * 40
        va, raw_size, raw_ptr = struct.unpack_from("<III", b, o + 12)
        sections.append((va, raw_size, raw_ptr))

    def offset(rva):
        for va, raw_size, raw_ptr in sections:
            if va <= rva < va + max(raw_size, 1):
                return raw_ptr + (rva - va)
        return None

    names, i = [], 0
    while True:
        entry = offset(imports_rva) + i * 20
        _ilt, _stamp, _chain, name_rva, _iat = struct.unpack_from("<IIIII", b, entry)
        if name_rva == 0:
            break
        o = offset(name_rva)
        names.append(b[o:b.index(b"\0", o)].decode("ascii"))
        i += 1
    return names


def third_party(names) -> list[str]:
    return [n for n in names
            if not any(n.lower().startswith(p) for p in SYSTEM_PREFIXES)]


def main():
    c = Checks("check_native")

    # [pins] reads the manifest, not the bundle, so it runs even on a clone
    # that has never fetched. It is also the assert most likely to catch a
    # careless re-pin.
    for name, (rel, sha256, dlls) in sorted(native.PACKAGES.items()):
        c.check(bool(SHA256_RE.match(sha256)),
                f"[pins] {name} carries a 64-hex sha256 ({sha256[:12]}...)")
        c.check(rel.startswith("win-64/") and rel.endswith(".conda"),
                f"[pins] {name} names an exact win-64 artifact ({rel.split('/')[-1]})")
        c.check(all(d.endswith(".dll") for d in dlls) and bool(dlls),
                f"[pins] {name} declares the DLLs it contributes ({', '.join(dlls)})")

    c.check(len(set(native.REQUIRED_DLLS)) == len(native.REQUIRED_DLLS),
            f"[pins] no DLL is claimed by two packages "
            f"({len(native.REQUIRED_DLLS)} in the closure)")

    if not native.bundled():
        missing = [d for d in native.REQUIRED_DLLS
                   if not os.path.isfile(os.path.join(native.LIBARCHIVE_DIR, d))]
        if c.failures:
            return c.finish()
        return skip(
            f"build/libarchive is not installed ({len(missing)} of "
            f"{len(native.REQUIRED_DLLS)} DLLs absent: {', '.join(missing[:3])}"
            f"{'...' if len(missing) > 3 else ''}) -- run "
            f"`uv run --project sidecar python -m sidecar.native`"
        )

    present = sorted(f for f in os.listdir(native.LIBARCHIVE_DIR)
                     if f.lower().endswith(".dll"))
    c.check(present == sorted(native.REQUIRED_DLLS),
            f"[closure] the bundle holds exactly the declared closure, nothing "
            f"extra ({len(present)} DLLs)")

    have = {f.lower() for f in present}
    unresolved = {}
    for dll in present:
        for dep in third_party(pe_imports(os.path.join(native.LIBARCHIVE_DIR, dll))):
            if dep.lower() not in have:
                unresolved.setdefault(dep, []).append(dll)

    c.check(not unresolved,
            f"[closure] every non-system import resolves inside the bundle "
            f"({'; '.join(f'{d} <- {", ".join(u)}' for d, u in unresolved.items()) or 'none missing'})")

    # The control: if the parser silently returned nothing, the assert above
    # would pass over an empty set and prove nothing at all.
    archive_imports = pe_imports(os.path.join(native.LIBARCHIVE_DIR, "archive.dll"))
    c.check(len(archive_imports) > 5,
            f"[closure] control: archive.dll's import table really was read "
            f"({len(archive_imports)} entries)")
    c.check(any(d.lower().startswith("libxml2") for d in archive_imports),
            "[closure] control: and it names libxml2, so the names are real")

    everything = {d.lower()
                  for dll in present
                  for d in pe_imports(os.path.join(native.LIBARCHIVE_DIR, dll))}

    icu = sorted(d for d in everything if d.startswith("icu"))
    c.check(not icu,
            f"[no-icu] nothing in the bundle imports ICU (found {icu or 'none'}) "
            f"-- libxml2-16 must stay the h692994f variant")

    ssl = sorted(d for d in everything
                 if d.startswith("libcrypto") or d.startswith("libssl"))
    c.check(not ssl,
            f"[no-openssl] nothing imports OpenSSL (found {ssl or 'none'}); "
            f"conda declares it, the binary uses Windows CNG")
    c.check("bcrypt.dll" in everything,
            "[no-openssl] and bcrypt.dll IS imported -- the CNG path is real, "
            "not merely an absence")

    # Idempotence: a complete bundle must not reach the network. This is what
    # makes ensure_libarchive() safe to call on every start.
    c.check(native.ensure_libarchive() ==
            os.path.join(native.LIBARCHIVE_DIR, "archive.dll"),
            "[idempotent] ensure_libarchive returns the bundled path when the "
            "closure is already complete")

    # And the reader actually works through it, resolved the way the product
    # resolves it -- no MT_LIBARCHIVE, no PATH.
    from sidecar.containers import archive

    resolved = archive.libarchive_path()
    c.check(resolved and os.path.dirname(resolved) == native.LIBARCHIVE_DIR,
            f"[resolve] libarchive_path() finds the bundle ({resolved})")

    cbr = os.path.join(ROOT, "fixtures", "archives", "benign.cbr")
    if os.path.isfile(cbr):
        pages = [name for _o, name, _im in archive.pages(cbr)]
        c.check(len(pages) == 3,
                f"[resolve] and the bundle reads a real RAR through it ({pages})")

    return c.finish()


run(main)
