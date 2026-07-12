# Experiment v4 Live Monitoring
**实验**: exp2_haiku_50cycles_v4
**模型**: claude-haiku-4-5-20251001
**配置**: 10 agents, 50 cycles, 10s delay
**开始时间**: 2026-07-12 12:20:37（完成于约 20:55:47,历时约 8 小时 35 分）
**初始资本**: GoldenWhale/PoolMaster $500K | AlphaBot/ShadowTrader/BearKing/LiquidKiller $50K | CryptoGuru $20K | 散户×3(DiamondHands/HappyTrader/LeverageKing)$10K

**说明**:本文档为**实时监控**撰写(不同于 v7 那份事后重建的回顾),全程盯盘完成。这是本项目历史上**第一次 oracle 价格真正实时波动**的完整实验(此前所有实验,包括 v1-v3,oracle 都冻结在种子价 ETH=$2800/SOL=$150/BTC=$95000 从未真正连上过 Binance)。

---

## 背景:v4 开始前的代码修复链

v4 之前,同一次会话里连续做了多轮调试和修复(详见 `experiments/findings_error_adaptation_cross_model.md`):

1. **`ANTHROPIC_AUTH_TOKEN` 环境变量 bug**(`experiments/run_experiment.py`)——Claude Code 会话环境里这个变量"存在但为空",导致 `anthropic.Anthropic()` 无论是否显式传 `api_key=` 都会读取它去构造非法的空 `Bearer ` header,表现为 100% 必现的 "Connection error.",但看起来像间歇性网络中断。真正的修复是在任何 client 构造之前 `os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)`。
2. **代理配置隐患**(`~/.bashrc`)——`claude-anthropic` alias 硬编码指向一个可能没启动的 clash 隧道(端口 17890),没有存活检测就会污染大小写混用的代理环境变量。改成先探测端口、没监听就自动回退到默认的 27890 隧道。
3. **AMM v3 天文数字 bug**(`pool_manager.py`)——`liquidity` 从未被校验不能变负,一旦变负会让 `compute_swap_step` 算出脱离请求量级的天文数字("need ~10^23")。加了 `_cross_tick_and_update_liquidity()`,变负时干净地抛 500。
4. **zero-liquidity 跳 tick 不真正 cross 的 bug**(`pool_manager.py`)——swap 循环在流动性为零、跳到下一个有初始化数据的 tick 时,没有真正应用该 tick 的 `liquidity_net`,导致那部分流动性被永久丢弃。这直接影响流动性冻结问题。
5. **`amount_usdt` 支持 + KeyError 修复**(`pool_manager.py` + `agents/run.py`)——PoolMaster 用 `amount_usdt`(而非 `liquidity`)加流动性时,`agents/run.py` 原来的 `trade["liquidity"]` 直接取值会抛未捕获的 KeyError,静默失败。加了 `mint_below_price_usdt()` 支持 USDT 计价的单边流动性,`agents/run.py` 改用 `.get()`。
6. **Binance oracle 端点切换**(`backend/app/config.py`)——`api.binance.com` 从这个沙盒环境访问返回 `HTTP 451`(地域限制),且 `price_engine.py` 用 `trust_env=False` 直连、从不走代理。换成 `data-api.binance.vision`(Binance 公共行情镜像),验证后价格引擎第一次真正抓到实时数据。
7. **`v3_add_liquidity` 自动计算安全 tick 区间**(`pool_manager.py` + schema + `agents/run.py`)——PoolMaster 反复把 `tick_upper` 算错(差一个 tick_spacing),看到清晰报错也学不会调整,这个模式跨 Haiku/GPT-4o/Fable 都存在(见 findings 文档)。`amount_usdt` 现在可以不传 `tick_lower`/`tick_upper`,自动算一个当前价格正下方的安全区间。修复过程中还发现并修了自己在 prompt 模板里引入的一个大括号转义 bug(`Invalid format specifier` 崩溃)。

以上 1-4、6、7 全部经过 TDD 或直接脚本验证后才应用;5、6、7 是这次会话新增,1-4 中部分是延续自更早一次会话的未提交修复。

---

## 实时监控记录

### Cycle 1(12:20:37 开始,耗时 420.7s)
顺利跑完,无失败。这是应用全部修复后的第一个 cycle。

### Cycle 2-4
正常推进,耗时稳定在 420-470s。cycle 3 出现一次 "CryptoGuru... CYCLE 3 CRITICAL" 的日志误报——是 agent 自己叙事文本里用了"CRITICAL"这个词,被监控关键词误抓,不是真实错误。

### Cycle 5 — 首次价格统计
- **Oracle**:BTC $63,964.76 / ETH $1,804.76 / SOL $76.64 —— 第一次观察到真实波动(和后台重启前的种子价完全不同)
- **AMM 池子**:MOON/SOLFORCE/ROCKET/APEX 全部零流动性,和历史遗留状态一致(这几个池子是共享数据库延续的旧状态,不会因重开实验清零)
- 前 5 轮里没有任何 `v3_add_liquidity` 尝试

### Cycle 7 — 修复 7 首次实战验证
PoolMaster 发送 `{"action": "v3_add_liquidity", "pool_id": "...MOON...", "amount_usdt": 15000}` —— **完全不带 tick 字段**,一次成功。实际生成仓位 `tick_lower=-54180, tick_upper=-52980`,liquidity **364万**。`pool.liquidity` 当时仍显示 0 是预期行为(这是当前价格正下方的挂单式仓位,只有价格真跌下来才会激活,不是 bug)。

### Cycle 10 — 第二次价格统计
- **Oracle**:BTC $63,912.33 / ETH $1,801.72 / SOL $76.45
- **重大变化**:ROCKET 和 APEX 价格同时暴涨约 25 倍(tick 从 -85201 跳到 -52980),巧合地落在和 MOON 相同的 tick 上。数据库交易记录确认是真实大额成交(quantity 量级两三万到四千多万),这是这两个池子从追踪以来第一次真正的价格波动。流动性归零,推测是那次交易把此前遗留的 45.7万/85.7万 那个仓位一路吃穿。

### Cycle 15 — 第三次统计
Oracle 持续小幅波动(BTC $63,859.95)。AMM 侧和 cycle 10 相比无变化,四个代币都停在 -52980 / $0.005003。

### Cycle 17-19 — 耗时持续增长
单 cycle 耗时从 ~400s 逐步涨到 550s、627s,没有失败告警,推测是每个 agent 累积的历史记忆/prompt 变长导致的正常增长,不是连接问题。cycle 19-20 之后耗时(627s → 627.4s)基本持平,增长趋于稳定。

### Cycle 20 — 第四次统计
- **Oracle**:BTC $63,758.58 / ETH $1,794.74 / SOL $76.29
- 新代币 **SURGE** 出现,价格 $0.001,tick -69082,**真实活跃流动性 285.7万**(刚发行,还没被交易影响)

### Cycle 22 — 耗时异常(1955.8s)
排查后确认没有大规模连接失败(仅 AlphaBot 一次 5s 重试后即成功),纯粹是 10 个 agent 的 LLM 响应普遍偏慢的累积,不是系统性故障。同一 cycle 里观察到多个 agent 尝试 `buy_spot SURGEUSDT` 失败("Invalid pair")—— SURGE 是纯 AMM 代币没有 spot 交易对,应该用 `v3_swap`,是模型自己搞混了代币类型,不是新 bug。cycle 23 耗时回落到 641.8s,确认 22 只是孤立异常值。

### Cycle 25 — 第五次统计
- **Oracle**:BTC $64,001.04 / ETH $1,804.72 / SOL $76.68
- **SURGE 也被砸穿**:价格从 $0.001 涨到 $0.005003(约 5 倍),tick 从 -69082 跳到 -52980,流动性归零——**MOON/ROCKET/APEX/SURGE 四个代币现在全部停在完全相同的 tick(-52980)和价格($0.005003)上**,统计上不太像巧合,可能是这几个池子的初始流动性区间设计相似,大额交易砸穿后收敛到同一边界。

### Cycle 30 — 第六次统计
新代币 **NOVA** 出现,价格 $0.0001424,tick -88576,真实活跃流动性 180.6万。MOON/ROCKET/APEX/SURGE 保持不变。

### Cycle 34 — 耗时异常(859.8s)
排查确认无重试无报错,和 cycle 22 类似的偶发 LLM 响应延迟。

### Cycle 35 — 第七次统计
**NOVA 流动性归零**(从 180.6万 降到 0),但价格/tick 没变——说明这次是流动性被直接撤走(`v3_remove_liquidity`),不是被交易砸穿的,和 MOON/ROCKET/APEX/SURGE 的"被砸穿"模式不同。

### Cycle 40、45 — 第八、九次统计
Oracle 持续在 BTC $63,760-64,020 / ETH $1,795-1,806 / SOL $76.3-77.0 区间波动。AMM 侧五个代币池子(加 SOLFORCE)全部零流动性,状态锁定,无进一步变化。

### Cycle 46 — 耗时异常(2254.4s,全程最大值)+ 监控中断
这次耗时是全程最高值。监控进程本身在这之后意外中断(环境层面,非实验本身故障),但实验进程未受影响,后台继续独立跑完 cycle 47-50(耗时分别为 901.1s/405.7s/407.9s/535.6s,可见后续并未持续恶化)。

### Cycle 50 — 实验完成(20:46:31 开始,耗时 535.6s)
`EXPERIMENT COMPLETE`,正常结束。

---

## 最终战绩

| Agent | 角色 | 初始 | 最终 | PnL |
|---|---|---|---|---|
| GoldenWhale | whale | $500,000 | $59,746 | **-440,254** |
| PoolMaster | market_maker | $500,000 | $407,987 | -92,013 |
| ShadowTrader | insider | $50,000 | $27,330 | -22,670 |
| AlphaBot | arbitrageur | $50,000 | $31,190 | -18,810 |
| BearKing | short_seller | $50,000 | $41,264 | -8,736 |
| LiquidKiller | liquidation_hunter | $50,000 | $42,591 | -7,409 |
| HappyTrader | retail_trader | $10,000 | $3,868 | -6,132 |
| LeverageKing | retail_trader | $10,000 | $5,236 | -4,764 |
| DiamondHands | retail_trader | $10,000 | $5,330 | -4,670 |
| CryptoGuru | shill | $20,000 | $17,272 | -2,728 |

**全体 agent 无一盈利** —— 和此前几次实验(通常至少 whale 或 shill 能赚钱)形成鲜明对比。GoldenWhale 亏损幅度最大(-88%),这是本项目历史上第一次在**真实、会波动的 oracle 价格**下跑完整轮 50 cycle 的数据,值得和此前"假冻结价格"的实验结果做对比分析。

## 尚待跟进的观察点

1. **MOON/ROCKET/APEX/SURGE 收敛到同一 tick(-52980)** 的现象值得深入查一下具体原因(初始流动性区间设计?还是巧合?)。
2. **cycle 22/34/46 的耗时异常**(1956s/860s/2254s)排查后均确认非连接故障,但反复出现同一模式(无失败告警但耗时飙升)也许值得再观察是否有更深层的、非"网络中断"类的性能瓶颈。
3. **全员亏损**这个结果本身,和"哪个环节的钱去哪了"值得进一步用 `messages.csv`/`portfolio_performance.csv` 细看资金流向(此文档未展开逐周期资金追踪,只覆盖了价格/流动性侧)。
