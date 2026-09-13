# Graph Report - MangaTranslator  (2026-09-14)

## Corpus Check
- 111 files · ~264,095 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1832 nodes · 3687 edges · 152 communities (101 shown, 47 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 110 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `04b2557c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pdf.py
- StubProvider
- main.py
- check_spotfix.py
- check_archives.py
- gen_fixtures.py
- lib.rs
- check_inpaint.py
- Page Image Manifest
- package.json
- archive.py
- pipeline.py
- Brand and Language Documentation
- check_probe.py
- Budget
- check_batch.py
- check_typeset.py
- fetch_fixtures.py
- Checks
- job.py
- Settings.tsx
- quads
- Tauri Application Configuration
- group.py
- inpainter.py
- read_translation
- llm.py
- check_cjk.py
- section_refs
- textmask.py
- check_id.py
- mock-tauri.ts
- check_group.py
- sidecar/__init__.py
- Frontend TypeScript Configuration
- repack_extras
- read_cbz.py
- atomic.py
- models.py
- _run_cached_page
- check_erase.py
- typeset.py
- Regression Test Runner
- OcrError
- App.tsx
- api.ts
- Komalingo Brand Assets
- check_models.py
- Translate.tsx
- _CountingReader
- typeset_page
- main.tsx
- cache.py
- LLMClient
- ocr_ja.py
- section_tier
- Job
- run_job
- SpotFix.tsx
- check_cancel.py
- check_ipc.py
- detect.py
- _floor_fits
- _dismissed
- Node TypeScript Configuration
- stub_provider.py
- run_page
- detect
- Fixture Determinism Check
- skip
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
- check_warmup
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
- check_provider.py
- _above_floor
- Path
- _repack
- Exception
- Image
- Lock

## God Nodes (most connected - your core abstractions)
1. `long_path()` - 50 edges
2. `Checks` - 44 edges
3. `LLMClient` - 39 edges
4. `skip()` - 34 edges
5. `StubProvider` - 32 edges
6. `main()` - 29 edges
7. `Budget` - 29 edges
8. `page_dir()` - 28 edges
9. `panels` - 25 edges
10. `_reset()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `Komalingo Open Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-open-a.png → README.md
- `Komalingo Split Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-split-a.png → README.md
- `section_zero_llm()` --calls--> `LLMClient`  [INFERRED]
  tests/check_spotfix.py → sidecar/llm.py
- `section_ingest_llm()` --calls--> `LLMClient`  [INFERRED]
  tests/check_spotfix.py → sidecar/llm.py
- `main()` --uses--> `ProviderError`  [INFERRED]
  tests/check_ipc.py → sidecar/llm.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Komalingo Brand Asset Family** — brand_komalingo_icon_dark_dark_app_icon, brand_komalingo_icon_light_app_icon, brand_komalingo_lockup_on_dark_dark_lockup, brand_komalingo_lockup_light_lockup, brand_komalingo_mark_on_dark_dark_mark, brand_komalingo_mark_light_mark [EXTRACTED 0.99]
- **Local Manga Translation Stack** — readme_translation_pipeline, readme_manga_ocr, readme_pp_ocrv5, readme_pp_ocrv3_db, readme_comic_text_detector, readme_lama_manga [EXTRACTED 1.00]
- **Komalingo Brand Concept Explorations** — brand_explorations_concept_open_a_image, brand_explorations_concept_split_a_image [INFERRED 0.90]
- **Scanned PDF Fixture and Rendered Pages** — fixtures_pdf_scan_document, fixtures_pdf_scan_p1_image, fixtures_pdf_scan_p2_image [INFERRED 0.95]

## Communities (152 total, 47 thin omitted)

### Community 0 - "pdf.py"
Cohesion: 0.06
Nodes (61): PdfDocument, PdfPage, The file is not an archive this build reads. Carries a reason string., UnsupportedArchive, _axis_aligned(), _decode_xobject(), detect(), _displayed() (+53 more)

### Community 1 - "StubProvider"
Cohesion: 0.06
Nodes (50): Return (execution_provider, reason). The reason is empty ONLY when CUDA was…, select_provider(), call(), main(), _parse_json(), Phase 0 -- the sidecar's HTTP surface and the shutdown gate (US-007). OFFLINE.…, Returns (status, body). A refused connection is status 0., (payload, why). `why` names the parse failure so the assert can print it. A… (+42 more)

### Community 2 - "main.py"
Cohesion: 0.05
Nodes (60): BaseModel, exception_handler, FastAPI, get, post, ProviderError, Request, Response (+52 more)

### Community 3 - "check_spotfix.py"
Cohesion: 0.10
Nodes (51): Checks, _archive_edits(), _call(), _guarded(), main(), _no_detect_or_ocr(), _quiet(), r"""Phase 3 -- the spot-fix editor and the page cache (AC-10). OFFLINE. uv run… (+43 more)

### Community 4 - "check_archives.py"
Cohesion: 0.10
Nodes (48): comicinfo(), detect_format(), pages(), The container family of `path`, from its bytes. The tar test is last and is…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Same…, `(member name, raw bytes)` of the archive's ComicInfo.xml, or None. RAW bytes,…, Repack `entries` -- an iterable of `(member name, bytes)` -- at `dest`. Through…, write_archive() (+40 more)

### Community 5 - "gen_fixtures.py"
Cohesion: 0.07
Nodes (53): PdfReader, PdfWriter, _copy_info(), copy_outline(), _outline_items(), Flatten pypdf's nested outline into `(depth, title, page index)`. pypdf…, Rebuild the source outline on the writer, page numbers by index. By index and…, Every string-valued /Info key of the source onto the writer, names kept as… (+45 more)

### Community 6 - "lib.rs"
Cohesion: 0.09
Nodes (34): AppHandle, CommandChild, Into, Mutex, Option, Path, Result, Self (+26 more)

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
Nodes (35): BytesIO, _decode(), _drain(), _head(), is_archive(), _libarchive(), libarchive_path(), LibarchiveMissing (+27 more)

### Community 11 - "pipeline.py"
Cohesion: 0.09
Nodes (35): Lock, _cache_miss_response(), 404 with a named kind. A missing cache entry is not a server fault. `kind` is…, AC-10: click a bubble, edit the translation, re-render that page alone. Neither…, rerender(), CacheMiss, _check_lang(), _container() (+27 more)

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
Cohesion: 0.17
Nodes (19): The files in `directory`, top level only, in natural order. Top level only: a…, scan(), build_folder(), check_cancel(), check_image_item_id(), check_page_slots(), check_page_window(), check_same_hash_files() (+11 more)

### Community 16 - "check_typeset.py"
Cohesion: 0.13
Nodes (28): ellipse_points(), The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.…, The job summary AC-1 requires: which regions were compromised, which failed.…, summary(), _batching_and_spotfix(), _check_page(), _compare_metrics(), _edge_cases() (+20 more)

### Community 17 - "fetch_fixtures.py"
Cohesion: 0.13
Nodes (24): main(), Phase 1 -- OCR truth on real vertical Japanese (AC-2). OFFLINE. Runs manga-ocr…, build_manifest(), _compare(), image_size(), load_manifest(), main(), print_report() (+16 more)

### Community 18 - "Checks"
Cohesion: 0.14
Nodes (16): main(), Phase 0 -- the write protocol. Offline, no fixtures, no network. Asserts, from…, build_source(), main(), Phase 0 -- encode policy. Offline, no network. Asserts, from the build order:…, A source image carrying an ICC profile and EXIF with and without GPS., main(), Phase 0 -- the Settings UI and the IPC client (US-009). OFFLINE. The frontend… (+8 more)

### Community 19 - "job.py"
Cohesion: 0.16
Nodes (12): Event, Container readers. One module per format, and each one reads only. Phase 3…, disambiguate(), _discard_output(), Item, Lock, r"""The Item model and the per-item error boundary. Moved here from Phase 8 on…, Remove what a REFUSED item already wrote. Best effort, never raises. The three… (+4 more)

### Community 20 - "Settings.tsx"
Cohesion: 0.20
Nodes (11): ModelCombobox, ModelComboboxHandle, displayPath(), ModelInfo, ProviderSettings, saveSettings(), samplePaths(), Settings() (+3 more)

### Community 21 - "quads"
Cohesion: 0.09
Nodes (26): _as_bgr(), _dedupe(), DetectError, _input_size(), _inverse(), _model(), ndarray, RuntimeError (+18 more)

### Community 22 - "Tauri Application Configuration"
Cohesion: 0.08
Nodes (24): app, security, windows, enable, scope, build, beforeBuildCommand, beforeDevCommand (+16 more)

### Community 23 - "group.py"
Cohesion: 0.13
Nodes (21): separated(i, j): does ink run across the gap between two adjacent quads? The…, _separator(), bbox(), convex_hull(), glyph_unit(), group(), _inside(), merge() (+13 more)

### Community 24 - "inpainter.py"
Cohesion: 0.13
Nodes (23): _crops(), erase(), _fill(), fill_white(), _flat(), _flat_surround(), _inpaint(), _lama() (+15 more)

### Community 25 - "read_translation"
Cohesion: 0.28
Nodes (9): model_slug(), A filesystem-safe name for a model id that two ids cannot share. The readable…, ``{region_id: {"text": str, "edited": bool}}`` for one (lang, model)., Merge a fresh translation in, and never overwrite an ``edited`` entry. A re-run…, A spot-fix edit IS a translation, so it lives in the translation file.…, read_translation(), translation_name(), write_edit() (+1 more)

### Community 26 - "llm.py"
Cohesion: 0.11
Nodes (18): RuntimeError, _decode_reply(), _from_event_stream(), glossary_text(), image_data_url(), ProviderError, OpenAI-compatible client. Owns the concurrency cap and the error contract.…, The glossary block for `lang`, or "" when the target has none. (+10 more)

### Community 27 - "check_cjk.py"
Cohesion: 0.17
Nodes (16): _blank_and_ja(), _cache(), _centroid(), _load(), main(), _ocr(), Phase 4 -- Chinese and Korean through PP-OCRv5 (AC-3). OFFLINE after first…, A cached page is a hit under its own source and a miss under another. (+8 more)

### Community 28 - "section_refs"
Cohesion: 0.14
Nodes (27): add_ref(), clear_running(), delete_job(), get_placement(), item_placements(), job_dir(), _job_key(), jobs_root() (+19 more)

### Community 29 - "textmask.py"
Cohesion: 0.19
Nodes (13): EraseError, mask(), _model(), probability(), ndarray, RuntimeError, Which PIXELS are text: comic-text-detector's segmentation head. WHY a second…, Boolean (H, W): True where the model reads text ink. (+5 more)

### Community 30 - "check_id.py"
Cohesion: 0.17
Nodes (18): Region, _glossary_doc(), _live(), main(), _payload_text(), _prompt(), Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always; live…, Which of the line's marked honorifics appear in `out`, and which forbidden… (+10 more)

### Community 31 - "mock-tauri.ts"
Cohesion: 0.16
Nodes (16): api(), Callback, callbacks, emit(), fakePage(), invoke(), jobs, listeners (+8 more)

### Community 32 - "check_group.py"
Cohesion: 0.14
Nodes (24): _bubble_of(), _ellipse_mask(), _fixture(), _geometry(), _ink(), _largest(), main(), _mask() (+16 more)

### Community 33 - "sidecar/__init__.py"
Cohesion: 0.12
Nodes (17): encode(), Image, Encode policy. The only place in the app that calls Image.save. Pillow silently…, Drop the GPS IFD, keep every other tag byte-identical., Encode to bytes in `fmt`, carrying metadata from `src` (default: img)., Encode `img` in the source image's format and write it atomically. Format comes…, save(), _save_kwargs() (+9 more)

### Community 34 - "Frontend TypeScript Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+10 more)

### Community 35 - "repack_extras"
Cohesion: 0.15
Nodes (18): _admit(), expected_pages(), _is_page_name(), _lazy(), members(), Whether a member name is a page CANDIDATE. Identical rule to read_cbz., gz" | "bz2" | "xz" for a whole-file-compressed tar, "" for a plain one. This…, Run every member past the budget; return the page candidates to stream. Every… (+10 more)

### Community 36 - "read_cbz.py"
Cohesion: 0.17
Nodes (15): _is_page(), members(), _natural_key(), pages(), r"""Read-only CBZ page enumeration. No repack, no safety budget, no other…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Streamed…, Sort key for a full archive member path, digit-aware and segment-wise. Segments…, A member that should be decoded as a page. Directory entries, macOS resource… (+7 more)

### Community 37 - "atomic.py"
Cohesion: 0.15
Nodes (13): atomic_write(), open_retry(), r"""The single write protocol. Every file this app produces goes through here.…, Yield a handle whose bytes land at `dest` only if the block completes. On any…, os.replace with a short, bounded retry on Windows sharing violations. Two…, `open` with the same bounded retry as `_replace`, for READERS. The other half…, _replace(), ensure_libarchive() (+5 more)

### Community 38 - "models.py"
Cohesion: 0.22
Nodes (13): ensure(), _ensure_directory(), fetch(), FetchError, _free_space(), First-launch model fetch, and the CUDA-or-CPU decision. Resumable by design.…, Always carries a reason a user can act on., Download `url` to `dest`, resuming a previous `.part` if one is there. Returns… (+5 more)

### Community 39 - "_run_cached_page"
Cohesion: 0.12
Nodes (29): Image, output_path(), Destination path whose extension matches the SOURCE format. Named off the…, _bbox(), _changed_in_polygon(), detect(), emit(), encode_and_write() (+21 more)

### Community 40 - "check_erase.py"
Cohesion: 0.27
Nodes (11): _dilate(), _flag(), _in_box(), main(), _outline_through_quad(), _poly_mask(), _pre_2c_fill(), ndarray (+3 more)

### Community 41 - "typeset.py"
Cohesion: 0.11
Nodes (27): _bbox(), _chord(), _edge_adjacent(), floor_px(), _has_orphan(), ink_style(), _inset_points(), _ladder() (+19 more)

### Community 42 - "Regression Test Runner"
Cohesion: 0.20
Nodes (16): append_record(), assert_interpreter(), discover(), env_class(), harvest_metrics(), last_status(), load_records(), main() (+8 more)

### Community 43 - "OcrError"
Cohesion: 0.29
Nodes (6): OcrError, ndarray, RuntimeError, A recogniser that cannot run. Named, like every sidecar failure path., One text line -> (text, mean character confidence)., _Recogniser

### Community 44 - "App.tsx"
Cohesion: 0.18
Nodes (14): react, App(), exitMessage(), frontPage(), loadTheme(), SidecarState, stageWord(), Theme (+6 more)

### Community 45 - "api.ts"
Cohesion: 0.13
Nodes (19): runFolder(), runItem(), IconName, api, ApiError, describeError(), isApiError(), isInternal() (+11 more)

### Community 46 - "Komalingo Brand Assets"
Cohesion: 0.13
Nodes (15): Komalingo Light-Tile App Icon PNG, Komalingo Dark-Tile App Icon PNG, Komalingo Dark-Tile App Icon, Komalingo Light-Tile App Icon, Komalingo Lockup PNG, Komalingo Lockup for Light Backgrounds, Komalingo Lockup for Dark Backgrounds, Komalingo Lockup on Dark PNG (+7 more)

### Community 47 - "check_models.py"
Cohesion: 0.14
Nodes (13): The app's per-user data directory, and the one-time move from its old name. The…, `base`/Komalingo, moving an old-named sibling there if it is the only one.…, under(), The cache root. MT_CACHE_DIR wins, so tests never touch the real one., root(), model_dir(), Where fetched weights live. Not beside the executable and not in the repo: a…, check_rename() (+5 more)

### Community 48 - "Translate.tsx"
Cohesion: 0.12
Nodes (20): @tauri-apps/plugin-dialog, Alert(), ICON, Tone, Icon(), PATHS, PathField(), LABEL (+12 more)

### Community 50 - "typeset_page"
Cohesion: 0.13
Nodes (19): FreeTypeFont, _commit(), _draw_line(), Fit, load_font(), Image, RuntimeError, _raster_metrics() (+11 more)

### Community 51 - "main.tsx"
Cohesion: 0.22
Nodes (9): ErrorBoundary, Props, State, installGlobalReporting(), reportError(), boot(), dismissSplash(), failSplash() (+1 more)

### Community 52 - "cache.py"
Cohesion: 0.13
Nodes (36): long_path(), r"""Absolute, normalized, and \\?\-prefixed on Windows. The prefix turns off…, _cap_bytes(), _dir_size(), disk_bytes(), drop_ref(), enforce_cap(), has_edit_for_other_model() (+28 more)

### Community 53 - "LLMClient"
Cohesion: 0.19
Nodes (9): LLMClient, probe_token(), The only way out to the provider. _request holds the gate for the call, on the…, {region_id: text}. A JSON null stays None -- see NOT_TEXT_INSTRUCTION. None and…, All regions of one page. One request unless the page is huge. Returns…, Rung 5's length-capped retry. ONE request for every capped region. `items` is…, Ask the model to read a token painted into an image. Latches text-only ONLY on…, Probe once per (base_url, model) per process; latch on evidence. The call the… (+1 more)

### Community 54 - "ocr_ja.py"
Cohesion: 0.15
Nodes (18): lines(), ocr(), Chinese and Korean OCR: PP-OCRv5 text-line recognition through onnxruntime.…, The parts that are text LINES, each read once. The detector answers per line…, Rows top to bottom (columns right to left), and WITHIN a row, left to right…, Read one region: its line parts, recognised and joined in reading order., _reading_order(), _as_image() (+10 more)

### Community 55 - "section_tier"
Cohesion: 0.13
Nodes (11): clear_tier(), page_hash(), Image, SHA-256 of the DECODED pixels, plus mode and size. Mode and size are in the…, LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds. It counts…, Drop `key` if resident. enforce_cap's path; never touch _items directly., Resident decoded bytes in the memory tier. Phase 6's RSS gate reads this., _Tier (+3 more)

### Community 56 - "Job"
Cohesion: 0.18
Nodes (4): Job, Every item, through the boundary, on `workers` threads. Never raises.…, Block until every item has a terminal status. False on timeout., AC-9, the half the product had never wired: probe once per job. Before this,…

### Community 57 - "run_job"
Cohesion: 0.17
Nodes (12): Every path through the boundary, and the record when all are done. The blocking…, run_job(), _chats_with_image(), check_probe_wiring(), check_running_refcount(), check_same_hash(), check_warning_once(), The cbr->cbz warning, once per job, with two workers racing for it. benign.cbr… (+4 more)

### Community 58 - "SpotFix.tsx"
Cohesion: 0.31
Nodes (10): Region, RepackStatus, inPolygon(), laidInto(), pageSrc(), severity(), SpotFix(), pick() (+2 more)

### Community 59 - "check_cancel.py"
Cohesion: 0.27
Nodes (11): build_inputs(), check_cancel(), check_no_partial(), check_resume(), _eight_page_archive(), events_of(), main(), ARCHIVE_PAGES pages from benign.cbz's three, each with one pixel of its own.… (+3 more)

### Community 60 - "check_ipc.py"
Cohesion: 0.31
Nodes (8): emitted_stages(), item_totals(), main(), Phase 0 -- the host/sidecar IPC contract (US-011). OFFLINE (US-003 stub). **Why…, Run one page as a CHILD PROCESS and read the stages off its stdout. In-process…, Run a 3-page .cbz as a CHILD PROCESS: the `total` on its lines, and the pages…, broken_checkout(), Exit 1 -- a file this checkout should already have is missing. skip() exists…

### Community 61 - "detect.py"
Cohesion: 0.29
Nodes (6): Text-region detection: a DB (differentiable-binarisation) net through cv2.dnn.…, as_points(), The shared Region type: detect.py's output, typeset.py's input. Defined here…, One detected text region, as it travels through the pipeline. `text` defaults…, Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.…, Region

### Community 62 - "_floor_fits"
Cohesion: 0.29
Nodes (8): _capacity(), _floor_fits(), _longest(), The largest n in [0, n_max] for which fits(n) holds, given fits is monotone.…, The rung-3 state -- floor, tightened, no inset, no bleed -- as a predicate., The largest character count of `text` that fits at the floor, tightened.…, Rung 5's terminal branch. Returns (placed or None, rendered, reason). Cannot…, _truncate()

### Community 63 - "_dismissed"
Cohesion: 0.25
Nodes (8): dismiss(), _load_translations(), punctuation_only(), Is there anything here a translator could change? A region that reads as…, (kept, dismissed): the regions the vision model said hold no text. Called after…, Fill translations from the cache. True only if EVERY region was covered.…, _dismissed(), A region the vision model answers null for is never erased. The erasure clause…

### Community 64 - "Node TypeScript Configuration"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 65 - "stub_provider.py"
Cohesion: 0.29
Nodes (7): _as_event_stream(), _chat_reply(), An OpenAI-compatible provider stub, in-process, no new dependency. Replays the…, The ids a request asked about; [0] when the prompt carried none., Echo one translation per region the request asked about. The client batches a…, A chat.completion re-framed as the chunks a streaming gateway sends. The…, _region_ids()

### Community 66 - "run_page"
Cohesion: 0.13
Nodes (14): BoundedSemaphore, Exception, Cancelled, _check_cancel(), _page_slots(), One page through all seven stages, in order. Returns the regions record.…, AC-13: the job's cancel token was set and this item stopped at a page boundary.…, Raise Cancelled if the token is set. `cancel` is anything with is_set() -- a… (+6 more)

### Community 67 - "detect"
Cohesion: 0.29
Nodes (7): Region, detect(), _glyph_px(), Sort key: top band first, then right to left inside the band. The band exists…, Text regions on one page, as Regions carrying polygon and confidence. ids are…, The source glyph size: the median short side of a block's quads. A tategaki…, _reading_order()

### Community 68 - "Fixture Determinism Check"
Cohesion: 0.43
Nodes (6): generate(), main(), Phase 0a gate: two regenerations from an empty tree are byte-identical. uv run…, Relative-path -> sha256 for everything under the generated subdirs., sha256(), snapshot()

### Community 69 - "skip"
Cohesion: 0.25
Nodes (9): main(), pe_imports(), r"""The native bundle libarchive needs (AC-6's .cbr clause). OFFLINE. uv run…, The DLL names in `path`'s PE import directory. Hand-rolled rather than a…, third_party(), main(), Phase 0 -- the seven-stage pipeline and its progress contract (US-006).…, Exit 3 -- unless this is a LIVE skip and MT_REQUIRE_LIVE promotes it. Without… (+1 more)

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

### Community 97 - "check_warmup"
Cohesion: 0.16
Nodes (14): no_download(), on_disk(), onnx_session(), On this thread, fetch() raises FetchError('absent') instead of downloading. For…, Whether MANIFEST entry `name` is fully downloaded, by name and size only. No…, An onnxruntime session on the provider select_provider() names. Errors-only…, Load the models every page needs, before the first page asks. Returns what…, warm_models() (+6 more)

### Community 99 - "Scanned PDF Fixture"
Cohesion: 0.67
Nodes (3): Scanned PDF Fixture, Unreadable Scanned PDF Page 1 Image, Unreadable Scanned PDF Page 2 Image

### Community 145 - "check_provider.py"
Cohesion: 0.47
Nodes (5): env_local(), main(), Phase 0 -- LLM client contract. Fully OFFLINE, against tests/lib/stub_provider.…, [env-local] the loader fills gaps and never overwrites (lib/env_local.py)., regions()

### Community 146 - "_above_floor"
Cohesion: 0.50
Nodes (4): _above_floor(), _calibrate(), Seconds for one reference page's worth of raster work. Best of N.…, (ok, description) for §E's hardware floor. Measured, not read off a label.…

### Community 148 - "_repack"
Cohesion: 0.50
Nodes (4): output_path(), Where the repacked archive lands. Same extension, except RAR -> .cbz. The…, AC-6's round trip: the delivered pages, back into the input's format. **The…, _repack()

## Knowledge Gaps
- **291 isolated node(s):** `Where`, `Callback`, `SidecarState`, `Theme`, `View` (+286 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 900 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **47 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LLMClient` connect `LLMClient` to `check_group.py`, `main.py`, `run_page`, `check_spotfix.py`, `check_inpaint.py`, `check_cjk.py`, `check_probe.py`, `check_batch.py`, `check_typeset.py`, `check_provider.py`, `run_job`, `llm.py`, `check_cancel.py`, `check_ipc.py`, `check_id.py`, `_dismissed`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Why does `Checks` connect `Checks` to `check_group.py`, `StubProvider`, `pdf.py`, `check_archives.py`, `skip`, `check_inpaint.py`, `check_erase.py`, `check_cancel.py`, `check_probe.py`, `check_batch.py`, `check_models.py`, `check_provider.py`, `fetch_fixtures.py`, `check_typeset.py`, `check_cjk.py`, `check_ipc.py`, `check_id.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `skip()` connect `skip` to `check_group.py`, `StubProvider`, `pdf.py`, `check_spotfix.py`, `check_archives.py`, `check_inpaint.py`, `check_erase.py`, `check_cancel.py`, `check_probe.py`, `check_batch.py`, `check_typeset.py`, `fetch_fixtures.py`, `Checks`, `check_cjk.py`, `check_ipc.py`, `check_id.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Checks` (e.g. with `main()` and `main()`) actually correct?**
  _`Checks` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `LLMClient` (e.g. with `section_ingest_llm()` and `section_zero_llm()`) actually correct?**
  _`LLMClient` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `skip()` (e.g. with `main()` and `main()`) actually correct?**
  _`skip()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `StubProvider` (e.g. with `check_page_window()` and `check_probe_wiring()`) actually correct?**
  _`StubProvider` has 7 INFERRED edges - model-reasoned connections that need verification._