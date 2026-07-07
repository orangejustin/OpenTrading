---
title: 快速开始
sidebar_position: 2
---

# 快速开始

本文将带你从全新克隆仓库到完成第一次分析，大约只需五分钟。

## 前置条件

- 核心需要 **Python 3.9+**（`python3 --version`） —— 只有当你想使用可选的 TimesFM
  预测者时才需要 **3.10+**
- **git**
- macOS 或 Linux（Windows 通过 WSL）
- *可选，用于叙述层：*一个 LLM 密钥（Gemini 或 OpenRouter）**或** Claude Code / Codex
  CLI —— 仅用于"AI 分析"和辩论。整个数据层不需要它们中的任何一个即可运行。参见 [可选增强模块](#可选增强模块)。

## 1 · 克隆并安装

```bash
git clone https://github.com/orangejustin/OpenTrading.git
cd OpenTrading
bash install.sh                  # core: puts `ot` on your PATH, no keys, stdlib only
```

这就是整个核心。若要使用**可选的** TimesFM 预测者（一个较重、需主动选择安装的依赖），再运行：

```bash
bash install.sh --with-forecast  # adds the TimesFM module in an isolated venv
```

参见下方的 [可选增强模块](#可选增强模块) 了解它会拉取哪些内容以及其硬件需求。无论哪种方式，都可以验证工具链：

```bash
ot doctor                # checks python / deps / network
```

## 2 · 你的第一批命令

一切都通过单个命令 `ot` 来调用。试试这些 —— 全都不需要密钥：

```bash
ot                       # full market report: macro + news + smart money + options
ot quote SPY QQQ ^VIX    # live quotes, incl. pre-market and ^VIX
ot macro                 # rates & liquidity → a put/call bias
ot decide NVDA --dte 7   # CALL / PUT / NO-ACTION + a range plan
ot whales                # on-chain: labeled-wallet ETH balances + deltas
```

为**任意**工具加上 `--format json`（或 `--json`）即可获得机器可读的输出。

## 3 · 打开仪表盘

```bash
ot web                   # → http://127.0.0.1:8787
```

然后输入一个股票代码（例如 `NVDA`）即可看到完整的交易台 —— 共识条、带有做市商墙和预测锥的图表、多空辩论，以及共振价位梯。参见 **[Web 仪表盘](./web-dashboard.md)**。

要为叙述层使用 LLM，可以导出一个密钥或传入一个引擎：

```bash
export GEMINI_API_KEY=...        # or OPENROUTER_API_KEY
ot web --engine gemini           # or: claude / codex / openrouter
```

## 4 · 让它成为你的（两个被 git 忽略的文件）

两个文件保存你的私有配置，且**永不被提交**：

```bash
cp .env.example .env                     # SMTP creds, optional LLM keys
cp watchlist.example.json watchlist.json # your positions
```

编辑 `watchlist.json`，填入你持有或追踪的标的。如果你想要每日邮件，再加上一个 `recipient` 字段：

```json
{
  "recipient": "you@example.com",
  "positions": [
    {"ticker": "NVDA", "shares": 100},
    {"ticker": "SPY", "shares": 50}
  ]
}
```

:::tip 多个账本
你可以保留多个名册（例如 `watchlist.188284421.json`），并用 `OT_WATCHLIST=watchlist.188284421.json ot web` 让仪表盘指向其中一个。
:::

## 可选增强模块

核心是免密钥的。以下这两个附加组件完全是可选的。

### LLM 引擎与密钥（叙述层）

"AI 分析"面板和多空辩论需要一个引擎。选一个你已有的即可 —— 仪表盘顶部的下拉框可以在它们之间实时切换。

| 引擎 | 获取密钥 | 说明 |
|---|---|---|
| **Gemini** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | 有**免费额度**；设置最快 |
| **OpenRouter** | [openrouter.ai/keys](https://openrouter.ai/keys) | 一个密钥 → 300+ 个模型（部分免费）；按量付费 |
| **Claude Code / Codex CLI** | — | **无需密钥** —— 使用你已有的 CLI 订阅 |

在 `.env`（或你的 shell）中设置一个密钥，然后在该引擎上启动仪表盘：

```bash
# .env  (git-ignored)
GEMINI_API_KEY=...            # from Google AI Studio
# or
OPENROUTER_API_KEY=sk-or-v1-...   # from OpenRouter
```

```bash
ot web --engine gemini       # or: openrouter / claude / codex
```

完全没有密钥时，仪表盘仍然可以运行 —— 它只是显示免密钥的数据面板和基于确定性规则的分析，而不是 LLM 叙述。

### TimesFM 预测（一个基础模型锥）

`ot forecast` 会在预测叠加层上加入一个 [TimesFM 2.5](https://github.com/google-research/timesfm)
分位数锥 —— 它是 Google Research 预训练的时间序列基础模型。它**需要主动选择安装**，因为这是一个较重的依赖：

```bash
bash install.sh --with-forecast
```

- **Python 3.10+**（核心仍保持 3.9+）；安装到一个**隔离的 venv**（`.venv-forecast/`）中，因此永远不会触及免密钥的核心。
- 会拉取 **`timesfm[torch]`**（约 2 GB 的 PyTorch 依赖栈）以及一个在首次运行时下载的 **~500 MB**
  模型检查点。
- 模型：**`TimesFM 2.5 200M`**（torch 后端） —— **对 CPU 友好**，因此 Apple 芯片或现代笔记本都能顺畅运行（首次推理会因为编译/加载而较慢；后续调用则很快）。有
  GPU 会更好，但并非必需。
- 确切的硬件指引和模型卡片见 Google 的仓库：[google-research/timesfm](https://github.com/google-research/timesfm)。

如果没有安装它，`ot forecast` 只会打印一条提示，交易台的其余部分不受影响。

## 后续步骤

- **[Web 仪表盘](./web-dashboard.md)** —— 从头到尾读懂一个个股页
- **[每日邮件](./daily-email.md)** —— 一份定时发送的盘前简报
- **[预测台](./prediction-desk.md)** —— 流水线的工作原理
