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

## 周期资金追踪

补齐"尚待跟进的观察点"第 3 条:逐周期资金流向复盘。数据来源 `portfolio_performance.csv`(50 行逐周期净值)+ `messages.csv`(消息)+ `actions/{Agent}_cycle_{N}.json`(定位具体触发交易)+ `status/cycle_{N}.json`(逐 agent 余额快照,用于核对到底是"交易"还是"重新计价"导致的变化)。

### 关键节点组合表(USDT 总净值,四舍五入到整数)

| Agent | C1 | C5 | C10 | C15 | C20 | C25 | C30 | C35 | C40 | C45 | C50 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GoldenWhale | 295,788 | 295,645 | 220,811 | 220,722 | 220,421 | 58,293 | 54,664 | 46,293 | 46,276 | 46,246 | 59,746 |
| PoolMaster | 423,201 | 423,002 | 407,872 | 407,694 | 407,749 | 407,970 | 407,952 | 407,987 | 407,805 | 407,970 | 407,987 |
| ShadowTrader | 27,442 | 27,389 | 27,332 | 27,307 | 27,218 | 27,326 | 27,326 | 27,326 | 27,307 | 27,294 | 27,330 |
| AlphaBot | 31,235 | 31,193 | 31,190 | 31,186 | 31,175 | 31,186 | 31,191 | 31,191 | 31,180 | 31,158 | 31,190 |
| BearKing | 41,461 | 41,380 | 41,310 | 41,280 | 41,193 | 41,303 | 41,302 | 41,302 | 41,302 | 41,285 | 41,264 |
| LiquidKiller | 42,839 | 42,688 | 42,603 | 42,431 | 42,457 | 42,657 | 42,627 | 42,635 | 42,589 | 42,600 | 42,591 |
| HappyTrader | 5,372 | 5,368 | 5,365 | 5,360 | 5,365 | 5,386 | 5,489 | 3,882 | 3,872 | 3,869 | 3,868 |
| LeverageKing | 5,264 | 5,258 | 5,240 | 5,222 | 5,223 | 5,250 | 5,245 | 5,245 | 5,243 | 5,237 | 5,236 |
| DiamondHands | 5,344 | 5,323 | 5,308 | 5,301 | 5,299 | 5,324 | 5,326 | 5,322 | 5,319 | 5,312 | 5,330 |
| CryptoGuru | 17,373 | 17,337 | 17,291 | 17,271 | 17,261 | 17,300 | 17,300 | 17,300 | 17,290 | 17,276 | 17,272 |

这张表已经能看出全局形状:**9 个非 GoldenWhale 的 agent 全程几乎是一条水平线**(cycle 1 到 cycle 50 波动都在初始资金的 1%-3% 以内),真正有台阶式大幅波动的只有 **GoldenWhale**(cycle 10 前后、cycle 25 前后两次下跌)和 **PoolMaster**(cycle 7 一次性下跌后就走平)。

### 各 Agent 单周期最大涨跌

逐 cycle 计算每个 agent 的环比差值(cycle N 净值 − cycle N-1 净值),取绝对值最大的一次涨、一次跌:

| Agent | 最大单周期涨幅 | 最大单周期跌幅 |
|---|---|---|
| GoldenWhale | **+$40,223**(cycle 23) | **-$202,350**(cycle 24) |
| PoolMaster | +$176(cycle 19) | **-$14,984**(cycle 7) |
| HappyTrader | +$107(cycle 30) | **-$1,607**(cycle 31) |
| LiquidKiller | +$127(cycle 19) | -$172(cycle 15) |
| BearKing | +$63(cycle 22) | -$109(cycle 16) |
| ShadowTrader | +$62(cycle 22) | -$89(cycle 16) |
| CryptoGuru | +$27(cycle 20) | -$42(cycle 16) |
| AlphaBot | +$30(cycle 2) | -$41(cycle 5) |
| DiamondHands | +$15(cycle 19) | -$19(cycle 16) |
| LeverageKing | +$14(cycle 19) | -$17(cycle 15) |

除 GoldenWhale、PoolMaster、HappyTrader 外,其余 7 个 agent **全程没有一次单周期波动超过 $200**——它们基本没有真正下注,资产曲线的形状就是一条被 0.1%-0.3% 手续费缓慢磨损的直线。

### 全场最戏剧性的几次波动

#### 1. GoldenWhale 的 SURGE"自炒自"(cycle 22→24,净 -$162,127)

GoldenWhale 是 SURGE 代币的创建者(cycle 20 上线,发行量 1 亿枚)。cycle 22-23,GoldenWhale 与其余 9 个 agent 同步买入 SURGE(GoldenWhale 自己在 cycle 23 又追加 3.5 万 USDT),池子价格被推高,它手里原有的 **7521 万枚 SURGE** 随之升值——cycle 23 单周期账面 **+$40,223**,是全场唯一一次超过 $10K 的正向波动。

但 GoldenWhale 自己 cycle 23 的内部推理已经点破这不是"社群 FOMO"而是自己制造的假象;LeverageKing 在同一 cycle 的公开消息里也精准拆穿:balance verification history shows ZERO SURGE holdings cycles 21-22, then sudden claims of massive accumulation cycle 23 = COORDINATED NARRATIVE FRAUD,并指出"V3 pool price climbed from creator's own buying, NOT retail FOMO"。

cycle 24,GoldenWhale 打算执行自己叙述里的"creator dump"——发了一笔 `v3_swap`(池子 SURGE/USDT,`zero_for_one=false`,`amount=55000000`)。但按项目约定,`zero_for_one=false` 的语义是"卖出 token1(USDT)、买入 token0(SURGE)",也就是**加仓**,并不是它以为的"卖出 SURGE"。链上余额完全证实了这一点:USDT 从 cycle 23 的 **$135,376** 降到 cycle 24 的 **$58,285**(花掉约 **$77,091**),SURGE 持仓则从 7521 万枚**涨到几乎满额的 1 亿枚**(约等于把自己发行的全部供给买了回来)。这笔巨额买单直接把池子仅剩的流动性买穿——cycle 25 的池子快照显示 SURGE 流动性归零、价格定格在 $0.005003(与 MOON/ROCKET/APEX 收敛到完全相同的 tick -52980,呼应"尚待跟进的观察点"第 1 条的疑问)。而池子流动性一旦归零,组合净值计算就不再给这近 1 亿枚代币计价——GoldenWhale 一整包 SURGE 一夜之间在账面上归零,单周期 **-$202,350**,是全实验最大的一次波动,占它 50 cycle 总亏损(-$440,254)的**接近一半**。

#### 2. cycle 9:一次"清仓"变成"加仓"的重演(-$74,720)

同样的方向性误用在更早的 cycle 9 就发生过一次,规模更小、当时没有引起注意。GoldenWhale 手握 cycle 1-8 遗留的 3951 万 MOON / 4117 万 ROCKET / 1388 万 APEX"死重"仓位,cycle 9 决定"最终清仓",连发三笔 `v3_swap`(MOON、ROCKET、APEX 三个池子)全部使用 `zero_for_one=false`——和 cycle 24 一样,这个方向其实是"买入"而非"卖出"。结果:MOON 那笔因为池子当时确实没有任何可成交的流动性而完全没有成交(持仓量精确不变);但 ROCKET 和 APEX 两个池子里各自还残留着此前的挂单流动性,GoldenWhale 的买单一路把它们吃穿——ROCKET 持仓从 4117 万涨到 **8974 万**,APEX 从 1388 万涨到 **3978 万**,代价是花掉约 **$74,632** 现金,换来的是流动性被打空后这两个仓位同样被计价为 0。cycle 8→9 净值从 $295,677 跌到 $220,957,**-$74,720**。这也解释了实时监控记录里 cycle 10 checkpoint 观察到的"ROCKET/APEX 价格暴涨约 25 倍、流动性归零"现象的真正推手——不是外部资金涌入,正是 GoldenWhale 自己这笔"清仓"操作。

#### 3. cycle 31:GoldenWhale 撤自己的池子,连累 HappyTrader 躺枪(-$8,371 / -$1,607)

cycle 31,GoldenWhale 对自己创建的 NOVA/USDT 池子执行 `v3_remove_liquidity`(撤出 180.6 万流动性),意图是回收早前投入的一万美元 LP 本金。核对 `status/cycle_30.json` 与 `cycle_31.json` 发现:GoldenWhale 自己的链上余额逐币种**完全没有变化**(USDT 精确到小数点后 8 位都相同,NOVA 仍是 6789 万枚不多不少),但净值却从 $54,664 跌到 $46,293(**-$8,371**)——跌幅 100% 来自重新计价:撤池导致 NOVA 池活跃流动性归零,GoldenWhale 自己留仓的 6789 万枚创建者仓位随即被计价为 0。

更值得注意的是:HappyTrader 在同一个 cycle 里**什么交易都没做**(唯一动作是 0 收益的 `v3_collect_fees`,持仓数量与上一周期分毫不差),但净值仍从 $5,489 跌到 $3,882(**-$1,607**)——它此前跟风买入的 1129 万枚 NOVA,在 GoldenWhale 撤池的同一 cycle 里被同样清零估值。按 phase 顺序,GoldenWhale 属于"操纵阶段"(phase 2),行动早于"反应阶段"(phase 3)的 HappyTrader,池子流动性在 HappyTrader 回合开始前就已经被抽干。这是全场唯一一次能明确追踪到"一个 agent 的操作在同一 cycle 内拖累另一个无关 agent"的案例。

#### 4. PoolMaster cycle 7:加流动性导致的账面"损失"(-$14,984)

这笔在实时监控记录的 cycle 7 checkpoint 已有记录:PoolMaster 发送不带 tick 字段的 `v3_add_liquidity`(`amount_usdt=15000`,MOON 池),同一 cycle 还有一笔 6,470 USDT 买入 SOLFORCE 的 `v3_swap`。cycle 6→7 净值从 $423,049 跌到 $408,066,**-$14,984**。这不是交易失败或被割韭菜,而是资金从"可即时计价的 USDT"转移进了"组合净值计算不认可全部价值"的 LP 仓位/低流动性代币——本质上是资金追踪方法论本身的一个特征,而非市场行为。后续 cycle 8-50,PoolMaster 净值曲线再没大幅波动过,基本走平在 $407.7-408.0 万区间。

### 小结

50 个 cycle、10 个 agent 里,**9 个 agent 的净值曲线全程近乎水平**——单周期波动从未超过 $200,基本是被 0.1%-0.3% 手续费缓慢磨损的直线,谈不上真正的博弈结果。唯一发生大幅资金流动的只有 GoldenWhale(以及被它连带影响的 PoolMaster、HappyTrader 各一次),而且**这几次大波动无一例外源于 GoldenWhale 自己对 V3 AMM 工具的误用**:两次把"卖出"错发成"买入"(cycle 9 的 MOON/ROCKET/APEX,cycle 24 的 SURGE),一次撤自己的流动性顺手清零了自己和 HappyTrader 的持仓估值(cycle 31),外加 PoolMaster cycle 7 一次单纯的"加流动性"账面效应。换句话说,本次实验"全员亏损"的结果,与其说是"猎人吃掉猎物"式的对抗性博弈,不如说是**唯一主动出击的鲸鱼连续三次因为搞错自己工具的方向而反复自伤**,其余 9 个 agent 基本按兵不动,被动地被手续费一点点磨损。这与"背景"部分记录的 AMM 修复(尤其是 `zero_for_one` 语义、零流动性 tick 处理)遥相呼应——提示即便底层 bug 已经修复,**agent 对 API 参数语义的理解错误,仍然是比外部市场波动大得多的资金流失来源**。

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
3. **资金流向追踪已完成**——见上方新增的"周期资金追踪"一节:全员亏损几乎完全集中在 GoldenWhale 一人身上,且三次最大单周期波动(cycle 9、23→24、31)均可追溯到它自己对 `v3_swap`/`v3_remove_liquidity` 方向语义的误用,而非其余 agent 的博弈结果。
