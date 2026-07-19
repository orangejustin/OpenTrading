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
    ot debate NVDA --bear openrouter:z-ai/glm-5.2 --judge claude:opus   # engine[:model]

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
        # --- the playbook: a verdict nobody can act on is not a verdict ---
        "blocks_supporting": {
            "type": "array", "items": {"type": "string"},
            "description": "which evidence blocks [A]-[F] back this verdict. Two or more "
                           "DIFFERENT letters = corroborated; a single letter = one signal, "
                           "so confidence must stay low.",
        },
        "trigger": {
            "type": "string",
            "description": "the observable condition that puts this trade ON — a price level "
                           "crossed, a level reclaimed/lost, a level held on a retest. Must be "
                           "checkable on a chart without judgement, e.g. 'MU reclaims 869 and "
                           "holds it for a full session'. Never 'if sentiment improves'.",
        },
        "instrument": {
            "type": "string",
            "description": "what to actually trade and why that vehicle: shares / a specific "
                           "option structure with strike+expiry / an ETF. Name the leverage "
                           "explicitly and prefer the unleveraged expression unless the "
                           "horizon is short enough that daily-reset decay is immaterial.",
        },
        "targets": {
            "type": "array", "items": {"type": "number"},
            "description": "1-3 profit levels in ascending order of ambition, each a real "
                           "level from the evidence (a wall, a prior high, a cone quantile).",
        },
        "scale_plan": {
            "type": "string",
            "description": "how to build and unwind: tranches on entry, where to take partial "
                           "profit, what to do if it gaps through a target.",
        },
        "inverse_scenario": {
            "type": "string",
            "description": "the trade that becomes correct if `invalidation` breaks — the plan "
                           "for being wrong, not just the stop.",
        },
        "event_risk": {
            "type": "string",
            "description": "the dated catalyst inside the horizon from block [E] and whether "
                           "to hold through it, or 'none inside the horizon'.",
        },
    },
    "required": ["verdict", "confidence", "entry", "invalidation", "time_stop_days", "rationale",
                 "blocks_supporting", "trigger", "instrument", "inverse_scenario"],
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
        # The ticker filter is a regex on headlines — it returns nothing for most
        # names. A tape-wide pull is what actually carries the risk-on/risk-off read.
        "news_tape": _tool_json("tools/financialjuice/fj.py", "fetch",
                                "--minutes", "1440", "--limit", "18"),
        "lessons": _tool_text("tools/reflect/reflect.py", "lessons", "--ticker", t),
        "stats": _tool_json("tools/reflect/reflect.py"),
        "quant": _tool_json("tools/quant/quant.py", t, timeout=120),
        # FLOW + POSITIONING + EVENT — dimensions the desk owned as tools but never
        # showed the debate, so every verdict argued from price history alone.
        "options": _tool_json("tools/options/opt.py", t, "--dte", str(max(dte, 7))),
        "smart": _tool_json("tools/smartmoney/sm.py"),
        "catalysts": _tool_json("tools/catalysts/catalysts.py", "--days", "10"),
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
    """Render the pack compactly — the LLMs argue over THIS, nothing else.

    Grouped by INFORMATION SOURCE, not by tool. Every number under [A] is a
    transform of the same daily close series, so agreement between them is not
    corroboration — it is one signal counted four times. Independent confirmation
    can only come from a different block.
    """
    L = [f"EVIDENCE PACK — {t} (all data fetched just now by deterministic CLIs)",
         "",
         "HOW TO WEIGH THIS PACK — read before arguing:",
         "  Evidence is grouped [A]-[F] by INFORMATION SOURCE. Within a block the",
         "  items share one input, so they cannot confirm each other; treat a block",
         "  as ONE vote whose strength is its best member. A thesis backed by two",
         "  or more DIFFERENT blocks is materially stronger than one backed by four",
         "  items inside a single block. Say which blocks back your case.",
         "",
         "[A] PRICE HISTORY — every item below is a function of this name's past",
         "    closes ALONE. No news, no flows, no fundamentals reach these models.",
         "    They describe momentum; they cannot know why.",
         ""]
    d = pack.get("decide") or {}
    if d:
        plan = d.get("plan") or {}

        def _z(zone):
            """Zones arrive as raw float pairs — 12 decimals of noise the model has
            to parse before it can reason."""
            if isinstance(zone, (list, tuple)) and len(zone) == 2 and all(
                    isinstance(x, (int, float)) for x in zone):
                return f"{zone[0]:.2f}-{zone[1]:.2f}"
            return str(zone)

        def _pct(x):
            """`prior5` and `vix_chg` are FRACTIONS (-0.1331 = -13.31%). Rendered raw,
            a judge read -0.1331 as "-0.13%, basically flat" and dismissed the bear's
            momentum case on a 13% collapse (journal: MU 2026-07-07). Always stamp %."""
            return f"{x * 100:+.2f}%" if isinstance(x, (int, float)) else str(x)

        px = d.get("price")
        L.append(f"  PRICE/PLAN: last ${px:.2f}" if isinstance(px, (int, float))
                 else f"  PRICE/PLAN: last ${px}")
        L[-1] += (f", engine action {d.get('action')}"
                  f" (grade {plan.get('grade')}), buy_zone {_z(plan.get('buy_zone'))},"
                  f" trim_zone {_z(plan.get('trim_zone'))}, stop {plan.get('stop')},"
                  f" trend_up={d.get('trendup')}, 5d move {_pct(d.get('prior5'))},"
                  f" VIX {d.get('vix'):.2f} ({_pct(d.get('vix_chg'))} w/w)"
                  if isinstance(d.get("vix"), (int, float)) else
                  f", engine action {d.get('action')}"
                  f" (grade {plan.get('grade')}), buy_zone {_z(plan.get('buy_zone'))},"
                  f" trim_zone {_z(plan.get('trim_zone'))}, stop {plan.get('stop')},"
                  f" trend_up={d.get('trendup')}, 5d move {_pct(d.get('prior5'))},"
                  f" VIX {d.get('vix')}")
    q = pack.get("quant")
    if q and not q.get("error"):
        hit = q.get("oos_hit_rate")
        # Honest reliability label — only call the model weak when it IS weak
        # (a 69% OOS hit-rate is strong; an unconditional caveat misleads the bear).
        rel = ("reliability unknown" if hit is None
               else f"WEAK model ({hit}% OOS hit-rate, ~coin-flip) — discount it" if hit < 55
               else f"decent model ({hit}% OOS hit-rate)" if hit < 62
               else f"STRONG model ({hit}% OOS hit-rate) — weigh it seriously")
        L.append(f"  QUANT MODEL (logistic on this name's history, {q.get('horizon_days')}d):"
                 f" P(up)={q.get('p_up')}% vs base {q.get('base_rate_up')}%, {rel},"
                 f" range cone {json.dumps(q.get('cone'))}")
    fc = pack.get("forecast")
    if fc:
        L.append(f"  TIMESFM CONE (foundation model, {fc.get('horizon_days')}d):"
                 f" point_end {fc.get('point_end')}, cone {json.dumps(fc.get('cone'))}")
    if (q and not q.get("error")) or fc:
        L.append("  ^ NOTE: the quant cone and the TimesFM cone are two estimators of the"
                 " SAME close series. Their agreement measures method stability, NOT"
                 " independent confirmation — never cite one as corroborating the other.")

    L += ["", "[B] NEWS & NARRATIVE — the only text-derived evidence here. Nothing in",
          "    block [A] can see any of this.", ""]
    def _heads(feed, limit):
        items = feed if isinstance(feed, list) else (feed or {}).get("items") or []
        out = []
        for it in items[:limit]:
            if not isinstance(it, dict):
                continue
            h = it.get("headline") or it.get("title") or ""
            if not h:
                continue
            # Keep the timestamp and category the fetcher already resolved — a bare
            # headline list hides whether a story is 2 minutes or 2 days old.
            when, cat = it.get("time_et") or "", it.get("category") or ""
            tag = " · ".join(x for x in (when, cat) if x)
            out.append(f"  - {h}" + (f"   [{tag}]" if tag else ""))
        return out
    name_heads = _heads(pack.get("news"), 8)
    if name_heads:
        L.append(f"  NEWS — {t} (48h):")
        L += name_heads
    else:
        L.append(f"  NEWS — {t}: no name-specific headlines matched in 48h. The filter is"
                 " a regex on headlines, so this means SILENCE, not the absence of news.")
    tape_heads = _heads(pack.get("news_tape"), 14)
    if tape_heads:
        L.append("  NEWS — the tape (24h, all names; this carries the risk-on/risk-off read):")
        L += tape_heads

    m = pack.get("macro") or {}
    if m:
        L += ["", "[C] MACRO & RATES — liquidity/rates regime, independent of this name.", ""]
        # The verdict first — a raw truncated dump used to cut `bias` mid-sentence
        # (and dropped auto_score entirely whenever an extra indicator was present).
        inds = " · ".join(
            f"{i.get('label')} {i.get('value')} ({i.get('score'):+d})"
            for i in (m.get("auto_indicators") or [])
            if isinstance(i, dict) and isinstance(i.get("score"), int)
        )
        L.append(f"  MACRO: auto_score {m.get('auto_score')} — {m.get('bias')}"
                 + (f"\n    drivers: {inds}" if inds else ""))

    flow = []
    opts = pack.get("options")
    row = (opts[0] if isinstance(opts, list) and opts else opts) or {}
    if row and row.get("spot"):
        gex = row.get("net_gex_usd_per_1pct")
        # opt.py's vocabulary is positive/negative/flat — matching on long/short
        # silently rendered every negative-gamma tape as "no strong dealer effect".
        gsign = row.get("gex_sign")
        # Dealer gamma is the single most actionable non-price block for short-dated
        # trades: below the put wall in negative gamma, hedging AMPLIFIES the move.
        reading = ("dealer hedging AMPLIFIES moves — trends extend, and losing the put"
                   " wall accelerates the downside" if gsign == "negative"
                   else "dealer hedging DAMPENS moves — expect pinning toward the walls"
                   if gsign == "positive" else "no strong dealer effect")
        gtxt = f"${gex / 1e9:.2f}bn per 1%" if isinstance(gex, (int, float)) else str(gex)
        spot = row.get("spot")
        flow.append(f"  DEALER GAMMA ({t}, spot {spot:.2f}): net GEX {gtxt}"
                    if isinstance(spot, (int, float)) else
                    f"  DEALER GAMMA ({t}, spot {spot}): net GEX {gtxt}")
        flow[-1] += (f" — {gsign} gamma: {reading}. Call wall {row.get('call_wall')},"
                     f" put wall {row.get('put_wall')}, P/C OI {row.get('pc_oi'):.2f},"
                     f" P/C vol {row.get('pc_vol'):.2f}"
                     if isinstance(row.get("pc_oi"), (int, float))
                     and isinstance(row.get("pc_vol"), (int, float)) else
                     f" — {gsign} gamma: {reading}. Call wall {row.get('call_wall')},"
                     f" put wall {row.get('put_wall')}")
        # Where price sits relative to the walls is the actionable part, not the sign.
        if isinstance(spot, (int, float)) and isinstance(row.get("put_wall"), (int, float)):
            if spot < row["put_wall"]:
                flow.append(f"    ^ spot {spot:.2f} is BELOW the put wall {row['put_wall']}"
                            + (" in negative gamma — the configuration where selling begets"
                               " selling. Treat dip-buying as counter-flow."
                               if gsign == "negative" else "."))
            elif isinstance(row.get("call_wall"), (int, float)) and spot > row["call_wall"]:
                flow.append(f"    ^ spot {spot:.2f} is ABOVE the call wall {row['call_wall']}.")
    sm = pack.get("smart") or {}
    eq = (sm.get("equity_fng") or {}) if isinstance(sm, dict) else {}
    if eq.get("score") is not None:
        comps = eq.get("components") or {}
        cstr = " · ".join(f"{k} {v.get('score'):.0f}" for k, v in comps.items()
                          if isinstance(v, dict) and v.get("score") is not None)
        flow.append(f"  SENTIMENT (contrarian): equity Fear&Greed {eq.get('score'):.0f}"
                    f" ({eq.get('rating')}), week ago {eq.get('week_ago'):.0f}"
                    + (f"\n    components: {cstr}" if cstr else "")
                    + "\n    Extremes are contrarian: <25 = fear (bullish tilt),"
                      " >75 = greed (bearish tilt). BREADTH is the honest one —"
                      " it says how many names actually participate.")
    if flow:
        L += ["", "[D] FLOW & POSITIONING — what dealers and the crowd are actually"
                  " positioned for. Independent of both price history and news.", ""] + flow

    ev = []
    cat = pack.get("catalysts") or {}
    if cat:
        ev.append("  EVENT GATE: " + json.dumps(cat, ensure_ascii=False)[:400])
    e = pack.get("earnings")
    if e:
        ev.append("  EARNINGS GATE: " + json.dumps(e, ensure_ascii=False)[:300])
    p = (pack.get("poly") or {}).get("gate")
    if p:
        ev.append("  CROWD ODDS (Polymarket, forward-looking): "
                  + " · ".join(f"{k}={v['p']}%" for k, v in p.items()))
    if ev:
        L += ["", "[E] EVENTS & CALENDAR — the clock. A binary print inside the horizon"
                  " outranks any setup in blocks [A]-[D].", ""] + ev

    own = []
    if pack.get("lessons"):
        own.append("  " + pack["lessons"].replace("\n", "\n  "))
    s = pack.get("stats")
    if s and s.get("total"):
        n = s["total"]
        rows = []
        for dim in ("by_action", "by_source"):
            for k, b in (s.get(dim) or {}).items():
                if not b.get("n"):
                    continue
                npos = b["n"] - b.get("flat", 0)
                rr = f", avg {b['ret'] / npos:+.1f}%" if npos else ""
                rows.append(f"{k}: {b['right']}/{b['n']} right{rr}")
        rule = ("weight the analysts by this track record — it is statistically meaningful"
                if n >= 30 else
                f"sample too small (n={n} < 30) — keep analyst weights EQUAL; use this only "
                "as a humility check")
        own.append(f"  DESK CALIBRATION ({n} graded calls at a fixed 5-session horizon,"
                   f" direction-adjusted; {rule}): " + " · ".join(rows[:10]))
        own.append("  ^ If this desk's hit-rate is near 50% and its alpha is negative, that is"
                   " the base rate you are arguing against. Demand evidence from 2+ blocks"
                   " before claiming an edge, and size the conviction accordingly.")
    if own:
        L += ["", "[F] THIS DESK'S OWN TRACK RECORD — graded against realized prices.", ""] + own
    return "\n".join(L)


def _split_spec(spec: str | None):
    """'engine[:model]' → (engine, model). Split on the FIRST colon only —
    model slugs may themselves contain ':' (e.g. openrouter '…:free')."""
    if not spec:
        return None, None
    eng, _, mdl = spec.partition(":")
    return (eng or None), (mdl or None)


def _pick_engines(bull: str | None, bear: str | None, judge: str | None):
    """Each role spec is 'engine[:model]'. An unknown/missing engine falls back
    to the auto-pick (and drops its model override — it belonged to that engine).
    Returns three (engine, model|None) pairs."""
    avail = [e["id"] for e in llm.engines() if e.get("ok")]
    if not avail:
        raise RuntimeError("no LLM engine configured (GEMINI_API_KEY / OPENROUTER_API_KEY / claude CLI)")
    b, bm = _split_spec(bull)
    r, rm = _split_spec(bear)
    j, jm = _split_spec(judge)
    if b not in avail:
        b, bm = avail[0], None
    # perspective diversity: bear takes a DIFFERENT engine when one exists
    if r not in avail:
        others = [e for e in avail if e != b]
        r, rm = (others[0] if others else b), None
    if j not in avail:
        j, jm = ("claude" if "claude" in avail else avail[0]), None
    return (b, bm), (r, rm), (j, jm)


ZH_NOTE = ("\nLANGUAGE: write every free-text field (strongest_point, attack_on_bull, "
           "rationale, weakest_link, entry, risks) in fluent Simplified Chinese (简体中文). "
           "Keep tickers, prices and the JSON keys/enums (verdict etc.) exactly as-is.")


def run_debate(ticker: str, dte: int, market: str,
               bull_eng: str | None, bear_eng: str | None, judge_eng: str | None,
               lang: str = "en") -> dict:
    t = ticker.upper()
    t0 = time.time()
    pack = build_pack(t, dte, market)
    ev = _pack_text(t, pack)
    (b_eng, b_mdl), (r_eng, r_mdl), (j_eng, j_mdl) = _pick_engines(bull_eng, bear_eng, judge_eng)
    zh = ZH_NOTE if lang == "zh" else ""

    base = (f"{ev}\n\nYou are one analyst on a two-sided research desk for {t}. "
            "Argue ONLY from the evidence pack above — no outside facts. "
            "Short-term swing horizon (days to ~4 weeks). Educational only." + zh)

    def tag(meta: dict) -> str:
        return f"{meta.get('engine')}:{meta.get('model')}"

    bull, bmeta = llm.generate_json(base + "\n\nROLE: BULL. Make the strongest honest LONG case.",
                                    BULL_SCHEMA, engine=b_eng, model=b_mdl)
    bear, rmeta = llm.generate_json(
        base + "\n\nROLE: BEAR. Make the strongest honest SHORT/avoid case. "
               f"The bull's strongest point was: \"{bull.get('strongest_point', '')}\" — "
               "you MUST directly engage and attack it in `attack_on_bull`.",
        BEAR_SCHEMA, engine=r_eng, model=r_mdl)

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
        "(5) COUNT SOURCES, NOT SIGNALS — list in `blocks_supporting` which evidence blocks "
        "[A]-[F] actually back your verdict. Four agreeing items inside block [A] are ONE "
        "signal (all are transforms of the same close series), not four; a verdict resting "
        "on a single block cannot exceed 50 confidence. Independent corroboration means two "
        "different letters. (6) DELIVER A PLAYBOOK, NOT A RATING — a verdict nobody can act "
        "on is worthless. `trigger` must be mechanically checkable on a chart (a level "
        "crossed, reclaimed, lost, or held on a retest), never a vibe like 'if sentiment "
        "improves'. `instrument` must name the vehicle and its leverage, preferring the "
        "unleveraged expression when the horizon is long enough for daily-reset decay to "
        "bite. `inverse_scenario` is the trade that becomes right if the invalidation "
        "breaks — plan for being wrong, do not merely stop out. "
        "Educational only — not financial advice." + zh)
    verdict, jmeta = llm.generate_json(judge_prompt, JUDGE_SCHEMA, engine=j_eng, model=j_mdl)

    price = (pack.get("decide") or {}).get("price")
    return {
        "ticker": t, "price": price, "verdict": verdict.get("verdict"),
        "confidence": verdict.get("confidence"), "entry": verdict.get("entry"),
        "invalidation": verdict.get("invalidation"), "time_stop_days": verdict.get("time_stop_days"),
        "rationale": verdict.get("rationale"), "weakest_link": verdict.get("weakest_link"),
        "blocks_supporting": verdict.get("blocks_supporting"),
        "trigger": verdict.get("trigger"), "instrument": verdict.get("instrument"),
        "targets": verdict.get("targets"), "scale_plan": verdict.get("scale_plan"),
        "inverse_scenario": verdict.get("inverse_scenario"),
        "event_risk": verdict.get("event_risk"),
        "bull": bull, "bear": bear,
        "engines": {"bull": tag(bmeta), "bear": tag(rmeta), "judge": tag(jmeta)},
        "analysts": _analyst_tilts(pack),
        "elapsed_s": round(time.time() - t0, 1),
    }


def _analyst_tilts(pack: dict) -> dict:
    """Each analyst's stance AT decision time — journaled with the verdict so
    `ot reflect` can eventually grade analysts individually (F4)."""
    out: dict = {}
    d = pack.get("decide") or {}
    if d.get("ticker"):
        side = ((d.get("plan") or {}).get("side") or "watch").lower()
        out["engine"] = {"long": "bull", "short": "bear"}.get(side, "flat")
    q = pack.get("quant") or {}
    if isinstance(q.get("p_up"), (int, float)):
        pu, oos = q["p_up"], q.get("oos_hit_rate")
        tilt = "bull" if pu >= 55 else "bear" if pu <= 45 else "flat"
        out["quant"] = {"tilt": tilt, "p_up": pu, "oos": oos}
    fc = pack.get("forecast") or {}
    if fc.get("point_end") and fc.get("last"):
        drift = (fc["point_end"] / fc["last"] - 1) * 100
        out["timesfm"] = {"tilt": "bull" if drift > 0.5 else "bear" if drift < -0.5 else "flat",
                          "drift_pct": round(drift, 2)}
    return out


def render_text(r: dict) -> str:
    tone = {"STRONG_BUY": "++", "BUY": "+", "HOLD": "·", "SELL": "-", "STRONG_SELL": "--"}
    px = r.get("price")
    head = f"ot debate — {r['ticker']}  (last ${px:.2f})" if isinstance(px, (int, float)) \
        else f"ot debate — {r['ticker']}  (last ${px})"
    blocks = r.get("blocks_supporting") or []
    src = (f"  sources   {' + '.join(str(b) for b in blocks)}"
           + ("  ← single block: one signal, not corroboration" if len(blocks) == 1 else "")
           ) if blocks else None
    L = [head,
         "",
         f"  VERDICT   {r['verdict']} [{tone.get(r['verdict'], '?')}]  ·  confidence {r['confidence']}/100"]
    if src:
        L.append(src)
    L += [f"  entry     {r['entry']}",
          f"  invalid.  {r['invalidation']}  ·  time stop {r['time_stop_days']}d"]
    # The playbook — the part you can actually act on without re-reading the thesis.
    for label, key in (("trigger", "trigger"), ("vehicle", "instrument"),
                       ("targets", "targets"), ("scaling", "scale_plan"),
                       ("if wrong", "inverse_scenario"), ("event", "event_risk")):
        v = r.get(key)
        if not v:
            continue
        if isinstance(v, list):
            v = " · ".join(f"{x:g}" if isinstance(x, (int, float)) else str(x) for x in v)
        L.append(f"  {label:<9} {v}")
    L += ["",
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
    Re-runs the same day skip the append — one graded DEBATE call per name per
    day. The check must be debate-specific: the daily pipeline also journals
    plain decide reads under the same ticker-date id, and matching on the bare
    id silently swallowed every debate verdict on email days."""
    from datetime import date
    today = date.today().isoformat()
    jf = ROOT / "data/journal/decisions.jsonl"
    if jf.exists():
        for line in jf.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if (d.get("ticker") == r["ticker"] and str(d.get("date")) == today
                    and (d.get("source") == "debate"
                         or (d.get("source") == "manual"
                             and d.get("time_stop_days") is not None))):
                return
    action = {"STRONG_BUY": "CALL", "BUY": "CALL",
              "SELL": "PUT", "STRONG_SELL": "PUT"}.get(r["verdict"], "NO-ACTION")
    args = [sys.executable, str(ROOT / "tools/reflect/reflect.py"), "log",
            "--ticker", r["ticker"], "--action", action, "--source", "debate",
            "--thesis", (r.get("rationale") or "")[:200]]
    if r.get("confidence") is not None:
        args += ["--conviction", str(r["confidence"])]
    if r.get("price") is not None:
        args += ["--price", str(r["price"])]
    if r.get("invalidation") is not None:
        args += ["--invalidation", str(r["invalidation"])]
    if r.get("time_stop_days") is not None:
        args += ["--time-stop", str(r["time_stop_days"])]
    if r.get("analysts"):
        args += ["--analysts", json.dumps(r["analysts"], ensure_ascii=False)]
    subprocess.run(args, capture_output=True, text=True, timeout=15, cwd=str(ROOT),
                   stdin=subprocess.DEVNULL)


def main(argv=None):
    p = argparse.ArgumentParser(prog="debate",
                                description="bull/bear/judge research desk (3 LLM calls, deterministic pack)")
    p.add_argument("ticker")
    p.add_argument("--dte", type=int, default=5)
    p.add_argument("--market", choices=["US", "A", "HK"], default="US")
    p.add_argument("--bull", help="engine[:model] for the bull (e.g. gemini, openrouter:z-ai/glm-5.2)")
    p.add_argument("--bear", help="engine[:model] for the bear")
    p.add_argument("--judge", help="engine[:model] for the judge (default: claude if available)")
    p.add_argument("--log", action="store_true", help="journal the verdict via ot reflect")
    p.add_argument("--lang", choices=["en", "zh"], default="en",
                   help="language for the free-text fields (zh = 简体中文)")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)

    try:
        r = run_debate(a.ticker, a.dte, a.market, a.bull, a.bear, a.judge, a.lang)
    except Exception as e:  # noqa: BLE001
        print(f"debate: {e}", file=sys.stderr)
        return 1
    if a.log:
        _journal(r)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.format == "json" else render_text(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
