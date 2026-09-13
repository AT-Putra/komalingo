<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="brand/komalingo-lockup-on-dark.png">
    <img src="brand/komalingo-lockup.png" alt="Komalingo" width="420">
  </picture>
</p>

<p align="center">
  Translate manga, manhua and manhwa <b>on the page</b>: the original text is erased,<br>
  and the translation is typeset back into the bubbles it came from.
</p>

---

Komalingo is a Windows desktop app. Point it at a chapter or a whole folder and it
gives you back the same pages, in the same format, in another language. Detection,
OCR, text erasing and typesetting all run locally, on your GPU when you have one.
The only thing that leaves your machine is the translation request to the language
model you configure.

## What it does

- **Reads Japanese, Chinese and Korean** — manga-ocr for Japanese (a whole bubble
  in one pass, vertical text included), PP-OCRv5 for Chinese and Korean.
- **Translates to English or Indonesian** through any OpenAI-compatible endpoint:
  a cloud provider, or a local llama.cpp / Ollama server. A vision-capable model
  is sent the page image for context; a text-only model still works and is
  reported as such. Indonesian keeps Japanese honorifics the way Indonesian
  publishers print them — see [`docs/honorifics.md`](docs/honorifics.md).
- **Erases the original text, not the art under it.** A per-pixel text mask
  (comic-text-detector) takes just the glyphs, and a manga-tuned LaMa model
  continues the page underneath — no white boxes over the artwork.
- **Typesets the translation into the bubble's real shape**, shrinking,
  rewrapping, and as a last resort asking the model for a shorter line when
  the text will not fit. Anything that still does not fit is flagged.
- **Keeps your format.** Images (PNG, JPEG, WebP, BMP, TIFF), comic archives
  (`.cbz`, `.cb7`, `.cbt`, and `.cbr`, which comes back as `.cbz`) and PDFs go
  in, and the same format comes out, pages in the original order, ComicInfo
  and extra files carried across.
- **Lets you fix any bubble.** The editor shows every flagged region; rewrite a
  line, and that page re-renders in well under a second and the archive beside
  it is rebuilt in the background.
- **Handles whole series.** A folder runs as a queue with per-file results, can
  be cancelled, and resumes without redoing finished pages: every page is
  cached by its pixels, so re-running a volume, or switching target language,
  skips detection and OCR entirely.

Stylized sound effects drawn into the art are left as drawn.

## How it works

```
page ─► detect text regions ─► OCR ─► translate (LLM) ─► erase text ─► typeset ─► encode ─► write
```

A Tauri 2 shell (React + TypeScript) drives a Python sidecar (FastAPI) that owns
the pipeline. The models run on ONNX Runtime and PyTorch, and pick CUDA
automatically, falling back to the CPU with a stated reason when there is no GPU.

## Requirements

- Windows 10 or 11, x64. Other platforms are untested.
- An NVIDIA GPU is optional but strongly recommended; everything also runs on the CPU.
- About 750 MB of disk for the models, downloaded and checksum-verified on first use,
  plus the page cache (capped at 4 GB).
- An OpenAI-compatible chat endpoint and a model, set in **Settings**.

## Building from source

There is no packaged release yet. To build and run it yourself you need
[Node.js](https://nodejs.org/) 22+, [Rust](https://rustup.rs/),
[uv](https://docs.astral.sh/uv/) and Python 3.11–3.13.

```powershell
git clone https://github.com/AT-Putra/komalingo.git
cd komalingo
npm install

# The sidecar: dependencies, the bundled libarchive, then the packaged exe.
uv sync --project sidecar
uv run --project sidecar python -m sidecar.native
uv run --project sidecar python tests/check_package.py   # builds build\dist\sidecar\ and proves it

# Put the sidecar where Tauri expects it.
copy build\dist\sidecar\sidecar-x86_64-pc-windows-msvc.exe src-tauri\binaries\
robocopy build\dist\sidecar\_internal src-tauri\binaries\_internal /MIR

npm run tauri dev      # or: npm run tauri build
```

The sidecar build is large (about 3.5 GB with the CUDA libraries); see
[`src-tauri/binaries/README.md`](src-tauri/binaries/README.md) for why it ships
as a folder rather than a single file.

## Tests

The suite runs offline, against a stub translation provider:

```powershell
uv run --project sidecar python tests/run_all.py
```

The few checks that need a live model endpoint read `.env.local`
(copy [`.env.local.example`](.env.local.example)) and skip with a named reason
without it. Checks that grade OCR and erasing on real manga pages need scans that
are not redistributed with the repository; [`fixtures/README.md`](fixtures/README.md)
says how to reassemble them.

## Models

Downloaded on first use from their pinned sources, never bundled with the code.
Each keeps its own license.

| Model | Used for | Source | License |
|---|---|---|---|
| manga-ocr | Japanese OCR | [kha-white/manga-ocr-base](https://huggingface.co/kha-white/manga-ocr-base) | Apache-2.0 |
| PP-OCRv5 recognition (zh, ko) | Chinese and Korean OCR | PaddlePaddle weights, ONNX export by [GreatV/oar-ocr](https://github.com/GreatV/oar-ocr) | Apache-2.0 |
| PP-OCRv3 DB text detection | Text regions | [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo) | Apache-2.0 |
| comic-text-detector | Per-pixel text mask | ONNX by [mayocream](https://huggingface.co/mayocream/comic-text-detector-onnx); upstream training code [dmMaze/comic-text-detector](https://github.com/dmMaze/comic-text-detector) is GPL-3.0 | Apache-2.0 (as published) |
| LaMa, manga fine-tune | Erasing text | ONNX by [mayocream](https://huggingface.co/mayocream/lama-manga-onnx), from [dreMaz/AnimeMangaInpainting](https://huggingface.co/dreMaz/AnimeMangaInpainting) | Apache-2.0 |

## License

Komalingo's source code is released under the [MIT License](LICENSE).
The models above, and the manga you translate with it, belong to their respective owners.
