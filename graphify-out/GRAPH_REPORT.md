# Graph Report - MangaTranslator  (2026-09-13)

## Corpus Check
- 111 files · ~258,457 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1794 nodes · 3658 edges · 144 communities (98 shown, 42 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 128 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9c5a772b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pdf.py
- check_package.py
- main.py
- Spot Fix Validation
- check_archives.py
- Test Fixture Generation
- Image Endpoint Probe
- check_inpaint.py
- Page Image Manifest
- Frontend Package Dependencies
- archive.py
- run_item
- Brand and Language Documentation
- LLMClient
- Archive Safety Budget
- Job Reference Storage
- check_typeset.py
- Japanese OCR Fixtures
- skip
- Atomic File Operations
- React UI Components
- detect.py
- Tauri Application Configuration
- check_group.py
- Text Inpainting
- Page Cache Management
- StubProvider
- check_cjk.py
- pipeline.py
- group.py
- check_id.py
- Mock Tauri API
- Translation Cache
- Image Encoding and Metadata
- Frontend TypeScript Configuration
- repack_extras
- job.py
- sidecar/__init__.py
- Model Download Management
- _run_cached_page
- Text Mask Detection
- typeset.py
- Regression Test Runner
- Chinese Korean OCR
- Main Application UI
- Frontend Sidecar Client
- Komalingo Brand Assets
- App Data Migration
- Translation Form UI
- _CountingReader
- typeset_page
- Frontend Error Reporting
- TypesetError
- llm.py
- Japanese Manga OCR
- check_probe.py
- Text Erasure Validation
- Concurrent Job Processing
- Spot Fix UI
- Cancellation and Resume Checks
- Raster LRU Cache
- Settings UI Validation
- Typesetting Fit Fallbacks
- region.py
- Node TypeScript Configuration
- _member_dest
- _Verdicts
- Progress Tracking UI
- Fixture Determinism Check
- Translation Quality Metrics
- Spot Fix Guard Testing
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
- Async Import Probe
- Hardware Performance Calibration
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
- RuntimeError
- ValueError

## God Nodes (most connected - your core abstractions)
1. `Checks` - 73 edges
2. `long_path()` - 49 edges
3. `LLMClient` - 43 edges
4. `skip()` - 38 edges
5. `StubProvider` - 35 edges
6. `Budget` - 29 edges
7. `main()` - 29 edges
8. `page_dir()` - 28 edges
9. `panels` - 25 edges
10. `run_item()` - 23 edges

## Surprising Connections (you probably didn't know these)
- `Komalingo Open Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-open-a.png → README.md
- `Komalingo Split Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-split-a.png → README.md
- `main()` --uses--> `ProviderError`  [INFERRED]
  tests/check_ipc.py → sidecar/llm.py
- `_flag()` --uses--> `EraseError`  [INFERRED]
  tests/check_erase.py → sidecar/textmask.py
- `main()` --indirect_call--> `root()`  [INFERRED]
  tests/check_atomic.py → sidecar/cache.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Komalingo Brand Asset Family** — brand_komalingo_icon_dark_dark_app_icon, brand_komalingo_icon_light_app_icon, brand_komalingo_lockup_on_dark_dark_lockup, brand_komalingo_lockup_light_lockup, brand_komalingo_mark_on_dark_dark_mark, brand_komalingo_mark_light_mark [EXTRACTED 0.99]
- **Local Manga Translation Stack** — readme_translation_pipeline, readme_manga_ocr, readme_pp_ocrv5, readme_pp_ocrv3_db, readme_comic_text_detector, readme_lama_manga [EXTRACTED 1.00]
- **Komalingo Brand Concept Explorations** — brand_explorations_concept_open_a_image, brand_explorations_concept_split_a_image [INFERRED 0.90]
- **Scanned PDF Fixture and Rendered Pages** — fixtures_pdf_scan_document, fixtures_pdf_scan_p1_image, fixtures_pdf_scan_p2_image [INFERRED 0.95]

## Communities (144 total, 42 thin omitted)

### Community 0 - "pdf.py"
Cohesion: 0.06
Nodes (65): PdfDocument, PdfPage, PdfReader, PdfWriter, _axis_aligned(), _copy_info(), copy_outline(), _decode_xobject() (+57 more)

### Community 1 - "check_package.py"
Cohesion: 0.06
Nodes (55): health(), Liveness, plus which execution provider this process will run on. The provider…, Where the archive rebuild an edit scheduled has got to. The same dict…, GET can never shut anything down. A link or an <img> is a GET., repack_status(), shutdown_get(), Return (execution_provider, reason). The reason is empty ONLY when CUDA was…, select_provider() (+47 more)

### Community 2 - "main.py"
Cohesion: 0.05
Nodes (64): BaseModel, exception_handler, FastAPI, post, Request, Response, DetectError, RuntimeError (+56 more)

### Community 3 - "Spot Fix Validation"
Cohesion: 0.10
Nodes (49): clear_tier(), _archive_edits(), _call(), _guarded(), main(), _no_detect_or_ocr(), _quiet(), r"""Phase 3 -- the spot-fix editor and the page cache (AC-10). OFFLINE. uv run… (+41 more)

### Community 4 - "check_archives.py"
Cohesion: 0.10
Nodes (50): comicinfo(), detect_format(), pages(), The container family of `path`, from its bytes. The tar test is last and is…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Same…, `(member name, raw bytes)` of the archive's ComicInfo.xml, or None. RAW bytes,…, Repack `entries` -- an iterable of `(member name, bytes)` -- at `dest`. Through…, write_archive() (+42 more)

### Community 5 - "Test Fixture Generation"
Cohesion: 0.10
Nodes (43): _archive_page(), _cbz_page(), draw_columns(), draw_lines(), draw_vertical(), gen_archives(), gen_bubbles(), gen_cbz() (+35 more)

### Community 6 - "Image Endpoint Probe"
Cohesion: 0.09
Nodes (34): AppHandle, CommandChild, Into, Mutex, Option, Result, Self, attempt() (+26 more)

### Community 7 - "check_inpaint.py"
Cohesion: 0.10
Nodes (38): _assert_ink(), _assert_ring(), _assert_step_edge(), _band(), _best_ncc(), _chord_x(), _composite(), _dismissed() (+30 more)

### Community 8 - "Page Image Manifest"
Cohesion: 0.05
Nodes (40): sha256, size, sha256, size, sha256, size, sha256, size (+32 more)

### Community 9 - "Frontend Package Dependencies"
Cohesion: 0.06
Nodes (33): dependencies, react, react-dom, @tauri-apps/api, @tauri-apps/plugin-dialog, @tauri-apps/plugin-opener, devDependencies, @tauri-apps/cli (+25 more)

### Community 10 - "archive.py"
Cohesion: 0.06
Nodes (41): BytesIO, _decode(), _drain(), expected_pages(), _head(), is_archive(), _libarchive(), libarchive_path() (+33 more)

### Community 11 - "run_item"
Cohesion: 0.16
Nodes (14): output_path(), Where the repacked archive lands. Same extension, except RAR -> .cbz. The…, detect(), Whether the bytes start with a PDF header. The spec allows junk before `%PDF-`,…, _container(), item_dir(), r"""The per-ITEM output directory. Every file an item produces lands here.…, The container family of `src_path`, by signature: an archive family or… (+6 more)

### Community 12 - "Brand and Language Documentation"
Cohesion: 0.06
Nodes (31): Komalingo Open Concept A Brand Exploration, Komalingo Split Concept A Brand Exploration, Honorifics and register in the Indonesian output (AC-4), Register, The rule, The table, What stays as it is, What the gate holds (+23 more)

### Community 13 - "LLMClient"
Cohesion: 0.14
Nodes (11): glossary_text(), LLMClient, probe_token(), The glossary block for `lang`, or "" when the target has none., The only way out to the provider. _request holds the gate for the call, on the…, Every model the provider reports, in the provider's own order, as {"id",…, {region_id: text}. A JSON null stays None -- see NOT_TEXT_INSTRUCTION. None and…, All regions of one page. One request unless the page is huge. Returns… (+3 more)

### Community 14 - "Archive Safety Budget"
Cohesion: 0.09
Nodes (19): PathLike, Budget, is_comicinfo(), _normalized(), Exception, r"""AC-11: the ingest budget. Every untrusted archive is read through this.…, One rejected archive, carrying which rule refused it and where. `reason` is…, Member name with separators unified, for rule evaluation only. Backslash is a… (+11 more)

### Community 15 - "Job Reference Storage"
Cohesion: 0.15
Nodes (31): add_ref(), clear_running(), delete_job(), drop_ref(), job_dir(), _job_key(), jobs_root(), mark_running() (+23 more)

### Community 16 - "check_typeset.py"
Cohesion: 0.14
Nodes (26): ellipse_points(), The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.…, The job summary AC-1 requires: which regions were compromised, which failed.…, summary(), _batching_and_spotfix(), _check_page(), _compare_metrics(), _edge_cases() (+18 more)

### Community 17 - "Japanese OCR Fixtures"
Cohesion: 0.12
Nodes (26): main(), Phase 1 -- OCR truth on real vertical Japanese (AC-2). OFFLINE. Runs manga-ocr…, build_manifest(), _compare(), image_size(), load_manifest(), main(), print_report() (+18 more)

### Community 18 - "skip"
Cohesion: 0.13
Nodes (18): Phase 0 -- the write protocol. Offline, no fixtures, no network. Asserts, from…, emitted_stages(), item_totals(), main(), Phase 0 -- the host/sidecar IPC contract (US-011). OFFLINE (US-003 stub). **Why…, Run one page as a CHILD PROCESS and read the stages off its stdout. In-process…, Run a 3-page .cbz as a CHILD PROCESS: the `total` on its lines, and the pages…, main() (+10 more)

### Community 19 - "Atomic File Operations"
Cohesion: 0.10
Nodes (28): atomic_write(), long_path(), open_retry(), r"""The single write protocol. Every file this app produces goes through here.…, Yield a handle whose bytes land at `dest` only if the block completes. On any…, r"""Absolute, normalized, and \\?\-prefixed on Windows. The prefix turns off…, os.replace with a short, bounded retry on Windows sharing violations. Two…, `open` with the same bounded retry as `_replace`, for READERS. The other half… (+20 more)

### Community 20 - "React UI Components"
Cohesion: 0.13
Nodes (18): react, Alert(), ICON, Tone, Props, State, Icon(), IconName (+10 more)

### Community 21 - "detect.py"
Cohesion: 0.12
Nodes (24): _as_bgr(), _dedupe(), _input_size(), _inverse(), _model(), ndarray, _quad_to_polygon(), quads() (+16 more)

### Community 22 - "Tauri Application Configuration"
Cohesion: 0.08
Nodes (24): app, security, windows, enable, scope, build, beforeBuildCommand, beforeDevCommand (+16 more)

### Community 23 - "check_group.py"
Cohesion: 0.10
Nodes (31): Region, detect(), _glyph_px(), Sort key: top band first, then right to left inside the band. The band exists…, Text regions on one page, as Regions carrying polygon and confidence. ids are…, The source glyph size: the median short side of a block's quads. A tategaki…, _reading_order(), _bubble_of() (+23 more)

### Community 24 - "Text Inpainting"
Cohesion: 0.13
Nodes (23): _crops(), erase(), _fill(), fill_white(), _flat(), _flat_surround(), _inpaint(), _lama() (+15 more)

### Community 25 - "Page Cache Management"
Cohesion: 0.13
Nodes (22): _cap_bytes(), _dir_size(), disk_bytes(), enforce_cap(), get_placement(), has_edits(), item_placements(), pages_root() (+14 more)

### Community 26 - "StubProvider"
Cohesion: 0.09
Nodes (29): The files in `directory`, top level only, in natural order. Top level only: a…, scan(), build_folder(), _chats_with_image(), check_cancel(), check_cap(), check_probe_wiring(), check_running_refcount() (+21 more)

### Community 27 - "check_cjk.py"
Cohesion: 0.15
Nodes (20): _blank_and_ja(), _cache(), _centroid(), _fit(), _load(), main(), _ocr(), Phase 4 -- Chinese and Korean through PP-OCRv5 (AC-3). OFFLINE after first… (+12 more)

### Community 28 - "pipeline.py"
Cohesion: 0.08
Nodes (30): Container readers. One module per format, and each one reads only. Phase 3…, _bbox(), _changed_in_polygon(), _check_cancel(), _check_lang(), dismiss(), expecting(), flush_repacks() (+22 more)

### Community 29 - "group.py"
Cohesion: 0.13
Nodes (21): separated(i, j): does ink run across the gap between two adjacent quads? The…, _separator(), bbox(), convex_hull(), glyph_unit(), group(), _inside(), merge() (+13 more)

### Community 30 - "check_id.py"
Cohesion: 0.16
Nodes (17): _glossary_doc(), _live(), main(), _payload_text(), _prompt(), Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always; live…, Which of the line's marked honorifics appear in `out`, and which forbidden…, _renderings() (+9 more)

### Community 31 - "Mock Tauri API"
Cohesion: 0.16
Nodes (16): api(), Callback, callbacks, emit(), fakePage(), invoke(), jobs, listeners (+8 more)

### Community 32 - "Translation Cache"
Cohesion: 0.15
Nodes (19): has_edit_for_other_model(), model_slug(), page_hash(), SHA-256 of the DECODED pixels, plus mode and size. Mode and size are in the…, A filesystem-safe name for a model id that two ids cannot share. The readable…, ``{region_id: {"text": str, "edited": bool}}`` for one (lang, model)., Merge a fresh translation in, and never overwrite an ``edited`` entry. A re-run…, A spot-fix edit IS a translation, so it lives in the translation file.… (+11 more)

### Community 33 - "Image Encoding and Metadata"
Cohesion: 0.16
Nodes (17): encode(), output_path(), Image, Encode policy. The only place in the app that calls Image.save. Pillow silently…, Drop the GPS IFD, keep every other tag byte-identical., Encode to bytes in `fmt`, carrying metadata from `src` (default: img)., Destination path whose extension matches the SOURCE format. Named off the…, Encode `img` in the source image's format and write it atomically. Format comes… (+9 more)

### Community 34 - "Frontend TypeScript Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+10 more)

### Community 35 - "repack_extras"
Cohesion: 0.20
Nodes (14): _admit(), _is_page_name(), _lazy(), Whether a member name is a page CANDIDATE. Identical rule to read_cbz., gz" | "bz2" | "xz" for a whole-file-compressed tar, "" for a plain one. This…, Run every member past the budget; return the page candidates to stream. Every…, Compressed tar: admit and read in ONE forward pass over the stream. Two…, `(page names in natural order, name -> Member, payload source)`. The one place… (+6 more)

### Community 36 - "job.py"
Cohesion: 0.09
Nodes (26): Event, _is_page(), members(), _natural_key(), pages(), r"""Read-only CBZ page enumeration. No repack, no safety budget, no other…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Streamed…, Sort key for a full archive member path, digit-aware and segment-wise. Segments… (+18 more)

### Community 37 - "sidecar/__init__.py"
Cohesion: 0.18
Nodes (8): _bsdtar(), bundled(), NativeMissing, Exception, r"""The native libraries the sidecar needs and pip cannot deliver (AC-6, .cbr).…, A native dependency could not be installed, with a named reason., Whether build/libarchive already holds the whole closure., r"""Windows' own tar.exe, which is bsdtar and therefore reads .tar.zst. A…

### Community 38 - "Model Download Management"
Cohesion: 0.18
Nodes (16): ensure(), _ensure_directory(), fetch(), FetchError, _free_space(), model_dir(), RuntimeError, First-launch model fetch, and the CUDA-or-CPU decision. Resumable by design.… (+8 more)

### Community 39 - "_run_cached_page"
Cohesion: 0.18
Nodes (18): _deliver(), detect(), emit(), inpaint(), page_context_png(), _persist(), Image, Text regions from detect.py's DB model. Regions become plain dicts here rather… (+10 more)

### Community 40 - "Text Mask Detection"
Cohesion: 0.16
Nodes (15): onnx_session(), An onnxruntime session on the provider select_provider() names. Errors-only…, EraseError, mask(), _model(), probability(), ndarray, RuntimeError (+7 more)

### Community 41 - "typeset.py"
Cohesion: 0.10
Nodes (31): FreeTypeFont, _bbox(), _chord(), _draw_line(), _edge_adjacent(), floor_px(), _has_orphan(), _inset_points() (+23 more)

### Community 42 - "Regression Test Runner"
Cohesion: 0.20
Nodes (16): append_record(), assert_interpreter(), discover(), env_class(), harvest_metrics(), last_status(), load_records(), main() (+8 more)

### Community 43 - "Chinese Korean OCR"
Cohesion: 0.16
Nodes (13): lines(), ocr(), OcrError, ndarray, RuntimeError, Chinese and Korean OCR: PP-OCRv5 text-line recognition through onnxruntime.…, The parts that are text LINES, each read once. The detector answers per line…, Rows top to bottom (columns right to left), and WITHIN a row, left to right… (+5 more)

### Community 44 - "Main Application UI"
Cohesion: 0.18
Nodes (13): App(), exitMessage(), loadTheme(), SidecarState, stageWord(), Theme, THEMES, View (+5 more)

### Community 45 - "Frontend Sidecar Client"
Cohesion: 0.17
Nodes (16): runFolder(), runItem(), describeError(), displayPath(), isApiError(), isInternal(), loadSettings(), saveSettings() (+8 more)

### Community 46 - "Komalingo Brand Assets"
Cohesion: 0.13
Nodes (15): Komalingo Light-Tile App Icon PNG, Komalingo Dark-Tile App Icon PNG, Komalingo Dark-Tile App Icon, Komalingo Light-Tile App Icon, Komalingo Lockup PNG, Komalingo Lockup for Light Backgrounds, Komalingo Lockup for Dark Backgrounds, Komalingo Lockup on Dark PNG (+7 more)

### Community 47 - "App Data Migration"
Cohesion: 0.16
Nodes (9): The app's per-user data directory, and the one-time move from its old name. The…, `base`/Komalingo, moving an old-named sibling there if it is the only one.…, under(), check_rename(), main(), Phase 0 -- resumable fetch and EP selection (AC-14). OFFLINE. Serves bytes from…, [rename] MangaTranslator's data directory moves to Komalingo, once, whole. The…, Serves PAYLOAD with Range support. cut_after truncates the response. (+1 more)

### Community 48 - "Translation Form UI"
Cohesion: 0.21
Nodes (11): PathField(), ApiError, Progress, Source, SOURCES, Target, TARGETS, TranslateResult (+3 more)

### Community 50 - "typeset_page"
Cohesion: 0.18
Nodes (12): _commit(), Fit, ink_style(), Image, ndarray, One region's typeset result. Every field is output-only. `rung` is the RUNG…, Typeset every region of one page. Returns (image, [Fit]). Two-phase by…, INK_PLAIN, INK_DARK or INK_BUSY from the page's gray inside `points`. (+4 more)

### Community 51 - "Frontend Error Reporting"
Cohesion: 0.26
Nodes (7): ErrorBoundary, installGlobalReporting(), reportError(), boot(), dismissSplash(), failSplash(), splash()

### Community 52 - "TypesetError"
Cohesion: 0.40
Nodes (5): RuntimeError, A typeset pass that cannot proceed. Named, like every sidecar failure path., Raise a named error if called inside a running event loop, on EVERY page. The…, _refuse_running_loop(), TypesetError

### Community 53 - "llm.py"
Cohesion: 0.17
Nodes (14): RuntimeError, _decode_reply(), _from_event_stream(), ProviderError, OpenAI-compatible client. Owns the concurrency cap and the error contract.…, Carries the provider's own words to the UI. See AC-8., A 2xx body as the dict the OpenAI shape describes, or a ProviderError. Two…, Concatenate the chunks of choice 0 into one chat.completion. `delta` is the… (+6 more)

### Community 54 - "Japanese Manga OCR"
Cohesion: 0.26
Nodes (11): _as_image(), canonical(), _get_model(), _is_blank(), ocr(), Image, Japanese OCR with confidence and blank-crop gates. Model output is…, Fold the two encodings manga-ocr picks that the page does not print. (+3 more)

### Community 55 - "check_probe.py"
Cohesion: 0.20
Nodes (14): probe_png(), A PNG with `token` painted large and black on white. No prompt text. Built…, attempt(), main(), post(), Phase 0 -- the probe that touches a LIVE endpoint (US-012). Only this file…, Return (status, body) -- never raise on HTTP error., Never echo the live key, whatever the gateway reflected back. (+6 more)

### Community 56 - "Text Erasure Validation"
Cohesion: 0.27
Nodes (11): _dilate(), _flag(), _in_box(), main(), _outline_through_quad(), _poly_mask(), _pre_2c_fill(), ndarray (+3 more)

### Community 57 - "Concurrent Job Processing"
Cohesion: 0.20
Nodes (4): Job, Every item, through the boundary, on `workers` threads. Never raises.…, Block until every item has a terminal status. False on timeout., AC-9, the half the product had never wired: probe once per job. Before this,…

### Community 58 - "Spot Fix UI"
Cohesion: 0.31
Nodes (10): Region, RepackStatus, inPolygon(), laidInto(), pageSrc(), severity(), SpotFix(), pick() (+2 more)

### Community 59 - "Cancellation and Resume Checks"
Cohesion: 0.33
Nodes (9): build_inputs(), check_cancel(), check_no_partial(), check_resume(), events_of(), main(), Cancel the moment page 1 is on disk; the item must stop short., r"""Phase 9 -- AC-13 (cancel and resume). Offline, against the stub. uv run… (+1 more)

### Community 60 - "Raster LRU Cache"
Cohesion: 0.28
Nodes (3): Image, LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds. It counts…, _Tier

### Community 61 - "Settings UI Validation"
Cohesion: 0.31
Nodes (7): main(), Phase 0 -- the Settings UI and the IPC client (US-009). OFFLINE. The frontend…, Source with comments removed. The point of the whole file: an assert that…, read(), strip_comments(), walk_src(), _load_fixtures()

### Community 62 - "Typesetting Fit Fallbacks"
Cohesion: 0.29
Nodes (8): _capacity(), _floor_fits(), _longest(), The largest n in [0, n_max] for which fits(n) holds, given fits is monotone.…, The rung-3 state -- floor, tightened, no inset, no bleed -- as a predicate., The largest character count of `text` that fits at the floor, tightened.…, Rung 5's terminal branch. Returns (placed or None, rendered, reason). Cannot…, _truncate()

### Community 63 - "region.py"
Cohesion: 0.33
Nodes (5): as_points(), The shared Region type: detect.py's output, typeset.py's input. Defined here…, One detected text region, as it travels through the pipeline. `text` defaults…, Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.…, Region

### Community 64 - "Node TypeScript Configuration"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 65 - "_member_dest"
Cohesion: 0.50
Nodes (4): _member_dest(), r"""One path segment, made safe to CREATE on Windows. The colon is the one that…, r"""Where one archive member's translated page lands, under `dest_dir`.…, _safe_segment()

### Community 67 - "Progress Tracking UI"
Cohesion: 0.33
Nodes (6): LABEL, ProgressBar(), Stage, stageIndex(), STAGES, StageTrack()

### Community 68 - "Fixture Determinism Check"
Cohesion: 0.43
Nodes (6): generate(), main(), Phase 0a gate: two regenerations from an empty tree are byte-identical. uv run…, Relative-path -> sha256 for everything under the generated subdirs., sha256(), snapshot()

### Community 69 - "Translation Quality Metrics"
Cohesion: 0.38
Nodes (6): chrf_pp(), _ngrams(), Shared assert helpers, created where first needed (Phase 1: assert_cer). Phase…, chrF++'s word tokens: whitespace split, one leading or trailing ASCII…, Corpus chrF++ (Popovic 2017) over the stdlib, sacrebleu's arithmetic: character…, _words()

### Community 70 - "Spot Fix Guard Testing"
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

### Community 97 - "Async Import Probe"
Cohesion: 0.50
Nodes (4): load(), main(), Phase 0a spike: can we import the CV components in-process on the pinned stack?…, Import under a RUNNING event loop -- the condition the sidecar imposes.

### Community 98 - "Hardware Performance Calibration"
Cohesion: 0.50
Nodes (4): _above_floor(), _calibrate(), Seconds for one reference page's worth of raster work. Best of N.…, (ok, description) for §E's hardware floor. Measured, not read off a label.…

### Community 99 - "Scanned PDF Fixture"
Cohesion: 0.67
Nodes (3): Scanned PDF Fixture, Unreadable Scanned PDF Page 1 Image, Unreadable Scanned PDF Page 2 Image

## Knowledge Gaps
- **291 isolated node(s):** `Tone`, `Props`, `State`, `Where`, `Callback` (+286 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 883 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **42 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Checks` connect `Spot Fix Validation` to `pdf.py`, `check_package.py`, `check_archives.py`, `check_inpaint.py`, `Job Reference Storage`, `check_typeset.py`, `Japanese OCR Fixtures`, `skip`, `Atomic File Operations`, `check_group.py`, `StubProvider`, `check_cjk.py`, `check_id.py`, `Translation Cache`, `Image Encoding and Metadata`, `App Data Migration`, `llm.py`, `check_probe.py`, `Text Erasure Validation`, `Cancellation and Resume Checks`, `Settings UI Validation`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `skip()` connect `skip` to `pdf.py`, `check_package.py`, `Spot Fix Validation`, `check_archives.py`, `check_inpaint.py`, `Cancellation and Resume Checks`, `check_typeset.py`, `Japanese OCR Fixtures`, `check_probe.py`, `check_group.py`, `Text Erasure Validation`, `StubProvider`, `check_cjk.py`, `check_id.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `LLMClient` connect `LLMClient` to `main.py`, `Spot Fix Validation`, `check_inpaint.py`, `Cancellation and Resume Checks`, `check_typeset.py`, `skip`, `llm.py`, `check_probe.py`, `check_group.py`, `StubProvider`, `check_cjk.py`, `check_id.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 25 inferred relationships involving `Checks` (e.g. with `main()` and `_call()`) actually correct?**
  _`Checks` has 25 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Tone`, `Props`, `State` to the rest of the system?**
  _291 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pdf.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05698778833107191 - nodes in this community are weakly interconnected._
- **Should `check_package.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05786090005844535 - nodes in this community are weakly interconnected._