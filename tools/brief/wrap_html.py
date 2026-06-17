#!/usr/bin/env python3
"""
wrap_html.py — turn Claude's analysis into a good-looking, email-safe HTML brief.

The daily email used to send Claude's plain prose. This renders a styled,
Outlook-friendly HTML email instead: it takes an HTML *fragment* from Claude
(semantic tags only), inlines email-safe CSS onto every element (because Outlook
ignores <head> styles), and wraps it in a branded container. It also emits a
clean plain-text alternative on stdout for the multipart/alternative text part.

    printf '%s' "$CLAUDE_HTML" | python3 wrap_html.py --out /tmp/email.html --date "Tue Jun 16, 2026"
    printf '%s' "$RAW_DATA"    | python3 wrap_html.py --raw --note "data pack" --out /tmp/email.html

stdlib only (argparse + html.parser). Educational only — not financial advice.
"""
import argparse
import html as _html
import sys
from html.parser import HTMLParser

# Inline style per tag (source of truth — survives Outlook, Gmail, Apple Mail).
BASE = {
    "h1": "margin:18px 0 8px;font-size:17px;color:#0f172a;font-weight:700;",
    "h2": "margin:20px 0 6px;font-size:14px;color:#0f172a;font-weight:600;"
          "border-left:3px solid #2563eb;padding-left:9px;text-transform:uppercase;letter-spacing:.4px;",
    "h3": "margin:14px 0 4px;font-size:13px;color:#334155;font-weight:600;",
    "p":  "margin:8px 0;font-size:13.5px;line-height:1.6;color:#1f2937;",
    "ul": "margin:8px 0;padding-left:20px;",
    "ol": "margin:8px 0;padding-left:20px;",
    "li": "margin:5px 0;font-size:13.5px;line-height:1.55;color:#1f2937;",
    "table": "border-collapse:collapse;width:100%;margin:12px 0;font-size:12.5px;",
    "th": "text-align:left;background:#f1f5f9;color:#0f172a;padding:7px 9px;"
          "border-bottom:2px solid #cbd5e1;font-weight:600;white-space:nowrap;",
    "td": "padding:7px 9px;border-bottom:1px solid #e8edf3;color:#1f2937;vertical-align:top;",
    "strong": "color:#0f172a;",
    "b": "color:#0f172a;",
    "a": "color:#2563eb;text-decoration:none;",
    "pre": "background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:11px;"
           "font-size:11.5px;line-height:1.45;white-space:pre-wrap;color:#334155;"
           "font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-x:auto;",
    "code": "font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;",
    "em": "color:#475569;",
    "hr": "border:0;border-top:1px solid #e2e8f0;margin:16px 0;",
}
# class-specific overrides (key = "tag.class")
CLASS = {
    "p.regime": "margin:0 0 14px;padding:13px 15px;background:#0f172a;color:#f8fafc;"
                "border-radius:7px;font-size:14px;line-height:1.55;",
    "p.disclaimer": "margin:16px 0 0;font-size:11px;color:#94a3b8;font-style:italic;",
    "span.up": "color:#15803d;font-weight:600;",
    "span.down": "color:#b91c1c;font-weight:600;",
    "span.flat": "color:#64748b;font-weight:600;",
}
# Inside a dark callout (p.regime) the light background is gone, so nested inline
# emphasis must switch to light/high-contrast colors — otherwise a dark <strong>
# renders navy-on-navy and vanishes (the "buried text" bug).
REGIME_INLINE = {
    "strong": "color:#ffffff;font-weight:700;",
    "b": "color:#ffffff;font-weight:700;",
    "em": "color:#cbd5e1;font-style:italic;",
    "code": "color:#e2e8f0;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;",
    "a": "color:#93c5fd;text-decoration:underline;",
    "span.up": "color:#4ade80;font-weight:600;",
    "span.down": "color:#fca5a5;font-weight:600;",
    "span.flat": "color:#cbd5e1;font-weight:600;",
}
DROP = {"html", "head", "body", "meta", "title", "!doctype", "link"}   # unwrap if Claude adds them
DROP_TREE = {"style", "script"}                                          # drop tag + contents
BLOCK = {"p", "h1", "h2", "h3", "li", "tr", "pre", "ul", "ol", "table", "div", "hr"}
VOID = {"br", "hr", "img", "wbr", "col", "area", "input"}                # emit, but never open a context


def _clean_fragment(s):
    """Strip code fences / any preamble before the first tag."""
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    i = s.find("<")
    return s[i:].strip() if i > 0 else s


class Inliner(HTMLParser):
    """Re-emit HTML with inline styles injected onto known tags.

    Tracks a 'dark callout' context via a stack: inside <p class="regime"> the
    background is dark navy, so nested inline emphasis (strong/em/span/code/a)
    switches to light colors via REGIME_INLINE — else dark text vanishes on it.
    """
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self._skip = 0
        self._dark = []                       # stack: are we inside a dark callout?

    def _style_for(self, tag, attrs_d, dark):
        classes = (attrs_d.get("class") or "").split()
        if dark:                              # dark callout -> light/high-contrast overrides
            for c in classes:
                if f"{tag}.{c}" in REGIME_INLINE:
                    return REGIME_INLINE[f"{tag}.{c}"]
            if tag in REGIME_INLINE:
                return REGIME_INLINE[tag]
        for c in classes:
            if f"{tag}.{c}" in CLASS:
                return CLASS[f"{tag}.{c}"]
        return BASE.get(tag, "")

    def handle_starttag(self, tag, attrs):
        if tag in DROP_TREE:
            self._skip += 1
            return
        if tag in DROP:
            return
        attrs_d = {k: (v or "") for k, v in attrs}
        classes = (attrs_d.get("class") or "").split()
        dark = self._dark[-1] if self._dark else False
        self._emit(tag, attrs_d, dark, selfclose=False)
        if tag not in VOID:                   # void tags hold no children -> no context
            self._dark.append(dark or (tag == "p" and "regime" in classes))

    def handle_startendtag(self, tag, attrs):
        if tag in DROP or tag in DROP_TREE:
            return
        attrs_d = {k: (v or "") for k, v in attrs}
        dark = self._dark[-1] if self._dark else False
        self._emit(tag, attrs_d, dark, selfclose=True)

    def _emit(self, tag, attrs_d, dark, selfclose):
        style = self._style_for(tag, attrs_d, dark)
        if style:
            existing = attrs_d.get("style", "").strip().rstrip(";")
            attrs_d["style"] = (existing + ";" + style) if existing else style
        attrs_d.pop("class", None)            # folded into inline style
        parts = [tag]
        for k, v in attrs_d.items():
            parts.append(f'{k}="{_html.escape(v, quote=True)}"' if v != "" else k)
        self.out.append("<" + " ".join(parts) + (" />" if selfclose else ">"))

    def handle_endtag(self, tag):
        if tag in DROP_TREE:
            self._skip = max(0, self._skip - 1)
            return
        if tag in DROP or tag in VOID:
            return
        if self._dark:
            self._dark.pop()
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self._skip:
            self.out.append(data)

    def handle_entityref(self, name):
        if not self._skip:
            self.out.append(f"&{name};")

    def handle_charref(self, name):
        if not self._skip:
            self.out.append(f"&#{name};")

    def result(self):
        return "".join(self.out)


class Texter(HTMLParser):
    """Extract a readable plain-text version for the multipart text part."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.buf = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_TREE:
            self._skip += 1
        elif tag in ("th", "td") and self.buf and not self.buf[-1].endswith(("\n", " ")):
            self.buf.append("  ")

    def handle_endtag(self, tag):
        if tag in DROP_TREE:
            self._skip = max(0, self._skip - 1)
        elif tag in BLOCK:
            self.buf.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.buf.append(data)

    def text(self):
        import re
        t = "".join(self.buf)
        t = re.sub(r"[ \t]+\n", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip()


SHELL = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"></head>
<body style="margin:0;padding:0;background:#eef2f7;-webkit-text-size-adjust:100%;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f7;">
<tr><td align="center" style="padding:18px 10px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:640px;max-width:640px;background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(15,23,42,.08);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<tr><td style="background:#0f172a;padding:15px 22px;">
<div style="color:#ffffff;font-size:16px;font-weight:700;letter-spacing:.2px;">OpenTrading&nbsp;<span style="color:#60a5fa;font-weight:600;">· Pre-Market Read</span></div>
<div style="color:#94a3b8;font-size:12px;margin-top:3px;">{date}</div>
</td></tr>
<tr><td style="padding:16px 22px 20px;">
{body}
</td></tr>
<tr><td style="background:#f8fafc;padding:12px 22px;border-top:1px solid #e2e8f0;">
<div style="color:#94a3b8;font-size:11px;line-height:1.5;">Generated by OpenTrading — macro-first, risk-first. Sources: FinancialJuice (24h news), gov macro, CNN/crypto Fear&amp;Greed, CBOE option chains, Yahoo quotes, Coinbase BTC. <strong style="color:#64748b;">Educational only — not financial advice.</strong></div>
</td></tr>
</table></td></tr></table></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="path to write the full HTML email")
    ap.add_argument("--date", default="", help="date string for the header")
    ap.add_argument("--raw", action="store_true", help="treat stdin as plain text -> <pre>")
    ap.add_argument("--note", default="", help="banner note (used with --raw)")
    a = ap.parse_args()

    src = sys.stdin.read()
    if a.raw:
        note = a.note or "raw data pack"
        frag = (f'<p class="regime"><strong>{_html.escape(note)}</strong></p>'
                f'<pre>{_html.escape(src)}</pre>')
    else:
        frag = _clean_fragment(src)
        inl = Inliner(); inl.feed(frag); inl.close()
        frag = inl.result()

    full = SHELL.format(date=_html.escape(a.date), body=frag)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(full)

    tx = Texter(); tx.feed(frag); tx.close()
    sys.stdout.write(tx.text() + "\n")


if __name__ == "__main__":
    main()
