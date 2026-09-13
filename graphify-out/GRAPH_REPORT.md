# Graph Report - MangaTranslator  (2026-09-14)

## Corpus Check
- 111 files · ~271,970 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1869 nodes · 3910 edges · 140 communities (95 shown, 41 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 128 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `45c45cf6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pdf.py
- check_package.py
- atomic.py
- Checks
- check_archives.py
- gen_fixtures.py
- lib.rs
- check_inpaint.py
- Page Image Manifest
- package.json
- archive.py
- run_item
- Brand and Language Documentation
- llm.py
- Budget
- check_batch.py
- check_typeset.py
- fetch_fixtures.py
- skip
- describeError
- Job.tsx
- detect.py
- Tauri Application Configuration
- group.py
- inpainter.py
- _run_cached_page
- LLMClient
- check_cjk.py
- cache.py
- api.ts
- read_regions
- mock-tauri.ts
- check_group.py
- check_settings.py
- Frontend TypeScript Configuration
- _dedupe
- job.py
- sidecar/__init__.py
- models.py
- pipeline.py
- unhandled
- typeset.py
- Regression Test Runner
- OcrError
- App.tsx
- Settings.tsx
- Komalingo Brand Assets
- Server
- _decode
- _CountingReader
- imaging.py
- main.tsx
- _dismissed
- section_skipped
- ocr_ja.py
- _Tier
- lifespan
- rewrite_language
- SpotFix.tsx
- check_probe.py
- StubProvider
- Job
- section_clear
- Node TypeScript Configuration
- check_id.py
- _rerender_locked
- Fixture Determinism Check
- redcheck_spotfix.py
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
- warm_models
- main.py
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
- read_translation

## God Nodes (most connected - your core abstractions)
1. `Checks` - 78 edges
2. `long_path()` - 54 edges
3. `LLMClient` - 46 edges
4. `skip()` - 39 edges
5. `StubProvider` - 37 edges
6. `page_dir()` - 34 edges
7. `main()` - 32 edges
8. `Budget` - 29 edges
9. `run()` - 26 edges
10. `panels` - 25 edges

## Surprising Connections (you probably didn't know these)
- `Komalingo Open Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-open-a.png → README.md
- `Komalingo Split Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-split-a.png → README.md
- `section_not_text()` --calls--> `under()`  [INFERRED]
  tests/check_spotfix.py → sidecar/appdir.py
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

## Communities (140 total, 41 thin omitted)

### Community 0 - "pdf.py"
Cohesion: 0.05
Nodes (69): PdfDocument, PdfPage, PdfReader, PdfWriter, _axis_aligned(), _copy_info(), copy_outline(), _decode_xobject() (+61 more)

### Community 1 - "check_package.py"
Cohesion: 0.06
Nodes (57): cache_stats(), health(), Liveness, plus which execution provider this process will run on. The provider…, Where the archive rebuild an edit scheduled has got to. The same dict…, Size, page count and corrections in the page cache, for the Settings card., GET can never shut anything down. A link or an <img> is a GET., repack_status(), shutdown_get() (+49 more)

### Community 2 - "atomic.py"
Cohesion: 0.22
Nodes (8): atomic_write(), r"""The single write protocol. Every file this app produces goes through here.…, Yield a handle whose bytes land at `dest` only if the block completes. On any…, os.replace with a short, bounded retry on Windows sharing violations. Two…, _replace(), The evidence file check_package.py reads back. Atomic like every write., write_regions(), Phase 0 -- the write protocol. Offline, no fixtures, no network. Asserts, from…

### Community 3 - "Checks"
Cohesion: 0.08
Nodes (56): _above_floor(), _archive_edits(), _calibrate(), _call(), _guarded(), main(), _no_detect_or_ocr(), _quiet() (+48 more)

### Community 4 - "check_archives.py"
Cohesion: 0.09
Nodes (50): comicinfo(), pages(), Yield `(ordinal, member, image)` for every decodable page, 1-based. Same…, `(member name, raw bytes)` of the archive's ComicInfo.xml, or None. RAW bytes,…, Repack `entries` -- an iterable of `(member name, bytes)` -- at `dest`. Through…, write_archive(), classify(), What kind of item `path` is, by NAME alone. By name, because classification… (+42 more)

### Community 5 - "gen_fixtures.py"
Cohesion: 0.10
Nodes (43): _archive_page(), _cbz_page(), draw_columns(), draw_lines(), draw_vertical(), gen_archives(), gen_bubbles(), gen_cbz() (+35 more)

### Community 6 - "lib.rs"
Cohesion: 0.09
Nodes (34): AppHandle, CommandChild, Into, Mutex, Option, Result, Self, attempt() (+26 more)

### Community 7 - "check_inpaint.py"
Cohesion: 0.09
Nodes (38): _assert_ink(), _assert_ring(), _assert_step_edge(), _band(), _best_ncc(), _chord_x(), _composite(), _expected_font_px() (+30 more)

### Community 8 - "Page Image Manifest"
Cohesion: 0.05
Nodes (40): sha256, size, sha256, size, sha256, size, sha256, size (+32 more)

### Community 9 - "package.json"
Cohesion: 0.06
Nodes (33): dependencies, react, react-dom, @tauri-apps/api, @tauri-apps/plugin-dialog, @tauri-apps/plugin-opener, devDependencies, @tauri-apps/cli (+25 more)

### Community 10 - "archive.py"
Cohesion: 0.07
Nodes (40): BytesIO, _admit(), detect_format(), _drain(), expected_pages(), _head(), is_archive(), _is_page_name() (+32 more)

### Community 11 - "run_item"
Cohesion: 0.17
Nodes (13): BoundedSemaphore, _check_cancel(), _check_lang(), _page_slots(), One page through all seven stages, in order. Returns the regions record.…, Raise Cancelled if the token is set. `cancel` is anything with is_set() -- a…, Reject a target language that is not a language tag. `lang` is substituted into…, Every page of one archive or PDF, through the cache. Returns the record.… (+5 more)

### Community 12 - "Brand and Language Documentation"
Cohesion: 0.06
Nodes (31): Komalingo Open Concept A Brand Exploration, Komalingo Split Concept A Brand Exploration, Honorifics and register in the Indonesian output (AC-4), Register, The rule, The table, What stays as it is, What the gate holds (+23 more)

### Community 13 - "llm.py"
Cohesion: 0.15
Nodes (19): _decode_reply(), _from_event_stream(), image_data_url(), ProviderError, RuntimeError, OpenAI-compatible client. Owns the concurrency cap and the error contract.…, Carries the provider's own words to the UI. See AC-8., A 2xx body as the dict the OpenAI shape describes, or a ProviderError. Two… (+11 more)

### Community 14 - "Budget"
Cohesion: 0.08
Nodes (26): PathLike, (name, safety.Member) for every zip entry, in archive order., Plain tar only. A compressed one goes through `_tar_single_pass`. `"r:"`, never…, _sevenzip_entries(), _tar_entries(), _zip_entries(), Budget, is_comicinfo() (+18 more)

### Community 15 - "check_batch.py"
Cohesion: 0.11
Nodes (30): The files in `directory`, top level only, in natural order. Top level only: a…, scan(), build_folder(), _chats_with_image(), check_cancel(), check_cap(), check_image_item_id(), check_page_slots() (+22 more)

### Community 16 - "check_typeset.py"
Cohesion: 0.13
Nodes (28): ellipse_points(), The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.…, The job summary AC-1 requires: which regions were compromised, which failed.…, summary(), _batching_and_spotfix(), _check_page(), _compare_metrics(), _edge_cases() (+20 more)

### Community 17 - "fetch_fixtures.py"
Cohesion: 0.15
Nodes (22): build_manifest(), _compare(), image_size(), load_manifest(), main(), print_report(), What verify() found, split so a caller can assert on each part. `expected` is…, A mismatch line for one manifest entry, or None when the bytes match. (+14 more)

### Community 18 - "skip"
Cohesion: 0.16
Nodes (18): emitted_stages(), item_totals(), main(), Phase 0 -- the host/sidecar IPC contract (US-011). OFFLINE (US-003 stub). **Why…, Run one page as a CHILD PROCESS and read the stages off its stdout. In-process…, Run a 3-page .cbz as a CHILD PROCESS: the `total` on its lines, and the pages…, main(), Phase 0 -- the seven-stage pipeline and its progress contract (US-006).… (+10 more)

### Community 19 - "describeError"
Cohesion: 0.27
Nodes (10): runFolder(), runItem(), describeError(), isApiError(), isInternal(), loadSettings(), Job(), cancel() (+2 more)

### Community 20 - "Job.tsx"
Cohesion: 0.17
Nodes (13): Alert(), ICON, Tone, Icon(), IconName, PATHS, LABEL, ProgressBar() (+5 more)

### Community 21 - "detect.py"
Cohesion: 0.09
Nodes (34): Region, _as_bgr(), detect(), DetectError, _glyph_px(), _input_size(), _inverse(), _model() (+26 more)

### Community 22 - "Tauri Application Configuration"
Cohesion: 0.08
Nodes (24): app, security, windows, enable, scope, build, beforeBuildCommand, beforeDevCommand (+16 more)

### Community 23 - "group.py"
Cohesion: 0.14
Nodes (19): bbox(), convex_hull(), glyph_unit(), group(), _inside(), merge(), neighbours(), Group column-level detections into one region per bubble. Phase 2b. WHY this… (+11 more)

### Community 24 - "inpainter.py"
Cohesion: 0.07
Nodes (47): _crops(), erase(), _fill(), fill_white(), _flat(), _flat_surround(), _inpaint(), _lama() (+39 more)

### Community 25 - "_run_cached_page"
Cohesion: 0.13
Nodes (27): _bbox(), _box(), _changed_in_polygon(), _deliver(), detect(), emit(), expecting(), inpaint() (+19 more)

### Community 26 - "LLMClient"
Cohesion: 0.12
Nodes (11): glossary_text(), LLMClient, probe_token(), The glossary block for `lang`, or "" when the target has none., The only way out to the provider. _request holds the gate for the call, on the…, Every model the provider reports, in the provider's own order, as {"id",…, {region_id: text}. A JSON null stays None -- see NOT_TEXT_INSTRUCTION. None and…, All regions of one page. One request unless the page is huge. Returns… (+3 more)

### Community 27 - "check_cjk.py"
Cohesion: 0.15
Nodes (20): _blank_and_ja(), _cache(), _centroid(), _fit(), _load(), main(), _ocr(), Phase 4 -- Chinese and Korean through PP-OCRv5 (AC-3). OFFLINE after first… (+12 more)

### Community 28 - "cache.py"
Cohesion: 0.10
Nodes (49): long_path(), r"""Absolute, normalized, and \\?\-prefixed on Windows. The prefix turns off…, _cap_bytes(), clear(), delete_job(), _dir_size(), disk_bytes(), drop_ref() (+41 more)

### Community 29 - "api.ts"
Cohesion: 0.14
Nodes (16): PathField(), ApiError, CacheClearResult, DismissedRegion, JobItem, PageRecord, Progress, Source (+8 more)

### Community 30 - "read_regions"
Cohesion: 0.29
Nodes (7): The cache root. MT_CACHE_DIR wins, so tests never touch the real one., The cached record, or None. Touches the directory -- see ``touch``., read_regions(), root(), main(), [layout] content-keyed page directories, job-keyed placement only., section_layout()

### Community 31 - "mock-tauri.ts"
Cohesion: 0.14
Nodes (18): api(), Callback, callbacks, emit(), fakePage(), invoke(), jobs, listeners (+10 more)

### Community 32 - "check_group.py"
Cohesion: 0.14
Nodes (24): _bubble_of(), _ellipse_mask(), _fixture(), _geometry(), _ink(), _largest(), main(), _mask() (+16 more)

### Community 33 - "check_settings.py"
Cohesion: 0.43
Nodes (6): main(), Phase 0 -- the Settings UI and the IPC client (US-009). OFFLINE. The frontend…, Source with comments removed. The point of the whole file: an assert that…, read(), strip_comments(), walk_src()

### Community 34 - "Frontend TypeScript Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+10 more)

### Community 35 - "_dedupe"
Cohesion: 0.50
Nodes (4): _dedupe(), One quad per piece of text: of two that _same_text says are one line or column…, Do two bboxes cover the same line or column? See _SAME_SPAN., _same_text()

### Community 36 - "job.py"
Cohesion: 0.10
Nodes (24): Event, _is_page(), members(), _natural_key(), pages(), r"""Read-only CBZ page enumeration. No repack, no safety budget, no other…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Streamed…, Sort key for a full archive member path, digit-aware and segment-wise. Segments… (+16 more)

### Community 37 - "sidecar/__init__.py"
Cohesion: 0.13
Nodes (17): _bsdtar(), bundled(), ensure_libarchive(), NativeMissing, Exception, r"""The native libraries the sidecar needs and pip cannot deliver (AC-6, .cbr).…, A native dependency could not be installed, with a named reason., Whether build/libarchive already holds the whole closure. (+9 more)

### Community 38 - "models.py"
Cohesion: 0.10
Nodes (29): The app's per-user data directory, and the one-time move from its old name. The…, `base`/Komalingo, moving an old-named sibling there if it is the only one.…, under(), ensure(), _ensure_directory(), fetch(), FetchError, _free_space() (+21 more)

### Community 39 - "pipeline.py"
Cohesion: 0.15
Nodes (17): Container readers. One module per format, and each one reads only. Phase 3…, _container(), flush_repacks(), item_dir(), _member_dest(), The seven-stage pipeline: detect, ocr, translate, inpaint, render, encode,…, The item's archive, rebuilt from the loose pages already on disk. What…, Rebuild the item's archive soon, on a worker thread. Returns the status.… (+9 more)

### Community 40 - "unhandled"
Cohesion: 0.29
Nodes (7): exception_handler, Request, Exception, The last envelope. Every other error path in this file is deliberate; this one…, POST + correct nonce + loopback client, or the process stays up. Every…, shutdown(), unhandled()

### Community 41 - "typeset.py"
Cohesion: 0.06
Nodes (59): FreeTypeFont, as_points(), The shared Region type: detect.py's output, typeset.py's input. Defined here…, Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.…, _bbox(), _capacity(), _chord(), _commit() (+51 more)

### Community 42 - "Regression Test Runner"
Cohesion: 0.20
Nodes (16): append_record(), assert_interpreter(), discover(), env_class(), harvest_metrics(), last_status(), load_records(), main() (+8 more)

### Community 43 - "OcrError"
Cohesion: 0.29
Nodes (6): OcrError, ndarray, RuntimeError, A recogniser that cannot run. Named, like every sidecar failure path., One text line -> (text, mean character confidence)., _Recogniser

### Community 44 - "App.tsx"
Cohesion: 0.19
Nodes (13): App(), exitMessage(), frontPage(), loadTheme(), SidecarState, stageWord(), Theme, THEMES (+5 more)

### Community 45 - "Settings.tsx"
Cohesion: 0.15
Nodes (18): ModelCombobox, ModelComboboxHandle, api, CacheStats, displayPath(), ModelInfo, ProviderSettings, saveSettings() (+10 more)

### Community 46 - "Komalingo Brand Assets"
Cohesion: 0.13
Nodes (15): Komalingo Light-Tile App Icon PNG, Komalingo Dark-Tile App Icon PNG, Komalingo Dark-Tile App Icon, Komalingo Light-Tile App Icon, Komalingo Lockup PNG, Komalingo Lockup for Light Backgrounds, Komalingo Lockup for Dark Backgrounds, Komalingo Lockup on Dark PNG (+7 more)

### Community 49 - "_CountingReader"
Cohesion: 0.11
Nodes (12): _CountingReader, _libarchive(), libarchive_path(), LibarchiveMissing, Exception, _rar_entries(), _rar_payloads(), No usable libarchive, so the RAR read path cannot run. A named exception rather… (+4 more)

### Community 50 - "imaging.py"
Cohesion: 0.16
Nodes (17): encode(), output_path(), Image, Encode policy. The only place in the app that calls Image.save. Pillow silently…, Drop the GPS IFD, keep every other tag byte-identical., Encode to bytes in `fmt`, carrying metadata from `src` (default: img)., Destination path whose extension matches the SOURCE format. Named off the…, Encode `img` in the source image's format and write it atomically. Format comes… (+9 more)

### Community 51 - "main.tsx"
Cohesion: 0.21
Nodes (10): react, ErrorBoundary, Props, State, installGlobalReporting(), reportError(), boot(), dismissSplash() (+2 more)

### Community 52 - "_dismissed"
Cohesion: 0.14
Nodes (14): is_null_word(), The instruction's null, written as the STRING "null". Measured on a real…, _apply_translations(), dismiss(), _load_translations(), _pair_decisions(), punctuation_only(), Is there anything here a translator could change? A region that reads as… (+6 more)

### Community 53 - "section_skipped"
Cohesion: 0.14
Nodes (16): open_retry(), `open` with the same bounded retry as `_replace`, for READERS. The other half…, clear_tier(), page_hash(), Image, raster_name(), SHA-256 of the DECODED pixels, plus mode and size. Mode and size are in the…, Resident decoded bytes in the memory tier. Phase 6's RSS gate reads this. (+8 more)

### Community 54 - "ocr_ja.py"
Cohesion: 0.15
Nodes (18): lines(), ocr(), Chinese and Korean OCR: PP-OCRv5 text-line recognition through onnxruntime.…, The parts that are text LINES, each read once. The detector answers per line…, Rows top to bottom (columns right to left), and WITHIN a row, left to right…, Read one region: its line parts, recognised and joined in reading order., _reading_order(), _as_image() (+10 more)

### Community 55 - "_Tier"
Cohesion: 0.20
Nodes (4): LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds. It counts…, Drop `key` if resident., Drop every raster of the page -- enforce_cap's path, one per erased set., _Tier

### Community 56 - "lifespan"
Cohesion: 0.29
Nodes (8): FastAPI, lifespan(), r"""Repair leaked cache references before anything can be evicted against them.…, pipeline.warm_models on a daemon thread; the lifespan never waits on it.…, Exit the moment stdin closes -- which, under Tauri, means the parent died.…, start_warmup(), watch_parent(), Thread

### Community 58 - "SpotFix.tsx"
Cohesion: 0.36
Nodes (9): RepackStatus, inPolygon(), laidInto(), pageSrc(), severity(), SpotFix(), pick(), select() (+1 more)

### Community 59 - "check_probe.py"
Cohesion: 0.36
Nodes (9): probe_png(), A PNG with `token` painted large and black on white. No prompt text. Built…, attempt(), main(), post(), Phase 0 -- the probe that touches a LIVE endpoint (US-012). Only this file…, Return (status, body) -- never raise on HTTP error., Never echo the live key, whatever the gateway reflected back. (+1 more)

### Community 61 - "StubProvider"
Cohesion: 0.11
Nodes (21): build_inputs(), check_cancel(), check_no_partial(), check_resume(), _eight_page_archive(), events_of(), main(), ARCHIVE_PAGES pages from benign.cbz's three, each with one pixel of its own.… (+13 more)

### Community 62 - "Job"
Cohesion: 0.18
Nodes (4): Job, Every item, through the boundary, on `workers` threads. Never raises.…, Block until every item has a terminal status. False on timeout., AC-9, the half the product had never wired: probe once per job. Before this,…

### Community 63 - "section_clear"
Cohesion: 0.14
Nodes (25): add_ref(), clear_running(), get_placement(), item_placements(), job_dir(), _job_key(), jobs_root(), mark_running() (+17 more)

### Community 64 - "Node TypeScript Configuration"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 65 - "check_id.py"
Cohesion: 0.18
Nodes (17): _glossary_doc(), _live(), main(), _payload_text(), _prompt(), Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always; live…, Which of the line's marked honorifics appear in `out`, and which forbidden…, _renderings() (+9 more)

### Community 66 - "_rerender_locked"
Cohesion: 0.12
Nodes (16): CacheMiss, Cancelled, _content_region(), _model_id(), _page_lock(), _persist(), Exception, Lock (+8 more)

### Community 68 - "Fixture Determinism Check"
Cohesion: 0.43
Nodes (6): generate(), main(), Phase 0a gate: two regenerations from an empty tree are byte-identical. uv run…, Relative-path -> sha256 for everything under the generated subdirs., sha256(), snapshot()

### Community 70 - "redcheck_spotfix.py"
Cohesion: 0.43
Nodes (6): failed_tags(), main(), r"""Phase 3's red-check: sabotage each guarded behaviour, confirm its assert…, Run the gate. MT_REDCHECK tells it the sabotage marker is ours., run_check(), sha256()

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

### Community 97 - "warm_models"
Cohesion: 0.25
Nodes (8): no_download(), On this thread, fetch() raises FetchError('absent') instead of downloading. For…, Load the models every page needs, before the first page asks. Returns what…, warm_models(), load(), main(), Phase 0a spike: can we import the CV components in-process on the pinned stack?…, Import under a RUNNING event loop -- the condition the sidecar imposes.

### Community 98 - "main.py"
Cohesion: 0.08
Nodes (45): BaseModel, post, Response, ValueError, The configured settings cannot be used. Not the provider's fault. A ValueError…, SettingsError, _bad_settings_response(), cache_clear() (+37 more)

### Community 99 - "Scanned PDF Fixture"
Cohesion: 0.67
Nodes (3): Scanned PDF Fixture, Unreadable Scanned PDF Page 1 Image, Unreadable Scanned PDF Page 2 Image

### Community 143 - "read_translation"
Cohesion: 0.33
Nodes (7): model_slug(), A filesystem-safe name for a model id that two ids cannot share. The readable…, ``{region_id: {"text": str, "edited": bool}}`` for one (lang, model)., Merge a fresh translation in, and never overwrite an ``edited`` entry.…, read_translation(), translation_name(), write_translation()

## Knowledge Gaps
- **294 isolated node(s):** `expected_json_sha256`, `sha256`, `size`, `sha256`, `size` (+289 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 916 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **41 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Checks` connect `Checks` to `pdf.py`, `check_package.py`, `atomic.py`, `check_archives.py`, `check_inpaint.py`, `llm.py`, `check_batch.py`, `check_typeset.py`, `skip`, `inpainter.py`, `check_cjk.py`, `cache.py`, `read_regions`, `check_group.py`, `check_settings.py`, `sidecar/__init__.py`, `models.py`, `imaging.py`, `section_skipped`, `check_probe.py`, `StubProvider`, `section_clear`, `check_id.py`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `skip()` connect `skip` to `check_group.py`, `check_id.py`, `check_package.py`, `pdf.py`, `check_archives.py`, `sidecar/__init__.py`, `Checks`, `check_inpaint.py`, `check_probe.py`, `check_batch.py`, `check_typeset.py`, `fetch_fixtures.py`, `inpainter.py`, `check_cjk.py`, `StubProvider`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `LLMClient` connect `LLMClient` to `check_group.py`, `check_id.py`, `main.py`, `Checks`, `check_inpaint.py`, `check_probe.py`, `llm.py`, `check_batch.py`, `check_typeset.py`, `skip`, `_dismissed`, `section_skipped`, `check_cjk.py`, `StubProvider`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `Checks` (e.g. with `_call()` and `_guarded()`) actually correct?**
  _`Checks` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `LLMClient` (e.g. with `models()` and `section_skipped()`) actually correct?**
  _`LLMClient` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `expected_json_sha256`, `sha256`, `size` to the rest of the system?**
  _294 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pdf.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05352112676056338 - nodes in this community are weakly interconnected._