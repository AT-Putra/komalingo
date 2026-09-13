#!/usr/bin/env python3
r"""Phase 3's red-check: sabotage each guarded behaviour, confirm its assert fails.

    uv run --project sidecar python tests\redcheck_spotfix.py

A green gate proves nothing about a gate that cannot go red. Twenty-four sabotages,
each a minimal textual edit to the implementation, each expected to turn ONE
named assert tag in check_spotfix.py red. After every case the edited file is
restored and verified byte-identical by SHA-256 -- a restore that silently
failed would leave the repository broken and the next run green for the wrong
reason.

**A miss is investigated, never counted in either direction.** Phase 2a lost a
round to a red-check keyed on an assert tag that had been renamed: it reported
a miss, and the miss was very nearly recorded as a hole in the gate rather than
as a stale tag. So a case that does not go red prints the tag it looked for and
whether that tag appears in the output at all, which separates "the assert did
not fire" from "the assert is not called that any more".

Not destructive: every edit is reverted in a finally, and the run aborts if a
restore does not verify.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, "tests", "check_spotfix.py")

# While a sabotage is applied, the WORKING TREE is wrong. Anything else that
# runs the suite meanwhile -- a second terminal, CI, a reviewer reproducing this
# file -- sees a source tree that is deliberately broken and reports failures
# that look like flakiness and are not. The marker makes that state nameable:
# check_spotfix reads it and exits INCONCLUSIVE saying so, instead of exiting 1
# and sending the reader after a bug nobody introduced.
MARKER = os.path.join(ROOT, "tests", ".sabotage-active")

CACHE = os.path.join(ROOT, "sidecar", "cache.py")
PIPELINE = os.path.join(ROOT, "sidecar", "pipeline.py")
READ_CBZ = os.path.join(ROOT, "sidecar", "containers", "read_cbz.py")

# (name, file, old, new, tag it must turn red, what the sabotage proves)
CASES = [
    (
        "cache keyed on the job",
        CACHE,
        'def page_dir(page_hash: str) -> str:\n'
        '    return os.path.join(pages_root(), page_hash)',
        'def page_dir(page_hash: str) -> str:\n'
        '    return os.path.join(pages_root(), _sab_job(), page_hash)\n\n\n'
        'def _sab_job() -> str:\n'
        '    return sorted(_running)[0] if _running else "no-job"',
        "[crossjob]",
        "the iteration-1 layout: a re-run is a new job_id and finds an empty "
        "directory",
    ),
    (
        "hash over file bytes, not decoded pixels",
        CACHE,
        '    h = hashlib.sha256()\n'
        '    h.update(f"{img.mode}|{img.size[0]}x{img.size[1]}|".encode("ascii"))\n'
        '    h.update(img.tobytes())\n'
        '    return h.hexdigest()',
        '    h = hashlib.sha256()\n'
        '    h.update(f"{img.format}|{img.mode}|{img.size[0]}x{img.size[1]}|".encode("ascii"))\n'
        '    h.update(img.tobytes())\n'
        '    return h.hexdigest()',
        "[key]",
        "letting the CONTAINER into the digest is the file-byte defect in its "
        "smallest form -- the same page as a PNG and as a BMP stops hashing "
        "equal, which is the miss a decoded-pixel key exists to avoid",
    ),
    (
        "placement keyed on the page hash alone",
        PIPELINE,
        'placed.get("member") or f"{item_id}_{ordinal:04d}.png"',
        'record.get("member") or f"{item_id}_{ordinal:04d}.png"',
        "[placement]",
        "editing one of two identical pages writes over the other's output",
    ),
    (
        "refs.json as an integer count",
        CACHE,
        '    refs = _read_json(os.path.join(page_dir(page_hash_), REFS), [])\n'
        '    return [str(r) for r in refs] if isinstance(refs, list) else []',
        '    refs = _read_json(os.path.join(page_dir(page_hash_), REFS), [])\n'
        '    if isinstance(refs, int):\n'
        '        return ["?"] * refs\n'
        '    return [str(r) for r in refs] if isinstance(refs, list) else []',
        "[refs]",
        "a count cannot name the job that leaked -- asserted via the shape of "
        "the file itself",
        # This one also needs the WRITER to emit a count, below.
        (
            '            refs.append(job_id)\n'
            '            _write_json(os.path.join(page_dir(page_hash_), REFS), sorted(refs))',
            '            refs.append(job_id)\n'
            '            _write_json(os.path.join(page_dir(page_hash_), REFS), len(refs))',
        ),
    ),
    (
        "no touch on the read path",
        CACHE,
        '    record = _read_json(os.path.join(page_dir(page_hash_), REGIONS))\n'
        '    if record is not None:\n'
        '        touch(page_hash_)\n'
        '    return record',
        '    return _read_json(os.path.join(page_dir(page_hash_), REGIONS))',
        "[cap]",
        "mtime is write time, so the cap evicts the hot set",
    ),
    (
        "re-render allowed to re-translate",
        PIPELINE,
        '    drawn, fit_summary = render(\n'
        '        cleaned, regions, ordinal, client, allow_retranslate=False\n'
        '    )',
        '    drawn, fit_summary = render(\n'
        '        cleaned, regions, ordinal, client, allow_retranslate=True\n'
        '    )',
        "[zero-llm]",
        "rung 5 fires on the spot-fix path, spending a round trip inside the "
        "3.0s budget",
    ),
    (
        "fit flags loaded instead of recomputed",
        PIPELINE,
        '        r["fit_compromised"] = f.fit_compromised\n'
        '        r["fit_failed"] = f.fit_failed',
        '        r["fit_compromised"] = r.get("fit_compromised", f.fit_compromised)\n'
        '        r["fit_failed"] = r.get("fit_failed", f.fit_failed)',
        "[flag]",
        "a shortened edit keeps the old flag, so the editor highlights a bubble "
        "the user already fixed",
    ),
    (
        "a re-translation overwrites an edit",
        CACHE,
        '        if existing.get(rid, {}).get("edited"):\n'
        '            continue\n'
        '        merged[rid] = {"text": text, "edited": False}',
        '        merged[rid] = {"text": text, "edited": False}',
        "[edit]",
        "a re-run silently discards the user's correction",
    ),
    (
        "member names written unsanitised",
        PIPELINE,
        "        parts.append(_safe_segment(seg))",
        "        parts.append(seg)",
        "[safe-path]",
        "a member carrying a colon writes to an NTFS alternate data stream: the "
        "write succeeds, the listing shows nothing, and the page is lost",
    ),
    (
        "a torn page directory trusted",
        PIPELINE,
        "            if cached is not None and cache.read_raster(h) is None:",
        "            if False:",
        "[torn]",
        "has_page says yes, the raster is gone, and the renderer is handed a "
        "None -- a lost entry becomes a crashed run",
    ),
    (
        "lexicographic member order",
        READ_CBZ,
        "    return sorted((i.filename for i in zf.infolist() if _is_page(i)), key=_natural_key)",
        "    return sorted(i.filename for i in zf.infolist() if _is_page(i))",
        "[order]",
        "ch10 before ch2 and p10 before p9 -- a page order the editor then does "
        "not deliver, and invisible against any zero-padded archive",
    ),
    (
        "the memory tier unbounded",
        CACHE,
        "MAX_RASTERS = 3",
        "MAX_RASTERS = 10_000",
        "[tier]",
        "the tier grows without limit and AC-12's 400MB budget is spent on "
        "rasters nobody is looking at",
    ),
    (
        "rerender reports the shared record's position",
        PIPELINE,
        "        page=ordinal,\n        item_id=item_id,\n        member=placed.get(\"member\"),\n",
        "",
        "[placement]",
        "the response carries ordinal 7's page and member for an edit of "
        "ordinal 3, and the UI's next edit goes to page 7",
    ),
    (
        "prune deletes a dead job's pages",
        CACHE,
        "        for h in placed_hashes(job_id):\n"
        "            if job_id in read_refs(h):\n"
        "                drop_ref(h, job_id)\n"
        "                removed += 1\n"
        "        shutil.rmtree(os.path.join(jroot, job_id), ignore_errors=True)",
        "        removed += len(read_placement(job_id))\n"
        "        delete_job(job_id)",
        "[refs]",
        "a job that was the sole holder of its pages has every one deleted at "
        "the next launch -- Phase 9's scenario, and AC-13's pages",
    ),
    (
        "prune ignores the recorded pid",
        CACHE,
        "        if _pid_alive(marker.get(\"pid\")):\n            continue",
        "        if False:\n            continue",
        "[refs]",
        "a second sidecar instance's startup prune deletes the first's live job",
    ),
    (
        "translations never cached on ingest",
        PIPELINE,
        "                cache.write_translation(\n"
        "                    h, lang, model, {r[\"id\"]: r.get(\"translation\", \"\") for r in regions}\n"
        "                )",
        "                pass",
        "[ingest-llm]",
        "every re-run re-translates every page and bills for it, with every "
        "other assert green",
    ),
    (
        "the read-back after write_translation removed",
        PIPELINE,
        "                # just not on the page. Reachable when coverage was partial (a\n"
        "                # half-written translation file) and an edit exists.\n"
        "                _load_translations(regions, h, lang, model)",
        "                pass",
        "[edit-rendered]",
        "the file keeps the user's correction and the delivered page shows the "
        "provider's text",
    ),
    (
        "the cap never wired into the job",
        PIPELINE,
        "        warning = cache.enforce_cap(job_id)\n    finally:",
        "        warning = None\n    finally:",
        "[cap-wired]",
        "every cap assert stays green while the cache grows to disk-full",
    ),
    (
        "mixed-language re-render allowed",
        PIPELINE,
        "    if uncovered:",
        "    if False:",
        "[route]",
        "one bubble in the new language and the rest in the old one",
    ),
    (
        "the archive never rebuilt after an edit",
        PIPELINE,
        "    if placed.get(\"src_path\"):\n"
        "        record[\"repack\"] = schedule_repack(job_id, item_id, dest_dir, lang)",
        "    if False:\n"
        "        record[\"repack\"] = schedule_repack(job_id, item_id, dest_dir, lang)",
        "[archive]",
        "the loose page shows the edit and the volume beside it never does",
    ),
    (
        "an edit pins a page with no job",
        CACHE,
        "    if refs and has_edits(page_hash_):",
        "    if has_edits(page_hash_):",
        "[cap]",
        "a page whose last job is gone holds an edit nobody can open and is "
        "unevictable forever",
    ),
    (
        "the tier holds an oversized raster",
        CACHE,
        "        if n > MAX_TIER_BYTES:",
        "        if False:",
        "[tier]",
        "one raster over 150MB sits resident above the bound AC-12 counts -- "
        "the first draft's guard-less put plus its len==1 escape, together",
        (
            "            k, _ = self._items.popitem(last=False)",
            "            if len(self._items) == 1:\n"
            "                break\n"
            "            k, _ = self._items.popitem(last=False)",
        ),
    ),
    (
        "job_id used raw as a directory name",
        CACHE,
        "    return os.path.join(jobs_root(), _job_key(job_id))",
        "    return os.path.join(jobs_root(), str(job_id))",
        "[safe-path]",
        "a traversing job id writes files outside the cache root",
    ),
    (
        "the models unlocked under concurrent jobs",
        PIPELINE,
        "                with _MODEL_LOCK:\n"
        "                    regions = detect(img, ordinal)\n"
        "                    ocr_calls = ocr(regions, img, ordinal)",
        "                if True:\n"
        "                    regions = detect(img, ordinal)\n"
        "                    ocr_calls = ocr(regions, img, ordinal)",
        "[parallel]",
        "concurrent POSTs on uncached pages raise DetectError out of OpenCV's "
        "forward pass -- loud, not lossy, but the route promises otherwise",
    ),
    (
        "the startup prune disabled",
        CACHE,
        'def prune_refs() -> int:',
        'def prune_refs() -> int:\n'
        '    if True:\n'
        '        return 0',
        "[refs]",
        "a job killed mid-run leaks a reference that pins its pages forever",
    ),
]


def sha256(path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run_check() -> tuple[int, str]:
    """Run the gate. MT_REDCHECK tells it the sabotage marker is ours."""
    proc = subprocess.run(
        [sys.executable, CHECK],
        capture_output=True, encoding="utf-8", errors="replace", cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8",
                 MT_REDCHECK="1"),
    )
    return proc.returncode, proc.stdout + proc.stderr


def failed_tags(output: str) -> set[str]:
    tags = set()
    for line in output.splitlines():
        if "] FAIL: [" in line:
            tags.add(line.split("FAIL: ", 1)[1].split("]", 1)[0] + "]")
    return tags


def main() -> int:
    if not os.path.exists(CHECK):
        print(f"FAIL: {CHECK} does not exist")
        return 1

    if os.path.exists(MARKER):
        print(f"FAIL: {MARKER} already exists -- another red-check is running, "
              f"or a previous one died without restoring the tree. Check "
              f"`git status` before running this again.")
        return 1

    code, out = run_check()
    baseline_tags = failed_tags(out)
    if code not in (0, 2) or baseline_tags:
        print(f"FAIL: the gate is not green before sabotage "
              f"(exit {code}, failing tags {sorted(baseline_tags)})")
        return 1
    print(f"baseline: check_spotfix exits {code} with no failing assert\n")

    hits = misses = 0
    for case in CASES:
        name, path, old, new, tag, why = case[:6]
        extra = case[6] if len(case) > 6 else None

        # The marker is taken with O_EXCL BEFORE the source is read, so two
        # concurrent red-checks cannot both proceed. The review saw two running
        # at once: the loser snapshots the winner's sabotage as its `before`,
        # and its own hash check then passes while it restores the sabotage
        # PERMANENTLY. An exists() test does not close that; only an atomic
        # create does. Taken per case rather than once, so a run that dies
        # between cases leaves nothing held.
        try:
            fd = os.open(MARKER, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            print(f"ABORT: {MARKER} appeared mid-run -- another red-check "
                  f"started. Neither result can be trusted; check `git status` "
                  f"and re-run one of them.")
            return 1
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(f"{name}\n{path}\n")

        try:
            before = open(path, encoding="utf-8", newline="").read()
            digest = sha256(path)
            if old not in before:
                print(f"  MISS  {name}: the text to sabotage is not in "
                      f"{os.path.basename(path)} -- the implementation moved, "
                      f"so this case is stale, not a hole")
                misses += 1
                continue
            patched = before.replace(old, new, 1)
            if extra:
                if extra[0] not in patched:
                    print(f"  MISS  {name}: the second half of this sabotage is "
                          f"not present; case is stale")
                    misses += 1
                    continue
                patched = patched.replace(extra[0], extra[1], 1)
            open(path, "w", encoding="utf-8", newline="").write(patched)
            try:
                _, output = run_check()
                tags = failed_tags(output)
            finally:
                open(path, "w", encoding="utf-8", newline="").write(before)
                if sha256(path) != digest:
                    print(f"ABORT: restoring {path} did not reproduce the "
                          f"original bytes. Fix the tree before trusting any "
                          f"result above.")
                    return 1
        finally:
            try:
                os.remove(MARKER)
            except FileNotFoundError:
                pass

        if tag in tags:
            hits += 1
            print(f"  RED   {name}: {tag} went red -- {why}")
        else:
            misses += 1
            present = tag in output
            print(f"  MISS  {name}: expected {tag} to go red. "
                  f"Tag {'IS' if present else 'is NOT'} present in the output, "
                  f"so this is {'a hole in the gate' if present else 'a STALE TAG in this file, not a hole'}. "
                  f"Failing tags were {sorted(tags) or 'none'}")

    print(f"\nred-checks: {hits} of {len(CASES)} turned their named assert red")
    return 0 if misses == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
