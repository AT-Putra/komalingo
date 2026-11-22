# Graph Report - MangaTranslator  (2026-11-22)

## Corpus Check
- 115 files · ~294,125 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: .cbz 5, (none) 4, .cbt 2)

## Summary
- 2228 nodes · 5091 edges · 160 communities (116 shown, 44 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 193 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0d669750`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- check_pdf.py
- check_package.py
- run_item
- check_spotfix.py
- check_archives.py
- gen_fixtures.py
- lib.rs
- check_inpaint.py
- Page Image Manifest
- package.json
- archive.py
- run_item
- Brand and Language Documentation
- stub_provider.py
- Budget
- check_batch.py
- check_typeset.py
- json
- check_cjk.py
- describeError
- Job.tsx
- detect.py
- Tauri Application Configuration
- group.py
- pil
- pipeline.py
- LLMClient
- StubProvider
- ._parse
- os
- inpainter.py
- mock-tauri.ts
- check_group.py
- _repack
- Frontend TypeScript Configuration
- job.py
- main.py
- check_settings.py
- models.py
- repack_extras
- native.py
- typeset.py
- run_all.py
- retry_page
- App.tsx
- api.ts
- Komalingo Brand Assets
- main
- check_id.py
- check_api.py
- imaging.py
- main.tsx
- cache.py
- start_job
- Checks
- section_tier
- EraseError
- translate_item
- _no_detect_or_ocr
- check_probe.py
- _read_page
- NeedsAttention
- section_not_text
- skip
- Node TypeScript Configuration
- write_pdf
- check_warmup
- pdf.py
- redcheck_spotfix.py
- llm.py
- load_font
- Tauri Window Permissions
- Panel Fixture 007
- Panel Fixture 010 Upper
- Panel Fixture 010 Left
- Panel Fixture 010 Lower
- Panel Fixture 011
- Panel Fixture 012 Upper
- Panel Fixture 012 Center
- Panel Fixture 012 Left
- Panel Fixture 012 Right
- Panel Fixture 012 Lower
- Panel Fixture 013 Upper
- Panel Fixture 013 Lower
- Panel Fixture 014
- Panel Fixture 015
- Panel Fixture 017 Upper
- Panel Fixture 017 Center
- Panel Fixture 017 Left
- Panel Fixture 017 Lower
- Panel Fixture 018
- Panel Fixture 019
- Panel Fixture 020
- Panel Fixture 021 Upper
- Panel Fixture 021 Lower
- Panel Fixture 023
- Fixture Provenance Metadata
- Control
- typeset_page
- Scanned PDF Fixture
- Panel Manifest Validation
- Contact Sheet Branding
- Hand-Drawn Logo Concepts
- Indonesian Language Policy
- Bubble Processing Fixture
- Bubble Geometry Fixture
- Bubble Length Fixture
- Mid-Token Bubble Fixture
- Word Fit Failure Fixture
- Bubble Success Fixture
- Page Erasure Fixture
- Unreadable Page Fixture
- Partial PDF Fixture
- Text PDF Fixture
- Rotated PDF Fixture
- Bad Gateway Fixture
- Vertical Japanese Panel
- Unreadable Vertical Text Fixture
- Komalingo Application
- Komalingo Sidecar
- Speech Bubble Logo
- Tauri Branding
- Vite Branding
- React Branding
- High-Density Application Icon
- Application Icon
- Small Application Icon
- Primary Application Icon
- Square Application Logo
- Square Application Logo
- Square Application Logo
- Square Application Logo
- Square Application Logo
- Square Application Logo
- Square Application Logo
- Square Application Logo
- Square Application Logo
- Store Application Logo
- _sevenzip_payloads
- check_round_trip
- check_page_slots
- check_cancel.py
- check_erase.py
- _Recogniser
- read_raster
- _reset
- probe.py
- _run_cached_page
- _floor_fits
- _wrap_from
- imports.py
- model_dir
- launch_drained
- main
- read_bounded
- item_placements

## God Nodes (most connected - your core abstractions)
1. `Checks` - 87 edges
2. `long_path()` - 63 edges
3. `LLMClient` - 59 edges
4. `page_dir()` - 42 edges
5. `StubProvider` - 42 edges
6. `skip()` - 41 edges
7. `ProviderError` - 35 edges
8. `main()` - 33 edges
9. `review_fixes()` - 30 edges
10. `Budget` - 29 edges

## Surprising Connections (you probably didn't know these)
- `Komalingo Open Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-open-a.png → README.md
- `Komalingo Split Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-split-a.png → README.md
- `main()` --indirect_call--> `root()`  [INFERRED]
  tests/check_atomic.py → sidecar/cache.py
- `main()` --indirect_call--> `root()`  [INFERRED]
  tests/check_imaging.py → sidecar/cache.py
- `_dismissed()` --indirect_call--> `root()`  [INFERRED]
  tests/check_inpaint.py → sidecar/cache.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Komalingo Brand Asset Family** — brand_komalingo_icon_dark_dark_app_icon, brand_komalingo_icon_light_app_icon, brand_komalingo_lockup_on_dark_dark_lockup, brand_komalingo_lockup_light_lockup, brand_komalingo_mark_on_dark_dark_mark, brand_komalingo_mark_light_mark [EXTRACTED 0.99]
- **Local Manga Translation Stack** — readme_translation_pipeline, readme_manga_ocr, readme_pp_ocrv5, readme_pp_ocrv3_db, readme_comic_text_detector, readme_lama_manga [EXTRACTED 1.00]
- **Komalingo Brand Concept Explorations** — brand_explorations_concept_open_a_image, brand_explorations_concept_split_a_image [INFERRED 0.90]
- **Scanned PDF Fixture and Rendered Pages** — fixtures_pdf_scan_document, fixtures_pdf_scan_p1_image, fixtures_pdf_scan_p2_image [INFERRED 0.95]

## Communities (160 total, 44 thin omitted)

### Community 0 - "check_pdf.py"
Cohesion: 0.16
Nodes (22): functools, pypdf, pypdfium2, pypdfium2_raw, pages(), Yield `(ordinal, member, image)` for every page, 1-based. Same contract as…, check_boundary(), check_cache_key() (+14 more)

### Community 1 - "check_package.py"
Cohesion: 0.12
Nodes (27): glob, Return (execution_provider, reason). The reason is empty ONLY when CUDA was…, select_provider(), build(), _exe_provider(), find_mt(), _folder_bytes(), free_port() (+19 more)

### Community 2 - "run_item"
Cohesion: 0.09
Nodes (23): BoundedSemaphore, Cancelled, _check_cancel(), _check_lang(), expecting(), _page_slots(), _pause_job(), Paused (+15 more)

### Community 3 - "check_spotfix.py"
Cohesion: 0.13
Nodes (19): The repack status for one item: idle, pending, running, done or failed., repack_status(), _above_floor(), _archive_edits(), _calibrate(), _call(), r"""Phase 3 -- the spot-fix editor and the page cache (AC-10). OFFLINE. uv run…, Run a pipeline entry point; an exception is a RED assert, not a dead run. Every… (+11 more)

### Community 4 - "check_archives.py"
Cohesion: 0.10
Nodes (48): bz2, lzma, psutil, comicinfo(), detect_format(), pages(), The container family of `path`, from its bytes. The tar test is last and is…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Same… (+40 more)

### Community 5 - "gen_fixtures.py"
Cohesion: 0.06
Nodes (55): binascii, gzip, pathlib, struct, generate(), main(), Phase 0a gate: two regenerations from an empty tree are byte-identical. uv run…, Relative-path -> sha256 for everything under the generated subdirs. (+47 more)

### Community 6 - "lib.rs"
Cohesion: 0.08
Nodes (38): AppHandle, CommandChild, Into, Mutex, Option, process, Result, Self (+30 more)

### Community 7 - "check_inpaint.py"
Cohesion: 0.09
Nodes (38): _assert_ink(), _assert_ring(), _assert_step_edge(), _band(), _best_ncc(), _chord_x(), _composite(), _expected_font_px() (+30 more)

### Community 8 - "Page Image Manifest"
Cohesion: 0.05
Nodes (40): sha256, size, sha256, size, sha256, size, sha256, size (+32 more)

### Community 9 - "package.json"
Cohesion: 0.06
Nodes (32): dependencies, react, react-dom, @tauri-apps/api, @tauri-apps/plugin-dialog, @tauri-apps/plugin-opener, devDependencies, @tauri-apps/cli (+24 more)

### Community 10 - "archive.py"
Cohesion: 0.06
Nodes (34): BytesIO, _decode(), _drain(), _head(), _libarchive(), libarchive_path(), LibarchiveMissing, Exception (+26 more)

### Community 11 - "run_item"
Cohesion: 0.09
Nodes (22): is_archive(), Whether `path` has an extension AC-6 covers. Cheap, name-only. Used to decide…, classify(), disambiguate(), _discard_output(), Item, Lock, One delivered page: count it, and list it when it was skipped. Called from up… (+14 more)

### Community 12 - "Brand and Language Documentation"
Cohesion: 0.06
Nodes (31): Komalingo Open Concept A Brand Exploration, Komalingo Split Concept A Brand Exploration, Honorifics and register in the Indonesian output (AC-4), Register, The rule, The table, What stays as it is, What the gate holds (+23 more)

### Community 13 - "stub_provider.py"
Cohesion: 0.14
Nodes (16): http_server, _as_event_stream(), _chat_reply(), _cut_off(), _load_fixtures(), An OpenAI-compatible provider stub, in-process, no new dependency. Replays the…, The region objects a request asked about, read out of the prompt. Parsed from…, The ids a request asked about; [0] when the prompt carried none. (+8 more)

### Community 14 - "Budget"
Cohesion: 0.09
Nodes (20): PathLike, posixpath, Budget, is_comicinfo(), _normalized(), Exception, r"""AC-11: the ingest budget. Every untrusted archive is read through this.…, One rejected archive, carrying which rule refused it and where. `reason` is… (+12 more)

### Community 15 - "check_batch.py"
Cohesion: 0.09
Nodes (32): contextlib, itertools, r"""The single write protocol. Every file this app produces goes through here.…, The files in `directory`, top level only, in natural order. Top level only: a…, scan(), build_folder(), check_cancel(), check_cap() (+24 more)

### Community 16 - "check_typeset.py"
Cohesion: 0.12
Nodes (28): ellipse_points(), One detected text region, as it travels through the pipeline. `text` defaults…, The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.…, Region, The job summary AC-1 requires: which regions were compromised, which failed.…, summary(), _batching_and_spotfix(), _check_page() (+20 more)

### Community 17 - "json"
Cohesion: 0.12
Nodes (28): datetime, json, main(), Phase 1 -- OCR truth on real vertical Japanese (AC-2). OFFLINE. Runs manga-ocr…, build_manifest(), _compare(), image_size(), load_manifest() (+20 more)

### Community 18 - "check_cjk.py"
Cohesion: 0.10
Nodes (28): detect(), Text regions from detect.py's DB model. Regions become plain dicts here rather…, _blank_and_ja(), _cache(), _centroid(), _fit(), _load(), main() (+20 more)

### Community 19 - "describeError"
Cohesion: 0.14
Nodes (23): Alert(), ModelCombobox, ModelComboboxHandle, api, CacheStats, describeError(), displayPath(), ModelInfo (+15 more)

### Community 20 - "Job.tsx"
Cohesion: 0.11
Nodes (28): react, @tauri-apps/plugin-dialog, ICON, Tone, Icon(), IconName, PATHS, PathField() (+20 more)

### Community 21 - "detect.py"
Cohesion: 0.08
Nodes (37): _as_bgr(), _dedupe(), detect(), DetectError, _glyph_px(), _input_size(), _inverse(), _model() (+29 more)

### Community 22 - "Tauri Application Configuration"
Cohesion: 0.08
Nodes (24): app, security, windows, enable, scope, build, beforeBuildCommand, beforeDevCommand (+16 more)

### Community 23 - "group.py"
Cohesion: 0.16
Nodes (15): convex_hull(), glyph_unit(), group(), _inside(), merge(), neighbours(), Group column-level detections into one region per bubble. Phase 2b. WHY this…, Degrees the polygon's longest edge sits off the nearer axis, in [0, 45]. (+7 more)

### Community 24 - "pil"
Cohesion: 0.10
Nodes (26): numpy, pil, bbox(), lines(), area(), inside(), ocr(), Chinese and Korean OCR: PP-OCRv5 text-line recognition through onnxruntime.… (+18 more)

### Community 25 - "pipeline.py"
Cohesion: 0.06
Nodes (62): get_placement(), The placement entry for one position, or None. See put_placement., Rebuild the item's archive after a fix, unless it has none., _schedule_item_repack(), _bbox(), CacheMiss, _changed_in_polygon(), _container() (+54 more)

### Community 26 - "LLMClient"
Cohesion: 0.09
Nodes (38): LLMClient, Region, What the Settings UI sends. No defaults -- absent means absent., Settings, _archive(), client_ok(), inputs(), kinds() (+30 more)

### Community 27 - "StubProvider"
Cohesion: 0.07
Nodes (16): Job, Every item, through the boundary, on `workers` threads. Never raises.…, Cancel the rest. On a job that already PAUSED and settled, the workers are…, Block until every item has a terminal status. False on timeout., AC-9, the half the product had never wired: probe once per job. Before this,…, _chats_with_image(), check_probe_wiring(), (chat payloads, those carrying an image_url part). Three asserts ask this. (+8 more)

### Community 28 - "._parse"
Cohesion: 0.12
Nodes (11): glossary_text(), image_data_url(), probe_token(), The glossary block for `lang`, or "" when the target has none., A data URL whose media type is what the bytes ARE, by signature. The page…, The only way out to the provider. _request holds the gate for the call, on the…, {region_id: text}. A JSON null stays None -- see NOT_TEXT_INSTRUCTION. None and…, All regions of one page. One request unless the page is huge. Returns… (+3 more)

### Community 29 - "os"
Cohesion: 0.19
Nodes (14): asyncio, os, The app's per-user data directory, and the one-time move from its old name. The…, sys, tempfile, Phase 0 -- the write protocol. Offline, no fixtures, no network. Asserts, from…, Phase 0 -- encode policy. Offline, no network. Asserts, from the build order:…, Phase 0 -- the host/sidecar IPC contract (US-011). OFFLINE (US-003 stub). **Why… (+6 more)

### Community 30 - "inpainter.py"
Cohesion: 0.13
Nodes (23): _crops(), erase(), _fill(), fill_white(), _flat(), _flat_surround(), _inpaint(), _lama() (+15 more)

### Community 31 - "mock-tauri.ts"
Cohesion: 0.13
Nodes (21): api(), Callback, callbacks, emit(), fakePage(), invoke(), itemPages, jobs (+13 more)

### Community 32 - "check_group.py"
Cohesion: 0.15
Nodes (24): _box(), The region's bounding box in thousandths of the page, for the vision model.…, _bubble_of(), _ellipse_mask(), _fixture(), _geometry(), _ink(), _largest() (+16 more)

### Community 33 - "_repack"
Cohesion: 0.40
Nodes (4): output_path(), Where the repacked archive lands. Same extension, except RAR -> .cbz. The…, AC-6's round trip: the delivered pages, back into the input's format. **The…, _repack()

### Community 34 - "Frontend TypeScript Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+10 more)

### Community 35 - "job.py"
Cohesion: 0.08
Nodes (28): collections, hashlib, io, r"""A chapter of loose page images, read the way an archive is read. A folder…, Container readers. One module per format, and each one reads only. Phase 3…, _is_page(), members(), _natural_key() (+20 more)

### Community 36 - "main.py"
Cohesion: 0.07
Nodes (42): FastAPI, get, pydantic, secrets, buffer(), cache_stats(), health(), job_item() (+34 more)

### Community 37 - "check_settings.py"
Cohesion: 0.16
Nodes (14): re, env_local(), [env-local] the loader fills gaps and never overwrites (lib/env_local.py)., main(), Phase 0 -- the Settings UI and the IPC client (US-009). OFFLINE. The frontend…, Source with comments removed. The point of the whole file: an assert that…, read(), strip_comments() (+6 more)

### Community 38 - "models.py"
Cohesion: 0.18
Nodes (15): http_client, ensure(), _ensure_directory(), fetch(), FetchError, _free_space(), RuntimeError, First-launch model fetch, and the CUDA-or-CPU decision. Resumable by design.… (+7 more)

### Community 39 - "repack_extras"
Cohesion: 0.10
Nodes (20): _admit(), _CountingReader, expected_pages(), _is_page_name(), _lazy(), members(), Whether a member name is a page CANDIDATE. Identical rule to read_cbz., gz" | "bz2" | "xz" for a whole-file-compressed tar, "" for a plain one. This… (+12 more)

### Community 40 - "native.py"
Cohesion: 0.14
Nodes (16): shutil, os.replace with a short, bounded retry on Windows sharing violations. Two…, _replace(), _bsdtar(), bundled(), ensure_libarchive(), NativeMissing, Exception (+8 more)

### Community 41 - "typeset.py"
Cohesion: 0.14
Nodes (21): dataclasses, math, as_points(), The shared Region type: detect.py's output, typeset.py's input. Defined here…, Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.…, _bbox(), _edge_adjacent(), floor_px() (+13 more)

### Community 42 - "run_all.py"
Cohesion: 0.20
Nodes (16): append_record(), assert_interpreter(), discover(), env_class(), harvest_metrics(), last_status(), load_records(), main() (+8 more)

### Community 43 - "retry_page"
Cohesion: 0.06
Nodes (45): clear_refusals(), model_slug(), A filesystem-safe name for a model id that two ids cannot share. The readable…, ``{region_id: {"text": str, "edited": bool}}`` for one (lang, model)., Merge a fresh translation in, and never overwrite an ``edited`` entry.…, A successful translation of the page, under ANY key, ends its refusals., read_refusal(), read_translation() (+37 more)

### Community 44 - "App.tsx"
Cohesion: 0.14
Nodes (21): App(), refreshBatch(), refuseUnconfigured(), retriedPages(), runJob(), updatePage(), exitMessage(), frontPage() (+13 more)

### Community 45 - "api.ts"
Cohesion: 0.10
Nodes (30): @tauri-apps/api, MODE_WORDS, Outcome, sleep(), ApiError, CacheClearResult, DismissedRegion, isApiError() (+22 more)

### Community 46 - "Komalingo Brand Assets"
Cohesion: 0.13
Nodes (15): Komalingo Light-Tile App Icon PNG, Komalingo Dark-Tile App Icon PNG, Komalingo Dark-Tile App Icon, Komalingo Light-Tile App Icon, Komalingo Lockup PNG, Komalingo Lockup for Light Backgrounds, Komalingo Lockup for Dark Backgrounds, Komalingo Lockup on Dark PNG (+7 more)

### Community 47 - "main"
Cohesion: 0.18
Nodes (3): main(), Serves PAYLOAD with Range support. cut_after truncates the response., Server

### Community 48 - "check_id.py"
Cohesion: 0.27
Nodes (11): _glossary_doc(), _live(), main(), _payload_text(), _prompt(), Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always; live…, Which of the line's marked honorifics appear in `out`, and which forbidden…, _renderings() (+3 more)

### Community 49 - "check_api.py"
Cohesion: 0.16
Nodes (15): call(), main(), _parse_json(), Phase 0 -- the sidecar's HTTP surface and the shutdown gate (US-007). OFFLINE.…, Returns (status, body). A refused connection is status 0., (payload, why). `why` names the parse failure so the assert can print it. A…, wait_up(), captured() (+7 more)

### Community 50 - "imaging.py"
Cohesion: 0.17
Nodes (15): pil_pngimageplugin, encode(), output_path(), Image, Encode policy. The only place in the app that calls Image.save. Pillow silently…, Drop the GPS IFD, keep every other tag byte-identical., Encode to bytes in `fmt`, carrying metadata from `src` (default: img)., Destination path whose extension matches the SOURCE format. Named off the… (+7 more)

### Community 51 - "main.tsx"
Cohesion: 0.23
Nodes (9): ErrorBoundary, Props, State, installGlobalReporting(), reportError(), boot(), dismissSplash(), failSplash() (+1 more)

### Community 52 - "cache.py"
Cohesion: 0.07
Nodes (73): long_path(), r"""Absolute, normalized, and \\?\-prefixed on Windows. The prefix turns off…, add_ref(), _cap_bytes(), choice_name(), clear(), clear_running(), delete_job() (+65 more)

### Community 53 - "start_job"
Cohesion: 0.14
Nodes (15): BaseModel, ItemRequest, JobRequest, One archive or PDF, start to finish. Phase 8 owns the QUEUE, not this route.…, AC-7: a folder, or an explicit list, through the queue. Exactly one of `dir`…, Resume a paused job, with the settings as they are NOW: the pause was most…, AC-10's payload: one region of one page of one job. The page is addressed by…, Start a batch. Answers with the first status snapshot, immediately. (+7 more)

### Community 54 - "Checks"
Cohesion: 0.15
Nodes (13): _guarded(), main(), [zero-llm] rung 5 must not fire on the spot-fix path., [parallel] concurrent jobs on an EMPTY cache do not fall over the models., Run one section; a crash inside it is ONE red assert, not a dead run. Every…, [flag] the fit flags are RECOMPUTED, and regions.json is write-only for them., [edit] an edit is a translation, and a re-translation never overwrites it., section_edits() (+5 more)

### Community 55 - "section_tier"
Cohesion: 0.10
Nodes (13): page_hash(), Image, SHA-256 of the DECODED pixels, plus mode and size. Mode and size are in the…, LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds. It counts…, Drop `key` if resident., Drop every raster of the page -- enforce_cap's path, one per erased set., Resident decoded bytes in the memory tier. Phase 6's RSS gate reads this., _Tier (+5 more)

### Community 56 - "EraseError"
Cohesion: 0.19
Nodes (13): EraseError, mask(), _model(), probability(), ndarray, RuntimeError, Which PIXELS are text: comic-text-detector's segmentation head. WHY a second…, Boolean (H, W): True where the model reads text ink. (+5 more)

### Community 57 - "translate_item"
Cohesion: 0.08
Nodes (34): exception_handler, post, Request, Response, _bad_settings_response(), cache_clear(), _cache_miss_response(), cancel_job() (+26 more)

### Community 58 - "_no_detect_or_ocr"
Cohesion: 0.16
Nodes (15): _no_detect_or_ocr(), undo(), [cap-wired] the cap is connected to the job, not only to the check., [ingest-llm] the translation cache is counted at the provider., Patch both entrypoints to increment-and-RAISE. Returns (counter, undo).…, [edit-rendered] the edit survives on the PAGE, not only in the file., [route] the HTTP surface: one success over the wire, and named errors., [crossjob] a NEW job_id reads the same pages. The regression's own gate. (+7 more)

### Community 59 - "check_probe.py"
Cohesion: 0.36
Nodes (9): probe_png(), A PNG with `token` painted large and black on white. No prompt text. Built…, attempt(), main(), post(), Phase 0 -- the probe that touches a LIVE endpoint (US-012). Only this file…, Return (status, body) -- never raise on HTTP error., Never echo the live key, whatever the gateway reflected back. (+1 more)

### Community 60 - "_read_page"
Cohesion: 0.19
Nodes (15): PdfPage, _decode_xobject(), _displayed(), _full_page_image(), _is_scan(), Image, The ONE image object covering more than half the page, or None. Exactly one:…, The build order's rule, both halves. Returns the image or None. (+7 more)

### Community 61 - "NeedsAttention"
Cohesion: 0.25
Nodes (14): mergeRetried(), NeedsAttention(), finish(), follow(), retry(), togglePicker(), isFixed(), loadSettings() (+6 more)

### Community 62 - "section_not_text"
Cohesion: 0.25
Nodes (9): _quiet(), Run `fn` with stdout swallowed. The pipeline emits a progress line per stage,…, [not-text] each (lang, model) decides dismissal; legacy nulls are asked again.…, section_not_text(), edit_while_held(), make_legacy(), rasters(), run() (+1 more)

### Community 63 - "skip"
Cohesion: 0.27
Nodes (8): main(), pe_imports(), r"""The native bundle libarchive needs (AC-6's .cbr clause). OFFLINE. uv run…, The DLL names in `path`'s PE import directory. Hand-rolled rather than a…, third_party(), main(), Exit 3 -- unless this is a LIVE skip and MT_REQUIRE_LIVE promotes it. Without…, skip()

### Community 64 - "Node TypeScript Configuration"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 65 - "write_pdf"
Cohesion: 0.20
Nodes (11): PdfReader, PdfWriter, _copy_info(), copy_outline(), _outline_items(), walk(), Flatten pypdf's nested outline into `(depth, title, page index)`. pypdf…, Rebuild the source outline on the writer, page numbers by index. By index and… (+3 more)

### Community 66 - "check_warmup"
Cohesion: 0.16
Nodes (11): no_download(), on_disk(), onnx_session(), On this thread, fetch() raises FetchError('absent') instead of downloading. For…, Whether MANIFEST entry `name` is fully downloaded, by name and size only. No…, An onnxruntime session on the provider select_provider() names. Errors-only…, Load the models every page needs, before the first page asks. Returns what…, warm_models() (+3 more)

### Community 67 - "pdf.py"
Cohesion: 0.11
Nodes (19): gc, img2pdf, PdfDocument, pypdf_generic, _axis_aligned(), detect(), is_pdf(), member_name() (+11 more)

### Community 68 - "redcheck_spotfix.py"
Cohesion: 0.43
Nodes (6): failed_tags(), main(), r"""Phase 3's red-check: sabotage each guarded behaviour, confirm its assert…, Run the gate. MT_REDCHECK tells it the sabotage marker is ours., run_check(), sha256()

### Community 69 - "llm.py"
Cohesion: 0.08
Nodes (28): _decode_reply(), error_kind(), _error_object_kind(), _error_payload(), _from_event_stream(), _moderation_reasons(), ProviderError, RuntimeError (+20 more)

### Community 70 - "load_font"
Cohesion: 0.18
Nodes (12): FreeTypeFont, _draw_line(), load_font(), RuntimeError, _raster_metrics(), A typeset pass that cannot proceed. Named, like every sidecar failure path., One truetype face, cached per size. MT_TYPESET_FONT overrides the search., (overflow_x, overflow_y, clipped_glyphs, offpage_ink_px), read off drawn ink.… (+4 more)

### Community 71 - "Tauri Window Permissions"
Cohesion: 0.33
Nodes (5): description, identifier, permissions, $schema, windows

### Community 72 - "Panel Fixture 007"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/007_0071_0170.png

### Community 73 - "Panel Fixture 010 Upper"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/010_0088_1101.png

### Community 74 - "Panel Fixture 010 Left"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/010_0116_0690.png

### Community 75 - "Panel Fixture 010 Lower"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/010_0486_0975.png

### Community 76 - "Panel Fixture 011"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/011_0670_0103.png

### Community 77 - "Panel Fixture 012 Upper"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/012_0234_0455.png

### Community 78 - "Panel Fixture 012 Center"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/012_0610_0489.png

### Community 79 - "Panel Fixture 012 Left"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/012_0616_0231.png

### Community 80 - "Panel Fixture 012 Right"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/012_0672_0662.png

### Community 81 - "Panel Fixture 012 Lower"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/012_0739_0414.png

### Community 82 - "Panel Fixture 013 Upper"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/013_0357_0947.png

### Community 83 - "Panel Fixture 013 Lower"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/013_0728_0878.png

### Community 84 - "Panel Fixture 014"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/014_0677_0105.png

### Community 85 - "Panel Fixture 015"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/015_0108_0144.png

### Community 86 - "Panel Fixture 017 Upper"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/017_0150_0202.png

### Community 87 - "Panel Fixture 017 Center"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/017_0375_1051.png

### Community 88 - "Panel Fixture 017 Left"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/017_0651_0057.png

### Community 89 - "Panel Fixture 017 Lower"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/017_0713_0872.png

### Community 90 - "Panel Fixture 018"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/018_0679_0091.png

### Community 91 - "Panel Fixture 019"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/019_0091_0707.png

### Community 92 - "Panel Fixture 020"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/020_0086_0204.png

### Community 93 - "Panel Fixture 021 Upper"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/021_0347_0176.png

### Community 94 - "Panel Fixture 021 Lower"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/021_0676_0869.png

### Community 95 - "Panel Fixture 023"
Cohesion: 0.40
Nodes (5): box, page, sha256, size, panels/023_0633_0994.png

### Community 96 - "Fixture Provenance Metadata"
Cohesion: 0.40
Nodes (5): provenance, date, note, volume, written_by

### Community 97 - "Control"
Cohesion: 0.20
Nodes (4): Event, Control, A job's stop signals, handed to every page in place of a bare Event. `is_set()`…, Count a finished page: a success resets the streak, a failure adds to it unless…

### Community 98 - "typeset_page"
Cohesion: 0.22
Nodes (10): _commit(), Fit, ink_style(), Image, ndarray, One region's typeset result. Every field is output-only. `rung` is the RUNG…, Typeset every region of one page. Returns (image, [Fit]). Two-phase by…, INK_PLAIN, INK_DARK or INK_BUSY from the page's gray inside `points`. (+2 more)

### Community 99 - "Scanned PDF Fixture"
Cohesion: 0.67
Nodes (3): Scanned PDF Fixture, Unreadable Scanned PDF Page 1 Image, Unreadable Scanned PDF Page 2 Image

### Community 143 - "check_round_trip"
Cohesion: 0.22
Nodes (10): page_boxes(), page_layout(), Every page's DISPLAYED box in points, `/Rotate` applied. What the output must…, Per page: `(page w, page h, image w, image h)` in displayed points. The image…, check_round_trip(), _flatten(), The product's path: job.run_job, both fixtures, offline., expected.json's [title, page, children] -> (depth, title, page). (+2 more)

### Community 144 - "check_page_slots"
Cohesion: 0.22
Nodes (4): check_page_slots(), __init__(), pages(), [slots] the page window is the PROCESS's, and a failed page stops new ones.…

### Community 145 - "check_cancel.py"
Cohesion: 0.27
Nodes (11): build_inputs(), check_cancel(), check_no_partial(), check_resume(), _eight_page_archive(), events_of(), main(), ARCHIVE_PAGES pages from benign.cbz's three, each with one pixel of its own.… (+3 more)

### Community 146 - "check_erase.py"
Cohesion: 0.27
Nodes (11): _dilate(), _flag(), _in_box(), main(), _outline_through_quad(), _poly_mask(), _pre_2c_fill(), ndarray (+3 more)

### Community 147 - "_Recogniser"
Cohesion: 0.29
Nodes (6): OcrError, ndarray, RuntimeError, A recogniser that cannot run. Named, like every sidecar failure path., One text line -> (text, mean character confidence)., _Recogniser

### Community 148 - "read_raster"
Cohesion: 0.10
Nodes (19): atomic_write(), open_retry(), Yield a handle whose bytes land at `dest` only if the block completes. On any…, `open` with the same bounded retry as `_replace`, for READERS. The other half…, _raster(), _raster_files(), raster_name(), The raster file for the erased region set `kept`; the undigested name for None.… (+11 more)

### Community 149 - "_reset"
Cohesion: 0.28
Nodes (9): clear_tier(), [skipped] "null" is never painted, and a skipped region is the user's to…, [torn] a page directory that lost its raster is a MISS, not a crash., Give a forked cache job B's placement, so its sections can re-render. Each fork…, Point the cache at `cache_dir` and clear every in-process remnant. The tier,…, _reset(), section_skipped(), section_torn() (+1 more)

### Community 150 - "probe.py"
Cohesion: 0.32
Nodes (7): base64, random, attempt(), post(), Phase 0a spike: does the endpoint actually pass images through? Freezes the…, A 4-char token painted large and black on white. No prompt text carries it., token_image()

### Community 151 - "_run_cached_page"
Cohesion: 0.33
Nodes (7): has_page(), has_raster(), Whether the page has any raster on disk, without decoding one., _covering_choice(), One page of an item, through the cache. Called under `_page_lock(h)`. The seven…, The user's choice for the page, when its pair covers every region. "Covers" is…, _run_cached_page()

### Community 152 - "_floor_fits"
Cohesion: 0.33
Nodes (9): _capacity(), _floor_fits(), fits(), _longest(), The largest n in [0, n_max] for which fits(n) holds, given fits is monotone.…, The rung-3 state -- floor, tightened, no inset, no bleed -- as a predicate., The largest character count of `text` that fits at the floor, tightened.…, Rung 5's terminal branch. Returns (placed or None, rendered, reason). Cannot… (+1 more)

### Community 153 - "_wrap_from"
Cohesion: 0.25
Nodes (8): _chord(), _narrowest(), The WIDEST contiguous span of the polygon at scanline y, or None. Contiguous,…, The tightest chord the line's own box spans, clipped to the page raster. A line…, Advance width including tracking, which PIL does not model. Tracking is applied…, Greedy wrap of `words` in slots starting at `top`. None if words remain. A slot…, text_width(), _wrap_from()

### Community 154 - "imports.py"
Cohesion: 0.33
Nodes (6): importlib, load(), main(), Phase 0a spike: can we import the CV components in-process on the pinned stack?…, Import under a RUNNING event loop -- the condition the sidecar imposes., traceback

### Community 155 - "model_dir"
Cohesion: 0.40
Nodes (6): `base`/Komalingo, moving an old-named sibling there if it is the only one.…, under(), model_dir(), Where fetched weights live. Not beside the executable and not in the repo: a…, check_rename(), [rename] MangaTranslator's data directory moves to Komalingo, once, whole. The…

### Community 156 - "launch_drained"
Cohesion: 0.29
Nodes (6): launch(), Popen, Start the exe with its output drained from the first byte. `force_cpu` sets…, launch_drained(), Popen, Popen with stdout (and by default stderr) read continuously by threads.…

### Community 157 - "main"
Cohesion: 0.47
Nodes (6): room_of(), main(), fresh_regions(), ten_pages(), translate_with(), regions()

### Community 158 - "read_bounded"
Cohesion: 0.40
Nodes (3): Reading an HTTP body without letting the read become the failure. Extracted…, Read a response body within `budget` WALL-CLOCK seconds, never raising.…, read_bounded()

## Knowledge Gaps
- **305 isolated node(s):** `expected_json_sha256`, `sha256`, `size`, `sha256`, `size` (+300 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1085 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **44 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Checks` connect `Checks` to `check_pdf.py`, `check_package.py`, `check_spotfix.py`, `check_archives.py`, `check_inpaint.py`, `check_batch.py`, `check_typeset.py`, `check_cancel.py`, `check_cjk.py`, `check_erase.py`, `read_raster`, `_reset`, `json`, `LLMClient`, `StubProvider`, `main`, `os`, `check_group.py`, `check_settings.py`, `main`, `check_id.py`, `check_api.py`, `imaging.py`, `cache.py`, `section_tier`, `_no_detect_or_ocr`, `check_probe.py`, `section_not_text`, `skip`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `LLMClient` connect `LLMClient` to `check_spotfix.py`, `check_inpaint.py`, `check_batch.py`, `check_typeset.py`, `check_cancel.py`, `check_cjk.py`, `_reset`, `StubProvider`, `._parse`, `main`, `os`, `check_group.py`, `main.py`, `retry_page`, `check_id.py`, `Checks`, `translate_item`, `_no_detect_or_ocr`, `check_probe.py`, `section_not_text`, `llm.py`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `ProviderError` connect `llm.py` to `main.py`, `typeset.py`, `retry_page`, `main`, `translate_item`, `LLMClient`, `StubProvider`, `._parse`, `os`, `pipeline.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 33 inferred relationships involving `Checks` (e.g. with `inputs()` and `kinds()`) actually correct?**
  _`Checks` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `LLMClient` (e.g. with `models()` and `retry_pages()`) actually correct?**
  _`LLMClient` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `expected_json_sha256`, `sha256`, `size` to the rest of the system?**
  _305 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `check_package.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12433862433862433 - nodes in this community are weakly interconnected._