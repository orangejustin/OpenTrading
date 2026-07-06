#!/usr/bin/env python3
"""
codex_cli.py — use YOUR ChatGPT/Codex subscription as an LLM engine, headless.

OPTIONAL module, the Codex twin of `claude_cli.py`: **no API key at all**.
It shells out to `codex exec` (non-interactive mode) and treats it as a pure
text-in → text-out engine, exactly like every other OpenTrading engine:

    codex exec --ephemeral -s read-only -C <tmpdir> -o <file> "<prompt>"

Deterministic-SOP discipline: the evidence pack in the prompt is the ONLY
input. We point the working root at an empty temp dir and run the strictest
sandbox, so Codex can't wander off reading the repo or running tools — no
AGENTS.md / .agents/ needed (that's why the repo doesn't carry them).

It degrades cleanly: if the `codex` binary isn't on PATH the caller simply
doesn't list this engine (see `have_cli()`).

Model: your Codex default, or pass a model slug via `model` / `OT_CODEX_MODEL`.

Educational only — not financial advice.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Reuse the tolerant JSON extractor — same reply-parsing problem, same fix.
import claude_cli

MODELS = ["default"]


def have_cli() -> bool:
    return bool(shutil.which("codex"))


def default_model() -> str:
    return os.environ.get("OT_CODEX_MODEL") or "default"


def _run(prompt: str, model: str | None, timeout: int) -> str:
    exe = shutil.which("codex")
    if not exe:
        raise RuntimeError("codex CLI not found on PATH (install Codex)")
    with tempfile.TemporaryDirectory(prefix="ot-codex-") as td:
        out_file = Path(td) / "last-message.txt"
        cmd = [exe, "exec", "--ephemeral", "--skip-git-repo-check",
               "-s", "read-only", "-C", td, "--color", "never",
               "-o", str(out_file)]
        mdl = (model or default_model()).strip()
        if mdl and mdl != "default":
            cmd += ["-m", mdl]
        cmd.append(prompt)
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if out.returncode != 0:
            raise RuntimeError(
                f"codex CLI exit {out.returncode}: {(out.stderr or out.stdout)[:300]}")
        if out_file.exists() and out_file.read_text(encoding="utf-8").strip():
            return out_file.read_text(encoding="utf-8")
        return out.stdout  # older CLI: fall back to stdout


def generate_text(prompt: str, *, model: str | None = None, timeout: int = 240) -> str:
    """Free-form text generation on your Codex subscription."""
    return _run(prompt, model, timeout)


def generate_json(prompt: str, schema: dict, *, model: str | None = None,
                  timeout: int = 300) -> dict:
    """Structured generation: schema goes in the prompt, output extracted robustly."""
    import json
    p = (prompt + "\n\nReturn ONLY one JSON object — no prose, no code fences, "
         "no preamble — matching exactly this JSON Schema:\n" + json.dumps(schema))
    return claude_cli._extract_json(_run(p, model, timeout))


if __name__ == "__main__":
    # Smoke test: python3 codex_cli.py "one sentence on market regime risk"
    import sys
    if not have_cli():
        print("codex CLI not found — this engine is disabled (data panels still work).")
        raise SystemExit(0)
    q = " ".join(sys.argv[1:]) or "Say 'codex cli ok' and nothing else."
    print(generate_text(q, timeout=120))
