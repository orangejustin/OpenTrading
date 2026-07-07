---
title: 每日邮件
sidebar_position: 4
---

# 每日邮件

OpenTrading 可以按计划发送一份**感知持仓的盘前简报** —— 一封样式精美、兼容 Outlook 的 HTML
邮件，由仪表盘所使用的同一批工具构建而成。

![每日邮件示例](/img/email-sample.png)

## 邮件里有什么

- 一个市场状态横幅（宏观 × 盘面 × 聪明钱）
- 你的持仓表格，按美元金额加权
- 涵盖宏观、聪明钱、期权 / 做市商 Gamma、24 小时新闻、集中度的各个板块
- 交易台当日的 **Top-3**（来自 `ot rank`），每个都附有评分，并给出立即买入 / 等待价格的操作建议

## 一次性预览

不发送，直接渲染到一个文件：

```bash
OT_EMAIL_RENDER_ONLY=1 OT_EMAIL_HTML_OUT=/tmp/brief.html \
  bash tools/brief/daily_email_claude.sh
open /tmp/brief.html
```

## 发送

邮件通过 SMTP 发出，使用你那个被 git 忽略的 `.env` 中的凭据（请先复制 `.env.example`）。选择**一个**服务商 ——
预设会自动设置 host/port/security。两个简单、免费的选项：

### 选项 A —— Gmail（可发给*任何人*，包括海外）

推荐：它可以投递到任何地址（包括 qq.com / 海外）。你需要一个 Google **应用专用密码**，而不是你的登录密码：

1. 在你的 Google 账户上开启**两步验证**。
2. 打开 **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**，创建一个 16 位的应用专用密码。
3. 在 `.env` 中设置这些：

| 键 | 值 |
|---|---|
| `OT_SMTP_PROVIDER` | `gmail` |
| `OT_SMTP_USER` | 你完整的 Gmail 地址 |
| `OT_SMTP_PASS` | 那个 16 位的应用专用密码 |
| `OT_EMAIL_FROM` | 你的 Gmail 地址 |
| `OT_EMAIL_TO` | 简报投递到的地址 |

### 选项 B —— Resend（发给*你自己*，零 SMTP 烦恼）

如果你只需要发到自己的收件箱，这是最简单的。免费额度从 `onboarding@resend.dev` 发送，并且**只投递到你的
Resend 账户邮箱** —— 要发给其他人，需要在 [resend.com/domains](https://resend.com/domains) 验证一个域名。

1. 在 **[resend.com](https://resend.com)** 注册，然后在 **[resend.com/api-keys](https://resend.com/api-keys)** 创建一个 API 密钥（以 `re_` 开头）。
2. 在 `.env` 中设置这些：

| 键 | 值 |
|---|---|
| `OT_SMTP_PROVIDER` | `resend` |
| `OT_SMTP_USER` | 字面量 `resend` |
| `OT_SMTP_PASS` | 你的 API 密钥（`re_…`） |
| `OT_EMAIL_FROM` | `onboarding@resend.dev`（或你验证过的域名） |
| `OT_EMAIL_TO` | 你的 Resend 账户邮箱 |

然后发送一次：

```bash
ot email                 # sends the current report to OT_EMAIL_TO
```

:::note Outlook / 个人版 Microsoft
Microsoft 已为个人账户禁用了应用专用密码的 SMTP，因此 `outlook`/`office365` 预设对个人邮箱无法使用 ——
请改用 Gmail 或 Resend。
:::

## 定时任务

在 macOS 上，安装一个 `launchd` 任务：

```bash
ot schedule email 6 0        # every weekday at 06:00 local time
ot schedule email uninstall  # remove it
```

对于**多个名册**（例如一个美股账本和一个 A 股 / 港股账本，采用不同的时间表和语言），OpenTrading
提供了一个名册群发器，它会遍历每一个 `watchlist*.json`，按各自的 `lang` 语言把邮件发送到各自的 `recipient`：

```bash
ot schedule roster us        # US rosters, weekday pre-market
ot schedule roster cn        # A/HK rosters, aligned to China pre-market
```

:::note 语言规则
每封邮件都是单一语言：英文账本收到英文，中文名册收到中文 —— 绝不会在同一封邮件里混用。
:::
