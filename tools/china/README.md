# China A-share quotes (`ot cn`)

Optional A-share + Hong Kong (沪深 / A股 / 港股) data layer via **Eastmoney's public `push2`
quote API** — no API key, no login, stdlib + curl only (no `akshare`/`tushare` dependency).

```bash
ot cn                       # Shanghai Composite (default)
ot cn 600519 002594         # Kweichow Moutai (SH), BYD (SZ)
ot cn shcomp csi300 chinext # index aliases
ot cn sh000001 sz399001     # explicit exchange prefix
ot cn hk00700 09988         # Hong Kong (Tencent, Alibaba)
ot cn 600519 --format json  # machine-readable
```

**Code resolution** — Eastmoney `secid = <market>.<code>` (market `1`=Shanghai, `0`=Shenzhen):

| Input | Resolves to | Notes |
|-------|-------------|-------|
| `shcomp` / `上证` / `zs000001` | `1.000001` | Shanghai Composite **index** |
| `csi300` / `沪深300` | `1.000300` | CSI 300 |
| `chinext` / `创业板` | `0.399006` | ChiNext |
| `star50` / `科创50` | `1.000688` | STAR 50 |
| `600519` (6/5/688…) | `1.600519` | Shanghai-listed |
| `002594` (0/3…) | `0.002594` | Shenzhen-listed |
| `sh000001` / `sz399001` | `1.000001` / `0.399001` | explicit prefix |
| `hk00700` / `09988` (5-digit) | `116.00700` / `116.09988` | Hong Kong (HKEX, market `116`, HKD) |

> ⚠️ Bare `000001` resolves to **Ping An Bank** (SZ stock), *not* the index — use
> `shcomp` / `sh000001` / `zs000001` for the Shanghai Composite index.

Fields returned: `last`, `prev_close`, `open/high/low`, `change`, `pct` (CNY). Quotes are
delayed. **Educational only — not financial advice.**

This is the data foundation for the (optional, roadmap) **A-share portfolio review** and
**multi-user** features — see `RELEASE_NOTES.md` / `ROADMAP.md`.
