# Graph Report - MangaTranslator  (2026-09-15)

## Corpus Check
- 111 files · ~273,876 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1879 nodes · 3926 edges · 138 communities (96 shown, 38 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 129 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1de86826`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pdf.py
- StubProvider
- job.py
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
- check_id.py
- Budget
- check_batch.py
- check_typeset.py
- skip
- check_cjk.py
- describeError
- Job.tsx
- detect.py
- Tauri Application Configuration
- ocr_cjk.py
- inpainter.py
- inpaint
- LLMClient
- OcrError
- cache.py
- api.ts
- EraseError
- mock-tauri.ts
- check_group.py
- llm.py
- Frontend TypeScript Configuration
- Member
- atomic.py
- load_font
- models.py
- pipeline.py
- sidecar/__init__.py
- typeset.py
- Regression Test Runner
- _repack
- App.tsx
- Settings.tsx
- Komalingo Brand Assets
- check_models.py
- typeset_page
- _CountingReader
- imaging.py
- main.tsx
- _run_cached_page
- _wrap_from
- ocr_ja.py
- _Tier
- select_provider
- check_erase.py
- SpotFix.tsx
- check_probe.py
- chrf_pp
- section_refs
- Node TypeScript Configuration
- rerender
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
- _floor_fits

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

## Communities (138 total, 38 thin omitted)

### Community 0 - "pdf.py"
Cohesion: 0.05
Nodes (73): PdfDocument, PdfPage, PdfReader, PdfWriter, The file is not an archive this build reads. Carries a reason string., UnsupportedArchive, _axis_aligned(), _copy_info() (+65 more)

### Community 1 - "StubProvider"
Cohesion: 0.05
Nodes (56): cache_stats(), Where the archive rebuild an edit scheduled has got to. The same dict…, Size, page count and corrections in the page cache, for the Settings card., GET can never shut anything down. A link or an <img> is a GET., repack_status(), shutdown_get(), The repack status for one item: idle, pending, running, done or failed., repack_status() (+48 more)

### Community 2 - "job.py"
Cohesion: 0.09
Nodes (26): Event, _is_page(), members(), _natural_key(), pages(), r"""Read-only CBZ page enumeration. No repack, no safety budget, no other…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Streamed…, Sort key for a full archive member path, digit-aware and segment-wise. Segments… (+18 more)

### Community 3 - "Checks"
Cohesion: 0.08
Nodes (61): clear_tier(), _above_floor(), _archive_edits(), _calibrate(), _call(), _guarded(), main(), _no_detect_or_ocr() (+53 more)

### Community 4 - "check_archives.py"
Cohesion: 0.10
Nodes (48): comicinfo(), detect_format(), pages(), The container family of `path`, from its bytes. The tar test is last and is…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Same…, `(member name, raw bytes)` of the archive's ComicInfo.xml, or None. RAW bytes,…, Repack `entries` -- an iterable of `(member name, bytes)` -- at `dest`. Through…, write_archive() (+40 more)

### Community 5 - "gen_fixtures.py"
Cohesion: 0.10
Nodes (43): _archive_page(), _cbz_page(), draw_columns(), draw_lines(), draw_vertical(), gen_archives(), gen_bubbles(), gen_cbz() (+35 more)

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
Cohesion: 0.07
Nodes (36): BytesIO, _admit(), _decode(), _drain(), expected_pages(), _head(), is_archive(), _is_page_name() (+28 more)

### Community 11 - "run_item"
Cohesion: 0.25
Nodes (8): page_hash(), SHA-256 of the DECODED pixels, plus mode and size. Mode and size are in the…, _model_id(), Run an item's pages concurrently. Returns records in page order. The reader…, What the translation file is keyed on. 'offline' is a real key, not a hole. The…, Every page of one archive or PDF, through the cache. Returns the record.…, run_item(), _run_pages()

### Community 12 - "Brand and Language Documentation"
Cohesion: 0.06
Nodes (31): Komalingo Open Concept A Brand Exploration, Komalingo Split Concept A Brand Exploration, Honorifics and register in the Indonesian output (AC-4), Register, The rule, The table, What stays as it is, What the gate holds (+23 more)

### Community 13 - "check_id.py"
Cohesion: 0.10
Nodes (30): Region, _glossary_doc(), _live(), main(), _payload_text(), _prompt(), Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always; live…, Which of the line's marked honorifics appear in `out`, and which forbidden… (+22 more)

### Community 14 - "Budget"
Cohesion: 0.09
Nodes (19): PathLike, Budget, is_comicinfo(), _normalized(), Exception, r"""AC-11: the ingest budget. Every untrusted archive is read through this.…, One rejected archive, carrying which rule refused it and where. `reason` is…, Member name with separators unified, for rule evaluation only. Backslash is a… (+11 more)

### Community 15 - "check_batch.py"
Cohesion: 0.05
Nodes (50): BoundedSemaphore, Job, The files in `directory`, top level only, in natural order. Top level only: a…, Every item, through the boundary, on `workers` threads. Never raises.…, Block until every item has a terminal status. False on timeout., AC-9, the half the product had never wired: probe once per job. Before this,…, Every path through the boundary, and the record when all are done. The blocking…, run_job() (+42 more)

### Community 16 - "check_typeset.py"
Cohesion: 0.12
Nodes (29): ellipse_points(), The shared Region type: detect.py's output, typeset.py's input. Defined here…, One detected text region, as it travels through the pipeline. `text` defaults…, The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.…, Region, The job summary AC-1 requires: which regions were compromised, which failed.…, summary(), _batching_and_spotfix() (+21 more)

### Community 17 - "skip"
Cohesion: 0.06
Nodes (53): Phase 0 -- the write protocol. Offline, no fixtures, no network. Asserts, from…, emitted_stages(), item_totals(), main(), Phase 0 -- the host/sidecar IPC contract (US-011). OFFLINE (US-003 stub). **Why…, Run one page as a CHILD PROCESS and read the stages off its stdout. In-process…, Run a 3-page .cbz as a CHILD PROCESS: the `total` on its lines, and the pages…, main() (+45 more)

### Community 18 - "check_cjk.py"
Cohesion: 0.13
Nodes (25): detect(), Text regions from detect.py's DB model. Regions become plain dicts here rather…, _blank_and_ja(), _cache(), _centroid(), _fit(), _load(), main() (+17 more)

### Community 19 - "describeError"
Cohesion: 0.27
Nodes (10): runFolder(), runItem(), describeError(), isApiError(), isInternal(), loadSettings(), Job(), cancel() (+2 more)

### Community 20 - "Job.tsx"
Cohesion: 0.17
Nodes (13): Alert(), ICON, Tone, Icon(), IconName, PATHS, LABEL, ProgressBar() (+5 more)

### Community 21 - "detect.py"
Cohesion: 0.09
Nodes (34): Region, _as_bgr(), _dedupe(), detect(), DetectError, _glyph_px(), _input_size(), _inverse() (+26 more)

### Community 22 - "Tauri Application Configuration"
Cohesion: 0.08
Nodes (24): app, security, windows, enable, scope, build, beforeBuildCommand, beforeDevCommand (+16 more)

### Community 23 - "ocr_cjk.py"
Cohesion: 0.10
Nodes (28): separated(i, j): does ink run across the gap between two adjacent quads? The…, _separator(), bbox(), convex_hull(), glyph_unit(), group(), _inside(), merge() (+20 more)

### Community 24 - "inpainter.py"
Cohesion: 0.13
Nodes (23): _crops(), erase(), _fill(), fill_white(), _flat(), _flat_surround(), _inpaint(), _lama() (+15 more)

### Community 25 - "inpaint"
Cohesion: 0.13
Nodes (23): _bbox(), _changed_in_polygon(), emit(), encode_and_write(), expecting(), inpaint(), ocr(), page_context_image() (+15 more)

### Community 26 - "LLMClient"
Cohesion: 0.11
Nodes (16): glossary_text(), image_data_url(), LLMClient, probe_token(), ValueError, The glossary block for `lang`, or "" when the target has none., The configured settings cannot be used. Not the provider's fault. A ValueError…, A data URL whose media type is what the bytes ARE, by signature. The page… (+8 more)

### Community 27 - "OcrError"
Cohesion: 0.29
Nodes (6): OcrError, ndarray, RuntimeError, A recogniser that cannot run. Named, like every sidecar failure path., One text line -> (text, mean character confidence)., _Recogniser

### Community 28 - "cache.py"
Cohesion: 0.11
Nodes (41): long_path(), r"""Absolute, normalized, and \\?\-prefixed on Windows. The prefix turns off…, _cap_bytes(), clear(), _dir_size(), disk_bytes(), enforce_cap(), has_edit_for_other_model() (+33 more)

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
Cohesion: 0.15
Nodes (24): _box(), The region's bounding box in thousandths of the page, for the vision model.…, _bubble_of(), _ellipse_mask(), _fixture(), _geometry(), _ink(), _largest() (+16 more)

### Community 33 - "llm.py"
Cohesion: 0.16
Nodes (13): _decode_reply(), _from_event_stream(), is_null_word(), ProviderError, RuntimeError, OpenAI-compatible client. Owns the concurrency cap and the error contract.…, The instruction's null, written as the STRING "null". Measured on a real…, Carries the provider's own words to the UI. See AC-8. (+5 more)

### Community 34 - "Frontend TypeScript Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+10 more)

### Community 35 - "Member"
Cohesion: 0.14
Nodes (14): _libarchive(), libarchive_path(), _rar_entries(), _rar_payloads(), r"""Where the bundled libarchive lives, or None to let the loader search.…, Import the binding with the resolved library, or raise LibarchiveMissing. The…, (name, safety.Member) for every zip entry, in archive order., Plain tar only. A compressed one goes through `_tar_single_pass`. `"r:"`, never… (+6 more)

### Community 36 - "atomic.py"
Cohesion: 0.11
Nodes (18): atomic_write(), open_retry(), r"""The single write protocol. Every file this app produces goes through here.…, Yield a handle whose bytes land at `dest` only if the block completes. On any…, os.replace with a short, bounded retry on Windows sharing violations. Two…, `open` with the same bounded retry as `_replace`, for READERS. The other half…, _replace(), The cache root. MT_CACHE_DIR wins, so tests never touch the real one. (+10 more)

### Community 37 - "load_font"
Cohesion: 0.18
Nodes (12): FreeTypeFont, _draw_line(), load_font(), RuntimeError, _raster_metrics(), A typeset pass that cannot proceed. Named, like every sidecar failure path., One truetype face, cached per size. MT_TYPESET_FONT overrides the search., (overflow_x, overflow_y, clipped_glyphs, offpage_ink_px), read off drawn ink.… (+4 more)

### Community 38 - "models.py"
Cohesion: 0.16
Nodes (18): ensure(), _ensure_directory(), fetch(), FetchError, _free_space(), model_dir(), on_disk(), RuntimeError (+10 more)

### Community 39 - "pipeline.py"
Cohesion: 0.07
Nodes (34): Container readers. One module per format, and each one reads only. Phase 3…, _ask_with_retry(), CacheMiss, Cancelled, _check_cancel(), _check_lang(), _content_region(), flush_repacks() (+26 more)

### Community 40 - "sidecar/__init__.py"
Cohesion: 0.18
Nodes (8): _bsdtar(), bundled(), NativeMissing, Exception, r"""The native libraries the sidecar needs and pip cannot deliver (AC-6, .cbr).…, A native dependency could not be installed, with a named reason., Whether build/libarchive already holds the whole closure., r"""Windows' own tar.exe, which is bsdtar and therefore reads .tar.zst. A…

### Community 41 - "typeset.py"
Cohesion: 0.20
Nodes (16): _bbox(), _edge_adjacent(), floor_px(), _has_orphan(), _inset_points(), _ladder(), _layout(), max_font_px() (+8 more)

### Community 42 - "Regression Test Runner"
Cohesion: 0.20
Nodes (16): append_record(), assert_interpreter(), discover(), env_class(), harvest_metrics(), last_status(), load_records(), main() (+8 more)

### Community 43 - "_repack"
Cohesion: 0.50
Nodes (4): output_path(), Where the repacked archive lands. Same extension, except RAR -> .cbz. The…, AC-6's round trip: the delivered pages, back into the input's format. **The…, _repack()

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
Cohesion: 0.15
Nodes (11): The app's per-user data directory, and the one-time move from its old name. The…, `base`/Komalingo, moving an old-named sibling there if it is the only one.…, under(), check_rename(), check_warmup(), main(), Phase 0 -- resumable fetch and EP selection (AC-14). OFFLINE. Serves bytes from…, [warmup] models load ahead of the first page, and never in the way of one.… (+3 more)

### Community 48 - "typeset_page"
Cohesion: 0.15
Nodes (14): as_points(), Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.…, _commit(), Fit, ink_style(), Image, ndarray, One region's typeset result. Every field is output-only. `rung` is the RUNG… (+6 more)

### Community 49 - "_CountingReader"
Cohesion: 0.18
Nodes (5): _CountingReader, LibarchiveMissing, Exception, No usable libarchive, so the RAR read path cannot run. A named exception rather…, A read-only stream that charges every byte it produces to a Budget. This is the…

### Community 50 - "imaging.py"
Cohesion: 0.18
Nodes (15): encode(), output_path(), Image, Encode policy. The only place in the app that calls Image.save. Pillow silently…, Drop the GPS IFD, keep every other tag byte-identical., Encode to bytes in `fmt`, carrying metadata from `src` (default: img)., Destination path whose extension matches the SOURCE format. Named off the…, Encode `img` in the source image's format and write it atomically. Format comes… (+7 more)

### Community 51 - "main.tsx"
Cohesion: 0.21
Nodes (10): react, ErrorBoundary, Props, State, installGlobalReporting(), reportError(), boot(), dismissSplash() (+2 more)

### Community 52 - "_run_cached_page"
Cohesion: 0.10
Nodes (27): has_page(), has_raster(), model_slug(), A filesystem-safe name for a model id that two ids cannot share. The readable…, The cached record, or None. Touches the directory -- see ``touch``., Whether the page has any raster on disk, without decoding one., ``{region_id: {"text": str, "edited": bool}}`` for one (lang, model)., Merge a fresh translation in, and never overwrite an ``edited`` entry.… (+19 more)

### Community 53 - "_wrap_from"
Cohesion: 0.25
Nodes (8): _chord(), _narrowest(), The WIDEST contiguous span of the polygon at scanline y, or None. Contiguous,…, The tightest chord the line's own box spans, clipped to the page raster. A line…, Advance width including tracking, which PIL does not model. Tracking is applied…, Greedy wrap of `words` in slots starting at `top`. None if words remain. A slot…, text_width(), _wrap_from()

### Community 54 - "ocr_ja.py"
Cohesion: 0.26
Nodes (11): _as_image(), canonical(), _get_model(), _is_blank(), ocr(), Image, Japanese OCR with confidence and blank-crop gates. Model output is…, Fold the two encodings manga-ocr picks that the page does not print. (+3 more)

### Community 55 - "_Tier"
Cohesion: 0.18
Nodes (5): Image, LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds. It counts…, Drop `key` if resident., Drop every raster of the page -- enforce_cap's path, one per erased set., _Tier

### Community 56 - "select_provider"
Cohesion: 0.33
Nodes (6): health(), Liveness, plus which execution provider this process will run on. The provider…, onnx_session(), Return (execution_provider, reason). The reason is empty ONLY when CUDA was…, An onnxruntime session on the provider select_provider() names. Errors-only…, select_provider()

### Community 57 - "check_erase.py"
Cohesion: 0.27
Nodes (11): _dilate(), _flag(), _in_box(), main(), _outline_through_quad(), _poly_mask(), _pre_2c_fill(), ndarray (+3 more)

### Community 58 - "SpotFix.tsx"
Cohesion: 0.36
Nodes (9): RepackStatus, inPolygon(), laidInto(), pageSrc(), severity(), SpotFix(), pick(), select() (+1 more)

### Community 59 - "check_probe.py"
Cohesion: 0.36
Nodes (9): probe_png(), A PNG with `token` painted large and black on white. No prompt text. Built…, attempt(), main(), post(), Phase 0 -- the probe that touches a LIVE endpoint (US-012). Only this file…, Return (status, body) -- never raise on HTTP error., Never echo the live key, whatever the gateway reflected back. (+1 more)

### Community 60 - "chrf_pp"
Cohesion: 0.40
Nodes (5): chrf_pp(), _ngrams(), chrF++'s word tokens: whitespace split, one leading or trailing ASCII…, Corpus chrF++ (Popovic 2017) over the stdlib, sacrebleu's arithmetic: character…, _words()

### Community 63 - "section_refs"
Cohesion: 0.11
Nodes (36): add_ref(), clear_running(), delete_job(), drop_ref(), get_placement(), item_placements(), job_dir(), _job_key() (+28 more)

### Community 64 - "Node TypeScript Configuration"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 66 - "rerender"
Cohesion: 0.13
Nodes (19): exception_handler, Request, Response, _bad_settings_response(), _cache_miss_response(), models(), _provider_response(), Exception (+11 more)

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
Nodes (38): BaseModel, FastAPI, post, cache_clear(), cancel_job(), _client(), ItemRequest, _job_response() (+30 more)

### Community 99 - "Scanned PDF Fixture"
Cohesion: 0.67
Nodes (3): Scanned PDF Fixture, Unreadable Scanned PDF Page 1 Image, Unreadable Scanned PDF Page 2 Image

### Community 144 - "_floor_fits"
Cohesion: 0.29
Nodes (8): _capacity(), _floor_fits(), _longest(), The largest n in [0, n_max] for which fits(n) holds, given fits is monotone.…, The rung-3 state -- floor, tightened, no inset, no bleed -- as a predicate., The largest character count of `text` that fits at the floor, tightened.…, Rung 5's terminal branch. Returns (placed or None, rendered, reason). Cannot…, _truncate()

## Knowledge Gaps
- **294 isolated node(s):** `expected_json_sha256`, `sha256`, `size`, `sha256`, `size` (+289 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 920 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **38 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Checks` connect `Checks` to `check_group.py`, `StubProvider`, `pdf.py`, `check_archives.py`, `atomic.py`, `check_inpaint.py`, `check_id.py`, `check_batch.py`, `check_models.py`, `skip`, `check_cjk.py`, `imaging.py`, `check_typeset.py`, `check_erase.py`, `check_probe.py`, `section_refs`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `LLMClient` connect `LLMClient` to `check_group.py`, `llm.py`, `main.py`, `rerender`, `Checks`, `check_inpaint.py`, `check_id.py`, `check_batch.py`, `check_typeset.py`, `skip`, `check_cjk.py`, `check_probe.py`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `skip()` connect `skip` to `check_group.py`, `StubProvider`, `pdf.py`, `Checks`, `check_archives.py`, `check_inpaint.py`, `check_id.py`, `check_batch.py`, `check_typeset.py`, `check_cjk.py`, `check_erase.py`, `check_probe.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `Checks` (e.g. with `_call()` and `_guarded()`) actually correct?**
  _`Checks` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `LLMClient` (e.g. with `models()` and `section_skipped()`) actually correct?**
  _`LLMClient` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `expected_json_sha256`, `sha256`, `size` to the rest of the system?**
  _294 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pdf.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05009009009009009 - nodes in this community are weakly interconnected._