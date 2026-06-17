#!/usr/bin/env python3
"""
fj.py — FinancialJuice news CLI for OpenTrading.

Fetches the *public* FinancialJuice RSS squawk feed (no login required),
filters by timeframe / keyword / ticker, tags each headline with a category,
and prints to stdout or stores a date-stamped markdown log under data/news-log/.

This replaces the old "drive Chrome to scrape the site" approach: the feed at
https://www.financialjuice.com/feed.ashx?xy=rss is a clean, real-time RSS feed
that works with no account.

Stdlib only — no `pip install` needed (Python 3.9+).

Examples:
    python3 fj.py fetch                       # most recent headlines
    python3 fj.py fetch --window premarket    # 04:00-09:30 ET today
    python3 fj.py fetch --minutes 60          # last hour
    python3 fj.py fetch --ticker NVDA         # only NVDA-relevant headlines
    python3 fj.py fetch --since 13:00 --format json
    python3 fj.py store  --window open        # save 09:30-10:30 ET to data/news-log/
    python3 fj.py fetch  --feeds financialjuice,cnbc        # aggregate CNBC + FinancialJuice
    python3 fj.py fetch  --feeds yahoo --tickers AAPL,MSTR  # Yahoo per-ticker headlines
    python3 fj.py digest --days 7 --feeds financialjuice,cnbc --source cnbc
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from zoneinfo import ZoneInfo

    ET_TZ = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - zoneinfo missing/no tzdata
    ET_TZ = None

# Sort sentinel for items with no parsed timestamp (kept tz-consistent with ET_TZ).
_MIN_DT = datetime.min.replace(tzinfo=ET_TZ) if ET_TZ else datetime.min

# Default public squawk feed; override with OT_FJ_FEED_URL to point at a personalized PRO
# feed (the public feed is provider-agnostic — see tools/financialjuice/README.md).
FEED_URL = os.environ.get("OT_FJ_FEED_URL", "https://www.financialjuice.com/feed.ashx?xy=rss")
USER_AGENT = "Mozilla/5.0 (OpenTrading fj-cli; +https://github.com/orangejustin)"

# Multi-source news: FinancialJuice (default) + direct provider RSS. The public FJ feed is
# provider-agnostic, so for per-provider US-stock coverage we pull CNBC sections + Yahoo
# (per-ticker) directly. (Reuters/Bloomberg dropped their free RSS, so they're not included.)
_CNBC = "https://www.cnbc.com/id/{id}/device/rss/rss.html"
SOURCE_FEEDS = {
    "financialjuice": ("FinancialJuice", [FEED_URL]),
    "cnbc": ("CNBC", [_CNBC.format(id=i) for i in
                      ("100003114", "10000664", "15839135", "20910258")]),  # Top·Markets·Earnings·Economy
}
YAHOO_TPL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={t}&region=US&lang=en-US"
DEFAULT_LOG_DIR = Path(__file__).resolve().parents[2] / "data" / "news-log"
TITLE_PREFIX = "FinancialJuice:"

# First match wins; everything else falls through to "Other".
# Needles are matched as whole words (\b...\b) so short acronyms like "rba"
# don't match inside "ba-rba-rism". A trailing "s?" allows optional plurals.
CATEGORY_RULES = [
    ("Fed", ["fomc", "powell", "rate cuts?", "rate hikes?", "interest rates?", "fed",
             "central bank", "hawkish", "dovish", "rate decision", "dot plot",
             "ecb", "boe", "boj", "rba", "rate hold"]),
    ("Macro", ["cpi", "ppi", "pce", "inflation", "gdp", "unemployment", "jobless",
               "payrolls?", "nonfarm", "nfp", "retail sales", "ism", "pmi",
               "consumer confidence", "durable goods", "trade balance", "housing",
               "initial claims", "sentiment", "industrial production"]),
    ("Earnings", ["earnings", "eps", "revenue", "guidance", "results", "dividend",
                  "buybacks?", "downgrades?", "upgrades?", "price target",
                  "profit warning"]),
    ("Geopolitical", ["wars?", "sanctions?", "tariffs?", "russia", "ukraine", "israel",
                      "iran", "opec", "geopolitical", "elections?", "missiles?",
                      "ceasefire", "china", "north korea"]),
    ("Crypto", ["bitcoin", "btc", "ethereum", "ether", "crypto", "stablecoins?",
                "coinbase", "binance"]),
]
CATEGORY_PATTERNS = [
    (label, re.compile(r"\b(?:%s)\b" % "|".join(needles), re.IGNORECASE))
    for label, needles in CATEGORY_RULES
]

# Ticker -> extra alias terms to match in a headline.
TICKER_ALIASES = {
    "NVDA": ["nvidia"],
    "AAPL": ["apple"],
    "MSFT": ["microsoft"],
    "GOOGL": ["google", "alphabet"],
    "GOOG": ["google", "alphabet"],
    "AMZN": ["amazon"],
    "META": ["meta platforms", "facebook", "instagram"],
    "TSLA": ["tesla", "musk"],
    "SPY": ["s&p 500", "s&p500", "spx"],
    "QQQ": ["nasdaq 100", "nasdaq"],
    "BTC": ["bitcoin"],
    "ETH": ["ethereum"],
    # High-beta single names (extend freely; unknown tickers match literally)
    "MSTR": ["microstrategy", "saylor"],          # leveraged BTC proxy
    "ORCL": ["oracle"],                           # AI capex / cloud
    "HOOD": ["robinhood"],                         # crypto + retail flow
    "COIN": ["coinbase"],
    "PLTR": ["palantir"],
    "AMD": ["advanced micro"],
    "SPCX": ["spacex", "starlink", "starship"],   # private — news only, no live quote
}


@dataclass
class Item:
    headline: str
    dt_et: datetime | None
    link: str
    guid: str
    source: str = "FinancialJuice"

    @property
    def time_str(self) -> str:
        return self.dt_et.strftime("%H:%M") if self.dt_et else "--:--"

    @property
    def iso(self) -> str:
        return self.dt_et.isoformat() if self.dt_et else ""

    @property
    def category(self) -> str:
        for label, pattern in CATEGORY_PATTERNS:
            if pattern.search(self.headline):
                return label
        return "Other"


# --------------------------------------------------------------------------- #
# Fetch + parse
# --------------------------------------------------------------------------- #
def _ssl_context(insecure: bool) -> ssl.SSLContext:
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    try:  # macOS Python can't see the system CA store; certifi ships one.
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _curl_fetch(url: str, timeout: int) -> str | None:
    """Last-resort fetch via the system curl (uses the OS trust store)."""
    curl = shutil.which("curl")
    if not curl:
        return None
    try:
        out = subprocess.run(
            [curl, "-sL", "--max-time", str(timeout), "-A", USER_AGENT, url],
            capture_output=True, timeout=timeout + 5,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout.decode("utf-8", errors="replace")
    except Exception:
        return None
    return None


def fetch_raw(url: str, timeout: int = 20, insecure: bool = False) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=_ssl_context(insecure)) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError:
        raise  # 429 / 5xx — let the caller decide on retry/backoff.
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, ssl.SSLError) or "CERTIFICATE" in str(reason).upper():
            text = _curl_fetch(url, timeout)
            if text is not None:
                return text
        raise


def _cache_path(url: str) -> Path:
    digest = hashlib.md5(url.encode("utf-8")).hexdigest()[:10]
    return Path(tempfile.gettempdir()) / f"opentrading-fj-{digest}.xml"


def fetch_feed(url: str, *, insecure: bool, ttl: int, no_cache: bool,
               timeout: int = 20) -> str:
    """Fetch the feed with a short-lived disk cache and 429 backoff.

    The feed rate-limits rapid requests, so repeated agent calls reuse a cached
    copy for `ttl` seconds. On failure we fall back to a stale cache if present.
    """
    cache = _cache_path(url)
    if not no_cache and cache.exists():
        if time.time() - cache.stat().st_mtime < ttl:
            return cache.read_text(encoding="utf-8")

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            text = fetch_raw(url, timeout=timeout, insecure=insecure)
            try:
                cache.write_text(text, encoding="utf-8")
            except OSError:
                pass
            return text
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429 and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            break

    if cache.exists():
        sys.stderr.write(f"[fj] Live fetch failed ({last_exc}); using cached feed "
                         f"from {time.strftime('%H:%M', time.localtime(cache.stat().st_mtime))}.\n")
        return cache.read_text(encoding="utf-8")
    raise last_exc if last_exc else RuntimeError("fetch failed")


def now_et() -> datetime:
    base = datetime.now(ET_TZ) if ET_TZ else datetime.now()
    return base


def parse_feed(xml_text: str) -> list[Item]:
    root = ET.fromstring(xml_text)
    items: list[Item] = []
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        if title.startswith(TITLE_PREFIX):
            title = title[len(TITLE_PREFIX):].strip()
        link = (node.findtext("link") or "").strip()
        guid = (node.findtext("guid") or "").strip()
        pub = node.findtext("pubDate")
        dt_et = None
        if pub:
            try:
                dt = parsedate_to_datetime(pub)
                dt_et = dt.astimezone(ET_TZ) if ET_TZ else dt
            except (TypeError, ValueError):
                dt_et = None
        if title:
            items.append(Item(headline=title, dt_et=dt_et, link=link, guid=guid))
    return items


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
def window_bounds(window: str, now: datetime) -> tuple[datetime | None, datetime | None]:
    """Return (start, end) ET datetimes for a named intraday window."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def at(h: int, m: int) -> datetime:
        return midnight.replace(hour=h, minute=m)

    mapping = {
        "premarket": (at(4, 0), at(9, 30)),
        "open": (at(9, 30), at(10, 30)),
        "today": (at(9, 30), now),
        "afternoon": (at(13, 0), at(16, 0)),
        "afterhours": (at(16, 0), at(20, 0)),
        "session": (at(9, 30), at(16, 0)),
        "all": (None, None),
    }
    if window not in mapping:
        raise SystemExit(f"Unknown window '{window}'. Choose from: {', '.join(mapping)}")
    return mapping[window]


def parse_since(value: str, now: datetime) -> datetime:
    """Parse '13:00' (today ET) or '2026-06-15 13:00' into an ET datetime."""
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%H:%M"):
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if fmt == "%H:%M":
            parsed = now.replace(hour=parsed.hour, minute=parsed.minute,
                                 second=0, microsecond=0)
        elif ET_TZ:
            parsed = parsed.replace(tzinfo=ET_TZ)
        return parsed
    raise SystemExit(f"Could not parse --since '{value}'. Use HH:MM or 'YYYY-MM-DD HH:MM'.")


def ticker_matches(headline: str, ticker: str) -> bool:
    terms = [ticker.lower()] + TICKER_ALIASES.get(ticker.upper(), [])
    low = headline.lower()
    for term in terms:
        if re.search(r"\w", term) and " " not in term and "&" not in term:
            if re.search(rf"\b{re.escape(term)}\b", low):
                return True
        elif term in low:
            return True
    return False


def apply_filters(items: list[Item], args, now: datetime) -> list[Item]:
    start = end = None
    if getattr(args, "days", None) is not None:
        start, end = now - timedelta(days=args.days), now
    elif args.minutes is not None:
        start, end = now - timedelta(minutes=args.minutes), now
    elif args.since:
        start, end = parse_since(args.since, now), now
    elif args.window:
        start, end = window_bounds(args.window, now)

    out = []
    for it in items:
        if start and (it.dt_et is None or it.dt_et < start):
            continue
        if end and it.dt_et is not None and it.dt_et > end:
            continue
        if args.ticker and not ticker_matches(it.headline, args.ticker):
            continue
        if args.grep and not re.search(args.grep, it.headline, re.I):
            continue
        if args.category and it.category.lower() != args.category.lower():
            continue
        if getattr(args, "source", None):
            srcs = [s.strip() for s in args.source.split(",") if s.strip()]
            if srcs:
                pat = re.compile(r"\b(?:%s)\b" % "|".join(re.escape(s) for s in srcs), re.I)
                if not (pat.search(it.headline) or pat.search(getattr(it, "source", "") or "")):
                    continue
        out.append(it)
    if args.limit:
        out = out[: args.limit]
    return out


def describe_window(args) -> str:
    if getattr(args, "days", None) is not None:
        return f"Last {args.days} day(s)"
    if args.minutes is not None:
        return f"Last {args.minutes} min"
    if args.since:
        return f"Since {args.since} ET"
    if args.window and args.window != "all":
        return f"{args.window.capitalize()} window (ET)"
    return "Most recent"


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_table(items: list[Item], args) -> str:
    if not items:
        return "(no headlines matched this filter)"
    sources = sorted({getattr(it, "source", "FinancialJuice") for it in items})
    multi = len(sources) > 1
    tag = "+".join(sources) if multi else (sources[0] if sources else "FinancialJuice")
    head = f"News — {describe_window(args)} — {now_et():%Y-%m-%d %H:%M ET} — {len(items)} headlines [{tag}]"
    lines = [head, "=" * min(len(head), 100)]
    for it in items:
        if multi:
            lines.append(f"{it.time_str:>5}  {(getattr(it, 'source', '') or '')[:4]:<4} "
                         f"{it.category:<11} {it.headline}")
        else:
            lines.append(f"{it.time_str:>5}  {it.category:<13} {it.headline}")
    return "\n".join(lines)


def render_json(items: list[Item], args) -> str:
    payload = {
        "source": "financialjuice",
        "fetched_at_et": now_et().isoformat(),
        "filter": describe_window(args),
        "count": len(items),
        "items": [
            {
                "time_et": it.time_str,
                "iso": it.iso,
                "source": getattr(it, "source", "FinancialJuice"),
                "category": it.category,
                "headline": it.headline,
                "link": it.link,
                "guid": it.guid,
            }
            for it in items
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def render_markdown(items: list[Item], args) -> str:
    now = now_et()
    lines = [
        "# FinancialJuice News Log",
        f"**Date**: {now:%Y-%m-%d}",
        f"**Fetched at**: {now:%H:%M} ET",
        f"**Timeframe**: {describe_window(args)}",
        "",
        "---",
        "",
        "## Headlines (newest first)",
        "",
        "| Time (ET) | Headline | Category |",
        "|-----------|----------|----------|",
    ]
    for it in items:
        safe = it.headline.replace("|", "\\|")
        lines.append(f"| {it.time_str} | {safe} | {it.category} |")
    lines += ["", "---", "", f"## Raw Count: {len(items)} headlines in timeframe"]
    return "\n".join(lines)


RENDERERS = {"table": render_table, "json": render_json, "markdown": render_markdown}


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def _selected_feeds(args) -> list[str]:
    raw = getattr(args, "feeds", None) or os.environ.get("OT_NEWS_FEEDS", "") or "financialjuice"
    return [s.strip().lower() for s in raw.split(",") if s.strip()] or ["financialjuice"]


def _ticker_list(args) -> list[str]:
    raw = getattr(args, "tickers", None) or getattr(args, "ticker", None) or ""
    return [t.strip().upper() for t in raw.replace(" ", ",").split(",") if t.strip()]


def _fetch_one(url, args, label) -> list[Item]:
    """Fetch+parse one RSS url, tag each item with its source. One bad feed never
    kills the rest of an aggregation."""
    try:
        xml = fetch_feed(url, insecure=getattr(args, "insecure", False),
                         ttl=getattr(args, "cache_ttl", 60),
                         no_cache=getattr(args, "no_cache", False))
        items = parse_feed(xml)
        for it in items:
            it.source = label
        return items
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[fj] {label} feed failed: {exc}\n")
        return []


def fetch_source(name, args) -> list[Item]:
    if name == "yahoo":
        tickers = _ticker_list(args)
        if not tickers:
            sys.stderr.write("[fj] yahoo feed needs --tickers (or --ticker); skipped.\n")
            return []
        return _fetch_one(YAHOO_TPL.format(t=",".join(tickers[:20])), args, "Yahoo")
    spec = SOURCE_FEEDS.get(name)
    if not spec:
        sys.stderr.write(f"[fj] unknown feed '{name}' (have: {', '.join(SOURCE_FEEDS)}, yahoo)\n")
        return []
    label, urls = spec
    out: list[Item] = []
    for u in urls:
        out += _fetch_one(u, args, label)
    return out


def load_items(args) -> list[Item]:
    # Offline single-file mode (testing) stays FinancialJuice-only.
    if getattr(args, "file", None):
        try:
            return parse_feed(Path(args.file).read_text(encoding="utf-8"))
        except ET.ParseError as exc:
            sys.exit(f"[fj] Feed did not parse as RSS/XML: {exc}")
    feeds = _selected_feeds(args)
    # Fast path: FinancialJuice only -> keep the original single-feed behavior + errors.
    if feeds == ["financialjuice"]:
        try:
            xml_text = fetch_feed(args.feed_url, insecure=getattr(args, "insecure", False),
                                  ttl=getattr(args, "cache_ttl", 60),
                                  no_cache=getattr(args, "no_cache", False))
        except (urllib.error.URLError, TimeoutError) as exc:
            sys.exit(f"[fj] Could not reach FinancialJuice feed: {exc}\n      Feed: {args.feed_url}")
        try:
            return parse_feed(xml_text)
        except ET.ParseError as exc:
            sys.exit(f"[fj] Feed did not parse as RSS/XML: {exc}")
    # Multi-source: aggregate, tag by source, dedupe, newest-first; tolerate feed failures.
    items: list[Item] = []
    for f in feeds:
        items += fetch_source(f, args)
    items = dedupe_items(items)
    items.sort(key=lambda it: it.dt_et or _MIN_DT, reverse=True)
    return items


def cmd_fetch(args) -> None:
    items = apply_filters(load_items(args), args, now_et())
    print(RENDERERS[args.format](items, args))


def cmd_store(args) -> None:
    items = apply_filters(load_items(args), args, now_et())
    now = now_et()
    out_dir = Path(args.dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{now:%Y-%m-%d_%H-%M}_financialjuice.md"
    path = out_dir / fname
    path.write_text(render_markdown(items, args) + "\n", encoding="utf-8")
    print(f"[fj] Stored {len(items)} headlines -> {path}")
    if not args.quiet:
        print()
        print(render_table(items, args))


# --------------------------------------------------------------------------- #
# Digest — merge the stored archive (data/news-log/) with the live feed so a
# multi-day window works even though the RSS feed only retains ~40 headlines.
# --------------------------------------------------------------------------- #
_ARCHIVE_GLOB = "*_financialjuice.md"
_ROW_RE = re.compile(r"^\|\s*(\d{1,2}:\d{2}|--:--)\s*\|(.*)\|\s*([A-Za-z]+)\s*\|\s*$")
_DATE_RE = re.compile(r"\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})")
_FNAME_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def parse_archive_file(path: Path) -> list[Item]:
    """Reconstruct Items from one stored news-log markdown file (date from the
    file header / filename, HH:MM from each table row). Category is recomputed
    from the headline, so older logs benefit from current rules."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    m = _DATE_RE.search(text) or _FNAME_DATE_RE.match(path.name)
    day = None
    if m:
        try:
            day = datetime.strptime(m.group(1), "%Y-%m-%d")
            if ET_TZ:
                day = day.replace(tzinfo=ET_TZ)
        except ValueError:
            day = None
    items: list[Item] = []
    for line in text.splitlines():
        rm = _ROW_RE.match(line)
        if not rm:
            continue
        hhmm = rm.group(1)
        headline = rm.group(2).strip().replace("\\|", "|")
        if not headline:
            continue
        dt_et = None
        if day is not None and hhmm != "--:--":
            try:
                hh, mm = (int(x) for x in hhmm.split(":"))
                dt_et = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
            except ValueError:
                dt_et = None
        items.append(Item(headline=headline, dt_et=dt_et, link="", guid=""))
    return items


def load_archive_items(dirpath: str, start: datetime | None) -> list[Item]:
    """Parse every stored news-log file (skipping ones whose filename date is
    clearly before `start`) into Items."""
    d = Path(dirpath).expanduser()
    if not d.exists():
        return []
    start_day = (start.date() - timedelta(days=1)) if start else None
    items: list[Item] = []
    for p in sorted(d.glob(_ARCHIVE_GLOB)):
        if start_day:
            fm = _FNAME_DATE_RE.match(p.name)
            if fm:
                try:
                    if datetime.strptime(fm.group(1), "%Y-%m-%d").date() < start_day:
                        continue
                except ValueError:
                    pass
        items.extend(parse_archive_file(p))
    return items


def dedupe_items(items: list[Item]) -> list[Item]:
    """Drop repeated headlines — the same item recurs across archive snapshots.
    Key = (day, HH:MM, normalized headline)."""
    seen: set = set()
    out: list[Item] = []
    for it in items:
        day = it.dt_et.date().isoformat() if it.dt_et else ""
        key = (day, it.time_str, " ".join(it.headline.lower().split()))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def cmd_digest(args) -> None:
    """Combine the stored archive with a live fetch over a window (default 7d)."""
    now = now_et()
    if (getattr(args, "days", None) is None and args.minutes is None
            and not args.since and not args.window):
        args.days = 7  # sensible default for a "weekly" digest
    start = None
    if getattr(args, "days", None) is not None:
        start = now - timedelta(days=args.days)
    elif args.minutes is not None:
        start = now - timedelta(minutes=args.minutes)
    elif args.since:
        start = parse_since(args.since, now)
    elif args.window:
        start, _ = window_bounds(args.window, now)

    items = load_archive_items(args.dir, start)
    n_archive = len(items)
    try:  # live feeds (FJ + any --feeds) are best-effort — never fail the digest if offline
        items += load_items(args)
    except (SystemExit, Exception) as exc:  # noqa: BLE001 — the archive still works offline
        sys.stderr.write(f"[fj] live fetch skipped ({exc}); digest uses the archive only.\n")

    items = dedupe_items(items)
    items.sort(key=lambda it: it.dt_et or _MIN_DT, reverse=True)
    items = apply_filters(items, args, now)
    if not getattr(args, "quiet", False):
        sys.stderr.write(f"[fj] digest: {n_archive} archived rows + live feed -> "
                         f"{len(items)} after {describe_window(args)} filter.\n")
    print(RENDERERS[args.format](items, args))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def add_common_filters(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("filters")
    g.add_argument("--window", choices=["premarket", "open", "today", "afternoon",
                                        "afterhours", "session", "all"],
                   help="Named intraday window (ET).")
    g.add_argument("--minutes", type=int, help="Only headlines from the last N minutes.")
    g.add_argument("--days", type=int,
                   help="Only headlines from the last N days (digest reads the archive for real history).")
    g.add_argument("--since", help="Headlines since HH:MM (today, ET) or 'YYYY-MM-DD HH:MM'.")
    g.add_argument("--ticker", help="Only headlines relevant to this ticker (NVDA, AAPL, ...).")
    g.add_argument("--grep", help="Only headlines matching this regex (case-insensitive).")
    g.add_argument("--category", help="Only this category (Fed, Macro, Earnings, Geopolitical, Crypto, Other).")
    g.add_argument("--source", help="Keep only items whose source or headline matches any of these "
                                    "comma-separated names (e.g. cnbc,yahoo,wsj).")
    g.add_argument("--feeds", help="News sources to aggregate: financialjuice, cnbc, yahoo "
                                   "(comma list; default financialjuice, or $OT_NEWS_FEEDS).")
    g.add_argument("--tickers", help="Comma tickers for the yahoo per-ticker feed (e.g. AAPL,MSTR).")
    g.add_argument("--limit", type=int, default=40, help="Max headlines to show (default 40).")
    g.add_argument("--feed-url", default=FEED_URL, help="Override the RSS feed URL.")
    g.add_argument("--file", help="Read RSS from a local file instead of the network (offline/testing).")
    g.add_argument("--insecure", action="store_true", help="Skip TLS verification (last resort).")
    g.add_argument("--cache-ttl", type=int, default=60,
                   help="Reuse a cached feed for N seconds to avoid rate limits (default 60).")
    g.add_argument("--no-cache", action="store_true", help="Always fetch fresh, ignore the cache.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fj",
        description="FinancialJuice news CLI (public RSS squawk feed).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples:")[-1],
    )
    sub = p.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("fetch", help="Fetch and print headlines.")
    pf.add_argument("--format", choices=list(RENDERERS), default="table")
    add_common_filters(pf)
    pf.set_defaults(func=cmd_fetch)

    ps = sub.add_parser("store", help="Fetch and save a date-stamped markdown log.")
    ps.add_argument("--format", choices=list(RENDERERS), default="markdown",
                    help=argparse.SUPPRESS)
    ps.add_argument("--dir", default=str(DEFAULT_LOG_DIR),
                    help=f"Output dir (default: {DEFAULT_LOG_DIR}).")
    ps.add_argument("--quiet", action="store_true", help="Only print the saved path.")
    add_common_filters(ps)
    ps.set_defaults(func=cmd_store)

    pd = sub.add_parser("digest",
                        help="Multi-day digest: merge the stored archive with the live feed.")
    pd.add_argument("--format", choices=list(RENDERERS), default="table")
    pd.add_argument("--dir", default=str(DEFAULT_LOG_DIR),
                    help=f"News-log archive dir (default: {DEFAULT_LOG_DIR}).")
    pd.add_argument("--quiet", action="store_true", help="Suppress the stderr summary line.")
    add_common_filters(pd)
    pd.set_defaults(func=cmd_digest, limit=200)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
