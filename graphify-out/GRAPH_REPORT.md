# Graph Report - MangaTranslator  (2026-09-14)

## Corpus Check
- 111 files · ~271,970 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1875 nodes · 3909 edges · 154 communities (105 shown, 45 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 110 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `04e0d152`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pdf.py
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
- _run_pages
- Brand and Language Documentation
- RuntimeError
- Budget
- check_batch.py
- check_typeset.py
- fetch_fixtures.py
- Checks
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
- EraseError
- mock-tauri.ts
- check_group.py
- repack_extras
- Frontend TypeScript Configuration
- StubProvider
- long_path
- load_font
- models.py
- pipeline.py
- Response
- typeset.py
- Regression Test Runner
- translate
- App.tsx
- Settings.tsx
- Komalingo Brand Assets
- check_models.py
- typeset_page
- _CountingReader
- imaging.py
- main.tsx
- _apply_translations
- tier_bytes
- ocr_ja.py
- _Tier
- lifespan
- check_erase.py
- SpotFix.tsx
- check_probe.py
- ocr
- check_cancel.py
- Job
- section_clear
- Node TypeScript Configuration
- check_id.py
- rerender
- detect
- Fixture Determinism Check
- _rerender_locked
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
- BaseModel
- read_translation
- _floor_fits
- _wrap_from
- _member_dest
- _bad_settings_response
- SettingsError
- _above_floor
- ValueError
- Exception
- Image
- Lock

## God Nodes (most connected - your core abstractions)
1. `long_path()` - 54 edges
2. `Checks` - 50 edges
3. `LLMClient` - 46 edges
4. `skip()` - 38 edges
5. `StubProvider` - 36 edges
6. `page_dir()` - 34 edges
7. `main()` - 32 edges
8. `Budget` - 29 edges
9. `_reset()` - 25 edges
10. `run()` - 25 edges

## Surprising Connections (you probably didn't know these)
- `Komalingo Open Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-open-a.png → README.md
- `Komalingo Split Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-split-a.png → README.md
- `main()` --uses--> `ProviderError`  [INFERRED]
  tests/check_ipc.py → sidecar/llm.py
- `section_skipped()` --uses--> `LLMClient`  [INFERRED]
  tests/check_spotfix.py → sidecar/llm.py
- `section_not_text()` --calls--> `under()`  [INFERRED]
  tests/check_spotfix.py → sidecar/appdir.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Komalingo Brand Asset Family** — brand_komalingo_icon_dark_dark_app_icon, brand_komalingo_icon_light_app_icon, brand_komalingo_lockup_on_dark_dark_lockup, brand_komalingo_lockup_light_lockup, brand_komalingo_mark_on_dark_dark_mark, brand_komalingo_mark_light_mark [EXTRACTED 0.99]
- **Local Manga Translation Stack** — readme_translation_pipeline, readme_manga_ocr, readme_pp_ocrv5, readme_pp_ocrv3_db, readme_comic_text_detector, readme_lama_manga [EXTRACTED 1.00]
- **Komalingo Brand Concept Explorations** — brand_explorations_concept_open_a_image, brand_explorations_concept_split_a_image [INFERRED 0.90]
- **Scanned PDF Fixture and Rendered Pages** — fixtures_pdf_scan_document, fixtures_pdf_scan_p1_image, fixtures_pdf_scan_p2_image [INFERRED 0.95]

## Communities (154 total, 45 thin omitted)

### Community 0 - "pdf.py"
Cohesion: 0.05
Nodes (69): PdfDocument, PdfPage, PdfReader, PdfWriter, _axis_aligned(), _copy_info(), copy_outline(), _decode_xobject() (+61 more)

### Community 1 - "check_package.py"
Cohesion: 0.06
Nodes (55): health(), Liveness, plus which execution provider this process will run on. The provider…, Where the archive rebuild an edit scheduled has got to. The same dict…, GET can never shut anything down. A link or an <img> is a GET., repack_status(), shutdown_get(), Return (execution_provider, reason). The reason is empty ONLY when CUDA was…, select_provider() (+47 more)

### Community 2 - "run_item"
Cohesion: 0.11
Nodes (16): Event, output_path(), Where the repacked archive lands. Same extension, except RAR -> .cbz. The…, disambiguate(), Item, Lock, Process one item. Never raises. `cancel` (Phase 9) is the job's token, handed…, Give every item in a job a DISTINCT item_id. Mutates and returns them.… (+8 more)

### Community 3 - "check_spotfix.py"
Cohesion: 0.10
Nodes (54): Checks, clear_tier(), _archive_edits(), _call(), _guarded(), main(), _no_detect_or_ocr(), _quiet() (+46 more)

### Community 4 - "check_archives.py"
Cohesion: 0.10
Nodes (50): comicinfo(), detect_format(), pages(), The container family of `path`, from its bytes. The tar test is last and is…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Same…, `(member name, raw bytes)` of the archive's ComicInfo.xml, or None. RAW bytes,…, Repack `entries` -- an iterable of `(member name, bytes)` -- at `dest`. Through…, write_archive() (+42 more)

### Community 5 - "gen_fixtures.py"
Cohesion: 0.09
Nodes (46): ellipse_points(), The shared Region type: detect.py's output, typeset.py's input. Defined here…, The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.…, _archive_page(), _cbz_page(), draw_columns(), draw_lines(), draw_vertical() (+38 more)

### Community 6 - "lib.rs"
Cohesion: 0.09
Nodes (34): AppHandle, CommandChild, Into, Mutex, Option, Result, Self, attempt() (+26 more)

### Community 7 - "check_inpaint.py"
Cohesion: 0.08
Nodes (42): One page through all seven stages, in order. Returns the regions record.…, run_page(), _assert_ink(), _assert_ring(), _assert_step_edge(), _band(), _best_ncc(), _chord_x() (+34 more)

### Community 8 - "Page Image Manifest"
Cohesion: 0.05
Nodes (40): sha256, size, sha256, size, sha256, size, sha256, size (+32 more)

### Community 9 - "package.json"
Cohesion: 0.06
Nodes (33): dependencies, react, react-dom, @tauri-apps/api, @tauri-apps/plugin-dialog, @tauri-apps/plugin-opener, devDependencies, @tauri-apps/cli (+25 more)

### Community 10 - "archive.py"
Cohesion: 0.06
Nodes (35): BytesIO, _decode(), _drain(), expected_pages(), _head(), is_archive(), _libarchive(), libarchive_path() (+27 more)

### Community 11 - "_run_pages"
Cohesion: 0.40
Nodes (5): BoundedSemaphore, _page_slots(), The process's page semaphore, sized by PAGE_WINDOW as it is NOW (a check can…, Run an item's pages concurrently. Returns records in page order. The reader…, _run_pages()

### Community 12 - "Brand and Language Documentation"
Cohesion: 0.06
Nodes (31): Komalingo Open Concept A Brand Exploration, Komalingo Split Concept A Brand Exploration, Honorifics and register in the Indonesian output (AC-4), Register, The rule, The table, What stays as it is, What the gate holds (+23 more)

### Community 14 - "Budget"
Cohesion: 0.08
Nodes (25): PathLike, (name, safety.Member) for every zip entry, in archive order., Plain tar only. A compressed one goes through `_tar_single_pass`. `"r:"`, never…, _tar_entries(), _zip_entries(), Budget, is_comicinfo(), Member (+17 more)

### Community 15 - "check_batch.py"
Cohesion: 0.11
Nodes (30): The files in `directory`, top level only, in natural order. Top level only: a…, scan(), build_folder(), _chats_with_image(), check_cancel(), check_cap(), check_image_item_id(), check_page_slots() (+22 more)

### Community 16 - "check_typeset.py"
Cohesion: 0.14
Nodes (24): The job summary AC-1 requires: which regions were compromised, which failed.…, summary(), _batching_and_spotfix(), _check_page(), _compare_metrics(), _edge_cases(), _ink(), _ink_in_polygon() (+16 more)

### Community 17 - "fetch_fixtures.py"
Cohesion: 0.12
Nodes (28): main(), Phase 1 -- OCR truth on real vertical Japanese (AC-2). OFFLINE. Runs manga-ocr…, build_manifest(), _compare(), image_size(), load_manifest(), main(), print_report() (+20 more)

### Community 18 - "Checks"
Cohesion: 0.10
Nodes (25): main(), Phase 0 -- the write protocol. Offline, no fixtures, no network. Asserts, from…, build_source(), main(), Phase 0 -- encode policy. Offline, no network. Asserts, from the build order:…, A source image carrying an ICC profile and EXIF with and without GPS., main(), pe_imports() (+17 more)

### Community 19 - "describeError"
Cohesion: 0.27
Nodes (10): runFolder(), runItem(), describeError(), isApiError(), isInternal(), loadSettings(), Job(), cancel() (+2 more)

### Community 20 - "Job.tsx"
Cohesion: 0.17
Nodes (13): Alert(), ICON, Tone, Icon(), IconName, PATHS, LABEL, ProgressBar() (+5 more)

### Community 21 - "detect.py"
Cohesion: 0.11
Nodes (27): _as_bgr(), _dedupe(), DetectError, _input_size(), _inverse(), _model(), ndarray, RuntimeError (+19 more)

### Community 22 - "Tauri Application Configuration"
Cohesion: 0.08
Nodes (24): app, security, windows, enable, scope, build, beforeBuildCommand, beforeDevCommand (+16 more)

### Community 23 - "group.py"
Cohesion: 0.13
Nodes (21): separated(i, j): does ink run across the gap between two adjacent quads? The…, _separator(), bbox(), convex_hull(), glyph_unit(), group(), _inside(), merge() (+13 more)

### Community 24 - "inpainter.py"
Cohesion: 0.13
Nodes (23): _crops(), erase(), _fill(), fill_white(), _flat(), _flat_surround(), _inpaint(), _lama() (+15 more)

### Community 25 - "_run_cached_page"
Cohesion: 0.16
Nodes (22): Image, _deliver(), detect(), emit(), encode_and_write(), expecting(), inpaint(), page_context_image() (+14 more)

### Community 26 - "LLMClient"
Cohesion: 0.07
Nodes (32): RuntimeError, _decode_reply(), _from_event_stream(), glossary_text(), image_data_url(), LLMClient, probe_token(), ProviderError (+24 more)

### Community 27 - "check_cjk.py"
Cohesion: 0.17
Nodes (18): _blank_and_ja(), _cache(), _centroid(), _fit(), _load(), main(), _ocr(), Phase 4 -- Chinese and Korean through PP-OCRv5 (AC-3). OFFLINE after first… (+10 more)

### Community 28 - "cache.py"
Cohesion: 0.08
Nodes (54): open_retry(), `open` with the same bounded retry as `_replace`, for READERS. The other half…, _cap_bytes(), clear(), delete_job(), _dir_size(), disk_bytes(), drop_ref() (+46 more)

### Community 29 - "api.ts"
Cohesion: 0.14
Nodes (16): PathField(), ApiError, CacheClearResult, DismissedRegion, JobItem, PageRecord, Progress, Source (+8 more)

### Community 30 - "EraseError"
Cohesion: 0.19
Nodes (13): EraseError, mask(), _model(), probability(), ndarray, RuntimeError, Which PIXELS are text: comic-text-detector's segmentation head. WHY a second…, Boolean (H, W): True where the model reads text ink. (+5 more)

### Community 31 - "mock-tauri.ts"
Cohesion: 0.14
Nodes (18): api(), Callback, callbacks, emit(), fakePage(), invoke(), jobs, listeners (+10 more)

### Community 32 - "check_group.py"
Cohesion: 0.13
Nodes (26): _box(), The region's bounding box in thousandths of the page, for the vision model.…, _bubble_of(), _ellipse_mask(), _fixture(), _geometry(), _ink(), _largest() (+18 more)

### Community 33 - "repack_extras"
Cohesion: 0.20
Nodes (14): _admit(), _is_page_name(), _lazy(), Whether a member name is a page CANDIDATE. Identical rule to read_cbz., gz" | "bz2" | "xz" for a whole-file-compressed tar, "" for a plain one. This…, Run every member past the budget; return the page candidates to stream. Every…, Compressed tar: admit and read in ONE forward pass over the stream. Two…, `(page names in natural order, name -> Member, payload source)`. The one place… (+6 more)

### Community 34 - "Frontend TypeScript Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+10 more)

### Community 35 - "StubProvider"
Cohesion: 0.18
Nodes (9): emitted_stages(), item_totals(), main(), Phase 0 -- the host/sidecar IPC contract (US-011). OFFLINE (US-003 stub). **Why…, Run one page as a CHILD PROCESS and read the stages off its stdout. In-process…, Run a 3-page .cbz as a CHILD PROCESS: the `total` on its lines, and the pages…, _load_fixtures(), Usable as a context manager; `.url` is the OpenAI-compatible base URL. (+1 more)

### Community 36 - "long_path"
Cohesion: 0.07
Nodes (39): atomic_write(), long_path(), r"""The single write protocol. Every file this app produces goes through here.…, Yield a handle whose bytes land at `dest` only if the block completes. On any…, r"""Absolute, normalized, and \\?\-prefixed on Windows. The prefix turns off…, os.replace with a short, bounded retry on Windows sharing violations. Two…, _replace(), _is_page() (+31 more)

### Community 37 - "load_font"
Cohesion: 0.18
Nodes (12): FreeTypeFont, _draw_line(), load_font(), RuntimeError, _raster_metrics(), A typeset pass that cannot proceed. Named, like every sidecar failure path., One truetype face, cached per size. MT_TYPESET_FONT overrides the search., (overflow_x, overflow_y, clipped_glyphs, offpage_ink_px), read off drawn ink.… (+4 more)

### Community 38 - "models.py"
Cohesion: 0.16
Nodes (18): ensure(), _ensure_directory(), fetch(), FetchError, _free_space(), model_dir(), on_disk(), RuntimeError (+10 more)

### Community 39 - "pipeline.py"
Cohesion: 0.21
Nodes (11): Container readers. One module per format, and each one reads only. Phase 3…, _container(), flush_repacks(), The seven-stage pipeline: detect, ocr, translate, inpaint, render, encode,…, The item's archive, rebuilt from the loose pages already on disk. What…, Rebuild the item's archive soon, on a worker thread. Returns the status.…, Every pending repack, now, on this thread. For the exit paths. The app does not…, The container family of `src_path`, by signature: an archive family or… (+3 more)

### Community 40 - "Response"
Cohesion: 0.22
Nodes (10): exception_handler, Request, Response, _cache_miss_response(), Exception, The last envelope. Every other error path in this file is deliberate; this one…, 404 with a named kind. A missing cache entry is not a server fault. `kind` is…, POST + correct nonce + loopback client, or the process stays up. Every… (+2 more)

### Community 41 - "typeset.py"
Cohesion: 0.20
Nodes (16): _bbox(), _edge_adjacent(), floor_px(), _has_orphan(), _inset_points(), _ladder(), _layout(), max_font_px() (+8 more)

### Community 42 - "Regression Test Runner"
Cohesion: 0.20
Nodes (16): append_record(), assert_interpreter(), discover(), env_class(), harvest_metrics(), last_status(), load_records(), main() (+8 more)

### Community 43 - "translate"
Cohesion: 0.21
Nodes (12): _client(), _missing_source_response(), _probed(), _provider_response(), AC-8's envelope, built by json.dumps and never by an f-string. The body is the…, Run the vision probe for a route-built client; return its warning or "". The…, Build an LLMClient, or None for the offline placeholder path. Called INSIDE…, 404 naming the path when src_path is not a file; None when it is. Checked… (+4 more)

### Community 44 - "App.tsx"
Cohesion: 0.19
Nodes (13): App(), exitMessage(), frontPage(), loadTheme(), SidecarState, stageWord(), Theme, THEMES (+5 more)

### Community 45 - "Settings.tsx"
Cohesion: 0.15
Nodes (18): ModelCombobox, ModelComboboxHandle, api, CacheStats, displayPath(), ModelInfo, ProviderSettings, saveSettings() (+10 more)

### Community 46 - "Komalingo Brand Assets"
Cohesion: 0.13
Nodes (15): Komalingo Light-Tile App Icon PNG, Komalingo Dark-Tile App Icon PNG, Komalingo Dark-Tile App Icon, Komalingo Light-Tile App Icon, Komalingo Lockup PNG, Komalingo Lockup for Light Backgrounds, Komalingo Lockup for Dark Backgrounds, Komalingo Lockup on Dark PNG (+7 more)

### Community 47 - "check_models.py"
Cohesion: 0.13
Nodes (13): The app's per-user data directory, and the one-time move from its old name. The…, `base`/Komalingo, moving an old-named sibling there if it is the only one.…, under(), onnx_session(), An onnxruntime session on the provider select_provider() names. Errors-only…, check_rename(), check_warmup(), main() (+5 more)

### Community 48 - "typeset_page"
Cohesion: 0.18
Nodes (12): as_points(), Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.…, _commit(), Fit, ink_style(), Image, ndarray, One region's typeset result. Every field is output-only. `rung` is the RUNG… (+4 more)

### Community 50 - "imaging.py"
Cohesion: 0.31
Nodes (9): encode(), Image, Encode policy. The only place in the app that calls Image.save. Pillow silently…, Drop the GPS IFD, keep every other tag byte-identical., Encode to bytes in `fmt`, carrying metadata from `src` (default: img)., Encode `img` in the source image's format and write it atomically. Format comes…, save(), _save_kwargs() (+1 more)

### Community 51 - "main.tsx"
Cohesion: 0.21
Nodes (10): react, ErrorBoundary, Props, State, installGlobalReporting(), reportError(), boot(), dismissSplash() (+2 more)

### Community 52 - "_apply_translations"
Cohesion: 0.25
Nodes (8): is_null_word(), The instruction's null, written as the STRING "null". Measured on a real…, _apply_translations(), _load_translations(), _pair_decisions(), The page's regions with this (lang, model)'s translations and nulls on them. A…, Fill translations from the cache. True only if EVERY region was covered., Fill translations from the cache. Returns the ids still to translate. A stored…

### Community 54 - "ocr_ja.py"
Cohesion: 0.10
Nodes (24): lines(), ocr(), OcrError, ndarray, RuntimeError, Chinese and Korean OCR: PP-OCRv5 text-line recognition through onnxruntime.…, The parts that are text LINES, each read once. The detector answers per line…, Rows top to bottom (columns right to left), and WITHIN a row, left to right… (+16 more)

### Community 55 - "_Tier"
Cohesion: 0.20
Nodes (4): LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds. It counts…, Drop `key` if resident., Drop every raster of the page -- enforce_cap's path, one per erased set., _Tier

### Community 56 - "lifespan"
Cohesion: 0.29
Nodes (8): FastAPI, lifespan(), r"""Repair leaked cache references before anything can be evicted against them.…, pipeline.warm_models on a daemon thread; the lifespan never waits on it.…, Exit the moment stdin closes -- which, under Tauri, means the parent died.…, start_warmup(), watch_parent(), Thread

### Community 57 - "check_erase.py"
Cohesion: 0.27
Nodes (11): _dilate(), _flag(), _in_box(), main(), _outline_through_quad(), _poly_mask(), _pre_2c_fill(), ndarray (+3 more)

### Community 58 - "SpotFix.tsx"
Cohesion: 0.36
Nodes (9): RepackStatus, inPolygon(), laidInto(), pageSrc(), severity(), SpotFix(), pick(), select() (+1 more)

### Community 59 - "check_probe.py"
Cohesion: 0.36
Nodes (9): probe_png(), A PNG with `token` painted large and black on white. No prompt text. Built…, attempt(), main(), post(), Phase 0 -- the probe that touches a LIVE endpoint (US-012). Only this file…, Return (status, body) -- never raise on HTTP error., Never echo the live key, whatever the gateway reflected back. (+1 more)

### Community 60 - "ocr"
Cohesion: 0.20
Nodes (10): _bbox(), _changed_in_polygon(), _check_lang(), ocr(), punctuation_only(), Is there anything here a translator could change? A region that reads as…, Source text per region. Returns the number of OCR calls made. One call per…, Reject a target language that is not a language tag. `lang` is substituted into… (+2 more)

### Community 61 - "check_cancel.py"
Cohesion: 0.27
Nodes (11): build_inputs(), check_cancel(), check_no_partial(), check_resume(), _eight_page_archive(), events_of(), main(), ARCHIVE_PAGES pages from benign.cbz's three, each with one pixel of its own.… (+3 more)

### Community 62 - "Job"
Cohesion: 0.18
Nodes (4): Job, Every item, through the boundary, on `workers` threads. Never raises.…, Block until every item has a terminal status. False on timeout., AC-9, the half the product had never wired: probe once per job. Before this,…

### Community 63 - "section_clear"
Cohesion: 0.11
Nodes (30): add_ref(), clear_running(), get_placement(), item_placements(), job_dir(), _job_key(), jobs_root(), mark_running() (+22 more)

### Community 64 - "Node TypeScript Configuration"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 65 - "check_id.py"
Cohesion: 0.11
Nodes (26): _glossary_doc(), _live(), main(), _payload_text(), _prompt(), Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always; live…, Which of the line's marked honorifics appear in `out`, and which forbidden…, _renderings() (+18 more)

### Community 66 - "rerender"
Cohesion: 0.15
Nodes (13): Exception, Lock, AC-10: click a bubble, edit the translation, re-render that page alone. Neither…, rerender(), CacheMiss, Cancelled, _check_cancel(), _page_lock() (+5 more)

### Community 67 - "detect"
Cohesion: 0.22
Nodes (9): Region, detect(), _glyph_px(), Sort key: top band first, then right to left inside the band. The band exists…, Text regions on one page, as Regions carrying polygon and confidence. ids are…, The source glyph size: the median short side of a block's quads. A tategaki…, _reading_order(), One detected text region, as it travels through the pipeline. `text` defaults… (+1 more)

### Community 68 - "Fixture Determinism Check"
Cohesion: 0.43
Nodes (6): generate(), main(), Phase 0a gate: two regenerations from an empty tree are byte-identical. uv run…, Relative-path -> sha256 for everything under the generated subdirs., sha256(), snapshot()

### Community 69 - "_rerender_locked"
Cohesion: 0.22
Nodes (9): _content_region(), dismiss(), _model_id(), _persist(), (kept, dismissed): the regions the vision model said hold no text. Called after…, Write the page's content record: EVERY detected region, not the kept ones.…, The region as the page holds it: a vision model's null is not content., What the translation file is keyed on. 'offline' is a real key, not a hole. The… (+1 more)

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
Cohesion: 0.17
Nodes (14): post, cache_clear(), cache_stats(), cancel_job(), _job_response(), job_status(), JobRequest, The FastAPI sidecar. Loopback only, nonce-gated shutdown. Three security… (+6 more)

### Community 99 - "Scanned PDF Fixture"
Cohesion: 0.67
Nodes (3): Scanned PDF Fixture, Unreadable Scanned PDF Page 1 Image, Unreadable Scanned PDF Page 2 Image

### Community 142 - "BaseModel"
Cohesion: 0.25
Nodes (8): BaseModel, ItemRequest, What the Settings UI sends. No defaults -- absent means absent., One archive or PDF, start to finish. Phase 8 owns the QUEUE, not this route.…, AC-10's payload: one region of one page of one job. The page is addressed by…, RerenderRequest, Settings, TranslateRequest

### Community 143 - "read_translation"
Cohesion: 0.18
Nodes (12): model_slug(), page_hash(), Image, SHA-256 of the DECODED pixels, plus mode and size. Mode and size are in the…, A filesystem-safe name for a model id that two ids cannot share. The readable…, ``{region_id: {"text": str, "edited": bool}}`` for one (lang, model)., Merge a fresh translation in, and never overwrite an ``edited`` entry.…, read_translation() (+4 more)

### Community 144 - "_floor_fits"
Cohesion: 0.29
Nodes (8): _capacity(), _floor_fits(), _longest(), The largest n in [0, n_max] for which fits(n) holds, given fits is monotone.…, The rung-3 state -- floor, tightened, no inset, no bleed -- as a predicate., The largest character count of `text` that fits at the floor, tightened.…, Rung 5's terminal branch. Returns (placed or None, rendered, reason). Cannot…, _truncate()

### Community 145 - "_wrap_from"
Cohesion: 0.25
Nodes (8): _chord(), _narrowest(), The WIDEST contiguous span of the polygon at scanline y, or None. Contiguous,…, The tightest chord the line's own box spans, clipped to the page raster. A line…, Advance width including tracking, which PIL does not model. Tracking is applied…, Greedy wrap of `words` in slots starting at `top`. None if words remain. A slot…, text_width(), _wrap_from()

### Community 146 - "_member_dest"
Cohesion: 0.33
Nodes (6): output_path(), Destination path whose extension matches the SOURCE format. Named off the…, _member_dest(), r"""One path segment, made safe to CREATE on Windows. The colon is the one that…, r"""Where one archive member's translated page lands, under `dest_dir`.…, _safe_segment()

### Community 147 - "_bad_settings_response"
Cohesion: 0.40
Nodes (5): _bad_settings_response(), models(), ValueError, A 400 for settings this process cannot use. json.dumps, never f-string. Typed…, Populate the Settings model dropdown from the user's own endpoint.

### Community 148 - "SettingsError"
Cohesion: 0.50
Nodes (4): The configured settings cannot be used. Not the provider's fault. A ValueError…, SettingsError, One request for every rung-5 region on the page, through llm.py's semaphore.…, _retranslate()

### Community 149 - "_above_floor"
Cohesion: 0.50
Nodes (4): _above_floor(), _calibrate(), Seconds for one reference page's worth of raster work. Best of N.…, (ok, description) for §E's hardware floor. Measured, not read off a label.…

## Knowledge Gaps
- **294 isolated node(s):** `Callback`, `callbacks`, `listeners`, `STAGES`, `jobs` (+289 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 920 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **45 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `skip()` connect `Checks` to `check_group.py`, `check_id.py`, `check_package.py`, `StubProvider`, `check_archives.py`, `pdf.py`, `check_spotfix.py`, `check_inpaint.py`, `check_probe.py`, `check_batch.py`, `check_typeset.py`, `fetch_fixtures.py`, `check_erase.py`, `LLMClient`, `check_cjk.py`, `check_cancel.py`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `Checks` connect `Checks` to `check_group.py`, `check_package.py`, `check_id.py`, `StubProvider`, `check_archives.py`, `pdf.py`, `check_inpaint.py`, `check_probe.py`, `check_batch.py`, `check_models.py`, `fetch_fixtures.py`, `check_typeset.py`, `check_erase.py`, `LLMClient`, `check_cjk.py`, `check_cancel.py`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `LLMClient` connect `LLMClient` to `check_group.py`, `check_id.py`, `main.py`, `StubProvider`, `check_spotfix.py`, `check_inpaint.py`, `check_probe.py`, `translate`, `check_batch.py`, `check_typeset.py`, `_bad_settings_response`, `check_cjk.py`, `check_cancel.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `LLMClient` (e.g. with `models()` and `section_skipped()`) actually correct?**
  _`LLMClient` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `StubProvider` (e.g. with `section_ingest_llm()` and `section_not_text()`) actually correct?**
  _`StubProvider` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Callback`, `callbacks`, `listeners` to the rest of the system?**
  _294 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pdf.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05352112676056338 - nodes in this community are weakly interconnected._