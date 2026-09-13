# Graph Report - MangaTranslator  (2026-09-14)

## Corpus Check
- 111 files · ~270,220 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1869 nodes · 3850 edges · 151 communities (105 shown, 42 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 90 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `73993a5a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pdf.py
- check_package.py
- start_job
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
- llm.py
- Budget
- StubProvider
- check_typeset.py
- fetch_fixtures.py
- Checks
- repack_extras
- Settings.tsx
- detect.py
- Tauri Application Configuration
- ocr_cjk.py
- inpainter.py
- _run_cached_page
- LLMClient
- check_cjk.py
- cache.py
- api.ts
- textmask.py
- mock-tauri.ts
- check_group.py
- typeset_page
- Frontend TypeScript Configuration
- check_erase.py
- job.py
- native.py
- models.py
- pipeline.py
- Response
- typeset.py
- Regression Test Runner
- OcrError
- App.tsx
- describeError
- Komalingo Brand Assets
- check_models.py
- _client
- _CountingReader
- imaging.py
- main.tsx
- _dismissed
- section_tier
- ocr_ja.py
- _Tier
- main.py
- load_font
- SpotFix.tsx
- check_probe.py
- detect
- check_cancel.py
- Job
- section_refs
- Node TypeScript Configuration
- check_id.py
- run_page
- get
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
- rerender
- read_translation
- Progress.tsx
- region.py
- _above_floor
- get_placement
- Image
- Exception
- ValueError

## God Nodes (most connected - your core abstractions)
1. `long_path()` - 54 edges
2. `Checks` - 50 edges
3. `LLMClient` - 43 edges
4. `skip()` - 38 edges
5. `StubProvider` - 36 edges
6. `page_dir()` - 33 edges
7. `main()` - 31 edges
8. `Budget` - 29 edges
9. `run()` - 25 edges
10. `panels` - 25 edges

## Surprising Connections (you probably didn't know these)
- `Komalingo Open Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-open-a.png → README.md
- `Komalingo Split Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-split-a.png → README.md
- `main()` --indirect_call--> `root()`  [INFERRED]
  tests/check_imaging.py → sidecar/cache.py
- `_dismissed()` --indirect_call--> `root()`  [INFERRED]
  tests/check_inpaint.py → sidecar/cache.py
- `main()` --indirect_call--> `root()`  [INFERRED]
  tests/check_models.py → sidecar/cache.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Komalingo Brand Asset Family** — brand_komalingo_icon_dark_dark_app_icon, brand_komalingo_icon_light_app_icon, brand_komalingo_lockup_on_dark_dark_lockup, brand_komalingo_lockup_light_lockup, brand_komalingo_mark_on_dark_dark_mark, brand_komalingo_mark_light_mark [EXTRACTED 0.99]
- **Local Manga Translation Stack** — readme_translation_pipeline, readme_manga_ocr, readme_pp_ocrv5, readme_pp_ocrv3_db, readme_comic_text_detector, readme_lama_manga [EXTRACTED 1.00]
- **Komalingo Brand Concept Explorations** — brand_explorations_concept_open_a_image, brand_explorations_concept_split_a_image [INFERRED 0.90]
- **Scanned PDF Fixture and Rendered Pages** — fixtures_pdf_scan_document, fixtures_pdf_scan_p1_image, fixtures_pdf_scan_p2_image [INFERRED 0.95]

## Communities (151 total, 42 thin omitted)

### Community 0 - "pdf.py"
Cohesion: 0.05
Nodes (69): PdfDocument, PdfPage, PdfReader, PdfWriter, _axis_aligned(), _copy_info(), copy_outline(), _decode_xobject() (+61 more)

### Community 1 - "check_package.py"
Cohesion: 0.07
Nodes (47): Return (execution_provider, reason). The reason is empty ONLY when CUDA was…, select_provider(), call(), main(), _parse_json(), Phase 0 -- the sidecar's HTTP surface and the shutdown gate (US-007). OFFLINE.…, Returns (status, body). A refused connection is status 0., (payload, why). `why` names the parse failure so the assert can print it. A… (+39 more)

### Community 2 - "start_job"
Cohesion: 0.25
Nodes (9): post, cache_clear(), cancel_job(), _job_response(), job_status(), Start a batch. Answers with the first status snapshot, immediately., AC-13: items not yet started are cancelled outright; an item mid-run stops at…, Empty the page cache, keeping only pages a running job holds. POST, never GET,… (+1 more)

### Community 3 - "check_spotfix.py"
Cohesion: 0.09
Nodes (55): Checks, The cached record, or None. Touches the directory -- see ``touch``., read_regions(), pages(), Yield `(ordinal, member, image)` for every decodable page, 1-based. Streamed…, _archive_edits(), _call(), _guarded() (+47 more)

### Community 4 - "check_archives.py"
Cohesion: 0.09
Nodes (52): comicinfo(), detect_format(), pages(), The container family of `path`, from its bytes. The tar test is last and is…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Same…, `(member name, raw bytes)` of the archive's ComicInfo.xml, or None. RAW bytes,…, Repack `entries` -- an iterable of `(member name, bytes)` -- at `dest`. Through…, write_archive() (+44 more)

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
Nodes (32): dependencies, react, react-dom, @tauri-apps/api, @tauri-apps/plugin-dialog, @tauri-apps/plugin-opener, devDependencies, @tauri-apps/cli (+24 more)

### Community 10 - "archive.py"
Cohesion: 0.06
Nodes (37): BytesIO, _decode(), _drain(), _head(), is_archive(), _libarchive(), libarchive_path(), LibarchiveMissing (+29 more)

### Community 11 - "run_item"
Cohesion: 0.15
Nodes (16): _check_lang(), _container(), item_dir(), _member_dest(), AC-6's round trip: the delivered pages, back into the input's format. **The…, The item's archive, rebuilt from the loose pages already on disk. What…, r"""One path segment, made safe to CREATE on Windows. The colon is the one that…, Reject a target language that is not a language tag. `lang` is substituted into… (+8 more)

### Community 12 - "Brand and Language Documentation"
Cohesion: 0.06
Nodes (31): Komalingo Open Concept A Brand Exploration, Komalingo Split Concept A Brand Exploration, Honorifics and register in the Indonesian output (AC-4), Register, The rule, The table, What stays as it is, What the gate holds (+23 more)

### Community 13 - "llm.py"
Cohesion: 0.14
Nodes (21): _decode_reply(), _from_event_stream(), image_data_url(), ProviderError, RuntimeError, OpenAI-compatible client. Owns the concurrency cap and the error contract.…, Carries the provider's own words to the UI. See AC-8., A 2xx body as the dict the OpenAI shape describes, or a ProviderError. Two… (+13 more)

### Community 14 - "Budget"
Cohesion: 0.09
Nodes (21): PathLike, Budget, is_comicinfo(), Member, _normalized(), Exception, r"""AC-11: the ingest budget. Every untrusted archive is read through this.…, One rejected archive, carrying which rule refused it and where. `reason` is… (+13 more)

### Community 15 - "StubProvider"
Cohesion: 0.09
Nodes (32): The files in `directory`, top level only, in natural order. Top level only: a…, scan(), build_folder(), _chats_with_image(), check_cancel(), check_cap(), check_image_item_id(), check_page_slots() (+24 more)

### Community 16 - "check_typeset.py"
Cohesion: 0.14
Nodes (26): ellipse_points(), The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.…, The job summary AC-1 requires: which regions were compromised, which failed.…, summary(), _batching_and_spotfix(), _check_page(), _compare_metrics(), _edge_cases() (+18 more)

### Community 17 - "fetch_fixtures.py"
Cohesion: 0.13
Nodes (26): main(), Phase 1 -- OCR truth on real vertical Japanese (AC-2). OFFLINE. Runs manga-ocr…, build_manifest(), _compare(), image_size(), load_manifest(), main(), print_report() (+18 more)

### Community 18 - "Checks"
Cohesion: 0.11
Nodes (22): Phase 0 -- the write protocol. Offline, no fixtures, no network. Asserts, from…, emitted_stages(), item_totals(), main(), Phase 0 -- the host/sidecar IPC contract (US-011). OFFLINE (US-003 stub). **Why…, Run one page as a CHILD PROCESS and read the stages off its stdout. In-process…, Run a 3-page .cbz as a CHILD PROCESS: the `total` on its lines, and the pages…, main() (+14 more)

### Community 19 - "repack_extras"
Cohesion: 0.15
Nodes (18): _admit(), expected_pages(), _is_page_name(), _lazy(), members(), Whether a member name is a page CANDIDATE. Identical rule to read_cbz., gz" | "bz2" | "xz" for a whole-file-compressed tar, "" for a plain one. This…, Run every member past the budget; return the page candidates to stream. Every… (+10 more)

### Community 20 - "Settings.tsx"
Cohesion: 0.16
Nodes (15): react, @tauri-apps/plugin-dialog, Alert(), ICON, Tone, Icon(), IconName, PATHS (+7 more)

### Community 21 - "detect.py"
Cohesion: 0.12
Nodes (24): _as_bgr(), _dedupe(), DetectError, _input_size(), _model(), RuntimeError, _quad_to_polygon(), quads() (+16 more)

### Community 22 - "Tauri Application Configuration"
Cohesion: 0.08
Nodes (24): app, security, windows, enable, scope, build, beforeBuildCommand, beforeDevCommand (+16 more)

### Community 23 - "ocr_cjk.py"
Cohesion: 0.11
Nodes (26): bbox(), convex_hull(), glyph_unit(), group(), _inside(), merge(), neighbours(), Group column-level detections into one region per bubble. Phase 2b. WHY this… (+18 more)

### Community 24 - "inpainter.py"
Cohesion: 0.13
Nodes (23): _crops(), erase(), _fill(), fill_white(), _flat(), _flat_surround(), _inpaint(), _lama() (+15 more)

### Community 25 - "_run_cached_page"
Cohesion: 0.13
Nodes (27): _bbox(), _box(), _changed_in_polygon(), _deliver(), detect(), emit(), expecting(), inpaint() (+19 more)

### Community 26 - "LLMClient"
Cohesion: 0.11
Nodes (14): glossary_text(), LLMClient, probe_token(), ValueError, The glossary block for `lang`, or "" when the target has none., The configured settings cannot be used. Not the provider's fault. A ValueError…, The only way out to the provider. _request holds the gate for the call, on the…, Every model the provider reports, in the provider's own order, as {"id",… (+6 more)

### Community 27 - "check_cjk.py"
Cohesion: 0.15
Nodes (20): _blank_and_ja(), _cache(), _centroid(), _fit(), _load(), main(), _ocr(), Phase 4 -- Chinese and Korean through PP-OCRv5 (AC-3). OFFLINE after first… (+12 more)

### Community 28 - "cache.py"
Cohesion: 0.09
Nodes (50): atomic_write(), long_path(), open_retry(), Yield a handle whose bytes land at `dest` only if the block completes. On any…, r"""Absolute, normalized, and \\?\-prefixed on Windows. The prefix turns off…, `open` with the same bounded retry as `_replace`, for READERS. The other half…, _cap_bytes(), clear() (+42 more)

### Community 29 - "api.ts"
Cohesion: 0.13
Nodes (17): PathField(), ApiError, CacheClearResult, CacheStats, JobItem, JobStatus, Progress, ProviderSettings (+9 more)

### Community 30 - "textmask.py"
Cohesion: 0.19
Nodes (13): EraseError, mask(), _model(), probability(), ndarray, RuntimeError, Which PIXELS are text: comic-text-detector's segmentation head. WHY a second…, Boolean (H, W): True where the model reads text ink. (+5 more)

### Community 31 - "mock-tauri.ts"
Cohesion: 0.14
Nodes (18): api(), Callback, callbacks, emit(), fakePage(), invoke(), jobs, listeners (+10 more)

### Community 32 - "check_group.py"
Cohesion: 0.14
Nodes (24): _bubble_of(), _ellipse_mask(), _fixture(), _geometry(), _ink(), _largest(), main(), _mask() (+16 more)

### Community 33 - "typeset_page"
Cohesion: 0.18
Nodes (12): _commit(), Fit, ink_style(), Image, ndarray, One region's typeset result. Every field is output-only. `rung` is the RUNG…, Typeset every region of one page. Returns (image, [Fit]). Two-phase by…, INK_PLAIN, INK_DARK or INK_BUSY from the page's gray inside `points`. (+4 more)

### Community 34 - "Frontend TypeScript Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+10 more)

### Community 35 - "check_erase.py"
Cohesion: 0.27
Nodes (11): _dilate(), _flag(), _in_box(), main(), _outline_through_quad(), _poly_mask(), _pre_2c_fill(), ndarray (+3 more)

### Community 36 - "job.py"
Cohesion: 0.10
Nodes (23): Event, r"""The single write protocol. Every file this app produces goes through here.…, _is_page(), members(), _natural_key(), r"""Read-only CBZ page enumeration. No repack, no safety budget, no other…, Sort key for a full archive member path, digit-aware and segment-wise. Segments…, A member that should be decoded as a page. Directory entries, macOS resource… (+15 more)

### Community 37 - "native.py"
Cohesion: 0.13
Nodes (19): os.replace with a short, bounded retry on Windows sharing violations. Two…, _replace(), _bsdtar(), bundled(), ensure_libarchive(), NativeMissing, Exception, r"""The native libraries the sidecar needs and pip cannot deliver (AC-6, .cbr).… (+11 more)

### Community 38 - "models.py"
Cohesion: 0.16
Nodes (18): ensure(), _ensure_directory(), fetch(), FetchError, _free_space(), model_dir(), on_disk(), RuntimeError (+10 more)

### Community 39 - "pipeline.py"
Cohesion: 0.14
Nodes (18): Container readers. One module per format, and each one reads only. Phase 3…, _content_region(), flush_repacks(), _model_id(), _page_lock(), _persist(), Lock, The seven-stage pipeline: detect, ocr, translate, inpaint, render, encode,… (+10 more)

### Community 40 - "Response"
Cohesion: 0.22
Nodes (10): Exception, exception_handler, Request, Response, _missing_source_response(), The last envelope. Every other error path in this file is deliberate; this one…, 404 naming the path when src_path is not a file; None when it is. Checked…, POST + correct nonce + loopback client, or the process stays up. Every… (+2 more)

### Community 41 - "typeset.py"
Cohesion: 0.12
Nodes (26): _bbox(), _chord(), _edge_adjacent(), floor_px(), _has_orphan(), _inset_points(), _ladder(), _layout() (+18 more)

### Community 42 - "Regression Test Runner"
Cohesion: 0.20
Nodes (16): append_record(), assert_interpreter(), discover(), env_class(), harvest_metrics(), last_status(), load_records(), main() (+8 more)

### Community 43 - "OcrError"
Cohesion: 0.29
Nodes (6): OcrError, ndarray, RuntimeError, A recogniser that cannot run. Named, like every sidecar failure path., One text line -> (text, mean character confidence)., _Recogniser

### Community 44 - "App.tsx"
Cohesion: 0.19
Nodes (13): App(), exitMessage(), frontPage(), loadTheme(), SidecarState, stageWord(), Theme, THEMES (+5 more)

### Community 45 - "describeError"
Cohesion: 0.16
Nodes (20): runFolder(), runItem(), describeError(), displayPath(), isApiError(), isInternal(), loadSettings(), saveSettings() (+12 more)

### Community 46 - "Komalingo Brand Assets"
Cohesion: 0.13
Nodes (15): Komalingo Light-Tile App Icon PNG, Komalingo Dark-Tile App Icon PNG, Komalingo Dark-Tile App Icon, Komalingo Light-Tile App Icon, Komalingo Lockup PNG, Komalingo Lockup for Light Backgrounds, Komalingo Lockup for Dark Backgrounds, Komalingo Lockup on Dark PNG (+7 more)

### Community 47 - "check_models.py"
Cohesion: 0.13
Nodes (13): The app's per-user data directory, and the one-time move from its old name. The…, `base`/Komalingo, moving an old-named sibling there if it is the only one.…, under(), onnx_session(), An onnxruntime session on the provider select_provider() names. Errors-only…, check_rename(), check_warmup(), main() (+5 more)

### Community 48 - "_client"
Cohesion: 0.20
Nodes (10): BaseModel, _client(), ItemRequest, JobRequest, What the Settings UI sends. No defaults -- absent means absent., One archive or PDF, start to finish. Phase 8 owns the QUEUE, not this route.…, AC-7: a folder, or an explicit list, through the queue. Exactly one of `dir`…, Build an LLMClient, or None for the offline placeholder path. Called INSIDE… (+2 more)

### Community 50 - "imaging.py"
Cohesion: 0.16
Nodes (17): encode(), output_path(), Image, Encode policy. The only place in the app that calls Image.save. Pillow silently…, Drop the GPS IFD, keep every other tag byte-identical., Encode to bytes in `fmt`, carrying metadata from `src` (default: img)., Destination path whose extension matches the SOURCE format. Named off the…, Encode `img` in the source image's format and write it atomically. Format comes… (+9 more)

### Community 51 - "main.tsx"
Cohesion: 0.22
Nodes (9): ErrorBoundary, Props, State, installGlobalReporting(), reportError(), boot(), dismissSplash(), failSplash() (+1 more)

### Community 52 - "_dismissed"
Cohesion: 0.20
Nodes (10): _apply_translations(), dismiss(), _load_translations(), punctuation_only(), Is there anything here a translator could change? A region that reads as…, (kept, dismissed): the regions the vision model said hold no text. Called after…, Fill translations from the cache. True only if EVERY region was covered., Fill translations from the cache. Returns the ids still to translate. A stored… (+2 more)

### Community 53 - "section_tier"
Cohesion: 0.22
Nodes (9): clear_tier(), page_hash(), SHA-256 of the DECODED pixels, plus mode and size. Mode and size are in the…, Resident decoded bytes in the memory tier. Phase 6's RSS gate reads this., tier_bytes(), [tier] LRU bounded by count OR bytes, and it never touches the disk., [key] the hash is over decoded pixels, and mode and size are in it., section_key() (+1 more)

### Community 54 - "ocr_ja.py"
Cohesion: 0.26
Nodes (11): _as_image(), canonical(), _get_model(), _is_blank(), ocr(), Image, Japanese OCR with confidence and blank-crop gates. Model output is…, Fold the two encodings manga-ocr picks that the page does not print. (+3 more)

### Community 55 - "_Tier"
Cohesion: 0.18
Nodes (5): Image, LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds. It counts…, Drop `key` if resident., Drop every raster of the page -- enforce_cap's path, one per erased set., _Tier

### Community 56 - "main.py"
Cohesion: 0.25
Nodes (9): FastAPI, lifespan(), The FastAPI sidecar. Loopback only, nonce-gated shutdown. Three security…, r"""Repair leaked cache references before anything can be evicted against them.…, pipeline.warm_models on a daemon thread; the lifespan never waits on it.…, Exit the moment stdin closes -- which, under Tauri, means the parent died.…, start_warmup(), watch_parent() (+1 more)

### Community 57 - "load_font"
Cohesion: 0.20
Nodes (10): FreeTypeFont, _draw_line(), load_font(), RuntimeError, A typeset pass that cannot proceed. Named, like every sidecar failure path., One truetype face, cached per size. MT_TYPESET_FONT overrides the search., Draw one line glyph by glyph, because PIL has no tracking parameter. `tracking`…, Raise a named error if called inside a running event loop, on EVERY page. The… (+2 more)

### Community 58 - "SpotFix.tsx"
Cohesion: 0.36
Nodes (9): RepackStatus, inPolygon(), laidInto(), pageSrc(), severity(), SpotFix(), pick(), select() (+1 more)

### Community 59 - "check_probe.py"
Cohesion: 0.36
Nodes (9): probe_png(), A PNG with `token` painted large and black on white. No prompt text. Built…, attempt(), main(), post(), Phase 0 -- the probe that touches a LIVE endpoint (US-012). Only this file…, Return (status, body) -- never raise on HTTP error., Never echo the live key, whatever the gateway reflected back. (+1 more)

### Community 60 - "detect"
Cohesion: 0.15
Nodes (14): Region, detect(), _glyph_px(), _inverse(), ndarray, Sort key: top band first, then right to left inside the band. The band exists…, Text regions on one page, as Regions carrying polygon and confidence. ids are…, Per quad: light glyphs on a dark ground? (mean gray inside under 128) The… (+6 more)

### Community 61 - "check_cancel.py"
Cohesion: 0.27
Nodes (11): build_inputs(), check_cancel(), check_no_partial(), check_resume(), _eight_page_archive(), events_of(), main(), ARCHIVE_PAGES pages from benign.cbz's three, each with one pixel of its own.… (+3 more)

### Community 62 - "Job"
Cohesion: 0.18
Nodes (4): Job, Every item, through the boundary, on `workers` threads. Never raises.…, Block until every item has a terminal status. False on timeout., AC-9, the half the product had never wired: probe once per job. Before this,…

### Community 63 - "section_refs"
Cohesion: 0.12
Nodes (34): add_ref(), clear_running(), delete_job(), drop_ref(), item_placements(), job_dir(), _job_key(), jobs_root() (+26 more)

### Community 64 - "Node TypeScript Configuration"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 65 - "check_id.py"
Cohesion: 0.11
Nodes (26): _glossary_doc(), _live(), main(), _payload_text(), _prompt(), Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always; live…, Which of the line's marked honorifics appear in `out`, and which forbidden…, _renderings() (+18 more)

### Community 66 - "run_page"
Cohesion: 0.14
Nodes (14): BoundedSemaphore, CacheMiss, Cancelled, _check_cancel(), _page_slots(), Exception, One page through all seven stages, in order. Returns the regions record.…, AC-13: the job's cancel token was set and this item stopped at a page boundary.… (+6 more)

### Community 67 - "get"
Cohesion: 0.18
Nodes (11): get, cache_stats(), health(), Liveness, plus which execution provider this process will run on. The provider…, Where the archive rebuild an edit scheduled has got to. The same dict…, Size, page count and corrections in the page cache, for the Settings card., GET can never shut anything down. A link or an <img> is a GET., repack_status() (+3 more)

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
Cohesion: 0.18
Nodes (14): ProviderError, _bad_settings_response(), models(), _probed(), _provider_response(), AC-8's envelope, built by json.dumps and never by an f-string. The body is the…, A 400 for settings this process cannot use. json.dumps, never f-string. Typed…, Run the vision probe for a route-built client; return its warning or "". The… (+6 more)

### Community 99 - "Scanned PDF Fixture"
Cohesion: 0.67
Nodes (3): Scanned PDF Fixture, Unreadable Scanned PDF Page 1 Image, Unreadable Scanned PDF Page 2 Image

### Community 142 - "rerender"
Cohesion: 0.29
Nodes (7): CacheMiss, _cache_miss_response(), AC-10's payload: one region of one page of one job. The page is addressed by…, 404 with a named kind. A missing cache entry is not a server fault. `kind` is…, AC-10: click a bubble, edit the translation, re-render that page alone. Neither…, rerender(), RerenderRequest

### Community 143 - "read_translation"
Cohesion: 0.33
Nodes (7): model_slug(), A filesystem-safe name for a model id that two ids cannot share. The readable…, ``{region_id: {"text": str, "edited": bool}}`` for one (lang, model)., Merge a fresh translation in, and never overwrite an ``edited`` entry.…, read_translation(), translation_name(), write_translation()

### Community 144 - "Progress.tsx"
Cohesion: 0.33
Nodes (6): LABEL, ProgressBar(), Stage, stageIndex(), STAGES, StageTrack()

### Community 145 - "region.py"
Cohesion: 0.50
Nodes (3): as_points(), The shared Region type: detect.py's output, typeset.py's input. Defined here…, Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.…

### Community 146 - "_above_floor"
Cohesion: 0.50
Nodes (4): _above_floor(), _calibrate(), Seconds for one reference page's worth of raster work. Best of N.…, (ok, description) for §E's hardware floor. Measured, not read off a label.…

### Community 147 - "get_placement"
Cohesion: 0.67
Nodes (3): get_placement(), _placement_key(), The placement entry for one position, or None. See put_placement.

## Knowledge Gaps
- **294 isolated node(s):** `PATHS`, `Callback`, `callbacks`, `listeners`, `STAGES` (+289 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 918 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **42 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `long_path()` connect `cache.py` to `pdf.py`, `check_spotfix.py`, `job.py`, `check_archives.py`, `models.py`, `native.py`, `Response`, `archive.py`, `run_item`, `StubProvider`, `imaging.py`, `repack_extras`, `detect.py`, `_run_cached_page`, `section_refs`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `Checks` connect `Checks` to `check_group.py`, `check_package.py`, `check_id.py`, `check_erase.py`, `check_archives.py`, `native.py`, `pdf.py`, `check_inpaint.py`, `check_probe.py`, `llm.py`, `StubProvider`, `check_models.py`, `fetch_fixtures.py`, `imaging.py`, `check_typeset.py`, `check_cjk.py`, `cache.py`, `check_cancel.py`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `Job` connect `Job` to `start_job`, `job.py`, `check_archives.py`, `StubProvider`, `check_cancel.py`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `LLMClient` (e.g. with `section_ingest_llm()` and `section_not_text()`) actually correct?**
  _`LLMClient` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `StubProvider` (e.g. with `section_ingest_llm()` and `section_not_text()`) actually correct?**
  _`StubProvider` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `PATHS`, `Callback`, `callbacks` to the rest of the system?**
  _294 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pdf.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05352112676056338 - nodes in this community are weakly interconnected._