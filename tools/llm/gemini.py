#!/usr/bin/env python3
"""
gemini.py — minimal stdlib Google Gemini client for OpenTrading's web analysis.

OPTIONAL module. Used by `ot web` to turn the keyless data pack into an AI
analysis (summary, action, entry/exit levels, risks). No SDK — just a urllib POST
to the v1beta `generateContent` endpoint, with a curl fallback for macOS TLS.

It degrades cleanly: if `GEMINI_API_KEY` is missing the caller shows the keyless
data panels without the AI layer (see `have_key()`).

Config (env / git-ignored .env):
    GEMINI_API_KEY          required to enable the AI layer (free key: aistudio.google.com)
    GEMINI_MODEL            default model (default: gemini-2.5-flash)
    GEMINI_MODEL_FALLBACK   comma-separated fallbacks if the primary 404s

Educational only — not financial advice.
"""
from __future__ import annotations

import json
import os
import shutil
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"
# Sensible fallbacks if the configured model is unavailable on the key's tier.
_BUILTIN_FALLBACKS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]


def have_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _models() -> list[str]:
    """Ordered, de-duped model list: GEMINI_MODEL → GEMINI_MODEL_FALLBACK → builtins."""
    out, seen = [], set()
    cfg = [os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL]
    cfg += [m.strip() for m in (os.environ.get("GEMINI_MODEL_FALLBACK") or "").split(",") if m.strip()]
    for m in cfg + _BUILTIN_FALLBACKS:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _post(url: str, payload: bytes, timeout: int) -> tuple[int, str]:
    """POST JSON; return (status, body). urllib first, curl fallback on TLS/URL errors."""
    req = urllib.request.Request(url, data=payload, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")   # surface the error body (model 404 etc.)
    except Exception:
        curl = shutil.which("curl")
        if not curl:
            raise
        out = subprocess.run(
            [curl, "-sS", "--max-time", str(timeout), "-X", "POST",
             "-H", "Content-Type: application/json", "--data-binary", "@-", url],
            input=payload, capture_output=True, timeout=timeout + 5)
        body = out.stdout.decode("utf-8", "replace")
        # curl can't easily give us the HTTP status; infer failure from an error body.
        code = 200 if body and '"error"' not in body[:200] else 502
        return code, body


def _call(prompt: str, schema: dict | None, temperature: float, timeout: int) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    gen: dict = {"temperature": temperature}
    if schema:
        gen["responseMimeType"] = "application/json"
        gen["responseSchema"] = schema
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": gen,
    }).encode("utf-8")

    last_err = None
    for model in _models():
        url = BASE.format(model=model) + "?" + urllib.parse.urlencode({"key": key})
        try:
            status, body = _post(url, payload, timeout)
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            continue
        if status == 200:
            try:
                data = json.loads(body)
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:  # noqa: BLE001
                last_err = f"unparseable response: {e}; body={body[:200]}"
                continue
        # 404/400 → model unavailable or bad request: try the next model.
        last_err = f"HTTP {status}: {body[:200]}"
        if status not in (400, 403, 404):
            break
    raise RuntimeError(f"gemini call failed: {last_err}")


def generate_text(prompt: str, *, temperature: float = 0.4, timeout: int = 45) -> str:
    """Free-form text generation."""
    return _call(prompt, None, temperature, timeout)


def generate_json(prompt: str, schema: dict, *, temperature: float = 0.3, timeout: int = 45) -> dict:
    """Structured generation: returns a dict validated against `schema` (responseSchema)."""
    txt = _call(prompt, schema, temperature, timeout)
    return json.loads(txt)


if __name__ == "__main__":
    # Smoke test: python3 gemini.py "one sentence on market regime risk"
    import sys
    if not have_key():
        print("GEMINI_API_KEY not set — the AI layer is disabled (data panels still work).")
        raise SystemExit(0)
    q = " ".join(sys.argv[1:]) or "Say 'gemini ok' and nothing else."
    print(generate_text(q))
