# auto-doc-generator

> AI-powered documentation generator for any GitHub repository.
> Uses **100% open-source, local models** — zero API keys required.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Model](https://img.shields.io/badge/model-DistilGPT--2-orange)
![License](https://img.shields.io/github/license/PranayMahendrakar/auto-doc-generator)
![Stars](https://img.shields.io/github/stars/PranayMahendrakar/auto-doc-generator?style=social)

---

## What It Does

Point this tool at **any public GitHub repository** and it will automatically generate:

| Output File | Description |
|-------------|-------------|
| `README.md` | Project overview, badges, features, usage |
| `API_DOCS.md` | Function signatures, parameters, return values |
| `ARCHITECTURE.md` | Mermaid.js directory diagram of the repo structure |
| `SETUP_GUIDE.md` | Step-by-step installation and configuration guide |
| `manifest.json` | Metadata about the generation run |

All files are saved to a `docs_output/` folder and committed back to the repo.

---

## Architecture

```
GitHub Repo URL
      |
      v
  GitHub REST API  ──>  fetch file tree, source code, config files
      |
      v
  Code Analyzer   ──>  extract structure, languages, patterns
      |
      v
  DistilGPT-2      ──>  local Hugging Face inference (CPU, ~350 MB)
  (transformers)        no internet calls, no API keys
      |
      v
  Doc Writers      ──>  README / API Docs / Setup Guide / Architecture
      |
      v
  docs_output/     ──>  committed back to GitHub via Actions
```

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| LLM | [DistilGPT-2](https://huggingface.co/distilgpt2) | Tiny (~350 MB), runs on CPU, no API key |
| Inference | [Hugging Face Transformers](https://github.com/huggingface/transformers) | pip-installable, local |
| Repo scanning | GitHub REST API | No auth needed for public repos |
| Diagrams | Mermaid.js (Markdown) | Renders natively in GitHub |
| CI/CD | GitHub Actions | Free runner, caches model weights |

---

## Quick Start

### Option A — GitHub Actions (recommended)

1. Fork or clone this repository.
2. Go to **Actions** → **Generate Documentation** → **Run workflow**.
3. Enter the target repo (e.g. `torvalds/linux` or `https://github.com/owner/repo`).
4. The workflow runs, generates docs, and commits them to `docs_output/`.
5. Download the artifact or browse the folder in your repo.

### Option B — Run locally

```bash
# 1. Clone the repo
git clone https://github.com/PranayMahendrakar/auto-doc-generator.git
cd auto-doc-generator

# 2. Install dependencies (CPU-only torch recommended)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 3. Generate docs for any public repo
python generate_docs.py owner/repo

# 4. Output files will be in ./docs_output/
ls docs_output/
```

**For private repos**, pass a GitHub personal access token:

```bash
python generate_docs.py owner/private-repo --token ghp_XXXXXXXXXXXX
```

---

## Configuration

| Constant | Default | Description |
|----------|---------|-------------|
| `MAX_FILES` | `50` | Max source files scanned per repo |
| `MAX_CHARS` | `4000` | Max code characters fed to LLM |
| `OUTPUT_DIR` | `docs_output` | Output directory |
| Model | `distilgpt2` | Change to any HF text-generation model |

To use a larger (better) model locally, edit the `load_model()` function in `generate_docs.py`:

```python
# Examples of drop-in model replacements:
# model='gpt2'           # 500 MB, slightly better
# model='gpt2-medium'    # 1.5 GB, much better
# model='microsoft/phi-2' # 2.7B params, excellent quality (needs ~6 GB RAM)
gen = pipeline('text-generation', model='distilgpt2', device=-1)
```

---

## GitHub Actions Workflow Details

The workflow (`.github/workflows/generate-docs.yml`) supports two triggers:

- **Manual dispatch** — provide any target repo URL via the Actions UI
- **Auto on push to main** — re-documents this repo on every commit

The runner:
1. Installs CPU-only PyTorch + Transformers
2. Caches the DistilGPT-2 weights (`~/.cache/huggingface`) so subsequent runs are fast
3. Calls `generate_docs.py` with the target repo
4. Commits generated docs back to `docs_output/`
5. Uploads docs as a downloadable workflow artifact (retained 30 days)

---

## Supported Repository Types

- Any **public** GitHub repo (no token needed)
- **Private** repos with a PAT passed via `--token`
- Works best on repos with Python, JavaScript, TypeScript, Go, Rust, Java, C/C++

---

## Limitations

- DistilGPT-2 is a small model — output quality is basic but consistent.
  Swap to `gpt2-medium` or `microsoft/phi-2` for significantly better docs.
- GitHub Actions free runners have 7 GB RAM; models > 3B parameters may OOM.
- The GitHub API has a 60 req/hour unauthenticated rate limit.
  Pass a PAT with `--token` for 5,000 req/hour.

---

## License

MIT License — see [LICENSE](LICENSE).

---

## Author

Built by [@PranayMahendrakar](https://github.com/PranayMahendrakar)
