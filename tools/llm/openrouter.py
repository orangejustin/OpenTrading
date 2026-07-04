#!/usr/bin/env python3
"""
openrouter.py — minimal stdlib OpenRouter client for OpenTrading's web analysis.

OPTIONAL module. ONE key → any model: OpenAI (gpt-4o/gpt-5.x), Anthropic
(claude-*), Google (gemini-*), DeepSeek (deepseek-v4-*), Z.ai (glm-5.2), Grok,
Qwen… — switch per request via the `model` argument or `OPENROUTER_MODEL`.
No SDK — a urllib POST to the OpenAI-compatible /chat/completions endpoint,
with a curl fallback for macOS TLS.

It degrades cleanly: if `OPENROUTER_API_KEY` is missing the caller shows the
keyless data panels without this engine (see `have_key()`).

Config (env / git-ignored .env):
    OPENROUTER_API_KEY   required to enable this engine (openrouter.ai/settings/keys)
    OPENROUTER_MODEL     default model slug (default: z-ai/glm-5.2 — cheap + strong)

Educational only — not financial advice.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request

BASE = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "z-ai/glm-5.2"
# Attribution headers OpenRouter asks apps to send (public repo, no secrets).
REFERER = "https://github.com/orangejustin/OpenTrading"
TITLE = "OpenTrading"


def have_key() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def default_model() -> str:
    return os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _post(payload: bytes, timeout: int) -> tuple[int, str]:
    """POST JSON; return (status, body). urllib first, curl fallback on TLS errors."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}",
        "HTTP-Referer": REFERER,
        "X-Title": TITLE,
    }
    req = urllib.request.Request(BASE, data=payload, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception:
        curl = shutil.which("curl")
        if not curl:
            raise
        cmd = [curl, "-sS", "--max-time", str(timeout), "-X", "POST"]
        for k, v in headers.items():
            cmd += ["-H", f"{k}: {v}"]
        cmd += ["--data-binary", "@-", BASE]
        out = subprocess.run(cmd, input=payload, capture_output=True, timeout=timeout + 5)
        body = out.stdout.decode("utf-8", "replace")
        code = 200 if body and '"error"' not in body[:200] else 502
        return code, body


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


def _call(prompt: str, model: str | None, json_mode: bool,
          temperature: float, timeout: int) -> str:
    if not have_key():
        raise RuntimeError("OPENROUTER_API_KEY not set")
    mdl = model or default_model()
    body: dict = {
        "model": mdl,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    status, resp = _post(json.dumps(body).encode("utf-8"), timeout)
    if status != 200 and json_mode and "response_format" in resp:
        # Some routed models reject response_format — retry as plain text.
        body.pop("response_format", None)
        status, resp = _post(json.dumps(body).encode("utf-8"), timeout)
    if status != 200:
        try:
            msg = json.loads(resp)["error"]["message"]
        except Exception:
            msg = resp[:200]
        raise RuntimeError(f"openrouter {mdl} failed (HTTP {status}): {msg}")
    data = json.loads(resp)
    if data.get("error"):
        raise RuntimeError(f"openrouter {mdl}: {data['error'].get('message', 'unknown error')}")
    return data["choices"][0]["message"]["content"] or ""


def generate_text(prompt: str, *, model: str | None = None,
                  temperature: float = 0.4, timeout: int = 90) -> str:
    """Free-form text generation."""
    return _call(prompt, model, False, temperature, timeout)


def generate_json(prompt: str, schema: dict, *, model: str | None = None,
                  temperature: float = 0.3, timeout: int = 120) -> dict:
    """Structured generation: JSON-mode where supported, robust extraction always."""
    p = (prompt + "\n\nReturn ONLY one JSON object — no prose, no code fences — "
         "matching exactly this JSON Schema:\n" + json.dumps(schema))
    return _extract_json(_call(p, model, True, temperature, timeout))


if __name__ == "__main__":
    # Smoke test: python3 openrouter.py [model] "one sentence on market regime risk"
    import sys
    if not have_key():
        print("OPENROUTER_API_KEY not set — this engine is disabled (data panels still work).")
        raise SystemExit(0)
    args = sys.argv[1:]
    mdl = args.pop(0) if args and "/" in args[0] else None
    q = " ".join(args) or "Say 'openrouter ok' and nothing else."
    print(generate_text(q, model=mdl))
