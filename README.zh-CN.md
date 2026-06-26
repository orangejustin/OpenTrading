# OpenTrading

**简体中文** | [English](README.md)

*本文档为中文版，内容可能略滞后于英文版 [README.md](README.md)（以英文版为准）。*

**开源、本地优先的 Claude 短线交易分析项目** —— 覆盖股票、期权、衍生品与加密货币。它把一套专业的交易 *skill*（宏观优先、风险优先）与一组小巧、零依赖的 *数据 CLI* 结合起来：你可以自己运行这些命令，也可以交给 Claude 来驱动。

> ⚠️ **仅供教育用途，非投资建议。交易涉及重大亏损风险。**

> 📧 **全自动：** 每个交易日早晨，把一份带样式、感知你持仓的盘前简报直接发到你的邮箱
> —— 见 [每日盘前邮件](#每日盘前邮件)。📈 进阶用户还可实时桥接
> **TradingView** —— 见 [可选增强模块](#可选增强模块)。

---

## 快速开始

```bash
git clone https://github.com/orangejustin/OpenTrading
cd OpenTrading
bash install.sh            # 把 `ot` 加入你的 PATH 并跑一次健康检查（无需 key，无需编译）
```

之后一切都是 **一个命令 `ot`**：

```bash
ot                         # 早盘速览：宏观 + 新闻 + 聪明钱 + 期权 + 你的持仓
ot news --window premarket # FinancialJuice 实时头条（公开 RSS —— 无需账号）
ot macro                   # 评分制的盘中宏观面板（无需 API key）
ot options SPY --dte 7     # 看跌/看涨比 + 做市商 gamma（GEX）+ gamma 墙
ot help                    # 所有子命令
```

> 还不想改动 PATH？跳过 `install.sh`，直接原地运行：`bin/ot …`

然后用 **Claude Code**（或 Claude Desktop）打开这个文件夹，直接提问：

- *“给我今早的宏观简报 —— 今天 QQQ 是做 call 还是 put？”*
- *“过去一小时有没有关于 NVDA 的 FinancialJuice 新闻？存下来。”*
- *“NVDA 放量突破 $950，RSI 62，账户 $30k —— 这笔怎么交易？”*

内置的 **short-term-trader** skill 会自动激活，并通过 `ot` 拉取实时数据。

**环境要求：** Python 3.9+（以标准库为主；安装了 `certifi` 就用它做 TLS 校验，否则
自动回退到系统 `curl`）。无需任何 API key，无需付费数据源。

**依赖管理（推荐 uv）：** 推荐用 [`uv`](https://github.com/astral-sh/uv) 管理依赖与
虚拟环境（与 TradingAgents / OpenHands 一致）——`uv sync` 会按 `uv.lock` 安装锁定的依赖，
复现可靠的开发环境；日常运行用 `uv run …`。

**Runner：** 检测到 `uv` 时，`ot` 会自动优先使用它 —— 它运行的是独立 CPython
（PEP 723-ready，便于将来引入依赖，并规避 macOS framework-Python 在 launchd 下的挂起
问题）—— 否则回退到普通的 `python3`。可用 `OT_PYTHON=/path/to/python` 覆盖解释器，用
`OT_NO_UV=1` 强制禁用 uv，用 `ot doctor` 查看当前生效的 runner。

---

## 项目结构

| 组成 | 路径 | 用途 |
|------|------|------|
| **`ot` CLI** | `bin/ot` | **统一入口，前置所有工具**（运行 `ot help`） |
| 安装脚本 | `install.sh` | 把 `ot` 加入 PATH + `ot doctor` 健康检查 |
| 交易 skills | `.claude/skills/` | `short-term-trader`（交易形态/期权/风控）+ `market-report`（融合宏观+新闻+聪明钱+期权的报告） |
| FinancialJuice CLI | `tools/financialjuice/fj.py` | 通过公开 RSS 的实时新闻速报 |
| 宏观 CLI | `tools/macro/macro.py` | SOFR、2Y/10Y、TGA、RRP → 评分式偏向（无需 key） |
| 聪明钱 CLI | `tools/smartmoney/sm.py` | CNN + 加密货币恐惧贪婪指数、BTC 资金费率 —— 逆向情绪 |
| 期权 CLI | `tools/options/opt.py` | 看跌/看涨比 + 做市商 gamma（GEX）+ gamma 墙（CBOE，无需 key） |
| 行情 CLI | `tools/quote/q.py` | 无需 key 的行情，含盘前 + ^VIX（Yahoo）—— IBKR 的替身 |
| 中国 A 股（可选） | `tools/china/cn.py` | 经东方财富的 A 股行情 沪深/A股（无需 key）—— `ot cn` |
| 报告编排器 | `tools/report/report.py` | 把以上全部 + BTC + 你的持仓融合成一份报告 |
| 每日简报 | `tools/brief/daily_brief.py` | 更轻量的每日推送 + macOS 通知 |
| 每日邮件 | `tools/brief/daily_email_claude.sh` + `tools/brief/wrap_html.py` | Claude 撰写、感知持仓的 **HTML** 盘前邮件（SMTP） |
| 项目配置 | `CLAUDE.md`、`.claude/settings.json` | 接入 skills 并预授权相关工具 |
| 持仓清单 | `watchlist.json`（git 忽略） | 你的持仓；驱动所有感知持仓的板块 |
| 数据 | `data/news-log/`、`data/reports/`、`data/briefs/` | 带日期戳的输出（git 忽略） |

---

## FinancialJuice CLI

读取 **公开** 的 FinancialJuice RSS 源（`feed.ashx?xy=rss`）—— 无需登录、无需浏览器
自动化。它会把时间戳转换为美东时间（ET）、标注分类、缓存 60 秒，并在触发限流时自动退避。

```bash
ot news                          # 最新
ot news --window open            # 09:30–10:30 ET
ot news --minutes 60             # 最近一小时
ot news --ticker NVDA            # 仅与该标的相关
ot news --category Fed           # Fed/宏观/财报/...
ot news --json                   # 机器可读
ot news digest --days 7          # 多日摘要（合并已存档案 + 实时）
ot news store --window premarket # -> data/news-log/
```

完整参数说明：[`tools/financialjuice/README.md`](tools/financialjuice/README.md)。

> 公开的 FinancialJuice RSS 是 **来源无关的**（不带 Bloomberg/CNBC/Reuters 标签）。若要
> **按来源覆盖美股**，可 **聚合直连源**：`ot news --feeds financialjuice,cnbc`
> 或 `--feeds yahoo --tickers AAPL,MSTR`（CNBC Top/Markets/Earnings/Economy + Yahoo 按标的，
> 各自带来源标签；用 `--source cnbc` 过滤）。Reuters/Bloomberg 已停掉免费 RSS。
> `OT_FJ_FEED_URL` 也可指向你个人的 PRO 源。

## 宏观面板 CLI

自动抓取无需 API key 的利率/流动性指标，并按 skill 中 `macro-dashboard.md` 设定的阈值
逐项评分：

```
INTRADAY MACRO DASHBOARD — auto-fetched (no-key public data)
  SOFR            3.60%  [+ bull]  down vs 3.63%
  TGA             $801B  [+ bull]  bull<900 / bear>925
  2Y Yield        4.09%  [+ bull]  bull<4.18 / bear>4.30
  10Y Yield       4.48%  [  neut]  bull<4.35 / bear>4.50
  AUTO SCORE: +3  (from 4 indicators)  ->  LEAN CALLS (bullish tilt)
```

用 `ot macro`（或 `ot macro --json`）运行。它还会打印两个需要手动跟进的指标
（Polymarket 上的降息概率、PCE nowcast）及其 URL，供你手动纳入判断。详见：
[`tools/macro/README.md`](tools/macro/README.md)。

---

## 市场报告（完整融合）

一个命令即可把 **宏观 + 聪明钱仓位 + 期权/gamma + 行情 + BTC + 新闻 + 你的持仓**
汇成一份带自动市场状态（regime）的数据包：

```bash
ot                 # markdown 数据包 -> stdout（这是默认命令）
ot report --save   # 同时 -> data/reports/<date>.md
ot report --notify # + macOS 通知（定时任务会用到）
```

随后向 Claude 索要 **“the market report”**（或说 *“monday report”*）—— `market-report`
skill 会基于该数据包进行推理：跨资产综合、情绪/信用 **背离**、做市商 gamma 的钉住/趋势
解读，以及逐个持仓的操作计划。用 `ot schedule` 设置定时任务（注意 `tools/brief/README.md`
中关于 macOS TCC 的提示）。

---

## 这套 skill

`.claude/skills/short-term-trader/` 是一个标准的 Claude skill。它的工作流：

1. **每日宏观简报与看跌/看涨偏向** —— 8 指标评分面板 → CALLS / PUTS / NO TRADE
2. **FinancialJuice 新闻** —— 抓取 / 过滤 / 存档 / 对某标的做新闻影响分析
3. **交易形态分析** —— 逻辑、入场/止损/目标、盈亏比（R:R）、仓位大小
4. **期权分析** —— 希腊字母、IV 排名、策略选择、财报博弈
5. **加密货币交易分析** —— 资金费率、杠杆、考虑爆仓的仓位测算
6. **交易日志与盈亏复盘** —— R 倍数跟踪、行为模式
7. **策略回测** —— 指标 + 过拟合检查
8. **持仓复盘与仓位管理** —— 多空研判台 → 具体的 +/- 股数建议，并设集中度与因子上限

它强制执行的操作原则：**宏观优先 → 形态其次 → 仓位第三**、**先风险后机会**、
**新闻只有放在背景下才有意义**，并在每一份分析上都附带“仅供教育、非投资建议”的免责声明。

---

## 每日盘前邮件

OpenTrading 可在每个交易日早晨给你发一份 **感知持仓的盘前简报** —— 与 `ot report`
同样的融合内容，由 Claude 撰写，并以带样式、**兼容 Outlook 的 HTML** 邮件投递
（附纯文本回退）。每次运行融合的内容：

- **宏观** —— SOFR / 2s10s / TGA / RRP → 评分式方向偏向
- **聪明钱** —— CNN + 加密货币恐惧贪婪指数，以及 BTC 资金费率（逆向）
- **期权 EV** —— SPY + 你的标的：做市商 gamma（GEX）符号与 gamma 墙
- **新闻，最近 24 小时** —— 与 *你的* 持仓相关的 FinancialJuice 头条
- **你的持仓** —— 按美元加权的持仓表（敞口、权重 %、逐个标的解读）
- **集中度与今日关注** —— 主导因子风险 + 可操作的关键价位

启用它（基础档 —— 只需 SMTP 凭据，无其他手动步骤）：

```bash
cp .env.example .env        # 设置 OT_SMTP_* + OT_EMAIL_TO（Resend 无需 2FA 即可用）
ot email --dry-run          # 确认配置可正确解析（不发送）
ot email                    # 单次发送
ot schedule email           # 工作日本地时间 08:30（macOS launchd）
ot schedule email 9 0       # 改时间 · `ot schedule email uninstall` 移除
```

不发送、仅预览 HTML：

```bash
OT_EMAIL_RENDER_ONLY=1 OT_EMAIL_HTML_OUT=/tmp/brief.html \
  bash tools/brief/daily_email_claude.sh && open /tmp/brief.html
```

**中文版：** 加上 `--lang zh`（新闻邮件）或 `OT_EMAIL_LANG=zh`（每日简报），即可收到
简体中文版本。

> **计划中（v2）：用户可调的数据源** —— 自行选择简报融合 *哪些* 来源（宏观、
> FinancialJuice 新闻、聪明钱、期权 EV、TradingView），按来源逐项 opt-in，而不再总是
> 全部包含。见 [`RELEASE_NOTES.md`](RELEASE_NOTES.md)。
>
> macOS：launchd 无法读取位于 `~/Desktop`、`~/Documents` 或 `~/Downloads` 下的仓库
> （TCC 限制）—— 请把仓库放在别处（例如 `~/OpenTrading`）。各邮件服务商细节：
> [`tools/email/README.md`](tools/email/README.md)。

---

## 隐私与你的数据

你的持仓与密钥 **绝不** 进入 git，也 **绝不** 成为任何发布版本的一部分：

| 内容 | 存放于 | 状态 |
|------|--------|------|
| 你的持仓（如 ORCL、SPCX …） | `watchlist.json` | **git 忽略** —— 只有 `watchlist.example.json` 被纳入版本控制 |
| 邮件 / API 凭据 | `.env` | **git 忽略** —— 只有 `.env.example` 被纳入版本控制 |
| 抓取的新闻、报告、简报 | `data/` | **git 忽略** |

在任意机器上从模板重建这两个私有文件：

```bash
cp watchlist.example.json watchlist.json   # 然后填入你自己的持仓
cp .env.example .env                        # 然后填入你的 SMTP 凭据
```

正是这种隔离，让这个仓库可以安全地公开分享 —— `*.example` 文件只是占位模板，真实文件
始终留在你本机。**切勿提交 `.env` 或 `watchlist.json`。**

---

## 可选增强模块

上面的核心是 **基础档**：免费、无需 API key、无需手动步骤 —— `install.sh` 开箱即用。
下面这些模块能力更强，但都是 **可选的**，且需要 **手动配置**；核心功能不依赖它们中的任何一个。

### TradingView —— 实时图表，会话内可用
通过 [`tradesdontlie/tradingview-mcp`](https://github.com/tradesdontlie/tradingview-mcp)
服务器（Chrome DevTools 端口）把你的 **TradingView Desktop** 应用桥接给 Claude。配好之后，
在会话里直接问 Claude —— *“用 TV 数据分析一下 MSTR”* —— 它就会从你的图表上直接读取实时
行情 / 指标值 / 你的 Pine 价位。手动步骤：clone + `npm install` 该 MCP、`claude mcp add`、
以调试端口启动 TradingView、重启 Claude Code、运行 `tv_health_check`。*（ToS 灰色地带、
未公开的内部 API —— 仅对你自己已登录的客户端运行。）*

### IBKR —— 计划中（`tools/ibkr/`）
通过 [`ib_async`](https://github.com/ib-api-reloaded/ib_async) 接入 Interactive Brokers：
实时行情、期权链、持仓，以及在显式保护开关后的 **模拟盘** 执行。先做只读/模拟盘；绝不自动
提交实盘订单。需要 TWS / IB Gateway 处于运行状态。

---

## 路线图

简版（已发布历史见 [`RELEASE_NOTES.md`](RELEASE_NOTES.md)；完整细节见
[`ROADMAP.md`](ROADMAP.md)）：

- **邮件 v2 —— 用户可调的数据源**：自行选择每日简报融合哪些来源。
- **可选增强模块**（手动配置，核心永不依赖）：
  - **IBKR**（`tools/ibkr/`）—— 通过 `ib_async` 提供实时行情、期权链、持仓、模拟盘执行。
  - **TradingView** —— 把实时图表 / 指标 / Pine 价位融入报告（目前：会话内、按需）。
- **更多无需 key 的数据 CLI 与 API** —— FRED、期权 IV/IVR、资金费率曲线。
- **多智能体研究台** —— *未来探索方向，并非当前路线*：分析师 →
  多空辩论 → 交易员 → 风控官，借鉴
  [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)。

---

## 致谢与免责声明

由 [@orangejustin](https://github.com/orangejustin) 构建。（未来的）多智能体方向受
[TradingAgents](https://github.com/TauricResearch/TradingAgents) 启发。

本项目提供的分析 **仅供教育用途**，**并非投资建议**。市场有风险，请据此控制仓位并自行
做尽职研究。**仅供教育用途，非投资建议。交易涉及重大亏损风险。**
