#!/usr/bin/env python3
"""
symbols.py — map a roster code + market to Yahoo Finance's ticker conventions.

Yahoo carries A-shares and Hong Kong names alongside US, but with suffixes:

    market   example code        Yahoo symbol     rule
    ------   -----------------   --------------   ------------------------------
    US       AAPL, ^VIX          AAPL, ^VIX       pass through
    A (SH)   688008, 600519      688008.SS        Shanghai: 6-digit code starts 6
    A (SZ)   300394, 000538      300394.SZ        Shenzhen: starts 0 / 2 / 3
    HK       09988, 00883        9988.HK, 0883.HK 4-digit, leading zeros normalized

Centralizing here (the TradingAgents `dataflows/symbol_utils.py` pattern) means
every Yahoo call resolves the same way — A/HK support is a table, not new deps.
Verified 2026-06-17: 688008.SS / 300394.SZ / 9988.HK / 0883.HK all return OHLC.

Stdlib only. Educational only — not financial advice.
"""
import re

_CCY = {"US": "USD", "A": "CNY", "HK": "HKD"}
_SYM = {"USD": "$", "CNY": "¥", "HKD": "HK$"}
_YAHOO_SUFFIX = (".SS", ".SZ", ".HK", "=X", "=F", "-USD")


def to_yahoo(code, market="US"):
    """Resolve a roster code (+ its market) to a Yahoo Finance symbol."""
    code = str(code).strip().upper()
    if code.startswith("^") or code.endswith(_YAHOO_SUFFIX):
        return code                                   # already a Yahoo symbol
    m = (market or "US").upper()
    digits = re.sub(r"[^0-9]", "", code)
    if m == "HK" and digits:
        return f"{int(digits):04d}.HK"                # 09988 -> 9988.HK, 00883 -> 0883.HK
    if m == "A" and digits:
        return digits + (".SS" if digits.startswith("6") else ".SZ")
    return code                                       # US / unknown -> pass through


def currency(market):
    return _CCY.get((market or "US").upper(), "USD")


def ccy_symbol(market):
    return _SYM.get(currency(market), "$")
