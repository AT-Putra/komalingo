# Graph Report - MangaTranslator  (2026-09-14)

## Corpus Check
- 111 files · ~268,636 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1852 nodes · 3747 edges · 152 communities (100 shown, 48 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 116 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `22b0aa6e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pdf.py
- check_package.py
- main.py
- check_spotfix.py
- check_archives.py
- gen_fixtures.py
- lib.rs
- check_inpaint.py
- Page Image Manifest
- package.json
- archive.py
- item_dir
- Brand and Language Documentation
- check_probe.py
- Budget
- check_batch.py
- check_typeset.py
- fetch_fixtures.py
- Checks
- run_item
- Settings.tsx
- detect.py
- Tauri Application Configuration
- group.py
- inpainter.py
- _run_cached_page
- LLMClient
- check_cjk.py
- cache.py
- textmask.py
- Member
- mock-tauri.ts
- check_group.py
- typeset_page
- Frontend TypeScript Configuration
- run_item
- read_cbz.py
- atomic.py
- models.py
- pipeline.py
- check_erase.py
- typeset.py
- Regression Test Runner
- ocr_cjk.py
- App.tsx
- describeError
- Komalingo Brand Assets
- check_models.py
- api.ts
- _CountingReader
- imaging.py
- main.tsx
- _rerender_locked
- read_raster
- ocr_ja.py
- _Tier
- Progress.tsx
- load_font
- SpotFix.tsx
- Image
- detect
- check_cancel.py
- Job
- section_cap
- Node TypeScript Configuration
- StubProvider
- rerender
- OcrError
- Fixture Determinism Check
- _floor_fits
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
- ValueError
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
- RuntimeError
- _wrap_from
- read_regions
- Path
- output_path
- Exception
- tier_bytes
- Lock

## God Nodes (most connected - your core abstractions)
1. `long_path()` - 52 edges
2. `Checks` - 44 edges
3. `LLMClient` - 40 edges
4. `skip()` - 34 edges
5. `StubProvider` - 33 edges
6. `page_dir()` - 31 edges
7. `main()` - 30 edges
8. `Budget` - 29 edges
9. `panels` - 25 edges
10. `_reset()` - 23 edges

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

## Communities (152 total, 48 thin omitted)

### Community 0 - "pdf.py"
Cohesion: 0.05
Nodes (71): PdfDocument, PdfPage, PdfReader, PdfWriter, The file is not an archive this build reads. Carries a reason string., UnsupportedArchive, _axis_aligned(), _copy_info() (+63 more)

### Community 1 - "check_package.py"
Cohesion: 0.07
Nodes (47): Return (execution_provider, reason). The reason is empty ONLY when CUDA was…, select_provider(), call(), main(), _parse_json(), Phase 0 -- the sidecar's HTTP surface and the shutdown gate (US-007). OFFLINE.…, Returns (status, body). A refused connection is status 0., (payload, why). `why` names the parse failure so the assert can print it. A… (+39 more)

### Community 2 - "main.py"
Cohesion: 0.05
Nodes (60): BaseModel, exception_handler, FastAPI, get, post, ProviderError, Request, Response (+52 more)

### Community 3 - "check_spotfix.py"
Cohesion: 0.08
Nodes (60): Checks, clear_tier(), _above_floor(), _archive_edits(), _calibrate(), _call(), _guarded(), main() (+52 more)

### Community 4 - "check_archives.py"
Cohesion: 0.10
Nodes (48): comicinfo(), detect_format(), pages(), The container family of `path`, from its bytes. The tar test is last and is…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Same…, `(member name, raw bytes)` of the archive's ComicInfo.xml, or None. RAW bytes,…, Repack `entries` -- an iterable of `(member name, bytes)` -- at `dest`. Through…, write_archive() (+40 more)

### Community 5 - "gen_fixtures.py"
Cohesion: 0.10
Nodes (43): _archive_page(), _cbz_page(), draw_columns(), draw_lines(), draw_vertical(), gen_archives(), gen_bubbles(), gen_cbz() (+35 more)

### Community 6 - "lib.rs"
Cohesion: 0.09
Nodes (34): AppHandle, CommandChild, Into, Mutex, Option, Path, Result, Self (+26 more)

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
Cohesion: 0.07
Nodes (38): BytesIO, _admit(), _decode(), _drain(), expected_pages(), _head(), is_archive(), _is_page_name() (+30 more)

### Community 11 - "item_dir"
Cohesion: 0.14
Nodes (15): _container(), flush_repacks(), item_dir(), _member_dest(), The item's archive, rebuilt from the loose pages already on disk. What…, Rebuild the item's archive soon, on a worker thread. Returns the status.…, Every pending repack, now, on this thread. For the exit paths. The app does not…, r"""One path segment, made safe to CREATE on Windows. The colon is the one that… (+7 more)

### Community 12 - "Brand and Language Documentation"
Cohesion: 0.06
Nodes (31): Komalingo Open Concept A Brand Exploration, Komalingo Split Concept A Brand Exploration, Honorifics and register in the Indonesian output (AC-4), Register, The rule, The table, What stays as it is, What the gate holds (+23 more)

### Community 13 - "check_probe.py"
Cohesion: 0.20
Nodes (14): probe_png(), A PNG with `token` painted large and black on white. No prompt text. Built…, attempt(), main(), post(), Phase 0 -- the probe that touches a LIVE endpoint (US-012). Only this file…, Return (status, body) -- never raise on HTTP error., Never echo the live key, whatever the gateway reflected back. (+6 more)

### Community 14 - "Budget"
Cohesion: 0.09
Nodes (19): PathLike, Budget, is_comicinfo(), _normalized(), Exception, r"""AC-11: the ingest budget. Every untrusted archive is read through this.…, One rejected archive, carrying which rule refused it and where. `reason` is…, Member name with separators unified, for rule evaluation only. Backslash is a… (+11 more)

### Community 15 - "check_batch.py"
Cohesion: 0.09
Nodes (34): Container readers. One module per format, and each one reads only. Phase 3…, r"""The Item model and the per-item error boundary. Moved here from Phase 8 on…, The files in `directory`, top level only, in natural order. Top level only: a…, Every path through the boundary, and the record when all are done. The blocking…, run_job(), scan(), build_folder(), _chats_with_image() (+26 more)

### Community 16 - "check_typeset.py"
Cohesion: 0.12
Nodes (29): ellipse_points(), The shared Region type: detect.py's output, typeset.py's input. Defined here…, One detected text region, as it travels through the pipeline. `text` defaults…, The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.…, Region, The job summary AC-1 requires: which regions were compromised, which failed.…, summary(), _batching_and_spotfix() (+21 more)

### Community 17 - "fetch_fixtures.py"
Cohesion: 0.12
Nodes (26): main(), Phase 1 -- OCR truth on real vertical Japanese (AC-2). OFFLINE. Runs manga-ocr…, build_manifest(), _compare(), image_size(), load_manifest(), main(), print_report() (+18 more)

### Community 18 - "Checks"
Cohesion: 0.08
Nodes (31): main(), Phase 0 -- the write protocol. Offline, no fixtures, no network. Asserts, from…, build_source(), main(), Phase 0 -- encode policy. Offline, no network. Asserts, from the build order:…, A source image carrying an ICC profile and EXIF with and without GPS., emitted_stages(), item_totals() (+23 more)

### Community 19 - "run_item"
Cohesion: 0.18
Nodes (10): Event, disambiguate(), _discard_output(), Item, Lock, Remove what a REFUSED item already wrote. Best effort, never raises. The three…, Process one item. Never raises. `cancel` (Phase 9) is the job's token, handed…, Give every item in a job a DISTINCT item_id. Mutates and returns them.… (+2 more)

### Community 20 - "Settings.tsx"
Cohesion: 0.16
Nodes (15): react, Alert(), ICON, Tone, Icon(), IconName, PATHS, ModelCombobox (+7 more)

### Community 21 - "detect.py"
Cohesion: 0.11
Nodes (24): _as_bgr(), _dedupe(), DetectError, _input_size(), _model(), RuntimeError, _quad_to_polygon(), quads() (+16 more)

### Community 22 - "Tauri Application Configuration"
Cohesion: 0.08
Nodes (24): app, security, windows, enable, scope, build, beforeBuildCommand, beforeDevCommand (+16 more)

### Community 23 - "group.py"
Cohesion: 0.18
Nodes (15): convex_hull(), glyph_unit(), group(), _inside(), merge(), neighbours(), Group column-level detections into one region per bubble. Phase 2b. WHY this…, Degrees the polygon's longest edge sits off the nearer axis, in [0, 45]. (+7 more)

### Community 24 - "inpainter.py"
Cohesion: 0.13
Nodes (23): _crops(), erase(), _fill(), fill_white(), _flat(), _flat_surround(), _inpaint(), _lama() (+15 more)

### Community 25 - "_run_cached_page"
Cohesion: 0.19
Nodes (17): _deliver(), detect(), emit(), inpaint(), page_context_image(), Image, One page of an item, through the cache. Called under `_page_lock(h)`. The seven…, Text regions from detect.py's DB model. Regions become plain dicts here rather… (+9 more)

### Community 26 - "LLMClient"
Cohesion: 0.08
Nodes (30): RuntimeError, _decode_reply(), _from_event_stream(), glossary_text(), image_data_url(), LLMClient, probe_token(), ProviderError (+22 more)

### Community 27 - "check_cjk.py"
Cohesion: 0.11
Nodes (28): _blank_and_ja(), _cache(), _centroid(), _fit(), _load(), main(), _ocr(), Phase 4 -- Chinese and Korean through PP-OCRv5 (AC-3). OFFLINE after first… (+20 more)

### Community 28 - "cache.py"
Cohesion: 0.09
Nodes (54): long_path(), r"""Absolute, normalized, and \\?\-prefixed on Windows. The prefix turns off…, add_ref(), _cap_bytes(), delete_job(), _dir_size(), disk_bytes(), drop_ref() (+46 more)

### Community 29 - "textmask.py"
Cohesion: 0.16
Nodes (15): onnx_session(), An onnxruntime session on the provider select_provider() names. Errors-only…, EraseError, mask(), _model(), probability(), ndarray, RuntimeError (+7 more)

### Community 30 - "Member"
Cohesion: 0.14
Nodes (14): _libarchive(), libarchive_path(), _rar_entries(), _rar_payloads(), r"""Where the bundled libarchive lives, or None to let the loader search.…, Import the binding with the resolved library, or raise LibarchiveMissing. The…, (name, safety.Member) for every zip entry, in archive order., Plain tar only. A compressed one goes through `_tar_single_pass`. `"r:"`, never… (+6 more)

### Community 31 - "mock-tauri.ts"
Cohesion: 0.16
Nodes (16): api(), Callback, callbacks, emit(), fakePage(), invoke(), jobs, listeners (+8 more)

### Community 32 - "check_group.py"
Cohesion: 0.15
Nodes (22): _bubble_of(), _ellipse_mask(), _fixture(), _geometry(), _ink(), _largest(), main(), _mask() (+14 more)

### Community 33 - "typeset_page"
Cohesion: 0.15
Nodes (14): as_points(), Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.…, _commit(), Fit, ink_style(), Image, ndarray, One region's typeset result. Every field is output-only. `rung` is the RUNG… (+6 more)

### Community 34 - "Frontend TypeScript Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+10 more)

### Community 35 - "run_item"
Cohesion: 0.15
Nodes (13): BoundedSemaphore, _check_cancel(), _check_lang(), _page_slots(), AC-6's round trip: the delivered pages, back into the input's format. **The…, Raise Cancelled if the token is set. `cancel` is anything with is_set() -- a…, Reject a target language that is not a language tag. `lang` is substituted into…, Every page of one archive or PDF, through the cache. Returns the record.… (+5 more)

### Community 36 - "read_cbz.py"
Cohesion: 0.20
Nodes (13): _is_page(), members(), pages(), r"""Read-only CBZ page enumeration. No repack, no safety budget, no other…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Streamed…, A member that should be decoded as a page. Directory entries, macOS resource…, Page-candidate members of an OPEN archive, in yield order. One implementation,…, The page-candidate member names of `path`, in the order `pages` uses.… (+5 more)

### Community 37 - "atomic.py"
Cohesion: 0.12
Nodes (19): atomic_write(), r"""The single write protocol. Every file this app produces goes through here.…, Yield a handle whose bytes land at `dest` only if the block completes. On any…, os.replace with a short, bounded retry on Windows sharing violations. Two…, _replace(), _bsdtar(), bundled(), ensure_libarchive() (+11 more)

### Community 38 - "models.py"
Cohesion: 0.18
Nodes (17): ensure(), _ensure_directory(), fetch(), FetchError, _free_space(), model_dir(), on_disk(), First-launch model fetch, and the CUDA-or-CPU decision. Resumable by design.… (+9 more)

### Community 39 - "pipeline.py"
Cohesion: 0.22
Nodes (13): _bbox(), _box(), _changed_in_polygon(), expecting(), ocr(), punctuation_only(), The seven-stage pipeline: detect, ocr, translate, inpaint, render, encode,…, Is there anything here a translator could change? A region that reads as… (+5 more)

### Community 40 - "check_erase.py"
Cohesion: 0.27
Nodes (11): _dilate(), _flag(), _in_box(), main(), _outline_through_quad(), _poly_mask(), _pre_2c_fill(), ndarray (+3 more)

### Community 41 - "typeset.py"
Cohesion: 0.20
Nodes (16): _bbox(), _edge_adjacent(), floor_px(), _has_orphan(), _inset_points(), _ladder(), _layout(), max_font_px() (+8 more)

### Community 42 - "Regression Test Runner"
Cohesion: 0.20
Nodes (16): append_record(), assert_interpreter(), discover(), env_class(), harvest_metrics(), last_status(), load_records(), main() (+8 more)

### Community 43 - "ocr_cjk.py"
Cohesion: 0.22
Nodes (11): bbox(), lines(), ocr(), Chinese and Korean OCR: PP-OCRv5 text-line recognition through onnxruntime.…, The parts that are text LINES, each read once. The detector answers per line…, Rows top to bottom (columns right to left), and WITHIN a row, left to right…, Read one region: its line parts, recognised and joined in reading order., _reading_order() (+3 more)

### Community 44 - "App.tsx"
Cohesion: 0.19
Nodes (13): App(), exitMessage(), frontPage(), loadTheme(), SidecarState, stageWord(), Theme, THEMES (+5 more)

### Community 45 - "describeError"
Cohesion: 0.17
Nodes (16): runFolder(), runItem(), describeError(), displayPath(), isApiError(), isInternal(), loadSettings(), saveSettings() (+8 more)

### Community 46 - "Komalingo Brand Assets"
Cohesion: 0.13
Nodes (15): Komalingo Light-Tile App Icon PNG, Komalingo Dark-Tile App Icon PNG, Komalingo Dark-Tile App Icon, Komalingo Light-Tile App Icon, Komalingo Lockup PNG, Komalingo Lockup for Light Backgrounds, Komalingo Lockup for Dark Backgrounds, Komalingo Lockup on Dark PNG (+7 more)

### Community 47 - "check_models.py"
Cohesion: 0.14
Nodes (13): The app's per-user data directory, and the one-time move from its old name. The…, `base`/Komalingo, moving an old-named sibling there if it is the only one.…, under(), The cache root. MT_CACHE_DIR wins, so tests never touch the real one., root(), check_rename(), check_warmup(), main() (+5 more)

### Community 48 - "api.ts"
Cohesion: 0.16
Nodes (14): PathField(), ApiError, PageRecord, Progress, ProviderSettings, Source, SOURCES, Target (+6 more)

### Community 49 - "_CountingReader"
Cohesion: 0.18
Nodes (5): _CountingReader, LibarchiveMissing, Exception, No usable libarchive, so the RAR read path cannot run. A named exception rather…, A read-only stream that charges every byte it produces to a Budget. This is the…

### Community 50 - "imaging.py"
Cohesion: 0.21
Nodes (13): encode(), output_path(), Image, Encode policy. The only place in the app that calls Image.save. Pillow silently…, Drop the GPS IFD, keep every other tag byte-identical., Encode to bytes in `fmt`, carrying metadata from `src` (default: img)., Destination path whose extension matches the SOURCE format. Named off the…, Encode `img` in the source image's format and write it atomically. Format comes… (+5 more)

### Community 51 - "main.tsx"
Cohesion: 0.22
Nodes (9): ErrorBoundary, Props, State, installGlobalReporting(), reportError(), boot(), dismissSplash(), failSplash() (+1 more)

### Community 52 - "_rerender_locked"
Cohesion: 0.15
Nodes (13): _apply_translations(), _content_region(), dismiss(), _load_translations(), _model_id(), _persist(), (kept, dismissed): the regions the vision model said hold no text. Called after…, Write the page's content record: EVERY detected region, not the kept ones.… (+5 more)

### Community 53 - "read_raster"
Cohesion: 0.13
Nodes (17): open_retry(), `open` with the same bounded retry as `_replace`, for READERS. The other half…, has_raster(), page_hash(), Image, _raster(), _raster_files(), raster_name() (+9 more)

### Community 54 - "ocr_ja.py"
Cohesion: 0.26
Nodes (11): _as_image(), canonical(), _get_model(), _is_blank(), ocr(), Image, Japanese OCR with confidence and blank-crop gates. Model output is…, Fold the two encodings manga-ocr picks that the page does not print. (+3 more)

### Community 55 - "_Tier"
Cohesion: 0.20
Nodes (4): LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds. It counts…, Drop `key` if resident., Drop every raster of the page -- enforce_cap's path, one per erased set., _Tier

### Community 56 - "Progress.tsx"
Cohesion: 0.33
Nodes (6): LABEL, ProgressBar(), Stage, stageIndex(), STAGES, StageTrack()

### Community 57 - "load_font"
Cohesion: 0.18
Nodes (12): FreeTypeFont, _draw_line(), load_font(), RuntimeError, _raster_metrics(), A typeset pass that cannot proceed. Named, like every sidecar failure path., One truetype face, cached per size. MT_TYPESET_FONT overrides the search., (overflow_x, overflow_y, clipped_glyphs, offpage_ink_px), read off drawn ink.… (+4 more)

### Community 58 - "SpotFix.tsx"
Cohesion: 0.36
Nodes (9): RepackStatus, inPolygon(), laidInto(), pageSrc(), severity(), SpotFix(), pick(), select() (+1 more)

### Community 60 - "detect"
Cohesion: 0.18
Nodes (12): Region, detect(), _glyph_px(), _inverse(), ndarray, Sort key: top band first, then right to left inside the band. The band exists…, Text regions on one page, as Regions carrying polygon and confidence. ids are…, Per quad: light glyphs on a dark ground? (mean gray inside under 128) The… (+4 more)

### Community 61 - "check_cancel.py"
Cohesion: 0.27
Nodes (11): build_inputs(), check_cancel(), check_no_partial(), check_resume(), _eight_page_archive(), events_of(), main(), ARCHIVE_PAGES pages from benign.cbz's three, each with one pixel of its own.… (+3 more)

### Community 62 - "Job"
Cohesion: 0.20
Nodes (4): Job, Every item, through the boundary, on `workers` threads. Never raises.…, Block until every item has a terminal status. False on timeout., AC-9, the half the product had never wired: probe once per job. Before this,…

### Community 63 - "section_cap"
Cohesion: 0.36
Nodes (10): clear_running(), job_dir(), _job_key(), jobs_root(), mark_running(), The one form a job id takes inside this module: a safe path segment. job_id…, [safe-path] a member name is untrusted input on the WRITE side., [cap] LRU by mtime, touched on read, two skips, and an honest overflow. (+2 more)

### Community 64 - "Node TypeScript Configuration"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 65 - "StubProvider"
Cohesion: 0.10
Nodes (23): _glossary_doc(), _live(), main(), _payload_text(), _prompt(), Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always; live…, Which of the line's marked honorifics appear in `out`, and which forbidden…, _renderings() (+15 more)

### Community 66 - "rerender"
Cohesion: 0.16
Nodes (13): Exception, Lock, _cache_miss_response(), 404 with a named kind. A missing cache entry is not a server fault. `kind` is…, AC-10: click a bubble, edit the translation, re-render that page alone. Neither…, rerender(), CacheMiss, Cancelled (+5 more)

### Community 67 - "OcrError"
Cohesion: 0.29
Nodes (6): OcrError, ndarray, RuntimeError, A recogniser that cannot run. Named, like every sidecar failure path., One text line -> (text, mean character confidence)., _Recogniser

### Community 68 - "Fixture Determinism Check"
Cohesion: 0.43
Nodes (6): generate(), main(), Phase 0a gate: two regenerations from an empty tree are byte-identical. uv run…, Relative-path -> sha256 for everything under the generated subdirs., sha256(), snapshot()

### Community 69 - "_floor_fits"
Cohesion: 0.29
Nodes (8): _capacity(), _floor_fits(), _longest(), The largest n in [0, n_max] for which fits(n) holds, given fits is monotone.…, The rung-3 state -- floor, tightened, no inset, no bleed -- as a predicate., The largest character count of `text` that fits at the floor, tightened.…, Rung 5's terminal branch. Returns (placed or None, rendered, reason). Cannot…, _truncate()

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

### Community 99 - "Scanned PDF Fixture"
Cohesion: 0.67
Nodes (3): Scanned PDF Fixture, Unreadable Scanned PDF Page 1 Image, Unreadable Scanned PDF Page 2 Image

### Community 145 - "_wrap_from"
Cohesion: 0.25
Nodes (8): _chord(), _narrowest(), The WIDEST contiguous span of the polygon at scanline y, or None. Contiguous,…, The tightest chord the line's own box spans, clipped to the page raster. A line…, Advance width including tracking, which PIL does not model. Tracking is applied…, Greedy wrap of `words` in slots starting at `top`. None if words remain. A slot…, text_width(), _wrap_from()

### Community 146 - "read_regions"
Cohesion: 0.50
Nodes (4): Mark a page directory as used NOW. Called on every read, not only on write, and…, The cached record, or None. Touches the directory -- see ``touch``., read_regions(), touch()

## Knowledge Gaps
- **291 isolated node(s):** `Tone`, `Where`, `Callback`, `SidecarState`, `Theme` (+286 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 910 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **48 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LLMClient` connect `LLMClient` to `check_group.py`, `StubProvider`, `main.py`, `check_spotfix.py`, `check_inpaint.py`, `check_probe.py`, `check_batch.py`, `check_typeset.py`, `Checks`, `check_cjk.py`, `check_cancel.py`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `Checks` connect `Checks` to `check_group.py`, `check_package.py`, `StubProvider`, `pdf.py`, `check_archives.py`, `check_inpaint.py`, `check_erase.py`, `check_probe.py`, `check_batch.py`, `check_models.py`, `fetch_fixtures.py`, `check_typeset.py`, `LLMClient`, `check_cjk.py`, `check_cancel.py`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `skip()` connect `Checks` to `check_group.py`, `StubProvider`, `check_package.py`, `pdf.py`, `check_archives.py`, `check_spotfix.py`, `check_inpaint.py`, `check_erase.py`, `check_probe.py`, `check_batch.py`, `check_typeset.py`, `fetch_fixtures.py`, `check_cjk.py`, `check_cancel.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Checks` (e.g. with `main()` and `main()`) actually correct?**
  _`Checks` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `LLMClient` (e.g. with `section_ingest_llm()` and `section_not_text()`) actually correct?**
  _`LLMClient` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `skip()` (e.g. with `main()` and `main()`) actually correct?**
  _`skip()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `StubProvider` (e.g. with `check_page_window()` and `check_probe_wiring()`) actually correct?**
  _`StubProvider` has 8 INFERRED edges - model-reasoned connections that need verification._