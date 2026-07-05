#!/usr/bin/env python3
"""
debate.py — the 3-call bull/bear/judge desk (`ot debate TICKER`).

TradingAgents' research-desk idea, distilled to OpenTrading's deterministic
SOP: NO agentic tool use — the evidence pack is built up-front by running the
`ot` CLIs (quote, decide, macro, news, earnings gate, Polymarket odds, past-call
lessons), then exactly three LLM calls run on any configured engine(s):

    1. BULL  — argues the long case from the pack
    2. BEAR  — argues the short case AND must attack the bull's strongest point
    3. JUDGE — forced 5-tier verdict + entry + invalidation + time stop
               ("reserve HOLD for genuinely balanced evidence"), with the
               self-calibration lessons injected

Engines come from tools/llm/llm.py (gemini / openrouter / claude) — bull and
bear use different engines when two are available (real perspective diversity),
and the judge defaults to the Claude Code CLI when present.

    ot debate NVDA                       # full desk, text card
    ot debate NVDA --format json         # machine-readable row
    ot debate NVDA --log                 # also journal the verdict (ot reflect)
    ot debate NVDA --bull gemini --bear openrouter --judge claude

Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# Engine keys live in the git-ignored .env (same loader the email/web use).
sys.path.insert(0, str(ROOT / "tools/email"))
try:
    import send_email  # noqa: E402
    send_email.load_env_file(str(ROOT / ".env"))
except Exception:  # noqa: BLE001
    pass

VERDICTS = ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]

BULL_SCHEMA = {
    "type": "object",
    "properties": {
        "case": {"type": "string", "description": "the bull case, 3-5 sentences, tied to the evidence"},
        "strongest_point": {"type": "string", "description": "single strongest bull argument, one sentence"},
        "entry_idea": {"type": "string", "description": "where a long makes sense, with a $ level"},
        "what_would_change_my_mind": {"type": "string"},
    },
    "required": ["case", "strongest_point", "entry_idea"],
}

BEAR_SCHEMA = {
    "type": "object",
    "properties": {
        "case": {"type": "string", "description": "the bear case, 3-5 sentences, tied to the evidence"},
        "strongest_point": {"type": "string"},
        "attack_on_bull": {"type": "string",
                           "description": "direct rebuttal of the bull's strongest point"},
        "what_would_change_my_mind": {"type": "string"},
    },
    "required": ["case", "strongest_point", "attack_on_bull"],
}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": VERDICTS},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "entry": {"type": "string", "description": "$ level + one-phrase reason"},
        "invalidation": {"type": "number", "description": "the price that voids the thesis"},
        "time_stop_days": {"type": "integer"},
        "rationale": {"type": "string", "description": "2-4 sentences: which side won and why"},
        "weakest_link": {"type": "string", "description": "the most fragile assumption in the verdict"},
    },
    "required": ["verdict", "confidence", "entry", "invalidation", "time_stop_days", "rationale"],
}


def _tool_json(script: str, *args: str, timeout: int = 90):
    """Run one ot tool CLI, parse its JSON. Missing feeds degrade to None."""
    try:
        out = subprocess.run([sys.executable, str(ROOT / script), *args, "--format", "json"],
                             capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
        return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else None
    except Exception:  # noqa: BLE001
        return None


def _tool_text(script: str, *args: str, timeout: int = 60) -> str:
    try:
        out = subprocess.run([sys.executable, str(ROOT / script), *args],
                             capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return ""


def build_pack(ticker: str, dte: int, market: str) -> dict:
    """The deterministic evidence pack — every feed is an existing ot CLI."""
    t = ticker.upper()
    pack = {
        "decide": _tool_json("tools/sim/decide.py", t, "--dte", str(dte), "--market", market),
        "macro": _tool_json("tools/macro/macro.py"),
        "earnings": _tool_json("tools/earnings/earnings.py", t),
        "poly": _tool_json("tools/predict/poly.py"),
        "news": _tool_json("tools/financialjuice/fj.py", "fetch", "--ticker", t,
                           "--minutes", "2880", "--limit", "10"),
        "lessons": _tool_text("tools/reflect/reflect.py", "lessons", "--ticker", t),
        "quant": _tool_json("tools/quant/quant.py", t, timeout=120),
    }
    # Optional power module: TimesFM cone, only when its venv exists (ot forecast).
    tfm_py = ROOT / ".venv-forecast/bin/python"
    if tfm_py.exists():
        try:
            out = subprocess.run([str(tfm_py), str(ROOT / "tools/forecast/tfm.py"), t,
                                  "--format", "json"],
                                 capture_output=True, text=True, timeout=300, cwd=str(ROOT))
            fc = json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else None
            pack["forecast"] = fc if fc and fc.get("available") else None
        except Exception:  # noqa: BLE001
            pack["forecast"] = None
    return pack


def _pack_text(t: str, pack: dict) -> str:
    """Render the pack compactly — the LLMs argue over THIS, nothing else."""
    L = [f"EVIDENCE PACK — {t} (all data fetched just now by deterministic CLIs)"]
    d = pack.get("decide") or {}
    if d:
        plan = d.get("plan") or {}
        L.append(f"PRICE/PLAN: last ${d.get('price')}, engine action {d.get('action')}"
                 f" (grade {plan.get('grade')}), buy_zone {plan.get('buy_zone')},"
                 f" trim_zone {plan.get('trim_zone')}, stop {plan.get('stop')},"
                 f" trend_up={d.get('trendup')}, 5d {d.get('prior5')},"
                 f" VIX {d.get('vix')} ({d.get('vix_chg')})")
    m = pack.get("macro") or {}
    if m:
        L.append("MACRO: " + json.dumps(m.get("score") or m, ensure_ascii=False)[:500])
    e = pack.get("earnings")
    if e:
        L.append("EARNINGS GATE: " + json.dumps(e, ensure_ascii=False)[:300])
    p = (pack.get("poly") or {}).get("gate")
    if p:
        odds = " · ".join(f"{k}={v['p']}%" for k, v in p.items())
        L.append(f"CROWD ODDS (Polymarket): {odds}")
    q = pack.get("quant")
    if q and not q.get("error"):
        hit = q.get("oos_hit_rate")
        # Honest reliability label — only call the model weak when it IS weak
        # (a 69% OOS hit-rate is strong; an unconditional caveat misleads the bear).
        rel = ("reliability unknown" if hit is None
               else f"WEAK model ({hit}% OOS hit-rate, ~coin-flip) — discount it" if hit < 55
               else f"decent model ({hit}% OOS hit-rate)" if hit < 62
               else f"STRONG model ({hit}% OOS hit-rate) — weigh it seriously")
        L.append(f"QUANT MODEL (logistic on this name's history, {q.get('horizon_days')}d):"
                 f" P(up)={q.get('p_up')}% vs base {q.get('base_rate_up')}%, {rel},"
                 f" range cone {json.dumps(q.get('cone'))}")
    fc = pack.get("forecast")
    if fc:
        L.append(f"TIMESFM CONE (foundation model, {fc.get('horizon_days')}d):"
                 f" point_end {fc.get('point_end')}, cone {json.dumps(fc.get('cone'))}")
    news = pack.get("news")
    items = news if isinstance(news, list) else (news or {}).get("items") or []
    heads = [it.get("title") or it.get("headline") or "" for it in items if isinstance(it, dict)][:8]
    if heads:
        L.append("NEWS (48h, this name):\n" + "\n".join(f"  - {h}" for h in heads if h))
    if pack.get("lessons"):
        L.append(pack["lessons"])
    return "\n".join(L)


def _pick_engines(bull: str | None, bear: str | None, judge: str | None):
    avail = [e["id"] for e in llm.engines() if e.get("ok")]
    if not avail:
        raise RuntimeError("no LLM engine configured (GEMINI_API_KEY / OPENROUTER_API_KEY / claude CLI)")
    b = bull if bull in avail else avail[0]
    # perspective diversity: bear takes a DIFFERENT engine when one exists
    others = [e for e in avail if e != b]
    r = bear if bear in avail else (others[0] if others else b)
    j = judge if judge in avail else ("claude" if "claude" in avail else avail[0])
    return b, r, j


def run_debate(ticker: str, dte: int, market: str,
               bull_eng: str | None, bear_eng: str | None, judge_eng: str | None) -> dict:
    t = ticker.upper()
    t0 = time.time()
    pack = build_pack(t, dte, market)
    ev = _pack_text(t, pack)
    b_eng, r_eng, j_eng = _pick_engines(bull_eng, bear_eng, judge_eng)

    base = (f"{ev}\n\nYou are one analyst on a two-sided research desk for {t}. "
            "Argue ONLY from the evidence pack above — no outside facts. "
            "Short-term swing horizon (days to ~4 weeks). Educational only.")

    def tag(meta: dict) -> str:
        return f"{meta.get('engine')}:{meta.get('model')}"

    bull, bmeta = llm.generate_json(base + "\n\nROLE: BULL. Make the strongest honest LONG case.",
                                    BULL_SCHEMA, engine=b_eng)
    bear, rmeta = llm.generate_json(
        base + "\n\nROLE: BEAR. Make the strongest honest SHORT/avoid case. "
               f"The bull's strongest point was: \"{bull.get('strongest_point', '')}\" — "
               "you MUST directly engage and attack it in `attack_on_bull`.",
        BEAR_SCHEMA, engine=r_eng)

    judge_prompt = (
        f"{ev}\n\nBULL CASE ({tag(bmeta)}):\n{json.dumps(bull, ensure_ascii=False)}\n\n"
        f"BEAR CASE ({tag(rmeta)}):\n{json.dumps(bear, ensure_ascii=False)}\n\n"
        f"You are the JUDGE on this research desk for {t}. Weigh both cases against the "
        "evidence pack. Rules: (1) COMMIT — reserve HOLD for genuinely balanced evidence, "
        "not as a refuge; (2) risk-first — the invalidation price is mandatory and must be "
        "a real level from the evidence, not a round-number guess; (3) respect the event "
        "gate — if a Tier-1 event or this name's earnings are imminent, say so in the "
        "rationale and prefer patience over initiation; (4) weigh the PAST-CALL LESSONS: "
        "if this desk has been wrong on this name or this setup type, demand more evidence. "
        "Educational only — not financial advice.")
    verdict, jmeta = llm.generate_json(judge_prompt, JUDGE_SCHEMA, engine=j_eng)

    price = (pack.get("decide") or {}).get("price")
    return {
        "ticker": t, "price": price, "verdict": verdict.get("verdict"),
        "confidence": verdict.get("confidence"), "entry": verdict.get("entry"),
        "invalidation": verdict.get("invalidation"), "time_stop_days": verdict.get("time_stop_days"),
        "rationale": verdict.get("rationale"), "weakest_link": verdict.get("weakest_link"),
        "bull": bull, "bear": bear,
        "engines": {"bull": tag(bmeta), "bear": tag(rmeta), "judge": tag(jmeta)},
        "elapsed_s": round(time.time() - t0, 1),
    }


def render_text(r: dict) -> str:
    tone = {"STRONG_BUY": "++", "BUY": "+", "HOLD": "·", "SELL": "-", "STRONG_SELL": "--"}
    L = [f"ot debate — {r['ticker']}  (last ${r.get('price')})",
         "",
         f"  VERDICT   {r['verdict']} [{tone.get(r['verdict'], '?')}]  ·  confidence {r['confidence']}/100",
         f"  entry     {r['entry']}",
         f"  invalid.  {r['invalidation']}  ·  time stop {r['time_stop_days']}d",
         "",
         f"  judge     {r['rationale']}"]
    if r.get("weakest_link"):
        L.append(f"  weakest   {r['weakest_link']}")
    L += ["",
          f"  bull ({r['engines']['bull']}): {r['bull'].get('strongest_point')}",
          f"  bear ({r['engines']['bear']}): {r['bear'].get('strongest_point')}",
          f"  bear on bull: {r['bear'].get('attack_on_bull')}",
          "",
          f"  3 LLM calls · {r['elapsed_s']}s · deterministic evidence pack (no agentic tool use)",
          "  Educational only — not financial advice."]
    return "\n".join(L)


def _journal(r: dict) -> None:
    """--log: drop the verdict into the ot reflect journal (closes the loop).
    Re-runs the same day skip the append — one graded call per name per day."""
    from datetime import date
    marker = f'"id": "{r["ticker"]}-{date.today().isoformat()}"'
    jf = ROOT / "data/journal/decisions.jsonl"
    if jf.exists() and marker in jf.read_text():
        return
    action = {"STRONG_BUY": "CALL", "BUY": "CALL",
              "SELL": "PUT", "STRONG_SELL": "PUT"}.get(r["verdict"], "NO-ACTION")
    args = [sys.executable, str(ROOT / "tools/reflect/reflect.py"), "log",
            "--ticker", r["ticker"], "--action", action,
            "--thesis", (r.get("rationale") or "")[:200]]
    if r.get("price") is not None:
        args += ["--price", str(r["price"])]
    if r.get("invalidation") is not None:
        args += ["--invalidation", str(r["invalidation"])]
    if r.get("time_stop_days") is not None:
        args += ["--time-stop", str(r["time_stop_days"])]
    subprocess.run(args, capture_output=True, text=True, timeout=15, cwd=str(ROOT),
                   stdin=subprocess.DEVNULL)


def main(argv=None):
    p = argparse.ArgumentParser(prog="debate",
                                description="bull/bear/judge research desk (3 LLM calls, deterministic pack)")
    p.add_argument("ticker")
    p.add_argument("--dte", type=int, default=5)
    p.add_argument("--market", choices=["US", "A", "HK"], default="US")
    p.add_argument("--bull", help="engine for the bull (gemini|openrouter|claude)")
    p.add_argument("--bear", help="engine for the bear")
    p.add_argument("--judge", help="engine for the judge (default: claude if available)")
    p.add_argument("--log", action="store_true", help="journal the verdict via ot reflect")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)

    try:
        r = run_debate(a.ticker, a.dte, a.market, a.bull, a.bear, a.judge)
    except Exception as e:  # noqa: BLE001
        print(f"debate: {e}", file=sys.stderr)
        return 1
    if a.log:
        _journal(r)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.format == "json" else render_text(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
