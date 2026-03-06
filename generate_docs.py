#!/usr/bin/env python3
"""
Auto Documentation Generator
Uses open-source Hugging Face models (no API keys required)
to generate README, API docs, architecture diagram, and setup guide
for any GitHub repository.
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from typing import Dict, List, Optional

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
GITHUB_API = "https://api.github.com"
OUTPUT_DIR = "docs_output"
MAX_FILES   = 50          # scan at most 50 files per repo
MAX_CHARS   = 4000        # chars of code fed to the LLM per doc section


# ─────────────────────────────────────────────
# 1. GitHub repo scanner (no auth needed for public repos)
# ─────────────────────────────────────────────
def fetch_repo_metadata(owner: str, repo: str, token: Optional[str] = None) -> Dict:
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_repo_tree(owner: str, repo: str, token: Optional[str] = None) -> List[Dict]:
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json().get("tree", [])


def fetch_file_content(owner: str, repo: str, path: str,
                       token: Optional[str] = None) -> str:
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    resp = requests.get(url, headers=headers, timeout=20)
    if resp.status_code != 200:
        return ""
    import base64
    raw = resp.json().get("content", "")
    try:
        return base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        return ""


CODE_EXTS = {".py", ".js", ".ts", ".java", ".go", ".rs", ".cpp",
             ".c", ".rb", ".php", ".cs", ".swift", ".kt", ".sh"}
CONFIG_FILES = {"requirements.txt", "package.json", "Cargo.toml",
                "go.mod", "pom.xml", "build.gradle", "Makefile",
                "Dockerfile", ".github"}


def collect_code_snippets(owner: str, repo: str,
                           token: Optional[str] = None) -> str:
    """Return up to MAX_CHARS of representative source code."""
    tree = fetch_repo_tree(owner, repo, token)
    blobs = [n for n in tree if n.get("type") == "blob"]
    selected = [
        b["path"] for b in blobs
        if Path(b["path"]).suffix in CODE_EXTS
    ][:MAX_FILES]

    chunks = []
    total = 0
    for path in selected:
        content = fetch_file_content(owner, repo, path, token)
        snippet = content[:800]
        chunks.append(f"### {path}\n{snippet}")
        total += len(snippet)
        if total >= MAX_CHARS:
            break
    return "\n\n".join(chunks)


def collect_config_info(owner: str, repo: str,
                        token: Optional[str] = None) -> str:
    """Grab contents of common config/manifest files."""
    tree = fetch_repo_tree(owner, repo, token)
    paths = [n["path"] for n in tree if n.get("type") == "blob"]
    out = []
    for p in paths:
        name = Path(p).name
        if name in CONFIG_FILES or p in CONFIG_FILES:
            content = fetch_file_content(owner, repo, p, token)[:600]
            out.append(f"### {p}\n{content}")
    return "\n\n".join(out)


# ─────────────────────────────────────────────
# 2. Local LLM inference with Hugging Face
#    Uses DistilGPT-2 (< 350 MB) — fits in
#    GitHub Actions' 7 GB RAM / 6-hour limit
# ─────────────────────────────────────────────
def load_model():
    """Lazy-load the text-generation pipeline once."""
    from transformers import pipeline, set_seed
    print("Loading DistilGPT-2 model (runs fully offline) …", flush=True)
    gen = pipeline(
        "text-generation",
        model="distilgpt2",
        device=-1,          # CPU
        truncation=True,
    )
    set_seed(42)
    return gen


_pipeline = None

def generate_text(prompt: str, max_new_tokens: int = 300) -> str:
    global _pipeline
    if _pipeline is None:
        _pipeline = load_model()
    result = _pipeline(
        prompt,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        pad_token_id=50256,
    )
    return result[0]["generated_text"][len(prompt):]


# ─────────────────────────────────────────────
# 3. Document generators
# ─────────────────────────────────────────────
def generate_readme(meta: Dict, code: str, config: str) -> str:
    prompt = (
        f"Write a professional GitHub README.md for the repository "
        f"'{meta['full_name']}'. Description: {meta.get('description','')}.\n"
        f"Primary language: {meta.get('language','unknown')}.\n"
        f"Sample source files:\n{code[:1200]}\n"
        f"Config files:\n{config[:600]}\n"
        f"README (markdown):\n"
    )
    body = generate_text(prompt, max_new_tokens=400)
    header = f"""# {meta['name']}

> {meta.get('description', 'No description provided.')}

![Language](https://img.shields.io/badge/language-{meta.get('language','unknown')}-blue)
![License](https://img.shields.io/github/license/{meta['full_name']})
![Stars](https://img.shields.io/github/stars/{meta['full_name']}?style=social)

"""
    return header + body


def generate_api_docs(meta: Dict, code: str) -> str:
    prompt = (
        f"Generate API documentation in Markdown for the project "
        f"'{meta['name']}' based on the following source code:\n"
        f"{code[:1500]}\n"
        f"Include: functions, parameters, return values, and usage examples.\n"
        f"API Documentation:\n"
    )
    body = generate_text(prompt, max_new_tokens=400)
    return f"# API Documentation – {meta['name']}\n\n" + body


def generate_setup_guide(meta: Dict, config: str) -> str:
    prompt = (
        f"Write a step-by-step setup / installation guide for the project "
        f"'{meta['name']}' (language: {meta.get('language','unknown')}).\n"
        f"Config files found:\n{config[:800]}\n"
        f"Setup Guide (markdown):\n"
    )
    body = generate_text(prompt, max_new_tokens=350)
    return f"# Setup Guide – {meta['name']}\n\n" + body


def generate_architecture_diagram(meta: Dict, tree: List[Dict]) -> str:
    """
    Produce a textual Mermaid.js architecture diagram
    derived from the real directory structure.
    """
    dirs = sorted({
        str(Path(n["path"]).parent)
        for n in tree
        if n.get("type") == "blob" and str(Path(n["path"]).parent) != "."
    })[:20]

    lines = ["graph TD"]
    lines.append(f'    ROOT["{meta["name"]} (root)"]')
    added = set()
    for d in dirs:
        parts = Path(d).parts
        for i, part in enumerate(parts):
            node_id = "_".join(parts[:i+1]).replace("-", "_").replace(".", "_")
            if node_id not in added:
                lines.append(f'    {node_id}["{part}/"]')
                added.add(node_id)
            if i == 0:
                lines.append(f"    ROOT --> {node_id}")
            else:
                parent_id = "_".join(parts[:i]).replace("-","_").replace(".","_")
                lines.append(f"    {parent_id} --> {node_id}")

    mermaid_block = "\n".join(lines)
    return f"""# Architecture Diagram – {meta['name']}

> Auto-generated from the repository file tree.

```mermaid
{mermaid_block}
```

## Directory Overview

| Directory | Purpose |
|-----------|---------|
""" + "\n".join(f"| `{d}/` | — |" for d in dirs[:15])


# ─────────────────────────────────────────────
# 4. Main entry point
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Generate docs for a GitHub repo using local open-source LLMs"
    )
    parser.add_argument("repo_url",
        help="GitHub repo URL or 'owner/repo' shorthand")
    parser.add_argument("--token", default=None,
        help="GitHub personal access token (optional, for private repos)")
    parser.add_argument("--output", default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})")
    args = parser.parse_args()

    # Parse owner/repo
    url = args.repo_url.rstrip("/")
    if "github.com" in url:
        parts = url.split("github.com/")[-1].split("/")
    else:
        parts = url.split("/")
    if len(parts) < 2:
        sys.exit("ERROR: Provide repo as 'owner/repo' or full GitHub URL.")
    owner, repo = parts[0], parts[1]

    print(f"\n📦 Fetching metadata for {owner}/{repo} …")
    meta  = fetch_repo_metadata(owner, repo, args.token)
    tree  = fetch_repo_tree(owner, repo, args.token)
    code  = collect_code_snippets(owner, repo, args.token)
    cfg   = collect_config_info(owner, repo, args.token)

    print("🤖 Running local LLM inference (DistilGPT-2) …")
    readme   = generate_readme(meta, code, cfg)
    api_docs = generate_api_docs(meta, code)
    setup    = generate_setup_guide(meta, cfg)
    arch     = generate_architecture_diagram(meta, tree)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    (out / "README.md").write_text(readme, encoding="utf-8")
    (out / "API_DOCS.md").write_text(api_docs, encoding="utf-8")
    (out / "SETUP_GUIDE.md").write_text(setup, encoding="utf-8")
    (out / "ARCHITECTURE.md").write_text(arch, encoding="utf-8")

    # Write a JSON manifest
    manifest = {
        "repo": f"{owner}/{repo}",
        "generated_files": [
            "README.md", "API_DOCS.md",
            "SETUP_GUIDE.md", "ARCHITECTURE.md"
        ],
        "model": "distilgpt2",
        "framework": "Hugging Face Transformers"
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"\n✅ Documentation written to ./{args.output}/")
    for f in ["README.md", "API_DOCS.md", "SETUP_GUIDE.md", "ARCHITECTURE.md"]:
        print(f"   • {f}")


if __name__ == "__main__":
    main()
