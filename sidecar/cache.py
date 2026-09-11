r"""The page cache: content-keyed, job-independent, and on disk.

Phases 6, 7, 9 and two ACs depend on every clause here, so the contract is
stated in full rather than implied by the code.

**The key is the decoded pixels, not the file bytes.** `page_hash` hashes
`img.tobytes()` plus mode and size. A re-saved JPEG and the original are
different files and the same page; the same page as a PDF XObject and as a CBZ
member are different bytes entirely. File-byte hashing misses both cases -- and
they are the cases the cache exists for, not exotic ones.

**The path is keyed on the hash and on nothing about the run.** This is the
regression the architect caught in iteration 1 of the build order, and it is
worth naming here because the layout looks arbitrary until you see it: an
earlier draft put the cache at ``cache\{job_id}\``, and a re-run is a NEW
job_id. AC-13's "a re-run skips completed pages" and the locked decision that
"a second pass re-translates and re-renders without re-detecting" would both
have looked a page hash up in a directory empty by construction -- a cache cold
exactly when it is needed, behind a gate that passes because the cancel check
re-runs inside one process. Choosing a decoded-pixel hash and then keying the
directory on the run throws away the entire reason for choosing it.

``job_id`` is retained for exactly two things:

  * **placement** -- ``(item_id, ordinal) -> page_hash`` in
    ``cache\jobs\{job_id}\placement.json``. Two identical pages in one archive
    (blank pages, repeated chapter dividers) share a hash, and sharing the
    *translation* is correct and wanted; spot-fixing one and silently editing
    both is a bug that would surface in Phase 6 looking like an archive bug.
    The hash says what the page IS, the placement says where it SITS, and only
    the second is per-job.
  * **delete scope** -- see ``delete_job``.

**References are a list of ids, not a count.** Cross-job sharing is the normal
case, and a count has no repair story: a job killed mid-run leaks a reference,
and the leak is permanent because the disk cap also skips pages referenced by a
running job -- so the cache fills with pages nothing can evict. A list of ids is
auditable, because a stale reference is identifiable precisely by being named:
``prune_refs`` runs at sidecar startup and drops every id that names no
directory under ``cache\jobs\``.

Concurrent updates are read-modify-``os.replace`` like every other write here,
**taken under ``_LOCK``**. The lock is not decoration and the first draft was
wrong to leave it out. Two jobs run in one sidecar -- the routes are sync, so
FastAPI runs them in its threadpool -- and an interleaved read-modify-write
loses one job's id. That is not the harmless "costs a re-detect" the first
draft claimed: a page whose reference was lost is no longer pinned by its own
running job, so the disk cap may evict it *while that job is still reading it*,
and the job then finds no raster where ``has_page`` had just said there was
one. One lock removes the whole class in-process. Across processes the writes
are still last-writer-wins, which is why ``run_item`` also treats a vanished
raster as a cache miss rather than as an error.

**``fit_compromised`` and ``fit_failed`` are stored for REPORTING only.** They
are recomputed from the geometry on every render -- see ``typeset.typeset_page``,
where they are output-only fields -- so a user shortening an edit clears the
flag by re-rendering rather than by anyone remembering to clear it. Nothing in
this module ever feeds a stored flag back in as input.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
from collections import OrderedDict

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from . import atomic

# -- layout ----------------------------------------------------------------

PAGES = "pages"
JOBS = "jobs"
REGIONS = "regions.json"
RASTER = "inpainted.png"
REFS = "refs.json"
PLACEMENT = "placement.json"
RUNNING = "running.json"

# The memory tier: current page + one ahead + one behind, for editor
# responsiveness. Everything else lives only on disk.
MAX_RASTERS = 3
MAX_TIER_BYTES = 150 * 1024 * 1024

# Disk growth. Env-overridable so check_spotfix can drive the eviction path
# with a few MB instead of four gigabytes of fixtures.
CAP_BYTES = 4 * 1024 * 1024 * 1024
TARGET_BYTES = 3 * 1024 * 1024 * 1024

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")

# Serialises every read-modify-write of refs.json and placement.json. Two jobs
# in one sidecar is the ordinary case, not the exotic one -- see the module
# docstring for what a lost reference actually costs.
_LOCK = threading.RLock()


def root() -> str:
    """The cache root. MT_CACHE_DIR wins, so tests never touch the real one."""
    override = os.environ.get("MT_CACHE_DIR")
    if override:
        return os.path.abspath(override)
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
    return os.path.join(base, "MangaTranslator", "cache")


def _cap_bytes() -> int:
    return int(os.environ.get("MT_CACHE_CAP_BYTES") or CAP_BYTES)


def _target_bytes() -> int:
    return int(os.environ.get("MT_CACHE_TARGET_BYTES") or TARGET_BYTES)


def pages_root() -> str:
    return os.path.join(root(), PAGES)


def jobs_root() -> str:
    return os.path.join(root(), JOBS)


def page_dir(page_hash: str) -> str:
    return os.path.join(pages_root(), page_hash)


def _job_key(job_id) -> str:
    """The one form a job id takes inside this module: a safe path segment.

    job_id arrives from the UI, and it is used as a DIRECTORY NAME. The review
    reproduced `job_dir("../../../../escaped-job")` writing running.json into
    %LOCALAPPDATA% itself, and the moment a delete route exists that is an
    rmtree primitive. So every public function that takes a job id passes it
    through here first, and refs.json, placement paths and the running set all
    hold the SAME form -- normalising only in job_dir would leave refs.json
    holding raw ids that name no directory, and the startup prune would then
    drop every one of them as stale.

    An id that is already safe is returned unchanged, so the ordinary case
    stays readable. One that needed altering carries a digest suffix, because
    "../x" and "..\\x" must not collapse onto one directory.
    """
    raw = str(job_id)
    safe = _UNSAFE.sub("-", raw).strip("-.")
    if safe == raw and raw:
        return raw
    return f"{safe[:40] or 'job'}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:8]}"


def job_dir(job_id: str) -> str:
    return os.path.join(jobs_root(), _job_key(job_id))


# -- the key ---------------------------------------------------------------


def page_hash(img: Image.Image) -> str:
    """SHA-256 of the DECODED pixels, plus mode and size.

    Mode and size are in the digest rather than assumed from the buffer: an
    L-mode 100x200 and an L-mode 200x100 page have the same byte count, and
    ``tobytes`` alone cannot tell them apart. They go in as a delimited prefix
    so no combination of dimensions can spell another one's prefix.
    """
    h = hashlib.sha256()
    h.update(f"{img.mode}|{img.size[0]}x{img.size[1]}|".encode("ascii"))
    h.update(img.tobytes())
    return h.hexdigest()


def model_slug(model: str) -> str:
    """A filesystem-safe name for a model id that two ids cannot share.

    The readable part is truncated and lossy on purpose -- ``gpt-4o`` and
    ``gpt/4o`` both sanitise to ``gpt-4o`` -- so the digest is not decoration.
    It is what makes the translation files of two different models two
    different files, which is the whole basis of the edit-scoping rule below.
    """
    safe = _UNSAFE.sub("-", model or "none").strip("-")[:40] or "none"
    return f"{safe}-{hashlib.sha256((model or '').encode('utf-8')).hexdigest()[:8]}"


def translation_name(lang: str, model: str) -> str:
    return f"tr_{_UNSAFE.sub('-', lang or 'none')}_{model_slug(model)}.json"


# -- small shared IO -------------------------------------------------------


def _read_json(path, default=None):
    try:
        with open(atomic.long_path(path), encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, NotADirectoryError):
        return default
    except ValueError:
        # A truncated JSON file is a cache miss, not a crash. Every writer here
        # is atomic, so this only happens to a file something else corrupted --
        # and re-deriving the page is always available.
        return default


def _write_json(path, obj) -> None:
    with atomic.atomic_write(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, sort_keys=True)


def touch(page_hash_: str) -> None:
    """Mark a page directory as used NOW.

    Called on every read, not only on write, and that is the whole point.
    mtime is write time: without the touch, a page reused by fifty jobs and
    never rewritten evicts before a page written once and never opened again --
    the cap evicting precisely the hot set that content-keying exists to keep.
    """
    d = atomic.long_path(page_dir(page_hash_))
    try:
        os.utime(d, None)
    except OSError:
        pass  # the page is gone, or the volume has no utime; a miss, not an error


# -- the in-memory raster tier --------------------------------------------


class _Tier:
    """LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds.

    It counts against AC-12's 400MB process budget rather than sitting outside
    it, which is why ``tier_bytes`` is public: ``check_archives.py`` (Phase 6)
    warms the tier to its cap before sampling peak RSS. An ingest measured with
    the tier cold never observes the residency it has to coexist with, and a
    400MB gate that passes only when the editor is idle is not a gate.

    Evicting here deletes nothing on disk. The tier is a read accelerator; the
    disk is the cache.
    """

    def __init__(self):
        self._items: OrderedDict[str, Image.Image] = OrderedDict()
        self._bytes: dict[str, int] = {}

    def get(self, key):
        img = self._items.get(key)
        if img is not None:
            self._items.move_to_end(key)
        return img

    def put(self, key, img: Image.Image) -> None:
        # Arithmetic, not len(img.tobytes()): tobytes materialises a second
        # full copy of the raster on every insert, and Phase 6's peak-RSS
        # sampler would see that spike as residency this tier does not have.
        n = img.size[0] * img.size[1] * len(img.getbands())
        self._items.pop(key, None)
        self._bytes.pop(key, None)
        if n > MAX_TIER_BYTES:
            # Served from disk every time rather than held. The first draft
            # kept one oversized raster resident as "still servable", which is
            # true, and left tier_bytes above the bound §E has Phase 6 count
            # inside AC-12's 400MB -- a bound with an exception is not a bound.
            return
        self._items[key] = img
        self._bytes[key] = n
        self._evict()

    def _evict(self) -> None:
        while self._items and (
            len(self._items) > MAX_RASTERS or self.total_bytes() > MAX_TIER_BYTES
        ):
            k, _ = self._items.popitem(last=False)
            self._bytes.pop(k, None)

    def total_bytes(self) -> int:
        return sum(self._bytes.values())

    def clear(self) -> None:
        self._items.clear()
        self._bytes.clear()


_tier = _Tier()


def tier_bytes() -> int:
    """Resident decoded bytes in the memory tier. Phase 6's RSS gate reads this."""
    return _tier.total_bytes()


def clear_tier() -> None:
    _tier.clear()


# -- running jobs ----------------------------------------------------------

# Two records of the same fact, and both are needed.
#
# The SET is what eviction consults: "running" means running in this sidecar,
# right now, and only this process can know that.
#
# The MARKER FILE is what survives the process. A job that finishes -- or fails,
# since the clear is in a `finally` -- removes its own marker. A job whose
# process was killed cannot, so at the next startup its marker is still there
# with nothing running. That is the only durable evidence distinguishing "this
# job died mid-run" from "this job completed", and without it `prune_refs` has
# nothing to repair: every id a killed job left behind names a job directory
# that very much exists, so a prune that only dropped unknown ids would pass
# over the one leak it was written for.
_running: set[str] = set()
_warned: set[str] = set()


def mark_running(job_id: str) -> None:
    job_id = _job_key(job_id)
    _running.add(job_id)
    _write_json(os.path.join(job_dir(job_id), RUNNING), {"pid": os.getpid()})


def clear_running(job_id: str) -> None:
    job_id = _job_key(job_id)
    _running.discard(job_id)
    _warned.discard(job_id)
    try:
        os.remove(atomic.long_path(os.path.join(job_dir(job_id), RUNNING)))
    except OSError:
        pass  # never written, or the job directory is already gone


# -- references ------------------------------------------------------------


def _pid_alive(pid) -> bool:
    """Is the process that wrote a running marker still running?

    psutil is already a dependency of the checks; here it is optional on
    purpose, and its ABSENCE is read as "alive". Deleting a live job's tree
    because a library was missing is the worse failure -- the leak this prune
    repairs is bounded, a destroyed job is not.
    """
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        import psutil
    except ImportError:
        return True
    try:
        return psutil.pid_exists(pid)
    except Exception:  # noqa: BLE001 -- any doubt reads as alive
        return True


def read_refs(page_hash_: str) -> list[str]:
    refs = _read_json(os.path.join(page_dir(page_hash_), REFS), [])
    return [str(r) for r in refs] if isinstance(refs, list) else []


def add_ref(page_hash_: str, job_id: str) -> list[str]:
    """Read-modify-``os.replace``, under ``_LOCK``. See the module docstring."""
    job_id = _job_key(job_id)
    with _LOCK:
        refs = read_refs(page_hash_)
        if job_id not in refs:
            refs.append(job_id)
            _write_json(os.path.join(page_dir(page_hash_), REFS), sorted(refs))
        return refs


def drop_ref(page_hash_: str, job_id: str) -> list[str]:
    job_id = _job_key(job_id)
    with _LOCK:
        refs = [r for r in read_refs(page_hash_) if r != job_id]
        _write_json(os.path.join(page_dir(page_hash_), REFS), sorted(refs))
        return refs


def prune_refs() -> int:
    """Repair leaked references. Runs at sidecar startup. Returns the count removed.

    This is the repair a reference COUNT cannot have. A job killed mid-run
    leaks its references; the leak pins those pages against the disk cap
    forever, because the cap also skips pages a running job holds; and with a
    count there is no way to tell a leak from a live holder. Named ids make the
    leak identifiable, in two passes:

      1. **A job directory carrying a running marker whose process is gone is a
         dead job.** Its placement is incomplete and its output was never
         delivered, so its directory and its references go. Its PAGES stay.
         The first draft called ``delete_job`` here, which removes any page
         reaching zero references -- and the review measured what that means:
         a job that was the only holder of its pages had every one of them
         deleted at the next launch. That is Phase 9's scenario exactly, and
         those pages are exactly what AC-13's "a re-run skips completed pages"
         exists to reuse. The plan says a dead job's pages become *evictable
         again*: unpinned, left to the cap, found by the next run through their
         content hash. Deleting them is not repair, it is the loss the cache
         exists to prevent.
      2. **A reference naming no job directory at all is stale.** Whatever
         removed the job did not get to the references.

    "Whose process is gone" is checked against the pid the marker records,
    not assumed from this process's own running set. Two sidecar instances --
    the packaged exe under check_package, a second one on another port -- each
    run this at startup, and without the pid check the second would find the
    first's live marker absent from ITS running set and delete a job that is
    still writing. The marker carries the pid for precisely this and the first
    draft never read it.

    Returns the number of references removed, so a check can assert the repair
    HAPPENED rather than assert that it is possible.
    """
    jroot = atomic.long_path(jobs_root())
    proot = atomic.long_path(pages_root())
    removed = 0

    for job_id in os.listdir(jroot) if os.path.isdir(jroot) else []:
        if job_id in _running:
            continue
        marker = _read_json(os.path.join(jroot, job_id, RUNNING))
        if marker is None:
            continue
        if _pid_alive(marker.get("pid")):
            continue  # another instance's live job; not ours to touch
        for h in placed_hashes(job_id):
            if job_id in read_refs(h):
                drop_ref(h, job_id)
                removed += 1
        shutil.rmtree(os.path.join(jroot, job_id), ignore_errors=True)

    live = set(os.listdir(jroot)) if os.path.isdir(jroot) else set()
    if not os.path.isdir(proot):
        return removed
    for h in os.listdir(proot):
        refs = read_refs(h)
        kept = [r for r in refs if r in live]
        if len(kept) != len(refs):
            removed += len(refs) - len(kept)
            _write_json(os.path.join(page_dir(h), REFS), sorted(kept))
    return removed


# -- placement -------------------------------------------------------------


def _placement_key(item_id, ordinal) -> str:
    # JSON object keys are strings, so the tuple is flattened here rather than
    # at four call sites. "\x1f" is the unit separator: it cannot occur in a
    # path or an ordinal, so no item_id can spell another item's key.
    return f"{item_id}\x1f{int(ordinal)}"


def read_placement(job_id: str) -> dict:
    return _read_json(os.path.join(job_dir(job_id), PLACEMENT), {}) or {}


def put_placement(job_id: str, item_id, ordinal: int, page_hash_: str,
                  member: str | None = None) -> None:
    """Record that this job's (item, ordinal) renders this page, under this name.

    Separately per ordinal, so two byte-identical pages in one archive share a
    page directory -- sharing the translation, which is wanted -- and still hold
    two independent positions in the delivered output.

    The MEMBER NAME lives here and not in the page record, and that distinction
    is load-bearing rather than tidy. The page record is keyed on content, so
    two identical pages share ONE of them, and whichever ordinal was ingested
    last would own the name. Re-rendering ordinal 3 then wrote its output over
    ordinal 7's file: the page hash says what the page IS, and only the
    placement can say what it is CALLED at this position. Found by the
    placement assert in check_spotfix, which is the assert that exists for
    exactly this confusion.
    """
    with _LOCK:
        placement = read_placement(job_id)
        placement[_placement_key(item_id, ordinal)] = {
            "page_hash": page_hash_,
            "member": member,
        }
        _write_json(os.path.join(job_dir(job_id), PLACEMENT), placement)
        add_ref(page_hash_, job_id)


def get_placement(job_id: str, item_id, ordinal: int):
    """The placement entry for one position, or None. See put_placement."""
    return read_placement(job_id).get(_placement_key(item_id, ordinal))


def placed_hashes(job_id: str) -> set[str]:
    """Every page hash this job placed. Delete scope reads this."""
    return {e["page_hash"] for e in read_placement(job_id).values()}


def delete_job(job_id: str) -> list[str]:
    """Remove a job's placement and its references. Returns the pages removed.

    A page reaching zero references is removed. A page another job still holds
    survives with that job's id intact -- which is the cross-job sharing the
    content key exists to provide, and the thing an over-eager "delete the job,
    delete its pages" would silently undo.
    """
    job_id = _job_key(job_id)
    hashes = placed_hashes(job_id)
    shutil.rmtree(atomic.long_path(job_dir(job_id)), ignore_errors=True)
    removed = []
    for h in hashes:
        if not drop_ref(h, job_id):
            shutil.rmtree(atomic.long_path(page_dir(h)), ignore_errors=True)
            removed.append(h)
    return removed


# -- page content ----------------------------------------------------------


def write_regions(page_hash_: str, record: dict) -> str:
    path = os.path.join(page_dir(page_hash_), REGIONS)
    _write_json(path, record)
    return atomic.long_path(path)


def read_regions(page_hash_: str):
    """The cached record, or None. Touches the directory -- see ``touch``."""
    record = _read_json(os.path.join(page_dir(page_hash_), REGIONS))
    if record is not None:
        touch(page_hash_)
    return record


def write_raster(page_hash_: str, img: Image.Image, src: Image.Image | None = None) -> str:
    """The inpainted page, as PNG, through the shared atomic write.

    `src` is the ORIGINAL archive member, and its icc_profile and exif ride
    along into the cached PNG. They have to: the member itself is inside a zip
    the re-render path never re-opens, so a colour profile not carried here is
    a colour profile the spot-fix output silently drops -- exactly the
    invisible data loss imaging.py exists to prevent, reintroduced one layer
    down. PngInfo() empty suppresses the tIME chunk so a re-store of identical
    pixels is byte-identical.
    """
    path = os.path.join(page_dir(page_hash_), RASTER)
    out = img.convert("RGB")
    kw = {"pnginfo": PngInfo()}
    info = (src or img).info
    if info.get("icc_profile"):
        kw["icc_profile"] = info["icc_profile"]
    if info.get("exif"):
        kw["exif"] = info["exif"]
    with atomic.atomic_write(path, "wb") as fh:
        out.save(fh, format="PNG", compress_level=1, **kw)
    kept = out.copy()
    kept.info.update({k: v for k, v in kw.items() if k != "pnginfo"})
    _tier.put(page_hash_, kept)
    return atomic.long_path(path)


def read_raster(page_hash_: str):
    """The inpainted page from the memory tier, or from disk, or None."""
    hit = _tier.get(page_hash_)
    if hit is not None:
        touch(page_hash_)
        return hit
    path = atomic.long_path(os.path.join(page_dir(page_hash_), RASTER))
    if not os.path.exists(path):
        return None
    with Image.open(path) as img:
        img.load()
        out = img.convert("RGB")
    _tier.put(page_hash_, out)
    touch(page_hash_)
    return out


def has_page(page_hash_: str) -> bool:
    d = atomic.long_path(page_dir(page_hash_))
    return os.path.exists(os.path.join(d, REGIONS)) and os.path.exists(
        os.path.join(d, RASTER)
    )


# -- translations and edits ------------------------------------------------


def read_translation(page_hash_: str, lang: str, model: str) -> dict:
    """``{region_id: {"text": str, "edited": bool}}`` for one (lang, model)."""
    path = os.path.join(page_dir(page_hash_), translation_name(lang, model))
    data = _read_json(path, {}) or {}
    return {str(k): v for k, v in data.items()} if isinstance(data, dict) else {}


def write_translation(page_hash_: str, lang: str, model: str, texts: dict) -> dict:
    """Merge a fresh translation in, and never overwrite an ``edited`` entry.

    A re-run must not silently discard the user's correction, so the merge is
    by region id with the stored edit winning. An edited region that the new
    response omits entirely is still preserved -- a provider that drops an id
    is exactly the case where the old text is all that is left.

    Scoping falls out of the filename: changing model or language writes a
    DIFFERENT file, so an edit made against one pair never leaks into another.
    """
    existing = read_translation(page_hash_, lang, model)
    merged = dict(existing)
    for rid, text in texts.items():
        rid = str(rid)
        if existing.get(rid, {}).get("edited"):
            continue
        merged[rid] = {"text": text, "edited": False}
    _write_json(
        os.path.join(page_dir(page_hash_), translation_name(lang, model)), merged
    )
    return merged


def write_edit(page_hash_: str, lang: str, model: str, region_id, text: str) -> dict:
    """A spot-fix edit IS a translation, so it lives in the translation file.

    Translations already key on ``(page_hash, target_lang, model)``, and an
    edit is a translation of that page in that language by that model's run --
    a second store keyed the same way would only be a second thing to keep in
    sync.
    """
    data = read_translation(page_hash_, lang, model)
    data[str(region_id)] = {"text": text, "edited": True}
    _write_json(os.path.join(page_dir(page_hash_), translation_name(lang, model)), data)
    return data


def has_edits(page_hash_: str) -> bool:
    """Any edited entry in any translation file. The eviction skip reads this."""
    d = atomic.long_path(page_dir(page_hash_))
    if not os.path.isdir(d):
        return False
    for name in os.listdir(d):
        if not (name.startswith("tr_") and name.endswith(".json")):
            continue
        data = _read_json(os.path.join(page_dir(page_hash_), name), {}) or {}
        if any(isinstance(v, dict) and v.get("edited") for v in data.values()):
            return True
    return False


def has_edit_for_other_model(page_hash_: str, lang: str, model: str) -> bool:
    """Is there a cached edit under a DIFFERENT pair than the current one?

    The UI notes this rather than acting on it: an edit made against another
    model is still the user's words, and silently importing it across a model
    change would undo the scoping the filename provides.
    """
    mine = translation_name(lang, model)
    d = atomic.long_path(page_dir(page_hash_))
    if not os.path.isdir(d):
        return False
    for name in os.listdir(d):
        if not (name.startswith("tr_") and name.endswith(".json")) or name == mine:
            continue
        data = _read_json(os.path.join(page_dir(page_hash_), name), {}) or {}
        if any(isinstance(v, dict) and v.get("edited") for v in data.values()):
            return True
    return False


# -- the disk cap ----------------------------------------------------------


def _dir_size(path) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(atomic.long_path(path)):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def disk_bytes() -> int:
    return _dir_size(pages_root())


def _pinned(page_hash_: str) -> str:
    """Why this page cannot be evicted, or "" if it can be.

    Returned as a REASON rather than a bool because the overflow warning has to
    say which of the two skips made the target unreachable, and recomputing it
    at warning time would be a second implementation of the same rule.
    """
    refs = read_refs(page_hash_)
    # "While its job exists" is the plan's qualifier and it is load-bearing: a
    # page whose last job was deleted or pruned has refs [], and an edit on it
    # no longer belongs to anything the user can open. Pinning it anyway made
    # such a page permanently unevictable and the overflow warning permanent
    # with it.
    if refs and has_edits(page_hash_):
        return "a user correction"
    if any(r in _running for r in refs):
        return "a running job"
    return ""


def enforce_cap(job_id: str | None = None) -> str | None:
    """Evict LRU by directory mtime down to the target. Returns a warning or None.

    Two skips: a page holding a user correction, and a page referenced by a
    running job. When they make the target unreachable the cache EXCEEDS its
    cap and says so, once per job, naming the achieved size and the reason.

    That is deliberate and is the smaller of three failures. Evicting a user's
    only copy of their own correction to honour a number is worse than being
    over the number; evicting a running job's input is worse than being over
    the number; and sitting above the cap with nobody told is the silent
    failure this codebase refuses everywhere else.
    """
    cap, target = _cap_bytes(), _target_bytes()
    size = disk_bytes()
    if size <= cap:
        return None

    proot = atomic.long_path(pages_root())
    reasons: list[str] = []
    # The whole sweep is under the lock, in a `with` rather than an
    # acquire/release pair: eviction is read-the-refs-then-delete, and a
    # reference added between those two steps is a page deleted out from under
    # the job that had just claimed it. An OSError partway through a sweep that
    # held the lock by hand would leave it held for the life of the process.
    with _LOCK:
        entries = []
        for h in os.listdir(proot) if os.path.isdir(proot) else []:
            try:
                entries.append((os.path.getmtime(os.path.join(proot, h)), h))
            except OSError:
                continue
        entries.sort()  # oldest touch first; `touch` is what makes this LRU

        for _mtime, h in entries:
            if size <= target:
                break
            why = _pinned(h)
            if why:
                reasons.append(why)
                continue
            freed = _dir_size(page_dir(h))
            shutil.rmtree(atomic.long_path(page_dir(h)), ignore_errors=True)
            _tier._items.pop(h, None)
            _tier._bytes.pop(h, None)
            size -= freed

    if size <= target:
        return None
    key = _job_key(job_id) if job_id is not None else "*"
    if key in _warned:
        return None
    _warned.add(key)
    held = " and ".join(sorted(set(reasons))) or "pages in use"
    return (
        f"page cache is {size / 1024 / 1024:.1f}MB, over its "
        f"{cap / 1024 / 1024:.1f}MB cap: every remaining page is held by {held}"
    )
