#!/usr/bin/env python3
"""
claude_cli.py — use YOUR Claude Code subscription as an LLM engine, headless.

OPTIONAL module, and the most OpenTrading-flavored one: **no API key at all**.
It shells out to the `claude` CLI in print mode (`claude -p --output-format json`),
exactly like the daily-email pipeline (`roster_mailer.sh`) already does — so the
web dashboard's AI analysis is billed to your existing Claude subscription.

It degrades cleanly: if the `claude` binary isn't on PATH the caller shows the
keyless data panels without this engine (see `have_cli()`).

Model: the CLI's default (your session model), or pass an alias — sonnet /
opus / haiku / fable — via the `model` argument or `OT_CLAUDE_MODEL`.

Educational only — not financial advice.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ["default", "sonnet", "opus", "haiku", "fable"]
# Verified against the CLI's own --help: an unknown value only warns and falls
# back to the default, so an unrecognised level degrades rather than failing.
EFFORTS = ["default", "low", "medium", "high", "xhigh", "max"]

# The exact model id the CLI actually used on the last run (e.g.
# "claude-opus-4-8"), parsed from the result envelope — aliases like
# "sonnet"/"default" resolve to whatever the CLI picks.
LAST_MODEL_ID: str | None = None


def have_cli() -> bool:
    return bool(shutil.which("claude"))


def default_model() -> str:
    return os.environ.get("OT_CLAUDE_MODEL") or "default"


def _extract_json(text: str) -> dict:
    """Parse a JSON object out of an LLM reply (tolerates code fences / prose)."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        pass
    start = t.find("{")
    if start < 0:
        raise ValueError(f"no JSON object in response: {t[:120]!r}")
    depth, instr, esc = 0, False, False
    for i in range(start, len(t)):
        ch = t[i]
        if instr:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                instr = False
        elif ch == '"':
            instr = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(t[start:i + 1])
    raise ValueError("unbalanced JSON object in response")


def default_effort() -> str:
    return os.environ.get("OT_CLAUDE_EFFORT") or "default"


def _run(prompt: str, model: str | None, timeout: int, effort: str | None = None) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI not found on PATH (install Claude Code)")
    cmd = [exe, "-p", "--output-format", "json"]
    mdl = (model or default_model()).strip()
    if mdl and mdl != "default":
        cmd += ["--model", mdl]
    eff = (effort or default_effort()).strip()
    if eff and eff != "default":
        cmd += ["--effort", eff]
    out = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                         timeout=timeout, cwd=str(ROOT))
    if out.returncode != 0:
        raise RuntimeError(f"claude CLI exit {out.returncode}: {(out.stderr or out.stdout)[:300]}")
    try:
        env = json.loads(out.stdout)
    except Exception:
        return out.stdout  # older CLI / unexpected format: treat stdout as the reply
    if isinstance(env, dict):
        if env.get("is_error"):
            raise RuntimeError(f"claude CLI error: {str(env.get('result'))[:300]}")
        global LAST_MODEL_ID
        mu = env.get("modelUsage")
        if isinstance(mu, dict) and mu:
            def _out_tokens(k):
                v = mu[k]
                return v.get("outputTokens", 0) if isinstance(v, dict) else 0
            LAST_MODEL_ID = max(mu, key=_out_tokens)
        elif env.get("model"):
            LAST_MODEL_ID = str(env["model"])
        if env.get("result") is not None:
            return str(env["result"])
    return out.stdout


def generate_text(prompt: str, *, model: str | None = None, timeout: int = 180) -> str:
    """Free-form text generation on your Claude subscription."""
    return _run(prompt, model, timeout)


def generate_json(prompt: str, schema: dict, *, model: str | None = None,
                  timeout: int = 240, effort: str | None = None) -> dict:
    """Structured generation: schema goes in the prompt, output is extracted robustly."""
    p = (prompt + "\n\nReturn ONLY one JSON object — no prose, no code fences, "
         "no preamble — matching exactly this JSON Schema:\n" + json.dumps(schema))
    return _extract_json(_run(p, model, timeout, effort))


if __name__ == "__main__":
    # Smoke test: python3 claude_cli.py "one sentence on market regime risk"
    import sys
    if not have_cli():
        print("claude CLI not found — this engine is disabled (data panels still work).")
        raise SystemExit(0)
    q = " ".join(sys.argv[1:]) or "Say 'claude cli ok' and nothing else."
    print(generate_text(q, timeout=120))
