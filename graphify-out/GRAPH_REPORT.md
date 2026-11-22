# Graph Report - MangaTranslator  (2026-11-22)

## Corpus Check
- 118 files · ~299,200 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: .cbz 5, (none) 4, .cbt 2)

## Summary
- 2267 nodes · 5216 edges · 165 communities (117 shown, 48 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 202 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `084ba1af`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main
- check_package.py
- _run_pages
- Checks
- check_archives.py
- gen_fixtures.py
- lib.rs
- check_inpaint.py
- Page Image Manifest
- package.json
- archive.py
- expand
- Brand and Language Documentation
- check_cjk.py
- Budget
- check_batch.py
- check_typeset.py
- fetch_fixtures.py
- check_id.py
- describeError
- Icon
- detect
- Tauri Application Configuration
- group
- check_group.py
- _rerender_locked
- check_skip.py
- Job
- LLMClient
- pipeline.py
- inpainter.py
- mock-tauri.ts
- detect
- _repack
- Frontend TypeScript Configuration
- pages
- main.py
- section_not_text
- fetch
- lines
- ensure_libarchive
- typeset.py
- run_all.py
- main
- App.tsx
- api.ts
- Komalingo Brand Assets
- Server
- repack_extras
- resumes
- long_path
- main.tsx
- cache.py
- run_item
- tier_bytes
- _Tier
- session
- shutdown
- get
- llm.py
- _decode_xobject
- SpotFix.tsx
- write_pdf
- retry_page
- Node TypeScript Configuration
- manual_page
- check_warmup
- .__init__
- redcheck_spotfix.py
- check_round_trip
- StubProvider
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
- _sevenzip_payloads
- _open
- page_hash
- skip
- main
- _Recogniser
- check_fixtures_deterministic.py
- _is_scan
- region.py
- check_cancel.py
- _floor_fits
- Progress.tsx
- imports.py
- schedule_repack
- _CountingReader
- EraseError
- _container
- root
- TypesetError
- main
- _Verdicts
- punctuation_only
- is_pdf

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
10. `App()` - 30 edges

## Surprising Connections (you probably didn't know these)
- `Komalingo Open Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-open-a.png → README.md
- `Komalingo Split Concept A Brand Exploration` --conceptually_related_to--> `Komalingo`  [INFERRED]
  brand/explorations/concept-split-a.png → README.md
- `main()` --indirect_call--> `root()`  [INFERRED]
  tests/check_atomic.py → sidecar/cache.py
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

## Communities (165 total, 48 thin omitted)

### Community 0 - "main"
Cohesion: 0.25
Nodes (11): check_fixtures(), check_info_names(), check_native(), check_no_agpl(), check_reader_close(), fixture(), main(), The reader alone, before the pipeline is involved. (+3 more)

### Community 1 - "check_package.py"
Cohesion: 0.06
Nodes (46): glob, Return (execution_provider, reason). The reason is empty ONLY when CUDA was…, select_provider(), call(), main(), _parse_json(), Returns (status, body). A refused connection is status 0., (payload, why). `why` names the parse failure so the assert can print it. A… (+38 more)

### Community 2 - "_run_pages"
Cohesion: 0.06
Nodes (25): BoundedSemaphore, Event, Cancelled, _check_cancel(), Control, expecting(), _page_slots(), _pause_job() (+17 more)

### Community 3 - "Checks"
Cohesion: 0.07
Nodes (56): clear_tier(), _above_floor(), _archive_edits(), _calibrate(), _call(), _guarded(), main(), _no_detect_or_ocr() (+48 more)

### Community 4 - "check_archives.py"
Cohesion: 0.08
Nodes (56): bz2, lzma, psutil, comicinfo(), detect_format(), pages(), The container family of `path`, from its bytes. The tar test is last and is…, Yield `(ordinal, member, image)` for every decodable page, 1-based. Same… (+48 more)

### Community 5 - "gen_fixtures.py"
Cohesion: 0.07
Nodes (51): binascii, gzip, img2pdf, pathlib, pil_pngimageplugin, struct, _archive_page(), _cbz_page() (+43 more)

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
Nodes (32): dependencies, react, react-dom, @tauri-apps/api, @tauri-apps/plugin-dialog, @tauri-apps/plugin-opener, devDependencies, @tauri-apps/cli (+24 more)

### Community 10 - "archive.py"
Cohesion: 0.07
Nodes (36): BytesIO, _decode(), _drain(), _head(), is_archive(), _libarchive(), libarchive_path(), LibarchiveMissing (+28 more)

### Community 11 - "expand"
Cohesion: 0.12
Nodes (14): disambiguate(), expand(), add(), _is_output(), Item, One delivered page: count it, and list it when it was skipped. Called from up…, A page this program wrote: `<name>_translated.<ext>`. Never an input, or a…, The folders directly inside `directory`, natural order, no dotfolders. (+6 more)

### Community 12 - "Brand and Language Documentation"
Cohesion: 0.06
Nodes (31): Komalingo Open Concept A Brand Exploration, Komalingo Split Concept A Brand Exploration, Honorifics and register in the Indonesian output (AC-4), Register, The rule, The table, What stays as it is, What the gate holds (+23 more)

### Community 13 - "check_cjk.py"
Cohesion: 0.12
Nodes (24): _blank_and_ja(), _cache(), _centroid(), _load(), main(), _ocr(), Phase 4 -- Chinese and Korean through PP-OCRv5 (AC-3). OFFLINE after first…, A cached page is a hit under its own source and a miss under another. (+16 more)

### Community 14 - "Budget"
Cohesion: 0.11
Nodes (16): PathLike, Budget, _normalized(), Exception, One rejected archive, carrying which rule refused it and where. `reason` is…, Member name with separators unified, for rule evaluation only. Backslash is a…, Per-archive accounting. One instance per item; never shared between two.…, Admit one entry, or raise. Call before streaming a single byte. (+8 more)

### Community 15 - "check_batch.py"
Cohesion: 0.09
Nodes (32): itertools, The files in `directory`, top level only, in natural order. Top level only: a…, scan(), build_folder(), _chats_with_image(), check_cancel(), check_cap(), press() (+24 more)

### Community 16 - "check_typeset.py"
Cohesion: 0.12
Nodes (28): ellipse_points(), The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.…, The job summary AC-1 requires: which regions were compromised, which failed.…, summary(), _batching_and_spotfix(), _check_page(), _compare_metrics(), _edge_cases() (+20 more)

### Community 17 - "fetch_fixtures.py"
Cohesion: 0.13
Nodes (27): datetime, main(), Phase 1 -- OCR truth on real vertical Japanese (AC-2). OFFLINE. Runs manga-ocr…, build_manifest(), _compare(), image_size(), load_manifest(), main() (+19 more)

### Community 18 - "check_id.py"
Cohesion: 0.15
Nodes (17): re, _glossary_doc(), _live(), main(), _payload_text(), _prompt(), Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always; live…, Which of the line's marked honorifics appear in `out`, and which forbidden… (+9 more)

### Community 19 - "describeError"
Cohesion: 0.14
Nodes (30): NeedsAttention(), finish(), follow(), retry(), togglePicker(), sleep(), SetupCard(), allSettings() (+22 more)

### Community 20 - "Icon"
Cohesion: 0.10
Nodes (31): react, @tauri-apps/plugin-dialog, Alert(), ICON, Tone, ErrorAlert(), ExplainedError, explainError() (+23 more)

### Community 21 - "detect"
Cohesion: 0.08
Nodes (30): _as_bgr(), detect(), DetectError, _glyph_px(), _input_size(), _inverse(), _model(), ndarray (+22 more)

### Community 22 - "Tauri Application Configuration"
Cohesion: 0.08
Nodes (24): app, security, windows, enable, scope, build, beforeBuildCommand, beforeDevCommand (+16 more)

### Community 23 - "group"
Cohesion: 0.10
Nodes (19): separated(i, j): does ink run across the gap between two adjacent quads? The…, _separator(), convex_hull(), glyph_unit(), group(), _inside(), merge(), neighbours() (+11 more)

### Community 24 - "check_group.py"
Cohesion: 0.10
Nodes (25): numpy, _dedupe(), Text-region detection: a DB (differentiable-binarisation) net through cv2.dnn.…, One quad per piece of text: of two that _same_text says are one line or column…, Do two bboxes cover the same line or column? See _SAME_SPAN., _same_text(), bbox(), Group column-level detections into one region per bubble. Phase 2b. WHY this… (+17 more)

### Community 25 - "_rerender_locked"
Cohesion: 0.06
Nodes (53): has_page(), has_raster(), The cached record, or None. Touches the directory -- see ``touch``., Whether the page has any raster on disk, without decoding one., read_regions(), write_regions(), _apply_translations(), _ask_with_retry() (+45 more)

### Community 26 - "check_skip.py"
Cohesion: 0.09
Nodes (35): item_placements(), Every (ordinal, entry) this job placed for one item, in page order. The repack…, Region, _archive(), client_ok(), inputs(), kinds(), kind_of() (+27 more)

### Community 27 - "Job"
Cohesion: 0.11
Nodes (10): Job, Every item, through the boundary, on `workers` threads. Never raises.…, Cancel the rest. On a job that already PAUSED and settled, the workers are…, Block until every item has a terminal status. False on timeout., AC-9, the half the product had never wired: probe once per job. Before this,…, emitted_stages(), item_totals(), main() (+2 more)

### Community 28 - "LLMClient"
Cohesion: 0.07
Nodes (30): _decode_reply(), error_kind(), _error_object_kind(), _from_event_stream(), glossary_text(), LLMClient, _moderation_reasons(), probe_token() (+22 more)

### Community 29 - "pipeline.py"
Cohesion: 0.09
Nodes (37): contextlib, dataclasses, functools, gc, hashlib, io, math, os (+29 more)

### Community 30 - "inpainter.py"
Cohesion: 0.13
Nodes (23): _crops(), erase(), _fill(), fill_white(), _flat(), _flat_surround(), _inpaint(), _lama() (+15 more)

### Community 31 - "mock-tauri.ts"
Cohesion: 0.13
Nodes (21): api(), Callback, callbacks, emit(), fakePage(), invoke(), itemPages, jobs (+13 more)

### Community 32 - "detect"
Cohesion: 0.13
Nodes (20): _box(), detect(), Text regions from detect.py's DB model. Regions become plain dicts here rather…, The region's bounding box in thousandths of the page, for the vision model.…, Both engines patched to counters; each source moves exactly one., _route(), _bubble_of(), _ellipse_mask() (+12 more)

### Community 33 - "_repack"
Cohesion: 0.33
Nodes (5): output_path(), Where the repacked archive lands. Same extension, except RAR -> .cbz. The…, output_path(), AC-6's round trip: the delivered pages, back into the input's format. **The…, _repack()

### Community 34 - "Frontend TypeScript Configuration"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+10 more)

### Community 35 - "pages"
Cohesion: 0.20
Nodes (10): _is_page(), members(), pages(), Yield `(ordinal, member, image)` for every decodable page, 1-based. Streamed…, A member that should be decoded as a page. Directory entries, macOS resource…, Page-candidate members of an OPEN archive, in yield order. One implementation,…, The page-candidate member names of `path`, in the order `pages` uses.…, _sorted_members() (+2 more)

### Community 36 - "main.py"
Cohesion: 0.06
Nodes (58): BaseModel, post, pydantic, Response, secrets, _bad_settings_response(), cache_clear(), _cache_miss_response() (+50 more)

### Community 37 - "section_not_text"
Cohesion: 0.08
Nodes (25): open_retry(), `open` with the same bounded retry as `_replace`, for READERS. The other half…, _raster(), _raster_files(), raster_name(), Mark a page directory as used NOW. Called on every read, not only on write, and…, The raster file for the erased region set `kept`; the undigested name for None.…, This eraser's raster files on disk for the page, newest first. (+17 more)

### Community 38 - "fetch"
Cohesion: 0.11
Nodes (20): `base`/Komalingo, moving an old-named sibling there if it is the only one.…, under(), ensure(), _ensure_directory(), fetch(), FetchError, _free_space(), model_dir() (+12 more)

### Community 39 - "lines"
Cohesion: 0.25
Nodes (6): lines(), area(), inside(), The parts that are text LINES, each read once. The detector answers per line…, Rows top to bottom (columns right to left), and WITHIN a row, left to right…, _reading_order()

### Community 40 - "ensure_libarchive"
Cohesion: 0.16
Nodes (13): os.replace with a short, bounded retry on Windows sharing violations. Two…, _replace(), _bsdtar(), bundled(), ensure_libarchive(), NativeMissing, Exception, A native dependency could not be installed, with a named reason. (+5 more)

### Community 41 - "typeset.py"
Cohesion: 0.10
Nodes (31): FreeTypeFont, _bbox(), _chord(), _draw_line(), _edge_adjacent(), floor_px(), _has_orphan(), _inset_points() (+23 more)

### Community 42 - "run_all.py"
Cohesion: 0.20
Nodes (16): append_record(), assert_interpreter(), discover(), env_class(), harvest_metrics(), last_status(), load_records(), main() (+8 more)

### Community 43 - "main"
Cohesion: 0.28
Nodes (8): _page_stairwell(), room_of(), The page that lost three blocks to the coarse-only detector and GAP alone.…, main(), fresh_regions(), ten_pages(), translate_with(), regions()

### Community 44 - "App.tsx"
Cohesion: 0.14
Nodes (24): App(), allowCache(), openItem(), refreshBatch(), refuseUnconfigured(), retriedPages(), runJob(), updatePage() (+16 more)

### Community 45 - "api.ts"
Cohesion: 0.09
Nodes (27): @tauri-apps/api, MODE_WORDS, Outcome, browse(), ApiError, CacheClearResult, isApiError(), isInternal() (+19 more)

### Community 46 - "Komalingo Brand Assets"
Cohesion: 0.13
Nodes (15): Komalingo Light-Tile App Icon PNG, Komalingo Dark-Tile App Icon PNG, Komalingo Dark-Tile App Icon, Komalingo Light-Tile App Icon, Komalingo Lockup PNG, Komalingo Lockup for Light Backgrounds, Komalingo Lockup for Dark Backgrounds, Komalingo Lockup on Dark PNG (+7 more)

### Community 48 - "repack_extras"
Cohesion: 0.12
Nodes (22): _admit(), expected_pages(), _is_page_name(), _lazy(), members(), Whether a member name is a page CANDIDATE. Identical rule to read_cbz., gz" | "bz2" | "xz" for a whole-file-compressed tar, "" for a plain one. This…, Run every member past the budget; return the page candidates to stream. Every… (+14 more)

### Community 49 - "resumes"
Cohesion: 0.15
Nodes (15): _client(), JobRequest, What the Settings UI sends. No defaults -- absent means absent., AC-7: a folder, or an explicit list, through the queue. Exactly one of `dir`…, Resume a paused job, with the settings as they are NOW: the pause was most…, Build an LLMClient, or None for the offline placeholder path. Called INSIDE…, Start a batch. Answers with the first status snapshot, immediately., Plan 1.5.5: a paused job goes on under the same id, with the settings as they… (+7 more)

### Community 50 - "long_path"
Cohesion: 0.08
Nodes (33): atomic_write(), long_path(), Yield a handle whose bytes land at `dest` only if the block completes. On any…, r"""Absolute, normalized, and \\?\-prefixed on Windows. The prefix turns off…, _cap_bytes(), clear(), _dir_size(), disk_bytes() (+25 more)

### Community 51 - "main.tsx"
Cohesion: 0.27
Nodes (7): ErrorBoundary, installGlobalReporting(), reportError(), boot(), dismissSplash(), failSplash(), splash()

### Community 52 - "cache.py"
Cohesion: 0.08
Nodes (55): collections, add_ref(), choice_name(), clear_refusals(), delete_job(), drop_ref(), has_choices(), has_edit_for_other_model() (+47 more)

### Community 53 - "run_item"
Cohesion: 0.09
Nodes (22): member_name(), pages(), The name the delivered page is written under. A PDF has no member names of its…, Yield `(ordinal, member, image)` for every page, 1-based. Same contract as…, One page's pixels and the path they took. Runs under the pdfium lock., _read_page(), _discard_output(), Lock (+14 more)

### Community 55 - "_Tier"
Cohesion: 0.18
Nodes (5): Image, LRU over decoded rasters, bounded by COUNT or BYTES, whichever binds. It counts…, Drop `key` if resident., Drop every raster of the page -- enforce_cap's path, one per erased set., _Tier

### Community 56 - "session"
Cohesion: 0.20
Nodes (11): onnx_session(), An onnxruntime session on the provider select_provider() names. Errors-only…, mask(), _model(), probability(), ndarray, Boolean (H, W): True where the model reads text ink., An onnxruntime session for MANIFEST entry `weights`, with named failures. Not… (+3 more)

### Community 57 - "shutdown"
Cohesion: 0.25
Nodes (7): exception_handler, Request, Exception, The last envelope. Every other error path in this file is deliberate; this one…, POST + correct nonce + loopback client, or the process stays up. Every…, shutdown(), unhandled()

### Community 58 - "get"
Cohesion: 0.14
Nodes (14): get, cache_stats(), health(), job_item(), job_status(), Liveness, plus which execution provider this process will run on. The provider…, Where the archive rebuild an edit scheduled has got to. The same dict…, One item's page records, so the Editor can open any item of a job (plan 2.3).… (+6 more)

### Community 59 - "llm.py"
Cohesion: 0.10
Nodes (31): asyncio, base64, http_client, json, random, _error_payload(), image_data_url(), is_null_word() (+23 more)

### Community 60 - "_decode_xobject"
Cohesion: 0.25
Nodes (9): _axis_aligned(), _decode_xobject(), _displayed(), Image, Whether the image is placed with no rotation, skew or flip. Only then are the…, The XObject's pixels, at the XObject's size. Three tiers, and the order is the…, A PdfBitmap's pixels as an RGB Pillow image, and the bitmap freed HERE.…, The page as the reader shows it. /Rotate is clockwise; Pillow's ROTATE_n is… (+1 more)

### Community 61 - "SpotFix.tsx"
Cohesion: 0.11
Nodes (22): DismissedRegion, ItemPages, PageRecord, RepackStatus, inPolygon(), laidInto(), ManualPanel(), render() (+14 more)

### Community 62 - "write_pdf"
Cohesion: 0.20
Nodes (11): PdfReader, PdfWriter, _copy_info(), copy_outline(), _outline_items(), walk(), Flatten pypdf's nested outline into `(depth, title, page index)`. pypdf…, Rebuild the source outline on the writer, page numbers by index. By index and… (+3 more)

### Community 63 - "retry_page"
Cohesion: 0.22
Nodes (10): _describe_skip(), _model_id(), The key a translation made WITHOUT the page image is stored under, so a later…, One skipped page, asked again (plan 2.1). Returns its fresh record. `mode` is…, What a refusal is remembered under: endpoint, model, image or not., The one line the Queue and the review panel show for a skipped page., What the translation file is keyed on. 'offline' is a real key, not a hole. The…, refusal_key() (+2 more)

### Community 64 - "Node TypeScript Configuration"
Cohesion: 0.25
Nodes (7): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include

### Community 65 - "manual_page"
Cohesion: 0.25
Nodes (9): get_placement(), _placement_key(), The placement entry for one position, or None. See put_placement., manual_page(), (placement, content record, original page) for a page of a job, or CacheMiss…, Erase, render and deliver a page the user fixed, and persist it., A skipped page translated by the user, every bubble at once (plan 2.2). `texts`…, _render_fixed() (+1 more)

### Community 66 - "check_warmup"
Cohesion: 0.20
Nodes (9): no_download(), on_disk(), On this thread, fetch() raises FetchError('absent') instead of downloading. For…, Whether MANIFEST entry `name` is fully downloaded, by name and size only. No…, Load the models every page needs, before the first page asks. Returns what…, warm_models(), check_warmup(), recorder() (+1 more)

### Community 67 - ".__init__"
Cohesion: 0.15
Nodes (12): _as_event_stream(), _chat_reply(), _cut_off(), _load_fixtures(), The ids a request asked about; [0] when the prompt carried none., Echo one translation per region the request asked about. The client batches a…, A chat.completion whose content a token cap cut mid-JSON. Cut at the midpoint…, A chat.completion re-framed as the chunks a streaming gateway sends. The… (+4 more)

### Community 68 - "redcheck_spotfix.py"
Cohesion: 0.43
Nodes (6): failed_tags(), main(), r"""Phase 3's red-check: sabotage each guarded behaviour, confirm its assert…, Run the gate. MT_REDCHECK tells it the sabotage marker is ours., run_check(), sha256()

### Community 69 - "check_round_trip"
Cohesion: 0.22
Nodes (10): page_boxes(), page_layout(), Every page's DISPLAYED box in points, `/Rotate` applied. What the output must…, Per page: `(page w, page h, image w, image h)` in displayed points. The image…, check_round_trip(), _flatten(), The product's path: job.run_job, both fixtures, offline., expected.json's [title, page, children] -> (depth, title, page). (+2 more)

### Community 70 - "StubProvider"
Cohesion: 0.22
Nodes (6): One page through all seven stages, in order. Returns the regions record.…, run_page(), _fit(), AC-1's clauses over the second engine's pages, whole pipeline., Usable as a context manager; `.url` is the OpenAI-compatible base URL., StubProvider

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
Cohesion: 0.32
Nodes (8): _preview_factor(), The integer reduce factor for a w x h page's original preview: the short edge…, The page as it came in, for the Editor's original toggle, and the top of it,…, _write_previews(), base(), original(), thumb(), stamped()

### Community 98 - "typeset_page"
Cohesion: 0.18
Nodes (12): _commit(), Fit, ink_style(), Image, ndarray, One region's typeset result. Every field is output-only. `rung` is the RUNG…, Typeset every region of one page. Returns (image, [Fit]). Two-phase by…, INK_PLAIN, INK_DARK or INK_BUSY from the page's gray inside `points`. (+4 more)

### Community 99 - "Scanned PDF Fixture"
Cohesion: 0.67
Nodes (3): Scanned PDF Fixture, Unreadable Scanned PDF Page 1 Image, Unreadable Scanned PDF Page 2 Image

### Community 142 - "_sevenzip_payloads"
Cohesion: 0.10
Nodes (11): FastAPI, Every named member in ONE extract pass, into memory, budget-fed. py7zr 1.x has…, _sevenzip_payloads(), buffer(), lifespan(), r"""Repair leaked cache references before anything can be evicted against them.…, pipeline.warm_models on a daemon thread; the lifespan never waits on it.…, Exit the moment stdin closes -- which, under Tauri, means the parent died.… (+3 more)

### Community 143 - "_open"
Cohesion: 0.50
Nodes (4): PdfDocument, _open(), page_count(), How many pages `pages` will yield. The document's own count, no render.…

### Community 144 - "page_hash"
Cohesion: 0.29
Nodes (6): model_slug(), page_hash(), SHA-256 of the DECODED pixels, plus mode and size. Mode and size are in the…, A filesystem-safe name for a model id that two ids cannot share. The readable…, [key] the hash is over decoded pixels, and mode and size are in it., section_key()

### Community 145 - "skip"
Cohesion: 0.10
Nodes (27): shutil, r"""The native libraries the sidecar needs and pip cannot deliver (AC-6, .cbr).…, subprocess, sys, tempfile, Phase 0 -- the sidecar's HTTP surface and the shutdown gate (US-007). OFFLINE.…, Phase 0 -- the write protocol. Offline, no fixtures, no network. Asserts, from…, Phase 2c -- the erase gate: text off the page, and NO box where it was.… (+19 more)

### Community 146 - "main"
Cohesion: 0.29
Nodes (8): _dilate(), _flag(), _in_box(), main(), _poly_mask(), _pre_2c_fill(), ndarray, The inpainter as it was before Phase 2c, copied here so the flag is compared…

### Community 147 - "_Recogniser"
Cohesion: 0.29
Nodes (6): OcrError, ndarray, RuntimeError, A recogniser that cannot run. Named, like every sidecar failure path., One text line -> (text, mean character confidence)., _Recogniser

### Community 148 - "check_fixtures_deterministic.py"
Cohesion: 0.43
Nodes (6): generate(), main(), Phase 0a gate: two regenerations from an empty tree are byte-identical. uv run…, Relative-path -> sha256 for everything under the generated subdirs., sha256(), snapshot()

### Community 149 - "_is_scan"
Cohesion: 0.40
Nodes (6): PdfPage, _full_page_image(), _is_scan(), The ONE image object covering more than half the page, or None. Exactly one:…, The build order's rule, both halves. Returns the image or None., _render()

### Community 150 - "region.py"
Cohesion: 0.33
Nodes (5): as_points(), The shared Region type: detect.py's output, typeset.py's input. Defined here…, One detected text region, as it travels through the pipeline. `text` defaults…, Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.…, Region

### Community 151 - "check_cancel.py"
Cohesion: 0.20
Nodes (13): http_server, build_inputs(), check_cancel(), check_no_partial(), check_resume(), _eight_page_archive(), events_of(), main() (+5 more)

### Community 152 - "_floor_fits"
Cohesion: 0.33
Nodes (9): _capacity(), _floor_fits(), fits(), _longest(), The largest n in [0, n_max] for which fits(n) holds, given fits is monotone.…, The rung-3 state -- floor, tightened, no inset, no bleed -- as a predicate., The largest character count of `text` that fits at the floor, tightened.…, Rung 5's terminal branch. Returns (placed or None, rendered, reason). Cannot… (+1 more)

### Community 153 - "Progress.tsx"
Cohesion: 0.40
Nodes (5): LABEL, Stage, stageIndex(), STAGES, StageTrack()

### Community 154 - "imports.py"
Cohesion: 0.33
Nodes (6): importlib, load(), main(), Phase 0a spike: can we import the CV components in-process on the pinned stack?…, Import under a RUNNING event loop -- the condition the sidecar imposes., traceback

### Community 155 - "schedule_repack"
Cohesion: 0.40
Nodes (5): flush_repacks(), Rebuild the item's archive soon, on a worker thread. Returns the status.…, Every pending repack, now, on this thread. For the exit paths. The app does not…, _repack_worker(), schedule_repack()

### Community 157 - "EraseError"
Cohesion: 0.33
Nodes (5): The inpainter to use, from `name` or MT_INPAINTER. Unknown values raise., resolve(), EraseError, RuntimeError, The erase stage cannot run. Carries (reason, kind) like DetectError. Shared by…

### Community 158 - "_container"
Cohesion: 0.50
Nodes (5): detect(), Whether the bytes start with a PDF header. The spec allows junk before `%PDF-`,…, _container(), The container family of `src_path`, by signature: an archive family or…, check_detect()

### Community 159 - "root"
Cohesion: 0.14
Nodes (22): clear_running(), job_dir(), _job_key(), jobs_root(), mark_running(), The cache root. MT_CACHE_DIR wins, so tests never touch the real one., The one form a job id takes inside this module: a safe path segment. job_id…, read_placement() (+14 more)

### Community 160 - "TypesetError"
Cohesion: 0.40
Nodes (5): RuntimeError, A typeset pass that cannot proceed. Named, like every sidecar failure path., Raise a named error if called inside a running event loop, on EVERY page. The…, _refuse_running_loop(), TypesetError

### Community 161 - "main"
Cohesion: 0.40
Nodes (4): main(), pe_imports(), The DLL names in `path`'s PE import directory. Hand-rolled rather than a…, third_party()

## Knowledge Gaps
- **307 isolated node(s):** `expected_json_sha256`, `sha256`, `size`, `sha256`, `size` (+302 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1094 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **48 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Checks` connect `Checks` to `main`, `check_package.py`, `check_archives.py`, `check_inpaint.py`, `check_cjk.py`, `check_batch.py`, `page_hash`, `skip`, `main`, `check_id.py`, `fetch_fixtures.py`, `check_typeset.py`, `check_cancel.py`, `check_group.py`, `check_skip.py`, `Job`, `pipeline.py`, `root`, `detect`, `main`, `section_not_text`, `fetch`, `main`, `resumes`, `long_path`, `cache.py`, `llm.py`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `long_path()` connect `long_path` to `check_archives.py`, `archive.py`, `expand`, `_sevenzip_payloads`, `_open`, `check_batch.py`, `detect`, `_rerender_locked`, `pipeline.py`, `_container`, `root`, `pages`, `main.py`, `section_not_text`, `fetch`, `ensure_libarchive`, `repack_extras`, `resumes`, `cache.py`, `run_item`, `write_pdf`, `check_warmup`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `LLMClient` connect `LLMClient` to `Checks`, `check_inpaint.py`, `check_cjk.py`, `check_batch.py`, `check_typeset.py`, `skip`, `check_id.py`, `check_cancel.py`, `check_group.py`, `check_skip.py`, `Job`, `pipeline.py`, `detect`, `main.py`, `section_not_text`, `main`, `resumes`, `llm.py`, `StubProvider`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 33 inferred relationships involving `Checks` (e.g. with `inputs()` and `kinds()`) actually correct?**
  _`Checks` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `LLMClient` (e.g. with `models()` and `retry_pages()`) actually correct?**
  _`LLMClient` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `expected_json_sha256`, `sha256`, `size` to the rest of the system?**
  _307 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `check_package.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06431372549019608 - nodes in this community are weakly interconnected._