# Graph Report - MangaTranslator  (2026-09-14)

## Corpus Check
- 111 files · ~270,220 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1862 nodes · 3878 edges · 144 communities (102 shown, 38 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 125 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2fae9d57`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pdf.py
- check_package.py
- main.py
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
- StubProvider
- Budget
- check_batch.py
- check_typeset.py
- fetch_fixtures.py
- skip
- repack_extras
- Translate.tsx
- detect.py
- Tauri Application Configuration
- group.py
- inpainter.py
- _run_cached_page
- LLMClient
- check_cjk.py
- cache.py
- check_api.py
- atomic.py
- mock-tauri.ts
- check_group.py
- typeset_page
- Frontend TypeScript Configuration
- _repack
- job.py
- sidecar/__init__.py
- models.py
- pipeline.py
- Response
- typeset.py
- Regression Test Runner
- ocr_cjk.py
- App.tsx
- Settings.tsx
- Komalingo Brand Assets
- check_models.py
- check_settings.py
- _CountingReader
- imaging.py
- main.tsx
- _dismissed
- read_raster
- ocr_ja.py
- _Tier
- lifespan
- TypesetError
- api.ts
- stub_provider.py
- detect
- check_cancel.py
- Job
- section_clear
- Node TypeScript Configuration
- check_id.py
- rerender
- repack_status
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
- translate
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
- run_page
- enforce_cap

## God Nodes (most connected - your core abstractions)
1. `Checks` - 77 edges
2. `long_path()` - 54 edges
3. `LLMClient` - 45 edges
4. `skip()` - 39 edges
5. `StubProvider` - 37 edges
6. `page_dir()` - 33 edges
7. `main()` - 31 edges
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
  tests/check_atomic.py → sidecar/cache.py
- `main()` --indirect_call--> `root()`  [INFERRED]
  tests/check_imaging.py → sidecar/cache.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Komalingo Brand Asset Family** — brand_komalingo_icon_dark_dark_app_icon, brand_komalingo_icon_light_app_icon, brand_komalingo_lockup_on_dark_dark_lockup, brand_komalingo_lockup_light_lockup, brand_komalingo_mark_on_dark_dark_mark, brand_komalingo_mark_light_mark [EXTRACTED 0.99]
- **Local Manga Translation Stack** — readme_translation_pipeline, readme_manga_ocr, readme_pp_ocrv5, readme_pp_ocrv3_db, readme_comic_text_detector, readme_lama_manga [EXTRACTED 1.00]
- **Komalingo Brand Concept Explorations** — brand_explorations_concept_open_a_image, brand_explorations_concept_split_a_image [INFERRED 0.90]
- **Scanned PDF Fixture and Rendered Pages** — fixtures_pdf_scan_document, fixtures_pdf_scan_p1_image, fixtures_pdf_scan_p2_image [INFERRED 0.95]

## Communities (144 total, 38 thin omitted)

### Community 0 - "pdf.py"
Cohesion: 0.05
Nodes (69): PdfDocument, PdfPage, PdfReader, PdfWriter, _axis_aligned(), _copy_info(), copy_outline(), _decode_xobject() (+61 more)

### Community 1 - "check_package.py"
Cohesion: 0.09
Nodes (37): health(), Liveness, plus which execution provider this process will run on. The provider…, Return (execution_provider, reason). The reason is empty ONLY when CUDA was…, select_provider(), build(), _exe_provider(), find_mt(), _folder_bytes() (+29 more)

### Community 2 - "main.py"
Cohesion: 0.11
Nodes (24): BaseModel, post, cache_clear(), cache_stats(), cancel_job(), ItemRequest, _job_response(), job_status() (+16 more)

### Community 3 - "Checks"
Cohesion: 0.09
Nodes (54): _above_floor(), _archive_edits(), _calibrate(), _call(), _guarded(), main(), _no_detect_or_ocr(), _quiet() (+46 more)

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
Cohesion: 0.09
Nodes (38): _assert_ink(), _assert_ring(), _assert_step_edge(), _band(), _best_ncc(), _chord_x(), _composite(), _expected_font_px() (+30 more)

### Community 8 - "Page Image Manifest"
Cohesion: 0.05
Nodes (40): sha256, size, sha256, size, sha256, size, sha256, size (+32 more)

### Community 9 - "package.json"
Cohesion: 0.06
Nodes (33): dependencies, react, react-dom, @tauri-apps/api, @tauri-apps/plugin-dialog, @tauri-apps/plugin-opener, devDependencies, @tauri-apps/cli (+25 more)

### Community 10 - "archive.py"
Cohesion: 0.08
Nodes (29): BytesIO, _decode(), _drain(), is_archive(), _libarchive(), libarchive_path(), _rar_entries(), _rar_payloads() (+21 more)

### Community 11 - "run_item"
Cohesion: 0.14
Nodes (16): _check_lang(), _container(), item_dir(), _member_dest(), _model_id(), The item's archive, rebuilt from the loose pages already on disk. What…, What the translation file is keyed on. 'offline' is a real key, not a hole. The…, r"""One path segment, made safe to CREATE on Windows. The colon is the one that… (+8 more)

### Community 12 - "Brand and Language Documentation"
Cohesion: 0.06
Nodes (31): Komalingo Open Concept A Brand Exploration, Komalingo Split Concept A Brand Exploration, Honorifics and register in the Indonesian output (AC-4), Register, The rule, The table, What stays as it is, What the gate holds (+23 more)

### Community 13 - "StubProvider"
Cohesion: 0.11
Nodes (21): image_data_url(), A data URL whose media type is what the bytes ARE, by signature. The page…, Region, emitted_stages(), item_totals(), main(), Phase 0 -- the host/sidecar IPC contract (US-011). OFFLINE (US-003 stub). **Why…, Run one page as a CHILD PROCESS and read the stages off its stdout. In-process… (+13 more)

### Community 14 - "Budget"
Cohesion: 0.09
Nodes (19): PathLike, Budget, is_comicinfo(), _normalized(), Exception, r"""AC-11: the ingest budget. Every untrusted archive is read through this.…, One rejected archive, carrying which rule refused it and where. `reason` is…, Member name with separators unified, for rule evaluation only. Backslash is a… (+11 more)

### Community 15 - "check_batch.py"
Cohesion: 0.09
Nodes (37): BoundedSemaphore, The files in `directory`, top level only, in natural order. Top level only: a…, Every path through the boundary, and the record when all are done. The blocking…, run_job(), scan(), _page_slots(), The process's page semaphore, sized by PAGE_WINDOW as it is NOW (a check can…, Run an item's pages concurrently. Returns records in page order. The reader… (+29 more)

### Community 16 - "check_typeset.py"
Cohesion: 0.11
Nodes (31): ellipse_points(), The shared Region type: detect.py's output, typeset.py's input. Defined here…, One detected text region, as it travels through the pipeline. `text` defaults…, The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.…, Region, The job summary AC-1 requires: which regions were compromised, which failed.…, summary(), _batching_and_spotfix() (+23 more)

### Community 17 - "fetch_fixtures.py"
Cohesion: 0.15
Nodes (22): build_manifest(), _compare(), image_size(), load_manifest(), main(), print_report(), What verify() found, split so a caller can assert on each part. `expected` is…, A mismatch line for one manifest entry, or None when the bytes match. (+14 more)

### Community 18 - "skip"
Cohesion: 0.22
Nodes (11): Phase 0 -- the write protocol. Offline, no fixtures, no network. Asserts, from…, main(), Phase 0 -- the seven-stage pipeline and its progress contract (US-006).…, main(), Phase 1 -- OCR truth on real vertical Japanese (AC-2). OFFLINE. Runs manga-ocr…, broken_checkout(), The exit-code contract, in one place so seven checks cannot drift. 0 pass · 1…, Exit 3 -- unless this is a LIVE skip and MT_REQUIRE_LIVE promotes it. Without… (+3 more)

### Community 19 - "repack_extras"
Cohesion: 0.15
Nodes (18): _admit(), expected_pages(), _is_page_name(), _lazy(), members(), Whether a member name is a page CANDIDATE. Identical rule to read_cbz., gz" | "bz2" | "xz" for a whole-file-compressed tar, "" for a plain one. This…, Run every member past the budget; return the page candidates to stream. Every… (+10 more)

### Community 20 - "Translate.tsx"
Cohesion: 0.11
Nodes (23): Alert(), ICON, Tone, Icon(), IconName, PATHS, PathField(), LABEL (+15 more)

### Community 21 - "detect.py"
Cohesion: 0.12
Nodes (24): _as_bgr(), _dedupe(), DetectError, _input_size(), _model(), RuntimeError, _quad_to_polygon(), quads() (+16 more)

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
Cohesion: 0.16
Nodes (22): _deliver(), detect(), emit(), expecting(), inpaint(), ocr(), page_context_image(), Image (+14 more)

### Community 26 - "LLMClient"
Cohesion: 0.08
Nodes (28): _decode_reply(), _from_event_stream(), glossary_text(), LLMClient, probe_png(), probe_token(), ProviderError, RuntimeError (+20 more)

### Community 27 - "check_cjk.py"
Cohesion: 0.12
Nodes (26): _blank_and_ja(), _cache(), _centroid(), _fit(), _load(), main(), _ocr(), Phase 4 -- Chinese and Korean through PP-OCRv5 (AC-3). OFFLINE after first… (+18 more)

### Community 28 - "cache.py"
Cohesion: 0.10
Nodes (49): long_path(), r"""Absolute, normalized, and \\?\-prefixed on Windows. The prefix turns off…, add_ref(), clear(), delete_job(), drop_ref(), has_edit_for_other_model(), has_edits() (+41 more)

### Community 29 - "check_api.py"
Cohesion: 0.22
Nodes (12): call(), main(), _parse_json(), Phase 0 -- the sidecar's HTTP surface and the shutdown gate (US-007). OFFLINE.…, Returns (status, body). A refused connection is status 0., (payload, why). `why` names the parse failure so the assert can print it. A…, wait_up(), True if the child ever printed `needle`. Reads the whole capture. (+4 more)

### Community 30 - "atomic.py"
Cohesion: 0.20
Nodes (10): atomic_write(), open_retry(), r"""The single write protocol. Every file this app produces goes through here.…, Yield a handle whose bytes land at `dest` only if the block completes. On any…, os.replace with a short, bounded retry on Windows sharing violations. Two…, `open` with the same bounded retry as `_replace`, for READERS. The other half…, _replace(), The evidence file check_package.py reads back. Atomic like every write. (+2 more)

### Community 31 - "mock-tauri.ts"
Cohesion: 0.15
Nodes (17): api(), Callback, callbacks, emit(), fakePage(), invoke(), jobs, listeners (+9 more)

### Community 32 - "check_group.py"
Cohesion: 0.14
Nodes (24): _bubble_of(), _ellipse_mask(), _fixture(), _geometry(), _ink(), _largest(), main(), _mask() (+16 more)

### Community 33 - "typeset_page"
Cohesion: 0.15
Nodes (14): as_points(), Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.…, _commit(), Fit, ink_style(), Image, ndarray, One region's typeset result. Every field is output-only. `rung` is the RUNG… (+6 more)

### Community 34 - "Frontend TypeScript Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+10 more)

### Community 35 - "_repack"
Cohesion: 0.50
Nodes (4): output_path(), Where the repacked archive lands. Same extension, except RAR -> .cbz. The…, AC-6's round trip: the delivered pages, back into the input's format. **The…, _repack()

### Community 36 - "job.py"
Cohesion: 0.09
Nodes (26): Event, _is_page(), members(), _natural_key(), pages(), r"""Read-only CBZ page enumeration. No repack, no safety budget, no other…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Streamed…, Sort key for a full archive member path, digit-aware and segment-wise. Segments… (+18 more)

### Community 37 - "sidecar/__init__.py"
Cohesion: 0.13
Nodes (17): _bsdtar(), bundled(), ensure_libarchive(), NativeMissing, Exception, r"""The native libraries the sidecar needs and pip cannot deliver (AC-6, .cbr).…, A native dependency could not be installed, with a named reason., Whether build/libarchive already holds the whole closure. (+9 more)

### Community 38 - "models.py"
Cohesion: 0.16
Nodes (18): ensure(), _ensure_directory(), fetch(), FetchError, _free_space(), model_dir(), on_disk(), RuntimeError (+10 more)

### Community 39 - "pipeline.py"
Cohesion: 0.15
Nodes (17): Container readers. One module per format, and each one reads only. Phase 3…, _bbox(), _box(), _changed_in_polygon(), _content_region(), flush_repacks(), _persist(), The seven-stage pipeline: detect, ocr, translate, inpaint, render, encode,… (+9 more)

### Community 40 - "Response"
Cohesion: 0.22
Nodes (10): exception_handler, Request, Response, _cache_miss_response(), Exception, The last envelope. Every other error path in this file is deliberate; this one…, 404 with a named kind. A missing cache entry is not a server fault. `kind` is…, POST + correct nonce + loopback client, or the process stays up. Every… (+2 more)

### Community 41 - "typeset.py"
Cohesion: 0.10
Nodes (31): FreeTypeFont, _bbox(), _chord(), _draw_line(), _edge_adjacent(), floor_px(), _has_orphan(), _inset_points() (+23 more)

### Community 42 - "Regression Test Runner"
Cohesion: 0.20
Nodes (16): append_record(), assert_interpreter(), discover(), env_class(), harvest_metrics(), last_status(), load_records(), main() (+8 more)

### Community 43 - "ocr_cjk.py"
Cohesion: 0.16
Nodes (13): lines(), ocr(), OcrError, ndarray, RuntimeError, Chinese and Korean OCR: PP-OCRv5 text-line recognition through onnxruntime.…, The parts that are text LINES, each read once. The detector answers per line…, Rows top to bottom (columns right to left), and WITHIN a row, left to right… (+5 more)

### Community 44 - "App.tsx"
Cohesion: 0.16
Nodes (16): App(), runFolder(), runItem(), exitMessage(), frontPage(), loadTheme(), SidecarState, stageWord() (+8 more)

### Community 45 - "Settings.tsx"
Cohesion: 0.13
Nodes (23): ModelCombobox, ModelComboboxHandle, CacheStats, describeError(), displayPath(), isApiError(), isInternal(), ModelInfo (+15 more)

### Community 46 - "Komalingo Brand Assets"
Cohesion: 0.13
Nodes (15): Komalingo Light-Tile App Icon PNG, Komalingo Dark-Tile App Icon PNG, Komalingo Dark-Tile App Icon, Komalingo Light-Tile App Icon, Komalingo Lockup PNG, Komalingo Lockup for Light Backgrounds, Komalingo Lockup for Dark Backgrounds, Komalingo Lockup on Dark PNG (+7 more)

### Community 47 - "check_models.py"
Cohesion: 0.13
Nodes (13): The app's per-user data directory, and the one-time move from its old name. The…, `base`/Komalingo, moving an old-named sibling there if it is the only one.…, under(), onnx_session(), An onnxruntime session on the provider select_provider() names. Errors-only…, check_rename(), check_warmup(), main() (+5 more)

### Community 48 - "check_settings.py"
Cohesion: 0.31
Nodes (7): main(), Phase 0 -- the Settings UI and the IPC client (US-009). OFFLINE. The frontend…, Source with comments removed. The point of the whole file: an assert that…, read(), strip_comments(), walk_src(), _load_fixtures()

### Community 49 - "_CountingReader"
Cohesion: 0.13
Nodes (10): _CountingReader, _head(), LibarchiveMissing, Exception, rar_generation(), No usable libarchive, so the RAR read path cannot run. A named exception rather…, 4 or 5 for a RAR file, by signature. Raises for anything else. The `.cbr`…, A read-only stream that charges every byte it produces to a Budget. This is the… (+2 more)

### Community 50 - "imaging.py"
Cohesion: 0.16
Nodes (17): encode(), output_path(), Image, Encode policy. The only place in the app that calls Image.save. Pillow silently…, Drop the GPS IFD, keep every other tag byte-identical., Encode to bytes in `fmt`, carrying metadata from `src` (default: img)., Destination path whose extension matches the SOURCE format. Named off the…, Encode `img` in the source image's format and write it atomically. Format comes… (+9 more)

### Community 51 - "main.tsx"
Cohesion: 0.21
Nodes (10): react, ErrorBoundary, Props, State, installGlobalReporting(), reportError(), boot(), dismissSplash() (+2 more)

### Community 52 - "_dismissed"
Cohesion: 0.20
Nodes (10): _apply_translations(), dismiss(), _load_translations(), punctuation_only(), Is there anything here a translator could change? A region that reads as…, (kept, dismissed): the regions the vision model said hold no text. Called after…, Fill translations from the cache. True only if EVERY region was covered., Fill translations from the cache. Returns the ids still to translate. A stored… (+2 more)

### Community 53 - "read_raster"
Cohesion: 0.11
Nodes (20): clear_tier(), model_slug(), page_hash(), Image, _raster(), raster_name(), SHA-256 of the DECODED pixels, plus mode and size. Mode and size are in the…, A filesystem-safe name for a model id that two ids cannot share. The readable… (+12 more)

### Community 54 - "ocr_ja.py"
Cohesion: 0.26
Nodes (11): _as_image(), canonical(), _get_model(), _is_blank(), ocr(), Image, Japanese OCR with confidence and blank-crop gates. Model output is…, Fold the two encodings manga-ocr picks that the page does not print. (+3 more)

### Community 55 - "_Tier"
Cohesion: 0.20
Nodes (4): LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds. It counts…, Drop `key` if resident., Drop every raster of the page -- enforce_cap's path, one per erased set., _Tier

### Community 56 - "lifespan"
Cohesion: 0.29
Nodes (8): FastAPI, lifespan(), r"""Repair leaked cache references before anything can be evicted against them.…, pipeline.warm_models on a daemon thread; the lifespan never waits on it.…, Exit the moment stdin closes -- which, under Tauri, means the parent died.…, start_warmup(), watch_parent(), Thread

### Community 57 - "TypesetError"
Cohesion: 0.40
Nodes (5): RuntimeError, A typeset pass that cannot proceed. Named, like every sidecar failure path., Raise a named error if called inside a running event loop, on EVERY page. The…, _refuse_running_loop(), TypesetError

### Community 58 - "api.ts"
Cohesion: 0.16
Nodes (17): api, ApiError, CacheClearResult, PageRecord, Region, RepackStatus, Target, TranslateResult (+9 more)

### Community 59 - "stub_provider.py"
Cohesion: 0.29
Nodes (7): _as_event_stream(), _chat_reply(), An OpenAI-compatible provider stub, in-process, no new dependency. Replays the…, The ids a request asked about; [0] when the prompt carried none., Echo one translation per region the request asked about. The client batches a…, A chat.completion re-framed as the chunks a streaming gateway sends. The…, _region_ids()

### Community 60 - "detect"
Cohesion: 0.18
Nodes (12): Region, detect(), _glyph_px(), _inverse(), ndarray, Sort key: top band first, then right to left inside the band. The band exists…, Text regions on one page, as Regions carrying polygon and confidence. ids are…, Per quad: light glyphs on a dark ground? (mean gray inside under 128) The… (+4 more)

### Community 61 - "check_cancel.py"
Cohesion: 0.27
Nodes (11): build_inputs(), check_cancel(), check_no_partial(), check_resume(), _eight_page_archive(), events_of(), main(), ARCHIVE_PAGES pages from benign.cbz's three, each with one pixel of its own.… (+3 more)

### Community 62 - "Job"
Cohesion: 0.18
Nodes (4): Job, Every item, through the boundary, on `workers` threads. Never raises.…, Block until every item has a terminal status. False on timeout., AC-9, the half the product had never wired: probe once per job. Before this,…

### Community 63 - "section_clear"
Cohesion: 0.16
Nodes (19): clear_running(), get_placement(), item_placements(), job_dir(), _job_key(), jobs_root(), mark_running(), The cache root. MT_CACHE_DIR wins, so tests never touch the real one. (+11 more)

### Community 64 - "Node TypeScript Configuration"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 65 - "check_id.py"
Cohesion: 0.27
Nodes (11): _glossary_doc(), _live(), main(), _payload_text(), _prompt(), Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always; live…, Which of the line's marked honorifics appear in `out`, and which forbidden…, _renderings() (+3 more)

### Community 66 - "rerender"
Cohesion: 0.18
Nodes (11): AC-10: click a bubble, edit the translation, re-render that page alone. Neither…, rerender(), CacheMiss, Cancelled, _page_lock(), Exception, Lock, AC-10: one region's text changes, that page alone is re-drawn. Neither `detect`… (+3 more)

### Community 67 - "repack_status"
Cohesion: 0.50
Nodes (4): Where the archive rebuild an edit scheduled has got to. The same dict…, repack_status(), The repack status for one item: idle, pending, running, done or failed., repack_status()

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

### Community 98 - "translate"
Cohesion: 0.13
Nodes (20): ValueError, The configured settings cannot be used. Not the provider's fault. A ValueError…, SettingsError, _bad_settings_response(), _client(), _missing_source_response(), models(), _probed() (+12 more)

### Community 99 - "Scanned PDF Fixture"
Cohesion: 0.67
Nodes (3): Scanned PDF Fixture, Unreadable Scanned PDF Page 1 Image, Unreadable Scanned PDF Page 2 Image

### Community 142 - "run_page"
Cohesion: 0.50
Nodes (4): _check_cancel(), One page through all seven stages, in order. Returns the regions record.…, Raise Cancelled if the token is set. `cancel` is anything with is_set() -- a…, run_page()

### Community 146 - "enforce_cap"
Cohesion: 0.21
Nodes (13): _cap_bytes(), _dir_size(), disk_bytes(), enforce_cap(), pages_root(), The cached record, or None. Touches the directory -- see ``touch``., Evict LRU by directory mtime down to the target. Returns a warning or None. Two…, What the Settings card shows before the user decides to clear. `edited_pages`… (+5 more)

## Knowledge Gaps
- **294 isolated node(s):** `expected_json_sha256`, `sha256`, `size`, `sha256`, `size` (+289 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 913 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **38 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Checks` connect `Checks` to `pdf.py`, `check_package.py`, `check_archives.py`, `check_inpaint.py`, `StubProvider`, `check_batch.py`, `check_typeset.py`, `skip`, `enforce_cap`, `inpainter.py`, `LLMClient`, `check_cjk.py`, `cache.py`, `check_api.py`, `atomic.py`, `check_group.py`, `sidecar/__init__.py`, `check_models.py`, `check_settings.py`, `imaging.py`, `read_raster`, `check_cancel.py`, `section_clear`, `check_id.py`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `LLMClient` connect `LLMClient` to `check_group.py`, `check_id.py`, `main.py`, `translate`, `Checks`, `check_inpaint.py`, `StubProvider`, `check_batch.py`, `check_typeset.py`, `_dismissed`, `check_cjk.py`, `check_cancel.py`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `skip()` connect `skip` to `check_group.py`, `check_id.py`, `check_package.py`, `pdf.py`, `check_archives.py`, `sidecar/__init__.py`, `Checks`, `check_inpaint.py`, `StubProvider`, `check_batch.py`, `check_typeset.py`, `fetch_fixtures.py`, `inpainter.py`, `LLMClient`, `check_cjk.py`, `check_cancel.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 25 inferred relationships involving `Checks` (e.g. with `_call()` and `_guarded()`) actually correct?**
  _`Checks` has 25 INFERRED edges - model-reasoned connections that need verification._
- **What connects `expected_json_sha256`, `sha256`, `size` to the rest of the system?**
  _294 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pdf.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05352112676056338 - nodes in this community are weakly interconnected._
- **Should `check_package.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08906882591093117 - nodes in this community are weakly interconnected._