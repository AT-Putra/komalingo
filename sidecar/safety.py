r"""AC-11: the ingest budget. Every untrusted archive is read through this.

**Streamed bytes, not header fields.** A zip central directory is written by
whoever made the archive, so `ZipInfo.file_size` is a claim, not a measurement.
A bomb that declares 1 byte and expands to 4GB passes any check that reads the
header and fails every check that counts what came out of the stream. So the
expansion side of every rule here is fed by `account()`, which the reader calls
with the length of each chunk it actually decoded, and nothing in this module
reads `file_size` at all.

The COMPRESSION side of the ratio is the one number that cannot be measured
without owning the decompressor: `ZipFile.open` hands back plaintext and never
says how many compressed bytes it consumed. It is read from the header, and the
direction of the error matters: a header that UNDERSTATES the compressed size
makes the ratio look worse and can only over-reject; a header that OVERSTATES
it makes a bomb look tame. That second case is exactly what `max_file_bytes`
and `max_total_bytes` are for -- they are absolute, they are fed by streamed
bytes alone, and no header field can talk its way past them. The ratio rule
catches the small-and-obvious bomb early, before 256MB of zeros has been
decoded; the byte caps are what actually bound the damage.

**The per-member ratio rule is zip-only, by construction.** Only the zip
central directory carries a per-member COMPRESSED size, which is the
denominator. tar has no compression at the member level at all -- it is a
concatenation, compressed or not as a whole -- and 7z compresses members in
solid blocks, so py7zr reports a compressed size for the first member of a
block and `None` for the rest. Both therefore pass `declared_compressed=0`,
which disables the rule explicitly rather than accidentally: passing the
UNCOMPRESSED size instead would make every ratio 1:1 and leave a rule that
looks live in the code and can never fire. What bounds those two formats is
the pair of absolute byte caps, fed by streamed bytes, plus -- for a whole-file
compressed tar, where the expansion is a property of the container rather than
of any member -- the ARCHIVE-level ratio in `account_raw`.

**Rejection is per-ARCHIVE, not per-member.** A member that trips any rule
raises, the reader stops, and the item is skipped with the reason. Skipping the
bad member and continuing would mean a traversal attempt is a warning in a log
nobody reads, and it would let a 5001-member archive through by ignoring member
5001 rather than refusing the archive that carries it.
"""

from __future__ import annotations

import os
import posixpath
from dataclasses import dataclass

# Machine-readable reasons. One per rule, and the check asserts it observed
# every one of them -- a rule whose reason string never appears in a test run
# is a rule nothing exercises.
MEMBER_COUNT = "member-count"
ABSOLUTE_PATH = "absolute-path"
DRIVE_LETTER = "drive-letter"
PARENT_TRAVERSAL = "parent-traversal"
COMMONPATH_ESCAPE = "commonpath-escape"
LINK_ENTRY = "link-entry"
FILE_SIZE_CAP = "file-size-cap"
TOTAL_SIZE_CAP = "total-size-cap"
RATIO_CAP = "ratio-cap"

REASONS = frozenset({
    MEMBER_COUNT, ABSOLUTE_PATH, DRIVE_LETTER, PARENT_TRAVERSAL,
    COMMONPATH_ESCAPE, LINK_ENTRY, FILE_SIZE_CAP, TOTAL_SIZE_CAP, RATIO_CAP,
})

# COMMONPATH_ESCAPE is a BACKSTOP, and no archive can reach it while the three
# named path rules are in place: every member name whose destination escapes
# also starts with a separator, carries a drive letter, or contains a '..'
# component, and one of those fires first with the more useful reason. It is
# kept because the named rules encode the shapes we know and this one encodes
# the property -- if a future normalisation quirk lets a shape through, this
# catches it. It is separated out here so `check_archives` can require every
# OTHER reason to be observed on a real fixture, and assert this one through
# `Budget.escapes` directly, rather than quietly accepting a rule no test ever
# reaches.
BACKSTOP_REASONS = frozenset({COMMONPATH_ESCAPE})

# The spec names the member count and the ratio; the two byte caps it leaves to
# us. 8GB across one archive is a 200-page volume at 40MB a page, which is
# larger than any real one and smaller than a disk-filling attack.
MAX_MEMBERS = 5000
MAX_RATIO = 200
# 128MB, not 256. A reader buffers one member whole before decoding it, so the
# per-file cap is a floor under peak RSS -- and 256MB left one legal member
# peaking past AC-12's own 400MB budget before the decoded raster was even
# allocated. Two numbers that contradict each other are not two rules, they are
# one bug waiting for a big page. 128MB is still twice the largest single scan
# the comment below cites.
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024

# Below this, the ratio rule does not fire. A 40-byte ComicInfo.xml that
# deflates to 30 bytes is a ratio of 1.3; a 12-byte member that deflates to 8 is
# 1.5. But a member of a few hundred bytes that happens to compress well --
# a run of whitespace in an XML file -- can cross 200:1 while being incapable of
# doing any harm at all. The floor is what keeps the rule aimed at bombs rather
# than at well-compressed small text.
RATIO_FLOOR_BYTES = 64 * 1024


class UnsafeArchive(Exception):
    """One rejected archive, carrying which rule refused it and where.

    `reason` is from REASONS and is what the UI and the checks compare on;
    `detail` is for a human reading a log and is never asserted against.
    """

    def __init__(self, reason: str, member: str = "", detail: str = ""):
        self.reason = reason
        self.member = member
        self.detail = detail
        super().__init__(
            f"{reason}: {member}" + (f" ({detail})" if detail else "")
        )


@dataclass(frozen=True)
class Member:
    """One archive entry, in the terms the rules are written in.

    Every reader builds this from its own format's entry type, so the rules are
    written once rather than once per container. `declared_compressed` is the
    only field sourced from archive metadata, and the docstring above says why
    it is allowed to be and what bounds the damage when it lies.
    """

    name: str
    is_dir: bool = False
    is_link: bool = False
    declared_compressed: int = 0


def _normalized(name: str) -> str:
    """Member name with separators unified, for rule evaluation only.

    Backslash is a separator here even though zip says it is not: a member
    literally named `..\\..\\startup.png` is one path component to `posixpath`
    and three to every Windows API that would later create it. Evaluating the
    rules against the Windows reading is the conservative direction, and the
    name is never rewritten -- only the copy the rules look at.
    """
    return name.replace("\\", "/")


class Budget:
    """Per-archive accounting. One instance per item; never shared between two.

    Construct with smaller caps to exercise a rule without a fixture the size
    of the rule -- `Budget(max_file_bytes=1024)` trips FILE_SIZE_CAP on a 2KB
    member, which is how the byte caps are tested without generating 256MB of
    zeros and committing the runtime to it on every CI run.
    """

    def __init__(self, dest: str | os.PathLike = ".", *,
                 max_members: int = MAX_MEMBERS,
                 max_ratio: int = MAX_RATIO,
                 max_file_bytes: int = MAX_FILE_BYTES,
                 max_total_bytes: int = MAX_TOTAL_BYTES,
                 enforce: bool = True):
        # The destination is where members WOULD land. Nothing is written
        # during ingest -- the pages are streamed into memory one at a time --
        # but the escape rule is only meaningful relative to a root, and taking
        # the real destination means the rule is evaluated against the path the
        # writer would later build rather than against a placeholder.
        self.dest = os.path.normpath(os.path.abspath(os.fspath(dest)))
        self.max_members = max_members
        self.max_ratio = max_ratio
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes
        # The documented red-check hook. check_archives flips it to prove the
        # hostile fixtures are rejected BY THESE RULES and not by some accident
        # of the reader -- a safety assert that cannot be made to fail is not
        # evidence. Nothing in the sidecar ever sets it.
        self.enforce = enforce

        self.members = 0
        self.total_bytes = 0
        self._stream_compressed = 0
        self._stream_bytes = 0
        self._current = ""
        self._current_bytes = 0
        self._current_compressed = 0

    def _refuse(self, reason: str, member: str, detail: str = "") -> None:
        if self.enforce:
            raise UnsafeArchive(reason, member, detail)

    def check_member(self, member: Member) -> None:
        """Admit one entry, or raise. Call before streaming a single byte."""
        name = _normalized(member.name)

        # Counted before anything else, and directories count. An archive is
        # 5001 entries or it is not; excluding the ones that happen not to be
        # pages would let a caller past the cap by padding with directories.
        self.members += 1
        if self.members > self.max_members:
            self._refuse(MEMBER_COUNT, name,
                         f"{self.members} > {self.max_members}")

        if member.is_link:
            # Symlinks, hardlinks, and anything that is not a regular file or a
            # directory. A link member is a write outside the destination that
            # needs no traversal component at all, so it is refused by TYPE
            # rather than by where its target points.
            self._refuse(LINK_ENTRY, name, "link or special entry")

        if name.startswith("/"):
            self._refuse(ABSOLUTE_PATH, name, "leading separator")
        if len(name) > 1 and name[1] == ":":
            # `C:/x.png` and the sneakier `C:x.png`, which is drive-relative and
            # resolves against the process's per-drive working directory -- a
            # path that is neither absolute nor under the destination.
            self._refuse(DRIVE_LETTER, name, f"drive {name[0]!r}")
        if any(part == ".." for part in name.split("/")):
            self._refuse(PARENT_TRAVERSAL, name, "'..' component")

        # The backstop, and the only rule stated in terms of the real filesystem
        # path. The three rules above name the shapes we know; this one catches
        # the shapes we do not, including anything a future normalisation quirk
        # lets through the string checks.
        if self.escapes(name):
            self._refuse(COMMONPATH_ESCAPE, name, self._resolve(name))

    def begin(self, member: Member) -> None:
        """Start accounting for ONE member's stream. Resets the per-file counters.

        Separate from `check_member` because admission and streaming happen in
        different passes: every member is admitted first (the member-count rule
        is about the archive, and a traversal member 5000 entries in must be
        refused before the first page is decoded), and only the pages are then
        streamed, in a different order. Folding the reset into `check_member`
        left `_current_bytes` accumulating across the whole archive and
        `_current_compressed` pinned to whichever member happened to be
        admitted last -- which made the ratio rule read a 200-page archive's
        total against one page's compressed size and refuse a legitimate
        volume at page 200. Measured, not hypothetical: it is what the first
        run of `check_archives` did.
        """
        self._current = _normalized(member.name)
        self._current_bytes = 0
        self._current_compressed = max(0, int(member.declared_compressed))

    def begin_stream(self, compressed_size: int) -> None:
        """Start accounting a whole-container decompression of `compressed_size`.

        For a container that cannot be LISTED without being decompressed -- a
        `.tar.gz`, `.tar.bz2`, `.tar.xz` -- the expansion is a property of the
        container, not of any member, and it happens before a single member
        name is known. Nothing per-member can bound it, which is exactly how a
        12MB `.cbt` decompressed to 12GB with the budget counting zero bytes.
        `account_raw` is what the reader feeds while the stream is being
        consumed, and this is the denominator it divides by.
        """
        self._stream_compressed = max(0, int(compressed_size))
        self._stream_bytes = 0

    def account_raw(self, nbytes: int) -> None:
        """Count bytes read out of a whole-container decompressor.

        Two rules, and deliberately not the third: the running total (so the
        absolute cap bounds a listing pass as well as a page read) and the
        archive-level ratio (so a 200:1 container is refused at 200:1 rather
        than at the 8GB cap, which on a 12MB input is 600 times too late).
        The per-file cap is NOT applied here -- these bytes are the container's,
        not any member's, and charging them to whichever member happens to be
        current would refuse legitimate archives for the size of their
        neighbours.
        """
        self._stream_bytes += nbytes
        self.total_bytes += nbytes

        if self.total_bytes > self.max_total_bytes:
            self._refuse(TOTAL_SIZE_CAP, self._current or "(container stream)",
                         f"{self.total_bytes} > {self.max_total_bytes}")

        if (self._stream_compressed > 0
                and self._stream_bytes >= RATIO_FLOOR_BYTES):
            ratio = self._stream_bytes / self._stream_compressed
            if ratio > self.max_ratio:
                self._refuse(RATIO_CAP, self._current or "(container stream)",
                             f"container {ratio:.0f}:1 > {self.max_ratio}:1")

    def account(self, nbytes: int) -> None:
        """Count bytes that came OUT of the decompressor. Raise if over.

        Called per chunk, not per member, so a bomb is refused partway through
        its expansion rather than after it has been held in memory whole.
        """
        self._current_bytes += nbytes
        self.total_bytes += nbytes

        if self._current_bytes > self.max_file_bytes:
            self._refuse(FILE_SIZE_CAP, self._current,
                         f"{self._current_bytes} > {self.max_file_bytes}")
        if self.total_bytes > self.max_total_bytes:
            self._refuse(TOTAL_SIZE_CAP, self._current,
                         f"{self.total_bytes} > {self.max_total_bytes}")

        if (self._current_compressed > 0
                and self._current_bytes >= RATIO_FLOOR_BYTES):
            ratio = self._current_bytes / self._current_compressed
            if ratio > self.max_ratio:
                self._refuse(RATIO_CAP, self._current,
                             f"{ratio:.0f}:1 > {self.max_ratio}:1")

    def _resolve(self, name: str) -> str:
        """Where `name` would land under the destination, normalised.

        `..` is NOT stripped here: this is the function the escape rule
        evaluates, and a resolver that sanitised its input first could never
        report an escape.
        """
        parts = [p for p in _normalized(name).split("/") if p not in ("", ".")]
        if _normalized(name).startswith("/") or (len(name) > 1 and name[1] == ":"):
            # An absolute member is not joined to the destination at all -- it
            # IS the path, which is the whole reason it is an escape.
            return os.path.normpath(_normalized(name))
        return os.path.normpath(os.path.join(self.dest, *parts))

    def escapes(self, name: str) -> bool:
        """Whether `name`'s destination lands outside the budget's root.

        Public because it is the only way to exercise the backstop: the three
        named path rules fire first on every input that could reach it, so a
        test that went through `check_member` would always see the other
        reason. See BACKSTOP_REASONS.
        """
        resolved = self._resolve(name)
        try:
            return os.path.commonpath([self.dest, resolved]) != self.dest
        except ValueError:
            # Different drives -- commonpath raises rather than returning
            # something false. A member on another volume is an escape.
            return True


def is_comicinfo(name: str) -> bool:
    """ComicInfo.xml, wherever it sits and however it is cased.

    Case-insensitively, because the readers that write these archives are not
    consistent about it, and on the basename because a few writers put it in a
    subdirectory alongside the pages.
    """
    return posixpath.basename(_normalized(name)).lower() == "comicinfo.xml"
