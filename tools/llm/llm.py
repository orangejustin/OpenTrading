#!/usr/bin/env python3
"""
llm.py — engine dispatcher for OpenTrading's AI layer (`ot web`).

One interface, three interchangeable engines — all OPTIONAL, all degrade
cleanly to the keyless data panels:

    gemini      GEMINI_API_KEY        Google AI Studio (free tier)
    openrouter  OPENROUTER_API_KEY    ONE key → any model (GPT / Claude / Gemini /
                                      DeepSeek / GLM / Grok / Qwen …)
    claude      no key                your Claude Code subscription, via the
                                      `claude` CLI in headless print mode

Pick per request (`generate_json(..., engine=, model=)`), or set a default with
`OT_LLM_ENGINE` in .env. Unset → first available in the order above.

Educational only — not financial advice.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import gemini
except Exception:  # noqa: BLE001
    gemini = None
try:
    import openrouter
except Exception:  # noqa: BLE001
    openrouter = None
try:
    import claude_cli
except Exception:  # noqa: BLE001
    claude_cli = None

# Curated OpenRouter shortlist (UI suggestions; ANY slug can be typed in).
OPENROUTER_CHOICES = [
    "z-ai/glm-5.2",
    "deepseek/deepseek-v4-pro",
    "deepseek/deepseek-v4-flash",
    "openai/gpt-5.5",
    "openai/gpt-4o",
    "google/gemini-3.5-flash",
    "anthropic/claude-sonnet-5",
    "anthropic/claude-fable-5",
    "x-ai/grok-4.3",
    "qwen/qwen3.7-max",
]
GEMINI_CHOICES = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]


def _uniq(seq):
    out, seen = [], set()
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def engines() -> list[dict]:
    """Status + model suggestions for every engine (drives the UI switcher)."""
    out = []
    gm_ok = bool(gemini and gemini.have_key())
    gm_models = _uniq([os.environ.get("GEMINI_MODEL")] + GEMINI_CHOICES)
    out.append({"id": "gemini", "label": "Gemini", "ok": gm_ok,
                "models": gm_models, "model": gm_models[0],
                "hint": None if gm_ok else "set GEMINI_API_KEY in .env"})
    or_ok = bool(openrouter and openrouter.have_key())
    or_models = _uniq([os.environ.get("OPENROUTER_MODEL")] + OPENROUTER_CHOICES)
    out.append({"id": "openrouter", "label": "OpenRouter", "ok": or_ok,
                "models": or_models, "model": or_models[0],
                "hint": None if or_ok else "set OPENROUTER_API_KEY in .env"})
    cl_ok = bool(claude_cli and claude_cli.have_cli())
    out.append({"id": "claude", "label": "Claude Code", "ok": cl_ok,
                "models": claude_cli.MODELS if claude_cli else ["default"],
                "model": claude_cli.default_model() if claude_cli else "default",
                "hint": None if cl_ok else "install the claude CLI"})
    return out


def any_ok() -> bool:
    return any(e["ok"] for e in engines())


def default_engine() -> str | None:
    """OT_LLM_ENGINE if it's usable, else the first available engine."""
    es = engines()
    pref = (os.environ.get("OT_LLM_ENGINE") or "").strip().lower()
    for e in es:
        if e["id"] == pref and e["ok"]:
            return e["id"]
    for e in es:
        if e["ok"]:
            return e["id"]
    return None


def status_line() -> str:
    """One-line startup summary, e.g. `gemini ✓ · openrouter — (set …) · claude ✓`."""
    bits = []
    for e in engines():
        bits.append(f"{e['id']} ✓" if e["ok"] else f"{e['id']} — ({e['hint']})")
    return " · ".join(bits)


def generate_json(prompt: str, schema: dict, *, engine: str | None = None,
                  model: str | None = None) -> tuple[dict, dict]:
    """Structured generation on the chosen engine. Returns (data, {engine, model})."""
    eng = (engine or "").strip().lower() or default_engine()
    if not eng:
        raise RuntimeError("no LLM engine available — set GEMINI_API_KEY or "
                           "OPENROUTER_API_KEY in .env, or install the claude CLI")
    info = {e["id"]: e for e in engines()}.get(eng)
    if not info:
        raise RuntimeError(f"unknown engine '{eng}' (gemini | openrouter | claude)")
    if not info["ok"]:
        raise RuntimeError(f"engine '{eng}' is not available — {info['hint']}")
    mdl = (model or "").strip() or info["model"]
    if eng == "gemini":
        # gemini.py runs its own model-fallback chain off GEMINI_MODEL.
        if model:
            os.environ["GEMINI_MODEL"] = mdl
        data = gemini.generate_json(prompt, schema)
    elif eng == "openrouter":
        data = openrouter.generate_json(prompt, schema, model=mdl)
    else:
        data = claude_cli.generate_json(prompt, schema, model=mdl)
        # Surface the exact model the CLI resolved the alias to (e.g. "opus"
        # -> "claude-opus-4-8") so the UI can stamp the real model.
        if claude_cli.LAST_MODEL_ID:
            mdl = claude_cli.LAST_MODEL_ID
    return data, {"engine": eng, "model": mdl}


if __name__ == "__main__":
    print("engines:", status_line())
    print("default:", default_engine())
