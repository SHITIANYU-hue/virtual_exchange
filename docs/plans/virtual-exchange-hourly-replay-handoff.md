# 牛熊市历史行情回放计划


实验环境的其他部分保持不变，包括：

- agent 的角色、prompt 和 memory；
- wallet policy；
- 初始资金和持仓；
- agent 之间的沟通流程；
- spot、futures、AMM、audit 和 liquidation 机制；
- 模型配置和每轮执行顺序。

牛市和熊市实验之间，只改变 BTC、ETH 和 Solana 的历史价格路径。

## 历史区间

### 牛市区间

```text
2024-11-06 00:00 UTC
至
2024-11-09 00:00 UTC
```

这三天对应特朗普赢得美国总统选举之后的市场上涨。BTC 在选举结果明确后快速突破历史高点，ETH 和 Solana 也跟随市场上涨。

### 熊市区间

```text
2026-06-04 00:00 UTC
至
2026-06-07 00:00 UTC
```

这三天对应近期一次快速下跌。BTC 从约 6.7 万美元附近快速跌到约 5.9 万美元，ETH 和 Solana 同期也出现明显下跌。

两个区间长度相同：

```text
3 天 × 24 小时 = 72 小时 = 72 turns
```

## 锚定资产

实验使用以下三个币种作为外部市场价格锚点：

- BTC；
- ETH；
- Solana。

分别下载并回放：

- `BTCUSDT` 的 1 小时 candle；
- `ETHUSDT` 的 1 小时 candle；
- `SOLUSDT` 的 1 小时 candle。

三个币种必须使用相同的时间范围，并且每个小时严格对齐。

## Turn 的运行方式

一小时历史行情对应一个 agent turn。

在 Turn `t`：

1. Agent 只能获取上一个已经结束的小时，即 `t-1` 小时的行情。
2. 所有 agents 看到同一份 BTC、ETH 和 Solana 价格快照。
3. Agents 按照现有流程进行分析、沟通、audit 和交易。
4. 所有 agents 完成本轮动作之后，系统才推进并结算下一个小时的价格。
5. 新的小时价格在下一个 turn 才会提供给 agents。

运行顺序为：

```text
读取上一个小时的数据
  -> agents 分析和沟通
  -> agents 提交交易动作
  -> 完成本轮 audit 和执行
  -> 推进一个历史小时
  -> 进入下一个 turn
```

系统运行速度不需要真的等待一小时。无论一次 LLM 调用需要多长时间，模拟时间每完成一个 turn 只推进一个历史小时。

## 双盲处理

不能直接告诉 agents 当前运行的是牛市还是熊市，也不能让 agents 知道真实历史日期。

运行时只向 agents 提供：

- 当前 turn 编号；
- 上一个小时已经完成的 BTC、ETH 和 Solana 行情；
- 当前实验环境中的账户、市场和消息状态。

不能向 agents 提供：

- `bull` 或 `bear` 标签；
- 真实日期和年份；
- 完整历史行情文件；
- 当前 turn 之后的未来价格；
- 新闻、浏览器、互联网或实时市场数据；
- 包含时间区间和市场标签的文件名、日志或配置。

运行配置使用不带含义的名称，例如：

```text
World A
World B
```

World A 和 World B 对应牛市还是熊市，由单独的 private mapping 保存。分析结果完成之后再揭示对应关系。

为了避免历史绝对价格直接暴露年代，两个世界中的价格都从当前实验使用的共同初始价格开始，再按照真实历史小时收益变化：

```text
replay_price
  = common_start_price
  × historical_price / historical_start_price
```

这样可以保留真实的涨跌路径，同时避免 agents 仅通过 BTC 当时是 6 万、7 万或其他绝对价格直接判断历史时间。

## 数据准备

从 Binance 历史数据中下载两个区间的 1 小时 OHLC 数据。

每个正式区间需要：

- 72 根用于实验的小时 candle；
- 区间开始前额外 1 根 candle，作为 Turn 1 可以观察的“上一个小时”；
- BTC、ETH、SOL 三个币种各 73 根 candle。

如果存在缺失小时、重复数据或三个币种时间不一致，实验应直接停止，不能使用实时价格或默认价格补齐。

## 实验扩展

第一轮先运行三天，即 72 turns。

如果后续希望增加实验长度，就从相同的起始时间继续扩大两个历史区间，并且保证牛市和熊市增加相同数量的小时。例如：

```text
4 天 = 96 turns
5 天 = 120 turns
7 天 = 168 turns
```

扩展时只调整结束时间，不改变已经确定的起始时间，也不能根据已有实验结果重新挑选更有利的行情。

## 需要实现的内容

1. 下载并保存两个历史区间的 BTC、ETH 和 SOL 小时数据。
2. 在 backend 中加入 historical replay price mode。
3. Replay mode 下关闭实时价格更新。
4. 在 experiment runner 中每完成一个 turn 推进一个历史小时。
5. 确保同一个 turn 的所有 agents 使用同一价格快照。
6. 隐藏真实日期、牛熊标签和未来行情。
7. 将 World A/World B 与真实区间的关系保存到 private mapping。
8. 在实验日志中记录 turn、价格、agent 动作、wallet 结果、audit 结果和最终交易回执。

## 完成标准

- 牛市和熊市都可以完整运行 72 turns；
- Turn `t` 只能看到上一个小时的数据；
- 同一 turn 的所有 agents 看到相同价格；
- agents 无法访问真实日期、牛熊标签和未来行情；
- BTC、ETH、SOL 的价格按照各自真实历史路径变化；
- 除价格路径外，两个实验的其他配置保持一致；
- 如果增加 turns，两个区间按照相同长度继续扩展。

## 时间选择依据

- 特朗普胜选后 BTC 突破历史高点：<https://apnews.com/article/c2e2a1a895288c5e9c0df2721012a5bb>
- 2026 年 6 月 BTC 快速跌至约 5.9 万美元：<https://www.coindesk.com/markets/2026/06/06/bitcoin-back-above-usd61-000-after-rout-leads-to-usd1-6-billion-liquidations>
