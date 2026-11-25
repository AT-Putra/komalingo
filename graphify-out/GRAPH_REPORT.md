# Graph Report - MangaTranslator  (2026-11-25)

## Corpus Check
- 118 files · ~299,230 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: .cbz 5, (none) 4, .cbt 2)

## Summary
- 2269 nodes · 5215 edges · 160 communities (113 shown, 47 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 202 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a98ed4df`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main
- check_package.py
- _run_pages
- Checks
- detect_format
- gen_fixtures.py
- lib.rs
- check_inpaint.py
- Page Image Manifest
- package.json
- archive.py
- classify
- Brand and Language Documentation
- inpaint
- Budget
- StubProvider
- main
- fetch_fixtures.py
- imaging.py
- Settings.tsx
- Job.tsx
- detect
- Tauri Application Configuration
- group.py
- ocr_ja.py
- _run_cached_page
- check_skip.py
- Region
- LLMClient
- pipeline.py
- inpainter.py
- mock-tauri.ts
- detect
- describeError
- Frontend TypeScript Configuration
- read_cbz.py
- resumes
- section_not_text
- fetch
- main
- ensure_libarchive
- typeset.py
- run_all.py
- _sevenzip_payloads
- App.tsx
- api.ts
- Komalingo Brand Assets
- main
- repack_extras
- _wrap_from
- long_path
- main.tsx
- cache.py
- run_item
- warm_tier
- _Tier
- EraseError
- Response
- main.py
- llm.py
- _read_page
- SpotFix
- write_pdf
- _ink_in_polygon
- Node TypeScript Configuration
- model_dir
- check_warmup
- check_id.py
- redcheck_spotfix.py
- check_round_trip
- Image
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
- _write_previews
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
- lifespan
- pages
- page_hash
- skip
- main
- _Recogniser
- Path
- region.py
- check_cancel.py
- _floor_fits
- Progress.tsx
- imports.py
- _schedule_item_repack
- _CountingReader
- root
- load_font
- main
- _Verdicts

## God Nodes (most connected - your core abstractions)
1. `Checks` - 87 edges
2. `long_path()` - 65 edges
3. `LLMClient` - 59 edges
4. `page_dir()` - 45 edges
5. `StubProvider` - 42 edges
6. `skip()` - 41 edges
7. `ProviderError` - 35 edges
8. `main()` - 33 edges
9. `describeError()` - 32 edges
10. `review_fixes()` - 30 edges

## Surprising Connections (you probably didn't know these)
- `Komalingo Open Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-open-a.png → README.md
- `Komalingo Split Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-split-a.png → README.md
- `gen_cbz()` --indirect_call--> `_natural_key()`  [INFERRED]
  tests/gen_fixtures.py → sidecar/containers/read_cbz.py
- `_flag()` --uses--> `EraseError`  [INFERRED]
  tests/check_erase.py → sidecar/textmask.py
- `section_skipped()` --uses--> `LLMClient`  [INFERRED]
  tests/check_spotfix.py → sidecar/llm.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Komalingo Brand Asset Family** — brand_komalingo_icon_dark_dark_app_icon, brand_komalingo_icon_light_app_icon, brand_komalingo_lockup_on_dark_dark_lockup, brand_komalingo_lockup_light_lockup, brand_komalingo_mark_on_dark_dark_mark, brand_komalingo_mark_light_mark [EXTRACTED 0.99]
- **Local Manga Translation Stack** — readme_translation_pipeline, readme_manga_ocr, readme_pp_ocrv5, readme_pp_ocrv3_db, readme_comic_text_detector, readme_lama_manga [EXTRACTED 1.00]
- **Komalingo Brand Concept Explorations** — brand_explorations_concept_open_a_image, brand_explorations_concept_split_a_image [INFERRED 0.90]
- **Scanned PDF Fixture and Rendered Pages** — fixtures_pdf_scan_document, fixtures_pdf_scan_p1_image, fixtures_pdf_scan_p2_image [INFERRED 0.95]

## Communities (160 total, 47 thin omitted)

### Community 0 - "main"
Cohesion: 0.22
Nodes (13): check_cache_key(), check_fixtures(), check_info_names(), check_native(), check_no_agpl(), check_reader_close(), fixture(), main() (+5 more)

### Community 1 - "check_package.py"
Cohesion: 0.06
Nodes (46): glob, Return (execution_provider, reason). The reason is empty ONLY when CUDA was…, select_provider(), call(), main(), _parse_json(), Returns (status, body). A refused connection is status 0., (payload, why). `why` names the parse failure so the assert can print it. A… (+38 more)

### Community 2 - "_run_pages"
Cohesion: 0.06
Nodes (22): BoundedSemaphore, Event, Cancelled, _check_cancel(), Control, _page_slots(), _pause_job(), Paused (+14 more)

### Community 3 - "Checks"
Cohesion: 0.07
Nodes (58): clear_tier(), _above_floor(), _archive_edits(), _calibrate(), _call(), _guarded(), main(), _no_detect_or_ocr() (+50 more)

### Community 4 - "detect_format"
Cohesion: 0.09
Nodes (46): comicinfo(), detect_format(), pages(), The container family of `path`, from its bytes. The tar test is last and is…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Same…, `(member name, raw bytes)` of the archive's ComicInfo.xml, or None. RAW bytes,…, ComicInfo.xml with LanguageISO set to `lang` and nothing else touched. A byte-…, Repack `entries` -- an iterable of `(member name, bytes)` -- at `dest`. Through… (+38 more)

### Community 5 - "gen_fixtures.py"
Cohesion: 0.06
Nodes (58): binascii, gzip, img2pdf, Path, pathlib, pil_pngimageplugin, struct, tarfile (+50 more)

### Community 6 - "lib.rs"
Cohesion: 0.08
Nodes (38): AppHandle, CommandChild, Into, Mutex, Option, process, Result, Self (+30 more)

### Community 7 - "check_inpaint.py"
Cohesion: 0.10
Nodes (38): _assert_ink(), _assert_ring(), _assert_step_edge(), _band(), _best_ncc(), _chord_x(), _composite(), _dismissed() (+30 more)

### Community 8 - "Page Image Manifest"
Cohesion: 0.05
Nodes (40): sha256, size, sha256, size, sha256, size, sha256, size (+32 more)

### Community 9 - "package.json"
Cohesion: 0.06
Nodes (31): dependencies, react, react-dom, @tauri-apps/api, @tauri-apps/plugin-dialog, @tauri-apps/plugin-opener, devDependencies, @tauri-apps/cli (+23 more)

### Community 10 - "archive.py"
Cohesion: 0.08
Nodes (31): BytesIO, _decode(), _drain(), _head(), _libarchive(), libarchive_path(), LibarchiveMissing, Exception (+23 more)

### Community 11 - "classify"
Cohesion: 0.08
Nodes (24): is_archive(), Whether `path` has an extension AC-6 covers. Cheap, name-only. Used to decide…, is_pdf(), Whether `path` is named as a PDF. Cheap, name-only, like `is_archive`., classify(), disambiguate(), expand(), add() (+16 more)

### Community 12 - "Brand and Language Documentation"
Cohesion: 0.06
Nodes (31): Komalingo Open Concept A Brand Exploration, Komalingo Split Concept A Brand Exploration, Honorifics and register in the Indonesian output (AC-4), Register, The rule, The table, What stays as it is, What the gate holds (+23 more)

### Community 13 - "inpaint"
Cohesion: 0.10
Nodes (27): _ask_with_retry(), _bbox(), _box(), _changed_in_polygon(), expecting(), inpaint(), ocr(), page_context_image() (+19 more)

### Community 14 - "Budget"
Cohesion: 0.11
Nodes (16): PathLike, Budget, _normalized(), Exception, One rejected archive, carrying which rule refused it and where. `reason` is…, Member name with separators unified, for rule evaluation only. Backslash is a…, Per-archive accounting. One instance per item; never shared between two.…, Admit one entry, or raise. Call before streaming a single byte. (+8 more)

### Community 15 - "StubProvider"
Cohesion: 0.06
Nodes (27): Job, The files in `directory`, top level only, in natural order. Top level only: a…, Every item, through the boundary, on `workers` threads. Never raises.…, Cancel the rest. On a job that already PAUSED and settled, the workers are…, Block until every item has a terminal status. False on timeout., AC-9, the half the product had never wired: probe once per job. Before this,…, scan(), build_folder() (+19 more)

### Community 16 - "main"
Cohesion: 0.15
Nodes (18): ellipse_points(), The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.…, The job summary AC-1 requires: which regions were compromised, which failed.…, summary(), _batching_and_spotfix(), _check_page(), _compare_metrics(), _edge_cases() (+10 more)

### Community 17 - "fetch_fixtures.py"
Cohesion: 0.12
Nodes (29): datetime, main(), Phase 1 -- OCR truth on real vertical Japanese (AC-2). OFFLINE. Runs manga-ocr…, build_manifest(), _compare(), image_size(), load_manifest(), main() (+21 more)

### Community 18 - "imaging.py"
Cohesion: 0.13
Nodes (20): encode(), output_path(), Image, Encode policy. The only place in the app that calls Image.save. Pillow silently…, Drop the GPS IFD, keep every other tag byte-identical., Encode to bytes in `fmt`, carrying metadata from `src` (default: img)., Destination path whose extension matches the SOURCE format. Named off the…, Encode `img` in the source image's format and write it atomically. Format comes… (+12 more)

### Community 19 - "Settings.tsx"
Cohesion: 0.14
Nodes (24): react, @tauri-apps/api, ModelCombobox, ModelComboboxHandle, SetupCard(), allSettings(), loadModels(), save() (+16 more)

### Community 20 - "Job.tsx"
Cohesion: 0.11
Nodes (31): @tauri-apps/plugin-dialog, Alert(), ICON, Tone, ErrorAlert(), ExplainedError, explainError(), provider() (+23 more)

### Community 21 - "detect"
Cohesion: 0.07
Nodes (32): _as_bgr(), detect(), DetectError, _glyph_px(), _input_size(), _inverse(), _model(), ndarray (+24 more)

### Community 22 - "Tauri Application Configuration"
Cohesion: 0.08
Nodes (24): app, security, windows, enable, scope, build, beforeBuildCommand, beforeDevCommand (+16 more)

### Community 23 - "group.py"
Cohesion: 0.08
Nodes (28): _dedupe(), One quad per piece of text: of two that _same_text says are one line or column…, Do two bboxes cover the same line or column? See _SAME_SPAN., separated(i, j): does ink run across the gap between two adjacent quads? The…, _same_text(), _separator(), bbox(), convex_hull() (+20 more)

### Community 24 - "ocr_ja.py"
Cohesion: 0.26
Nodes (11): _as_image(), canonical(), _get_model(), _is_blank(), ocr(), Image, Japanese OCR with confidence and blank-crop gates. Model output is…, Fold the two encodings manga-ocr picks that the page does not print. (+3 more)

### Community 25 - "_run_cached_page"
Cohesion: 0.12
Nodes (23): has_page(), has_raster(), Whether the page has any raster on disk, without decoding one., _content_region(), _deliver(), dismiss(), emit(), _finish_page() (+15 more)

### Community 26 - "check_skip.py"
Cohesion: 0.10
Nodes (31): item_placements(), Every (ordinal, entry) this job placed for one item, in page order. The repack…, _archive(), client_ok(), inputs(), _loose_pages(), main(), _members() (+23 more)

### Community 27 - "Region"
Cohesion: 0.12
Nodes (18): Region, check_cap(), press(), worker(), check_same_hash_files(), hammer(), The mechanism under B1, isolated and deterministic. Two threads, 300 write+read…, room_of() (+10 more)

### Community 28 - "LLMClient"
Cohesion: 0.06
Nodes (37): _decode_reply(), error_kind(), _error_object_kind(), _from_event_stream(), glossary_text(), image_data_url(), LLMClient, _moderation_reasons() (+29 more)

### Community 29 - "pipeline.py"
Cohesion: 0.09
Nodes (38): bz2, collections, contextlib, dataclasses, functools, gc, hashlib, http_server (+30 more)

### Community 30 - "inpainter.py"
Cohesion: 0.12
Nodes (25): _crops(), erase(), _fill(), fill_white(), _flat(), _flat_surround(), _inpaint(), _lama() (+17 more)

### Community 31 - "mock-tauri.ts"
Cohesion: 0.14
Nodes (20): api(), Callback, callbacks, emit(), fakePage(), invoke(), itemPages, jobs (+12 more)

### Community 32 - "detect"
Cohesion: 0.12
Nodes (23): detect(), Text regions from detect.py's DB model. Regions become plain dicts here rather…, One page through all seven stages, in order. Returns the regions record.…, run_page(), _centroid(), _fit(), _ocr(), AC-1's clauses over the second engine's pages, whole pipeline. (+15 more)

### Community 33 - "describeError"
Cohesion: 0.19
Nodes (19): mergeRetried(), NeedsAttention(), finish(), follow(), retry(), togglePicker(), describeError(), isApiError() (+11 more)

### Community 34 - "Frontend TypeScript Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+10 more)

### Community 35 - "read_cbz.py"
Cohesion: 0.14
Nodes (15): re, _is_page(), r"""Read-only CBZ page enumeration. No repack, no safety budget, no other…, A member that should be decoded as a page. Directory entries, macOS resource…, Page-candidate members of an OPEN archive, in yield order. One implementation,…, _sorted_members(), main(), Phase 0 -- the Settings UI and the IPC client (US-009). OFFLINE. The frontend… (+7 more)

### Community 36 - "resumes"
Cohesion: 0.07
Nodes (44): BaseModel, post, ValueError, The configured settings cannot be used. Not the provider's fault. A ValueError…, SettingsError, _bad_settings_response(), cache_clear(), _client() (+36 more)

### Community 37 - "section_not_text"
Cohesion: 0.08
Nodes (28): open_retry(), `open` with the same bounded retry as `_replace`, for READERS. The other half…, _raster(), _raster_files(), raster_name(), Mark a page directory as used NOW. Called on every read, not only on write, and…, The cached record, or None. Touches the directory -- see ``touch``., The raster file for the erased region set `kept`; the undigested name for None.… (+20 more)

### Community 38 - "fetch"
Cohesion: 0.18
Nodes (13): ensure(), _ensure_directory(), fetch(), FetchError, _free_space(), RuntimeError, Always carries a reason a user can act on., Download `url` to `dest`, resuming a previous `.part` if one is there. Returns… (+5 more)

### Community 39 - "main"
Cohesion: 0.11
Nodes (15): lines(), area(), inside(), ocr(), The parts that are text LINES, each read once. The detector answers per line…, Rows top to bottom (columns right to left), and WITHIN a row, left to right…, Read one region: its line parts, recognised and joined in reading order., _reading_order() (+7 more)

### Community 40 - "ensure_libarchive"
Cohesion: 0.16
Nodes (13): os.replace with a short, bounded retry on Windows sharing violations. Two…, _replace(), _bsdtar(), bundled(), ensure_libarchive(), NativeMissing, Exception, A native dependency could not be installed, with a named reason. (+5 more)

### Community 41 - "typeset.py"
Cohesion: 0.20
Nodes (16): _bbox(), _edge_adjacent(), floor_px(), _has_orphan(), _inset_points(), _ladder(), _layout(), max_font_px() (+8 more)

### Community 42 - "run_all.py"
Cohesion: 0.20
Nodes (16): append_record(), assert_interpreter(), discover(), env_class(), harvest_metrics(), last_status(), load_records(), main() (+8 more)

### Community 44 - "App.tsx"
Cohesion: 0.14
Nodes (23): App(), allowCache(), openItem(), refreshBatch(), refuseUnconfigured(), retriedPages(), runJob(), updatePage() (+15 more)

### Community 45 - "api.ts"
Cohesion: 0.11
Nodes (24): MODE_WORDS, Outcome, sleep(), api, ApiError, CacheClearResult, DismissedRegion, ItemPages (+16 more)

### Community 46 - "Komalingo Brand Assets"
Cohesion: 0.13
Nodes (15): Komalingo Light-Tile App Icon PNG, Komalingo Dark-Tile App Icon PNG, Komalingo Dark-Tile App Icon, Komalingo Light-Tile App Icon, Komalingo Lockup PNG, Komalingo Lockup for Light Backgrounds, Komalingo Lockup for Dark Backgrounds, Komalingo Lockup on Dark PNG (+7 more)

### Community 47 - "main"
Cohesion: 0.18
Nodes (3): main(), Serves PAYLOAD with Range support. cut_after truncates the response., Server

### Community 48 - "repack_extras"
Cohesion: 0.12
Nodes (22): _admit(), expected_pages(), _is_page_name(), _lazy(), members(), Whether a member name is a page CANDIDATE. Identical rule to read_cbz., gz" | "bz2" | "xz" for a whole-file-compressed tar, "" for a plain one. This…, Run every member past the budget; return the page candidates to stream. Every… (+14 more)

### Community 49 - "_wrap_from"
Cohesion: 0.25
Nodes (8): _chord(), _narrowest(), The WIDEST contiguous span of the polygon at scanline y, or None. Contiguous,…, The tightest chord the line's own box spans, clipped to the page raster. A line…, Advance width including tracking, which PIL does not model. Tracking is applied…, Greedy wrap of `words` in slots starting at `top`. None if words remain. A slot…, text_width(), _wrap_from()

### Community 50 - "long_path"
Cohesion: 0.08
Nodes (50): atomic_write(), long_path(), Yield a handle whose bytes land at `dest` only if the block completes. On any…, r"""Absolute, normalized, and \\?\-prefixed on Windows. The prefix turns off…, add_ref(), _cap_bytes(), clear(), delete_job() (+42 more)

### Community 51 - "main.tsx"
Cohesion: 0.21
Nodes (10): react-dom, ErrorBoundary, Props, State, installGlobalReporting(), reportError(), boot(), dismissSplash() (+2 more)

### Community 52 - "cache.py"
Cohesion: 0.06
Nodes (64): choice_name(), clear_refusals(), get_placement(), has_edit_for_other_model(), has_refusals(), has_unmarked_nulls(), model_slug(), _placement_key() (+56 more)

### Community 53 - "run_item"
Cohesion: 0.09
Nodes (24): output_path(), Where the repacked archive lands. Same extension, except RAR -> .cbz. The…, detect(), output_path(), Whether the bytes start with a PDF header. The spec allows junk before `%PDF-`,…, _discard_output(), Lock, Remove what a REFUSED item already wrote. Best effort, never raises. The three… (+16 more)

### Community 54 - "warm_tier"
Cohesion: 0.50
Nodes (4): Resident decoded bytes in the memory tier. Phase 6's RSS gate reads this., tier_bytes(), Fill cache's in-memory LRU tier to its byte cap and return its size. Section E…, warm_tier()

### Community 55 - "_Tier"
Cohesion: 0.20
Nodes (4): LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds. It counts…, Drop `key` if resident., Drop every raster of the page -- enforce_cap's path, one per erased set., _Tier

### Community 56 - "EraseError"
Cohesion: 0.19
Nodes (13): EraseError, mask(), _model(), probability(), ndarray, RuntimeError, Which PIXELS are text: comic-text-detector's segmentation head. WHY a second…, Boolean (H, W): True where the model reads text ink. (+5 more)

### Community 57 - "Response"
Cohesion: 0.20
Nodes (10): exception_handler, Request, Response, _cache_miss_response(), Exception, The last envelope. Every other error path in this file is deliberate; this one…, 404 with a named kind. A missing cache entry is not a server fault. `kind` is…, POST + correct nonce + loopback client, or the process stays up. Every… (+2 more)

### Community 58 - "main.py"
Cohesion: 0.08
Nodes (37): get, pydantic, secrets, cache_stats(), cancel_job(), health(), job_item(), _job_response() (+29 more)

### Community 59 - "llm.py"
Cohesion: 0.09
Nodes (31): base64, http_client, random, _error_payload(), is_null_word(), probe_png(), OpenAI-compatible client. Owns the concurrency cap and the error contract.…, The instruction's null, written as the STRING "null". Measured on a real… (+23 more)

### Community 60 - "_read_page"
Cohesion: 0.16
Nodes (17): Image, PdfPage, _axis_aligned(), _decode_xobject(), _displayed(), _full_page_image(), _is_scan(), The ONE image object covering more than half the page, or None. Exactly one:… (+9 more)

### Community 61 - "SpotFix"
Cohesion: 0.17
Nodes (12): inPolygon(), laidInto(), severity(), SpotFix(), confirm(), down(), hidden(), owned() (+4 more)

### Community 62 - "write_pdf"
Cohesion: 0.20
Nodes (11): PdfReader, PdfWriter, _copy_info(), copy_outline(), _outline_items(), walk(), Flatten pypdf's nested outline into `(depth, title, page index)`. pypdf…, Rebuild the source outline on the writer, page numbers by index. By index and… (+3 more)

### Community 63 - "_ink_in_polygon"
Cohesion: 0.38
Nodes (7): _ink(), _ink_in_polygon(), _page_overflow(), _polygon_mask(), ndarray, (horizontal, vertical) px of DELIVERED ink outside the polygon. This file's…, Ink pixels inside the polygon. The raster half of "renders empty".

### Community 64 - "Node TypeScript Configuration"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 65 - "model_dir"
Cohesion: 0.40
Nodes (6): `base`/Komalingo, moving an old-named sibling there if it is the only one.…, under(), model_dir(), Where fetched weights live. Not beside the executable and not in the repo: a…, check_rename(), [rename] MangaTranslator's data directory moves to Komalingo, once, whole. The…

### Community 66 - "check_warmup"
Cohesion: 0.16
Nodes (11): no_download(), on_disk(), onnx_session(), On this thread, fetch() raises FetchError('absent') instead of downloading. For…, Whether MANIFEST entry `name` is fully downloaded, by name and size only. No…, An onnxruntime session on the provider select_provider() names. Errors-only…, Load the models every page needs, before the first page asks. Returns what…, warm_models() (+3 more)

### Community 67 - "check_id.py"
Cohesion: 0.07
Nodes (33): _glossary_doc(), _live(), main(), _payload_text(), _prompt(), Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always; live…, Which of the line's marked honorifics appear in `out`, and which forbidden…, _renderings() (+25 more)

### Community 68 - "redcheck_spotfix.py"
Cohesion: 0.43
Nodes (6): failed_tags(), main(), r"""Phase 3's red-check: sabotage each guarded behaviour, confirm its assert…, Run the gate. MT_REDCHECK tells it the sabotage marker is ours., run_check(), sha256()

### Community 69 - "check_round_trip"
Cohesion: 0.22
Nodes (10): page_boxes(), page_layout(), Every page's DISPLAYED box in points, `/Rotate` applied. What the output must…, Per page: `(page w, page h, image w, image h)` in displayed points. The image…, check_round_trip(), _flatten(), The product's path: job.run_job, both fixtures, offline., expected.json's [title, page, children] -> (depth, title, page). (+2 more)

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

### Community 97 - "_write_previews"
Cohesion: 0.24
Nodes (10): _preview_factor(), The integer reduce factor for a w x h page's original preview: the short edge…, The page as it came in, for the Editor's original toggle, and the top of it,…, _write_previews(), base(), original(), thumb(), check_warning_once() (+2 more)

### Community 98 - "typeset_page"
Cohesion: 0.18
Nodes (12): _commit(), Fit, ink_style(), Image, ndarray, One region's typeset result. Every field is output-only. `rung` is the RUNG…, Typeset every region of one page. Returns (image, [Fit]). Two-phase by…, INK_PLAIN, INK_DARK or INK_BUSY from the page's gray inside `points`. (+4 more)

### Community 99 - "Scanned PDF Fixture"
Cohesion: 0.67
Nodes (3): Scanned PDF Fixture, Unreadable Scanned PDF Page 1 Image, Unreadable Scanned PDF Page 2 Image

### Community 142 - "lifespan"
Cohesion: 0.20
Nodes (9): FastAPI, buffer(), lifespan(), r"""Repair leaked cache references before anything can be evicted against them.…, pipeline.warm_models on a daemon thread; the lifespan never waits on it.…, Exit the moment stdin closes -- which, under Tauri, means the parent died.…, start_warmup(), watch_parent() (+1 more)

### Community 143 - "pages"
Cohesion: 0.17
Nodes (12): Budget, PdfDocument, member_name(), _open(), page_count(), pages(), The name the delivered page is written under. A PDF has no member names of its…, How many pages `pages` will yield. The document's own count, no render.… (+4 more)

### Community 144 - "page_hash"
Cohesion: 0.33
Nodes (5): page_hash(), Image, SHA-256 of the DECODED pixels, plus mode and size. Mode and size are in the…, [key] the hash is over decoded pixels, and mode and size are in it., section_key()

### Community 145 - "skip"
Cohesion: 0.12
Nodes (29): asyncio, json, numpy, pil, Chinese and Korean OCR: PP-OCRv5 text-line recognition through onnxruntime.…, sys, tempfile, Phase 0 -- the write protocol. Offline, no fixtures, no network. Asserts, from… (+21 more)

### Community 146 - "main"
Cohesion: 0.29
Nodes (8): _dilate(), _flag(), _in_box(), main(), _poly_mask(), _pre_2c_fill(), ndarray, The inpainter as it was before Phase 2c, copied here so the flag is compared…

### Community 147 - "_Recogniser"
Cohesion: 0.29
Nodes (6): OcrError, ndarray, RuntimeError, A recogniser that cannot run. Named, like every sidecar failure path., One text line -> (text, mean character confidence)., _Recogniser

### Community 150 - "region.py"
Cohesion: 0.33
Nodes (5): as_points(), The shared Region type: detect.py's output, typeset.py's input. Defined here…, One detected text region, as it travels through the pipeline. `text` defaults…, Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.…, Region

### Community 151 - "check_cancel.py"
Cohesion: 0.36
Nodes (8): build_inputs(), check_no_partial(), check_resume(), _eight_page_archive(), main(), ARCHIVE_PAGES pages from benign.cbz's three, each with one pixel of its own.…, r"""Phase 9 -- AC-13 (cancel and resume). Offline, against the stub. uv run…, _run_driver()

### Community 152 - "_floor_fits"
Cohesion: 0.33
Nodes (9): _capacity(), _floor_fits(), fits(), _longest(), The largest n in [0, n_max] for which fits(n) holds, given fits is monotone.…, The rung-3 state -- floor, tightened, no inset, no bleed -- as a predicate., The largest character count of `text` that fits at the floor, tightened.…, Rung 5's terminal branch. Returns (placed or None, rendered, reason). Cannot… (+1 more)

### Community 153 - "Progress.tsx"
Cohesion: 0.40
Nodes (5): LABEL, Stage, stageIndex(), STAGES, StageTrack()

### Community 154 - "imports.py"
Cohesion: 0.33
Nodes (6): importlib, load(), main(), Phase 0a spike: can we import the CV components in-process on the pinned stack?…, Import under a RUNNING event loop -- the condition the sidecar imposes., traceback

### Community 155 - "_schedule_item_repack"
Cohesion: 0.22
Nodes (9): Rebuild the item's archive after a fix, unless it has none., _schedule_item_repack(), flush_repacks(), _is_images(), Whether a placement (or a source path) is a chapter of loose pages. The…, Rebuild the item's archive soon, on a worker thread. Returns the status.…, Every pending repack, now, on this thread. For the exit paths. The app does not…, _repack_worker() (+1 more)

### Community 159 - "root"
Cohesion: 0.18
Nodes (15): clear_running(), job_dir(), _job_key(), jobs_root(), mark_running(), The cache root. MT_CACHE_DIR wins, so tests never touch the real one., The one form a job id takes inside this module: a safe path segment. job_id…, root() (+7 more)

### Community 160 - "load_font"
Cohesion: 0.18
Nodes (12): FreeTypeFont, _draw_line(), load_font(), RuntimeError, _raster_metrics(), A typeset pass that cannot proceed. Named, like every sidecar failure path., One truetype face, cached per size. MT_TYPESET_FONT overrides the search., (overflow_x, overflow_y, clipped_glyphs, offpage_ink_px), read off drawn ink.… (+4 more)

### Community 161 - "main"
Cohesion: 0.40
Nodes (4): main(), pe_imports(), The DLL names in `path`'s PE import directory. Hand-rolled rather than a…, third_party()

## Knowledge Gaps
- **307 isolated node(s):** `komalingo-sidecar`, `komalingo`, `Stage`, `Tone`, `ExplainedError` (+302 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1096 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **47 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Checks` connect `Checks` to `main`, `check_package.py`, `detect_format`, `check_inpaint.py`, `StubProvider`, `page_hash`, `skip`, `main`, `imaging.py`, `fetch_fixtures.py`, `main`, `check_cancel.py`, `check_skip.py`, `Region`, `LLMClient`, `pipeline.py`, `root`, `detect`, `main`, `read_cbz.py`, `resumes`, `section_not_text`, `main`, `main`, `long_path`, `llm.py`, `check_id.py`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Why does `LLMClient` connect `LLMClient` to `detect`, `check_id.py`, `resumes`, `check_skip.py`, `Checks`, `check_inpaint.py`, `section_not_text`, `llm.py`, `StubProvider`, `main`, `skip`, `check_cancel.py`, `main.py`, `Region`, `pipeline.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `long_path()` connect `long_path` to `detect_format`, `archive.py`, `classify`, `inpaint`, `pages`, `StubProvider`, `imaging.py`, `detect`, `_run_cached_page`, `_schedule_item_repack`, `pipeline.py`, `root`, `resumes`, `section_not_text`, `fetch`, `ensure_libarchive`, `_sevenzip_payloads`, `repack_extras`, `cache.py`, `run_item`, `write_pdf`, `check_warmup`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 33 inferred relationships involving `Checks` (e.g. with `inputs()` and `kinds()`) actually correct?**
  _`Checks` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `LLMClient` (e.g. with `models()` and `retry_pages()`) actually correct?**
  _`LLMClient` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `komalingo-sidecar`, `komalingo`, `Stage` to the rest of the system?**
  _307 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `check_package.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06431372549019608 - nodes in this community are weakly interconnected._