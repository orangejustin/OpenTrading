---
title: 简介
sidebar_position: 1
slug: /intro
---

# 什么是 OpenTrading？

**OpenTrading** 是一套开源、本地优先的工具集，**同时**也是一个用于短线交易分析的
Claude skill —— 覆盖股票、期权、衍生品与加密货币 —— 采用**宏观优先、风险优先**的工作流。

它建立在一个理念之上：一个优秀的交易台不是靠一个聪明的模型，而是靠*许多相互独立的观点*被强制相互印证。因此
OpenTrading 运行一小组预测者，让它们互相争论，然后根据实际发生的情况给自己打分。

## 三个层次

```
FORECASTERS            →   FUSION                 →   LEARNING
independent views          reconcile them             grade & remember
─────────────────          ──────────────────         ─────────────────
rules engine (ot decide)   consensus strip            ot reflect grade
logistic P(up) (ot quant)  confluence ladder          lessons → next judge
TimesFM cone (ot forecast) bull vs bear + judge
dealer gamma / GEX         (ot debate)
crowd odds (ot poly)
on-chain whales (ot whales)
```

1. **预测者**各自从*不同的*信息中产生一个观点 —— 一个规则引擎、一个统计模型、一个基础模型、做市商持仓数据、一个
   LLM 分析师，以及一个预测市场的群体。
2. **融合**将它们组合起来：一个共识条（一旦两个分析师产生分歧就立刻翻转为**观望**）、一个共振价位梯（由
   2 个以上相互独立的方法共同点名的价格位），以及一场对抗式的**多空辩论**，其裁判会给出明确的判断。
3. **学习**会在事后为每一个已做出的判断打分，并把经验教训反馈到未来的判断中。

## 设计原则

- **确定性的 SOP，而不是一个 agent。**脚本负责收集并计算证据，将其冻结成一个文本包，*然后*模型才去读取它。没有任何东西会自行行动；相同的输入总是产生相同的证据。
- **免密钥、本地优先。**核心不依赖任何 API 密钥 —— 只需 Python 的标准库。你的持仓保存在一个被
  git 忽略的文件中，永不离开你的机器。
- **独立性优先于一致性。**五个共用一个大脑的分析师等于一个分析师。每个模块都刻意使用不同的数学方法、不同的数据，以及（在辩论中）不同厂商的模型。

## 适合谁使用

一位宏观优先的短线交易者，想要一个**可复现的第二意见** —— 不是让你盲目跟随的信号，而是一个会展示其推导过程并持续记录战绩的结构化交易台。

:::warning 仅供教育用途
OpenTrading 产生的一切都**仅供教育用途 —— 非投资建议。**它是一个个人研究工具。你需要为自己的交易负责。
:::

准备好了吗？前往 **[快速开始](./getting-started.md)**。
