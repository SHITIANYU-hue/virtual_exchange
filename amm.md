## 概述

在上一篇内容中，我们介绍 [Uniswap v2](https://hackmd.io/@wongssh/uniswap-v2) 的代码，在本篇内容中，我们将介绍 Uniswap v3 的源代码。但是由于 Uniswap v3 的代码极其庞大，所以我们无法像介绍 v2 那样逐行进行分析，本文主要从阅读 [白皮书](https://app.uniswap.org/whitepaper-v3.pdf) 及相关代码的视角展开。

假如读者希望体验自己动手实现 Uniswap v3 的话，建议观看此 [Youtube 系列视频](https://youtube.com/playlist?list=PLO5VPQH6OWdXp2_Nk8U7V-zh7suI05i0E&si=9qOZLLPs8WxXs1Cm)。笔者就是依靠该系列视频完整学习了 Uniswap v3 的代码。另一个学习 Uniswap v3 的材料是笔者之前编写的博客 [现代 DeFi: Uniswap V3](https://blog.wssh.dev/posts/uniswap-v3/)。

## ARCHITECTURAL CHANGES

在白皮书内，该节主要介绍了 Uniswap v3 相比于 v2 在架构上的创新，主要介绍了以下内容:

1. 允许 Pair 存在多个不同费率的 Pool。在 v2 中，每一个 Pair 只有一个硬编码的费率
2. 区间流动性提供

### Multiple Pools Per Pair

在 Uniswap v2 中，我们使用如下代码直接收取流动性手续费，此处的手续费比例 25 bps 是硬编码的，我们无法在 `factor` 内进行设置。

```solidity
uint256 balance0Adjusted = balance0 * 10000 - amount0In * 25
```

但在 Uniswap v3 中，我们可以在 `contracts/UniswapV3Factory.sol` 内看到 `createPool` 内的实现已经包含了 `fee` 字段:

```solidity
/// @inheritdoc IUniswapV3Factory
function createPool(
    address tokenA,
    address tokenB,
    uint24 fee
) external override noDelegateCall returns (address pool) {
    require(tokenA != tokenB);
    (address token0, address token1) = tokenA < tokenB ? (tokenA, tokenB) : (tokenB, tokenA);
    require(token0 != address(0));
    int24 tickSpacing = feeAmountTickSpacing[fee];
    require(tickSpacing != 0);
    require(getPool[token0][token1][fee] == address(0));
    pool = deploy(address(this), token0, token1, fee, tickSpacing);
    getPool[token0][token1][fee] = pool;
    // populate mapping in the reverse direction, deliberate choice to avoid the cost of comparing addresses
    getPool[token1][token0][fee] = pool;
    emit PoolCreated(token0, token1, fee, tickSpacing, pool);
}
```

此处需要注意 `fee` 并不是可以任意指定的，而是与 `tickSpacing` 是挂钩的。`tickSpacing` 实际上代表了添加区间流动性时的最小价格间隔，简单来说，`tickSpacing` 越小，那么用户添加流动性的颗粒度越高，用户可以选择流动性上下限更加精确，比如 `tickSpacing = 10`，那么用户可以选择作为流动性区间边界的 ticks 值位于 $(\dots, -20, -10, 0, 10, 20, \dots)$ 内，而 `tickSpacing = 1`，那么用户可以选择的 ticks 位于 $(\dots,-2,-1,0,1,2,\dots)$ 范围内。但是反之在 Uniswap v3 进行 swap 时，由于 `tickSpacing` 较小，那么可以被放置流动性的点位就更多，所以 v3 需要循环更多次以搜索可用的流动性。

一般来说，`tickSpacing` 越小，意味着预期 Pair 内的价格变动越小，比如 `tickSpacing = 1` 一般被用于稳定币交易对。价格波动小，流动性提供者应该获得更低的手续费，所以 Uniswap v3 在 Factory 内硬编码了几个 `tickSpacing` 与 `fee` 的对应关系，具体如下表(数据来源为 [Unisawp 文档](https://docs.uniswap.org/contracts/v4/quickstart/create-pool#1-configure-the-pool)):

| Fee   | Fee Value | Tick Spacing |
| ----- | --------- | ------------ |
| 0.01% | 100       | 1            |
| 0.05% | 500       | 10           |
| 0.30% | 3000      | 60           |
| 1.00% | 10_000    | 200          |

对于 `createPool` 的具体实现，读者可以自行阅读相关代码，与 uniswap v2 一致，v3 也使用了 `create2` 确定性地址部署方法，部署的具体代码位于 `UniswapV3PoolDeployer` 内部:

```solidity
parameters = Parameters({factory: factory, token0: token0, token1: token1, fee: fee, tickSpacing: tickSpacing});
pool = address(new UniswapV3Pool{salt: keccak256(abi.encode(token0, token1, fee))}());
```

这意味着任何代币 Pair 的 v3 地址都可以被预先计算出来，这对于一些创建 Pair 后进行自动交易的协议产生了威胁，比如 Four.meme 在过去使用了 v3 作为代币发射后的交易平台，但是由于代币 Pair 地址可以预先计算，所以黑客在 foure.meme 自动部署 Pair 前抢先部署了 Pair 然后使用不合理价格初始化，导致 four.meme 转移流动性时出现损失，具体可以 DeFiHackLabs 的 [PoC](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2025-02/FourMeme_exp.sol)。

关于具体的 tickSpacing 的使用和遍历方法，我们会在后文内介绍 ticks 概念及相关代码时一并分析。

### Non-Fungible Liquidity

非同质的流动性其实就是区间流动性的另一种表达方法，但是需要注意在 Uniswap v3 的核心合约内并不存在 ERC721 的部分，大家经常看到的使用 ERC721 表示区间流动性其实只是一个辅助功能，相关代码位于 `v3-peripher` 的 [NonfungiblePositionManager](https://github.com/Uniswap/v3-periphery/blob/main/contracts/NonfungiblePositionManager.sol) 内部。

在 v3-core 内部，用户提供的流动性被存储在 `positions` 状态变量内部，该状态变量的定义是:

```solidity
mapping(bytes32 => Position.Info) public override positions;
```

关于上述 mapping 内 `bytes32` 含义，我们可以参考 `contracts/libraries/Position.sol` 内的 `get` 函数:

```solidity
function get(
    mapping(bytes32 => Info) storage self,
    address owner,
    int24 tickLower,
    int24 tickUpper
) internal view returns (Position.Info storage position) {
    position = self[keccak256(abi.encodePacked(owner, tickLower, tickUpper))];
}
```

通过上述 `get` 函数，我们可以看到在 `v3-core` 内，我们通过 `owner` / `tickLower` 和 `tickUpper` 确定某一个用户的某一个流动性头寸。而 `Position.Info` 的具体定义为:

```solidity
struct Info {
    // the amount of liquidity owned by this position
    uint128 liquidity;
    // fee growth per unit of liquidity as of the last update to liquidity or fees owed
    uint256 feeGrowthInside0LastX128;
    uint256 feeGrowthInside1LastX128;
    // the fees owed to the position owner in token0/token1
    uint128 tokensOwed0;
    uint128 tokensOwed1;
}
```

此处的 `liquidity` 代表用户持有的流动性数量，我们常使用 `liquidity` 计算对应的 `token0` 和 `token1` 的数量。`feeGrowthInside0LastX128` 和 `feeGrowthInside1LastX128` 都是用于计算 LP 应获得的手续费收入的，该部分逻辑较为复杂，我们会在后文介绍手续费逻辑时详细介绍。而 `tokensOwed0` 和 `tokensOwed1` 代表实际的手续费，每次更新 LP 头寸时，合约会自动使用 `feeGrowthInside0LastX128` 和 `feeGrowthInside1LastX128` 计算手续费收入，然后累加到 `tokensOwed0` 和 `tokensOwed1` 内部。

我们首先回到 `Info` 结构体内的 `liquidity` 计算。该部分计算由 `contracts/libraries/SqrtPriceMath.sol` 内的 `getAmount0Delta` 和 `getAmount1Delta` 完成。这两个函数基本都是纯粹的数学函数，具体形式如下:

![Uniswap v3 liquidity to amount delta](https://img.gopic.xyz/uniswapV3LiquidityToDelta.png)

上述的 $i_c$ 是当前 Pair 内的价格(即 `slot0.tick`)，而 $i_l$ 和 $i_u$ 分别代表 `tickLower` 和 `tickUpper`。限于篇幅，我们无法介绍这两个函数背后依赖的数学公式的推导流程，读者可以参考 [LIQUIDITY MATH IN UNISWAP V3](https://atiselsts.github.io/pdfs/uniswap-v3-liquidity-math.pdf) 这篇论文内的推导。读者可能会注意到对于上述公式中 $\Delta Y$ 而言，$i_c \ge i_u$ 可以被视为 $i_l \le i_c < i_u$ 的一种特殊情况，即 $P = p(i_u)$ 的情况。对于 $\Delta X$ 而言同理，这就是为什么在 `SqrtPriceMath` 内部只存在两个函数 `getAmount0Delta` 和 `getAmount1Delta`，而不是存在四个函数。

基于上述知识，读者不难看懂 `_modifyPosition` 内的核心逻辑:

```solidity
function _modifyPosition(ModifyPositionParams memory params)
    private
    noDelegateCall
    returns (
        Position.Info storage position,
        int256 amount0,
        int256 amount1
    )
{
    checkTicks(params.tickLower, params.tickUpper);

    Slot0 memory _slot0 = slot0; // SLOAD for gas optimization

    position = _updatePosition(
        params.owner,
        params.tickLower,
        params.tickUpper,
        params.liquidityDelta,
        _slot0.tick
    );

    if (params.liquidityDelta != 0) {
        if (_slot0.tick < params.tickLower) {
            // current tick is below the passed range; liquidity can only become in range by crossing from left to
            // right, when we'll need _more_ token0 (it's becoming more valuable) so user must provide it
            amount0 = SqrtPriceMath.getAmount0Delta(
                TickMath.getSqrtRatioAtTick(params.tickLower),
                TickMath.getSqrtRatioAtTick(params.tickUpper),
                params.liquidityDelta
            );
        } else if (_slot0.tick < params.tickUpper) {
            // current tick is inside the passed range
            uint128 liquidityBefore = liquidity; // SLOAD for gas optimization

            // write an oracle entry
            (slot0.observationIndex, slot0.observationCardinality) = observations.write(
                _slot0.observationIndex,
                _blockTimestamp(),
                _slot0.tick,
                liquidityBefore,
                _slot0.observationCardinality,
                _slot0.observationCardinalityNext
            );

            amount0 = SqrtPriceMath.getAmount0Delta(
                _slot0.sqrtPriceX96,
                TickMath.getSqrtRatioAtTick(params.tickUpper),
                params.liquidityDelta
            );
            amount1 = SqrtPriceMath.getAmount1Delta(
                TickMath.getSqrtRatioAtTick(params.tickLower),
                _slot0.sqrtPriceX96,
                params.liquidityDelta
            );

            liquidity = LiquidityMath.addDelta(liquidityBefore, params.liquidityDelta);
        } else {
            // current tick is above the passed range; liquidity can only become in range by crossing from right to
            // left, when we'll need _more_ token1 (it's becoming more valuable) so user must provide it
            amount1 = SqrtPriceMath.getAmount1Delta(
                TickMath.getSqrtRatioAtTick(params.tickLower),
                TickMath.getSqrtRatioAtTick(params.tickUpper),
                params.liquidityDelta
            );
        }
    }
}
```

对于 `_updatePosition` 函数，该函数内部存在一些与流动性手续费计算的内容，在该函数内完成了上文介绍的 `feeGrowthInside0LastX128` / `feeGrowthInside1LastX128` 计算后累加到 `tokensOwed0` 和 `tokensOwed1` 的过程，在后文分析手续费逻辑时，我们会再次讨论。

对于后续的 `liquidityDelta` 向 `amount0` 和 `amount1` 的转换，结合上述公式，读者应该可以理解。比如对于 `_slot0.tick < params.tickLower` 即 $i_c < i_l$ 的情况，此时 $\Delta Y = 0$ 即 `amount1 = 0`，我们只需要调用函数计算 `amount0` 的数值。对于 `else if (_slot0.tick < params.tickUpper)`，该分支意味着 $i_l \le i_c < i_u$，所以我们需要分别计算 `amount0` 和 `amount1` 的数值。

上述函数中的 `getSqrtRatioAtTick` 是将 `tick` 转化为 $\sqrt{p}$ 的函数，本质上实现了以下数学公式:
$$
\sqrt{p}(i) = \sqrt{1.0001}^i = 1.0001^{\frac{i}{2}}
$$
实际上这也是 tick 与价格之间关系。我们会经常使用 `getSqrtRatioAtTick` 和 `getTickAtSqrtRatio` 函数，前者用于 tick 转化价格(后文所有的价格均指 $\sqrt{p}$ ，这是因为 uniswap v3 内不存在其他形式的价格)，而后者用于价格转化为 tick。

在 Uniswap v3 内，与流动性直接相关的函数包括:

1. `mint` 函数用于添加流动性
2. `burn` 函数用于提取流动性及 LP 获得的手续费
3. `collect` 函数用于提取 LP 手续费

其中 `collect` 函数实现最为简单，依赖上文介绍的 `Position.Info` 内的 `tokensOwed0` 和 `tokensOwed1` 字段，代码如下:

```solidity
function collect(
    address recipient,
    int24 tickLower,
    int24 tickUpper,
    uint128 amount0Requested,
    uint128 amount1Requested
) external override lock returns (uint128 amount0, uint128 amount1) {
    // we don't need to checkTicks here, because invalid positions will never have non-zero tokensOwed{0,1}
    Position.Info storage position = positions.get(msg.sender, tickLower, tickUpper);

    amount0 = amount0Requested > position.tokensOwed0 ? position.tokensOwed0 : amount0Requested;
    amount1 = amount1Requested > position.tokensOwed1 ? position.tokensOwed1 : amount1Requested;

    if (amount0 > 0) {
        position.tokensOwed0 -= amount0;
        TransferHelper.safeTransfer(token0, recipient, amount0);
    }
    if (amount1 > 0) {
        position.tokensOwed1 -= amount1;
        TransferHelper.safeTransfer(token1, recipient, amount1);
    }

    emit Collect(msg.sender, recipient, tickLower, tickUpper, amount0, amount1);
}
```

而 `burn` 函数复杂度也很低，代码如下:

```solidity
function burn(
    int24 tickLower,
    int24 tickUpper,
    uint128 amount
) external override lock returns (uint256 amount0, uint256 amount1) {
    (Position.Info storage position, int256 amount0Int, int256 amount1Int) =
        _modifyPosition(
            ModifyPositionParams({
                owner: msg.sender,
                tickLower: tickLower,
                tickUpper: tickUpper,
                liquidityDelta: -int256(amount).toInt128()
            })
        );

    amount0 = uint256(-amount0Int);
    amount1 = uint256(-amount1Int);

    if (amount0 > 0 || amount1 > 0) {
        (position.tokensOwed0, position.tokensOwed1) = (
            position.tokensOwed0 + uint128(amount0),
            position.tokensOwed1 + uint128(amount1)
        );
    }

    emit Burn(msg.sender, tickLower, tickUpper, amount, amount0, amount1);
}
```

在此处，我们需要补充在上文内没有介绍的 `liquidityDelta` 是 `int128` 类型，数值为正数代表流动性添加，而为负数代表流动性减少。注意，即使包含符号，上述给出的所有数学公式也是成立的。在 Uniswap v3 和 Uniswap v4 中，开发团队经常使用 `int` 类型并使用正负代表不同的含义，以此简化数学计算。比如在 Uniswap v3 中，另一个重要的存在符号的变量是 `swap` 函数中的 `amountSpecified`，其符号含义可以从 `bool exactInput = amountSpecified > 0;` 代码内看出。该数值为正数，代表 `exactInput` 模式，即用户指定输入代币的数量，要求 Pool 计算输出代币的数量；与之相反的是 `exactOut` 模式，即用户给定输出代币的数量，要求 Pool 计算输入代币的数量。另外，`swap` 函数的输出值 `amount0` 和 `amount1` 也是包含符号的，其含义为假如 `amount < 0`，那么合约就会将对应数量的代币发送给用户，代码如下:

```solidity
if (zeroForOne) {
    if (amount1 < 0) TransferHelper.safeTransfer(token1, recipient, uint256(-amount1));
```

上述代码内的 `zeroForOne` 也是 `swap` 的重要入参，用于指定代币兑换的情况，比如 `zeroForOne = true` 意味着用户希望给出输入 token0 并获得 token1 代币。这意味着 `zeroForOne` 是对用户而言，站在 Pool 的角度，`zeroForOne` 反而意味着输出 token0 代币并从用户处获得 token1 代币。对于最初接触 Uniswap v3 代码的读者，由于长时间阅读 Pool 合约，很容易站在 Pool 的角度思考问题，对于 `zeroForOne` 的含义时常搞反。

最后，我们介绍稍微复杂一些的 `mint` 函数，该函数体现了 Uniswap v3 内是如何处理代币转移问题的:

```solidity
function mint(
    address recipient,
    int24 tickLower,
    int24 tickUpper,
    uint128 amount,
    bytes calldata data
) external override lock returns (uint256 amount0, uint256 amount1) {
    require(amount > 0);
    (, int256 amount0Int, int256 amount1Int) =
        _modifyPosition(
            ModifyPositionParams({
                owner: recipient,
                tickLower: tickLower,
                tickUpper: tickUpper,
                liquidityDelta: int256(amount).toInt128()
            })
        );

    amount0 = uint256(amount0Int);
    amount1 = uint256(amount1Int);

    uint256 balance0Before;
    uint256 balance1Before;
    if (amount0 > 0) balance0Before = balance0();
    if (amount1 > 0) balance1Before = balance1();
    IUniswapV3MintCallback(msg.sender).uniswapV3MintCallback(amount0, amount1, data);
    if (amount0 > 0) require(balance0Before.add(amount0) <= balance0(), 'M0');
    if (amount1 > 0) require(balance1Before.add(amount1) <= balance1(), 'M1');

    emit Mint(msg.sender, recipient, tickLower, tickUpper, amount, amount0, amount1);
}
```

我们可以看到与 Uniswap v2 一致，在 Uniswap v3 内，我们仍使用了 Callback 的方法通知交易者支付资产，然后利用余额判断用户输入的代币数量是否足够。

## IMPLEMENTING CONCENTRATED LIQUIDITY

我们跳过了白皮书内关于治理和 Oracle 的两节内容，对于治理部分，这部分与核心功能关联较少，而 Oracle 部分其实被大量嵌入了核心的代码，但是 Oracle 部分稍微有一些复杂，我们可能会在未来单独编写一篇文章介绍，但假如读者对如何在 Uniswap v3 基础上实现流动性挖矿感兴趣，Oracle 部分是一定要读的。

本节内容在白皮书内主要介绍 Uniswap v3 的区间流动性提供是如何实现的，主要介绍了以下内容：

1. Tick 和 Tick Spacing 机制，在上文稍有介绍，但在本节中，我们要解决如何查找下一个 tick 的任务
2. 流动性计算机制，介绍 Uniswap v3 Pool 如何实时监控系统内的流动性，特别是在 `swap` 过程中穿过某一个 tick 后如何进行计算(cross tick)
3. 手续费机制，在上一节中我们忽视了此内容，在本节中，我们将介绍手续费是如何累计和计算的，将涉及到部分 `swap` 内的代码，但主要代码仍位于 `Position` 及其相关部分
4. Swap 内的具体计算，结合上述 cross tick 机制，我们可以获得当前的流动性数值，然后就可以完成 swap 的其他部分

本节内容将不完全与白皮书内的内容对应。

###  Ticks and Ranges

在上文，我们已经介绍了如下数学公式:
$$
\sqrt{p}(i) = \sqrt{1.0001}^i = 1.0001^{\frac{i}{2}}
$$
用户提交的流动性都存在 tickLower($i_l$) 和 tickUpper($i_u$) 两个核心参数。每一个 Pool 在初始化时就会选定 `tickSpacing` 作为核心参数。在上文中，我们介绍了 `tickSpacing` 与手续费之间的映射关系，但 `tickSpacing` 在初始化时会被用于计算另一个数值 `maxLiquidityPerTick`，该数值代表每一个 tick 上可以容纳的最大流动性数量，计算方法如下:

```solidity
function tickSpacingToMaxLiquidityPerTick(int24 tickSpacing) internal pure returns (uint128) {
    int24 minTick = (TickMath.MIN_TICK / tickSpacing) * tickSpacing;
    int24 maxTick = (TickMath.MAX_TICK / tickSpacing) * tickSpacing;
    uint24 numTicks = uint24((maxTick - minTick) / tickSpacing) + 1;
    return type(uint128).max / numTicks;
}
```

首先，我们需要明确在 Uniswap v3 内记录当前 Pool 的流动性的变量 `uint128 public override liquidity;` 的类型是 `uint128`，所以我们接下来的任务是计算当前系统内到底存在多少在当前 `tickSpacing` 下有效的 tick，具体分为两步:

1. 确认当前 tickSpacing 下有效的最小 tick 和最大 tick，注意都需要向 0 舍入，避免计算出的结果小于 `TickMath.MIN_TICK` 或者大于 `TickMath.MAX_TICK`。代码中的 `TickMath.MIN_TICK / tickSpacing` 内的除法是向 0 舍入的，所以此处计算出的结果已经完成向 0 舍入
2. 使用计算出的 `minTick` 和 `maxTick` 的差值计算 `numTicks`，使用 `(maxTick - minTick) / tickSpacing` 但是此处存在经典的 [Fencepost error](https://en.wikipedia.org/wiki/Off-by-one_error)，即间隔与个数差 1，所以最终的计算方法就是代码内的方法

那么计算出的常量 `maxLiquidityPerTick` 如何使用? 在 `contracts/libraries/Tick.sol` 内的 `update` 函数展示了该常量的用法:

```solidity
Tick.Info storage info = self[tick];

uint128 liquidityGrossBefore = info.liquidityGross;
uint128 liquidityGrossAfter = LiquidityMath.addDelta(liquidityGrossBefore, liquidityDelta);

require(liquidityGrossAfter <= maxLiquidity, 'LO');

flipped = (liquidityGrossAfter == 0) != (liquidityGrossBefore == 0);
```

上述代码内的 `maxLiquidity` 就是传入的 `maxLiquidityPerTick` 常量。在 `Tick.Info` 内存在 `liquidityGross` 变量，记录当前 tick 内的流动性总量，每次用户进行流动性调整都会更新该变量。显然，假如每一个 tick 的 `liquidityGross < maxLiquidityPerTick`，那么流动性总和不可能大于 `type(uint128).max`。此处额外注意 `liquidityGross` 与当前系统内活跃的流动性并不等同，比如下图中的一个用户在 tick 0 - tick3 之间添加了流动性，此时 tick 2 的 `liquidityGross = 0`，但并不代表此处没有流动性。我们会在下一节内详细介绍如何计算每一个区间的真实流动性。 

![Uniswap v3 Gross](https://img.gopic.xyz/UniswapV3Gross.svg)

上述代码中的 `flipped` 也是 `liquidityGross` 存在的重要原因，`flipped` 代表某一个 tick 是否需要“翻转”，更加具体说，是否需要从完成初始化状态修改为未初始化状态，或者反之从未初始化状态修改为初始化状态。假如当前 tick 需要 `flipTick`，那么我们就会调用 `tickBitmap.flipTick` 函数。

`tickBitmap` 是我们在本节要介绍的核心数据类型之一。回到上图，假如当前价格位于 tick 0 与 tick 1 之间，Swap 的计算实际上也使用了上文介绍的 `getAmount0Delta` 或 `getAmount1Delta` 函数，这些函数要求给定当前价格与下一个价格，在上图中，下一个价格指的是 `tick 3`，因为中间的 `tick 2` 是未初始化的，所以不需要考虑。那么如何基于当前价格搜索到下一个价格，这对应 `tickBitmap.nextInitializedTickWithinOneWord` 函数。

`tickBitmap` 是一个可以容纳 1774545 bit 的序列(tick 所在地范围为 $[−887272,887272]$，总共存在 1774545 个 tick)。但是显然在 solidity 内没有一个长度如此长的数据类型，所以 Uniswap v3 的开发团队使用了分组方法，设置了 2 ** 16 个分组，每一个分组都是 256 bit 长度，即:

```solidity
mapping(int16 => uint256) public override tickBitmap;
```

我们可以使用 `wordPos = int16(tick >> 8);` 快速定位 `tick` 位于的分组序号，使用 `bitPos = uint8(tick % 256);` 计算出在分组内的具体位置，实际上也就是 `contracts/libraries/TickBitmap.sol` 内的 `position` 函数。使用该函数，我们可以快速实现 `flipTick`，具体实现就是定位到需要翻转的 bit 在 `tickBitmap` 的 position 然后使用 XOR 函数写入:

```solidity
function flipTick(
    mapping(int16 => uint256) storage self,
    int24 tick,
    int24 tickSpacing
) internal {
    require(tick % tickSpacing == 0); // ensure that the tick is spaced
    (int16 wordPos, uint8 bitPos) = position(tick / tickSpacing);
    uint256 mask = 1 << bitPos;
    self[wordPos] ^= mask;
}
```

从上述代码内，我们可以看到我们会将 `tick` 使用 `tick / tickSpacing` 进行修正再进行写入，这其实意味着对于 `tickSpacing` 设置较大的 Pool，其内部的 `TickBitmap` 被占用的 bit 会越少。

然后我们介绍如何根据当前 tick 搜索下一个价格，注意此处使用的 `nextInitializedTickWithinOneWord` 获得的并不一定是下一个已经被初始化的 tick，正如函数名称中的 `WithinOneWord` ，该函数只是返回当前分组(word) 内的下一个初始化 tick，假如当前分组内没有任何初始化的 tick，那么返回值是当前分组的末尾 tick。此处的末尾有两种不同的情况:

1. 对于向左搜索的情况，寻找小于或者等于当前 `tick` 的位于当前 `word` 的 next tick
2. 对于向右搜索的情况，寻找大于当前 `tick` 且位于当前 `word` 的 next ticl

我们以向左搜索为例，代码如下:

```solidity
int24 compressed = tick / tickSpacing;
if (tick < 0 && tick % tickSpacing != 0) compressed--; // round towards negative infinity

if (lte) {
    (int16 wordPos, uint8 bitPos) = position(compressed);
    // all the 1s at or to the right of the current bitPos
    uint256 mask = (1 << bitPos) - 1 + (1 << bitPos);
    uint256 masked = self[wordPos] & mask;

    // if there are no initialized ticks to the right of or at the current tick, return rightmost in the word
    initialized = masked != 0;
    // overflow/underflow is possible, but prevented externally by limiting both tickSpacing and tick
    next = initialized
        ? (compressed - int24(bitPos - BitMath.mostSignificantBit(masked))) * tickSpacing
        : (compressed - int24(bitPos)) * tickSpacing;
```

这段代码的核心难点是如何处理舍入问题。我们可以看到 `int24 compressed = tick / tickSpacing;` 是向 0 舍入的，但是为了保证 bitmap 的连续性，我们利用 `if (tick < 0 && tick % tickSpacing != 0) compressed--;` 将不是 tickSpacing 整数倍的 `tick` 向下舍入。假如此处不进行上述操作，那么会导致 0 两侧的正负数 tick 进行除法计算后结果都为 0，这会导致 bitmap 的不连续。

然后我们构建一个以当前 `bitPos` 最为最右侧位，且 `bitPos` 左侧都为 `1` 的 mask 序列，举例说明:

```
bitPos = 3
mask = 0b1111
```

获得 `mask` 后，我们需要将当前 word 与 mask 进行异或操作，获得的结果是只包含当前 bitPos 及其左侧 bit 的序列。假如异或后的结果为 `0` 意味着当前 word 内已经不存在下一个初始化的 tick，我们只需要执行 `(compressed - int24(bitPos)) * tickSpacing` 操作直接获得当前 word 最左侧的 tick 返回即可。部分读者可能好奇为什么此处不能直接返回 `0`，这是因为返回的 `tick` 应该是包含 `wordPos` 和 `bitPos`，确实 word 中最右侧的 tick 的 `bitPos = 0`，但是我们不能忽略 `wordPos`，所以最简单的计算方法就是 `(compressed - int24(bitPos)) * tickSpacing`

假如异或后的结果不为 `0` ，那么就说明当前 word 内在指定 tick 的自身及其左侧存在一些已经被初始化的 tick。我们接下来的任务是找到该 tick。该任务等同为寻找异或结果中的最右侧且值为 `1` 的 bit 的位置。在计算机领域，该任务被称为 `mostSignificantBit`。假如读者对该算法内部实现感兴趣，可以阅读笔者之前编写的 [现代 DeFi: Uniswap V4 数学库分析](https://blog.wssh.dev/posts/uniswap-math/) 内的介绍。所以我们可以使用 `(compressed - int24(bitPos - BitMath.mostSignificantBit(masked))) * tickSpacing` 计算出寻找到下一个 word 内已初始化的 tick。

注意，在上文中，我们对于 `lte` 向左搜索的表述是找到小于等于当前 tick 的下一个 tick，所以该函数返回值有可能就是输入的 `tick`，对于这种情况，实际上 `swap` 函数是可以处理的，但是会导致一次 `swap` 循环的空转(即此次 swap 循环不消耗任何输入代币且不产生任何输出)，假如读者在 swap 时追求极致的 gas 效率，请考虑这种情况的影响。

对于另一种向右搜索的情况，读者可以自行研究，这种情况就永远不会返回输入的 `tick`，只会返回大于当前 `tick` 的最小 tick。实际以下代码中的 `+ 1` 保证了永远不会返回输入的 `compressed` 数值。

```solidity
next = initialized
    ? (compressed + 1 + int24(BitMath.leastSignificantBit(masked) - bitPos)) * tickSpacing
    : (compressed + 1 + int24(type(uint8).max - bitPos)) * tickSpacing;
```

### 流动性计算

在本节中，我们暂时脱离白皮书的内容，因为对于 Pool 内的流动性，我们会涉及到 **Global State** 和 **Tick-Indexed State** 的内容。众所周知，在 swap 过程中，我们依赖于 $L$ 即当前系统内的流动性数量计算代币 swap 后的输出等。在 Pool 层面，我们使用 `uint128 public override liquidity;` 来跟踪该数值。由于 Uniswap v3 使用了区间流动性方法，经常出现多个 LP 头寸都为当前流动性进行了贡献的情况，比如下图中的 LP #0 / LP #1 与 LP #2 都为当前的价格贡献了流动性:

![Uniswap v3 multi lp](https://img.gopic.xyz/UniswapV3MultiLP.svg)

所以我该如何正确更新当前价格可用的流动性？最简单的情况是修改流动性头寸时，比如用户直接修改了上图中 LP #0 内的流动性数量，此时我们会直接在全局变量 `liquidity` 内进行修改。在 `_modifyPosition` 内，我们可以看到如下代码:

```solidity
liquidity = LiquidityMath.addDelta(liquidityBefore, params.liquidityDelta);
```

除了这种直接在修改流动性时进行的 `liquidity` 更新，更加常见的是由于 swap 出现价格变化而进一步导致部分流动性变化，下图展示 $L_1$ 和 $L_2$ 两部分流动性，其中 $L_1$ 占据了 a - c 区间，而 $L_2$ 占据了 b - d 区间。假如价格当前穿过 `c` 价格，那么 $L_1$ 就会失效，而 $L_2$ 仍发挥作用。

![Tick with liquidity](https://img.gopic.xyz/tick-mange.webp)

那么在存在大量 LP 的情况下， Uniswap v3 如何计算出当前有效的 LP 贡献的总流动性数量？实际上，Uniswap v3 在 `Tick.Info` 结构体内存储了 `liquidityNet` 变量。该变量表示当前 tick 从左往右穿过对全局流动性的变化。以上图为例，我们假设最初 Pool 内的价格位于 a 的左侧，那么当价格从左往右移动穿过 `a` 时，liquidity 增加 500，这其实代表着 $L_1$ 已经生效，当价格继续向右移动穿过 `b` 时，liquidity 再次增加 700，因为此时 $L_2$ 生效；但价格继续向右移动穿过 `c` 时，liquidity 会减少 500，这是因为 $L_1$ 已经失效。

我们可以看到只需要在每次修改 LP 的流动性时，将当前流动性修改数量增加到 `tickLower` ，而将修改数量的相反数增加到 `tickUpper` 即可。如此就可以实现价格自左向右穿过 `tickLower` 时，自动增加当前的流动性修改，而自左向右穿过 `tickUpper` 时，减少当前的流动性修改。

在 `contracts/libraries/Tick.sol` 内，我们可以看到 `update` 函数的如下实现:

```solidity
info.liquidityNet = upper
    ? int256(info.liquidityNet).sub(liquidityDelta).toInt128()
    : int256(info.liquidityNet).add(liquidityDelta).toInt128();
```

其中 `upper` 是一个表示当前 tick 是否是 LP 的 `tickUpper`。接下来，我们要实现穿过 tick 后根据 tick 内的 `liquidityNet` 数据修改 `liquidity` 变量的代码。在 `UniswapV3Pool` 内的 `swap` 函数内，我们可以看到如下代码:

```solidity
int128 liquidityNet =
    ticks.cross(
        step.tickNext,
        (zeroForOne ? state.feeGrowthGlobalX128 : feeGrowthGlobal0X128),
        (zeroForOne ? feeGrowthGlobal1X128 : state.feeGrowthGlobalX128),
        cache.secondsPerLiquidityCumulativeX128,
        cache.tickCumulative,
        cache.blockTimestamp
    );
// if we're moving leftward, we interpret liquidityNet as the opposite sign
// safe because liquidityNet cannot be type(int128).min
if (zeroForOne) liquidityNet = -liquidityNet;

state.liquidity = LiquidityMath.addDelta(state.liquidity, liquidityNet);
```

此处的 `tick.cross` 就是一个处理 tick 被穿过的函数，该函数内部大部分内容都是与流动性手续费计算有关的，我们会在下一节分析。在上文中，我们介绍了从左往右穿过 tick 是在 `liquidity` 基础上增加 `liquidityNet`，反之，从右往左穿过 tick 就会减少 `liquidityNet`。`zeroForOne` 代表用户使用 token 0 换取 token 1，对于 Pool 来说会支出 token 1 获得 token 0，根据价格计算方法：
$$
\sqrt{P} = \sqrt{\frac{y}{x}}
$$
其中 $y$ 代表 token 1 的数量而 $x$ 代表 token 0 的数量，显然，`zeroForOne` 会似的价格下降，即从右往左穿过 tick，所以此处存在 `if (zeroForOne) liquidityNet = -liquidityNet;` 的代码。

此处

### 手续费计算

Uniswap v3 的手续费计算是一个较为复杂的内容，这部分内容的特点是数学公式较为简单，但背后的数学原理很难理解。为了简化本文，我们只介绍数学公式及其实现，对于数学原理，笔者在 [博客](https://blog.wssh.dev/posts/uniswap-v3/#%E6%89%8B%E7%BB%AD%E8%B4%B9%E8%AE%A1%E7%AE%97) 中给出了推导分析。本节的内容基本上与白皮书内的 **Tick-Indexed State** 一节有关。在后文中，如无特殊说明，所有的手续费都是指 LP 由于提供流动性以供交易者交易而获得的交易手续费。

在 `Tick.Info` 结构体内的 `feeGrowthOutside0X128` 和 `feeGrowthOutside1X128` 都与手续费计算有关，前者与 token 0 的手续费计算有关，而后者与 token 1 的手续费计算有关，在数学表达式内，我们一般使用 $f_o(i)$ 表示。从经济含义上，我们认为 $f_o$ 表示当前 tick 一侧所有 tick 历史累计的手续费总量。我们定义对于小于当前价格的 tick，$f_o(i)$ 的含义为:

![i Above](https://img.gopic.xyz/UniswapV3FoiAbove.webp)

即当前 tick i 右侧累计的所有手续费。反之，$f_o(i)$ 代表当前左侧累计的所有手续费:

![i below](https://img.gopic.xyz/UniswapV3FoiBelow.webp)

基于上述定义，我们引入代表当前 tick 右侧(above) 累计手续费 $f_a(i)$ 和当前 tick 左侧(below) 累计的手续费 $f_b(i)$ 两个公式:
$$
f_a(i) = \begin{cases}
f_g - f_o(i) &i_c \geq i \\\\
f_o(i) & i_c < i
\end{cases}
$$

$$
f_b(i) = \begin{cases}
f_o(i) &i_c \geq i \\\\
f_g - f_o(i) & i_c < i
\end{cases}
$$

另外，在 Pool 的状态中，我们会使用 `feeGrowthGlobal0X128` 和 `feeGrowthGlobal0X128` 记录全局手续费，在数学表达式内，我们一般使用 $f_g$ 表示。显然，对于任何情况，都存在 $f_g - f_a(i_u) - f_b(i_l)$ 代表当前价格区间的手续费，我们可以使用下图理解:

![Current Fee internal](https://img.gopic.xyz/UniswapFeeCurrent.svg)

所以，在代码中，我们首先计算 $f_b(i_l)$ 和 $f_a(i_u)$ 的值:

```solidity
// calculate fee growth below
uint256 feeGrowthBelow0X128;
uint256 feeGrowthBelow1X128;
if (tickCurrent >= tickLower) {
    feeGrowthBelow0X128 = lower.feeGrowthOutside0X128;
    feeGrowthBelow1X128 = lower.feeGrowthOutside1X128;
} else {
    feeGrowthBelow0X128 = feeGrowthGlobal0X128 - lower.feeGrowthOutside0X128;
    feeGrowthBelow1X128 = feeGrowthGlobal1X128 - lower.feeGrowthOutside1X128;
}

// calculate fee growth above
uint256 feeGrowthAbove0X128;
uint256 feeGrowthAbove1X128;
if (tickCurrent < tickUpper) {
    feeGrowthAbove0X128 = upper.feeGrowthOutside0X128;
    feeGrowthAbove1X128 = upper.feeGrowthOutside1X128;
} else {
    feeGrowthAbove0X128 = feeGrowthGlobal0X128 - upper.feeGrowthOutside0X128;
    feeGrowthAbove1X128 = feeGrowthGlobal1X128 - upper.feeGrowthOutside1X128;
}
```

最后，使用公式 $f_g - f_a(i_u) - f_b(i_l)$ 计算当前区间手续费情况:
```solidity
feeGrowthInside0X128 = feeGrowthGlobal0X128 - feeGrowthBelow0X128 - feeGrowthAbove0X128;
feeGrowthInside1X128 = feeGrowthGlobal1X128 - feeGrowthBelow1X128 - feeGrowthAbove1X128;
```

注意，其实上述所有的计算都是代表单位流动性可以获得的手续费，所以我们最终会使用如下算法计算真正的代币数量:

```solidity
// calculate accumulated fees
uint128 tokensOwed0 =
    uint128(
        FullMath.mulDiv(
            feeGrowthInside0X128 - _self.feeGrowthInside0LastX128,
            _self.liquidity,
            FixedPoint128.Q128
        )
    );
uint128 tokensOwed1 =
    uint128(
        FullMath.mulDiv(
            feeGrowthInside1X128 - _self.feeGrowthInside1LastX128,
            _self.liquidity,
            FixedPoint128.Q128
        )
    );
```

接下来，我们需要确定 tick 内的 `feeGrowthOutside0X128` 和 `feeGrowthOutside1X128` 的更新方法。根据上文中给出的 $f_o$ 的图示，大家不难发现每次 $f_o$ 只有被穿过的时候才会被更新，更新后的数值为 $f_g - f_o$。在 `cross` 的代码中有所体现:

```solidity
info.feeGrowthOutside0X128 = feeGrowthGlobal0X128 - info.feeGrowthOutside0X128;
info.feeGrowthOutside1X128 = feeGrowthGlobal1X128 - info.feeGrowthOutside1X128;
```

最后，我们要确定 tick 的初始化方法。这其实是一个难点，初始化的代码位于 `update` 内部，代码为:

```solidity
if (liquidityGrossBefore == 0) {
    // by convention, we assume that all growth before a tick was initialized happened _below_ the tick
    if (tick <= tickCurrent) {
        info.feeGrowthOutside0X128 = feeGrowthGlobal0X128;
        info.feeGrowthOutside1X128 = feeGrowthGlobal1X128;
    }
    info.initialized = true;
}
```

实际上，从初始化的角度看，tick 内的 `feeGrowthOutside0X128` 和 `feeGrowthOutside1X128` 并不代表真正的 $f_o$，但是实际上初始化的数值并不影响最终的手续费计算。背后的原理是因为手续费计算本质上是增量计算，初始化数值并不影响最终的计算结果。

除了流动性手续费外，实际上 Uniswap v3 也支持收取协议手续费且只对输入代币收取，而对输出代币不收取。但不同于 Uniswap v2，Uniswap v3 内的协议手续费是直接根据 swap 结果收取，而不是转化为 LP。在 Pool 的 `Slot0` 内部，存在 `feeProtocol` 变量，其中该变量的后 4 bit 代表对 token 0 收取的手续费，而前 4 bit 代表对 token 1 收取的手续费。

在 `swap` 函数内，我们可以看到如下代码:

```solidity
SwapCache memory cache =
    SwapCache({
        liquidityStart: liquidity,
        blockTimestamp: _blockTimestamp(),
        feeProtocol: zeroForOne ? (slot0Start.feeProtocol % 16) : (slot0Start.feeProtocol >> 4),
        secondsPerLiquidityCumulativeX128: 0,
        tickCumulative: 0,
        computedLatestObservation: false
    });
```

其中 `feeProtocol: zeroForOne ? (slot0Start.feeProtocol % 16) : (slot0Start.feeProtocol >> 4),` 完成了根据 `zeroForOne` 获得手续费比率的功能。在 swap 过程中，由于区间流动性的存在，单个区间不一定可以满足 swap 的需求，所以 swap 会以循环的方法进行，不断在可用的流动性区间中进行交易，每次交易结果都会存放在 `step` 结构体内，其中 `step.feeAmount` 代表交易过程中流动性手续费，而 `protocolFee` 就会从流动性手续费中拿出一部分，代码如下:

```solidity
if (cache.feeProtocol > 0) {
    uint256 delta = step.feeAmount / cache.feeProtocol;
    step.feeAmount -= delta;
    state.protocolFee += uint128(delta);
}
```

### Swap 过程

我们来到了 Uniswap v3 最核心的部分，就是如何进行 Swap? 我们需要将上述介绍的一系列知识组合起来完成该任务。在白皮书内存在如下经典的流程图:

![Swap Flow](https://img.gopic.xyz/UniswapV3SwapFlow.png)

第一步是检查用户输入的数值以及初始化用于 swap 流程的中间结构体 `SwapState`。对于输入检查，主要是检查用户输入的用于控制滑点的 `sqrtPriceLimitX96` 是否正确。`sqrtPriceLimitX96` 是用户希望 swap 停止的价格，比如当前价格为 1，用户希望将价格推动到 0.9 时就停止 swap，此时就可以将 `sqrtPriceLimitX96` 设置为 0.9。额外的未交易完成的代币会退还给用户。

```solidity
require(
    zeroForOne
        ? sqrtPriceLimitX96 < slot0Start.sqrtPriceX96 && sqrtPriceLimitX96 > TickMath.MIN_SQRT_RATIO
        : sqrtPriceLimitX96 > slot0Start.sqrtPriceX96 && sqrtPriceLimitX96 < TickMath.MAX_SQRT_RATIO,
    'SPL'
);
```

我们在之前提到 `zeroForOne` 会推动 Pool 内的价格下降，所以显然 `sqrtPriceLimitX96` 需要小于当前价格，但要大于最低价格(`MIN_SQRT_RATIO`)，对于 `oneForZero` 的情况同理。

另外，Uniswap v3 也会进行一次防止重入的检查 `require(slot0Start.unlocked, 'LOK');`。最后初始化 `SwapState` 暂存 swap 过程中的中间量:

```solidity
SwapState memory state =
    SwapState({
        amountSpecifiedRemaining: amountSpecified,
        amountCalculated: 0,
        sqrtPriceX96: slot0Start.sqrtPriceX96,
        tick: slot0Start.tick,
        feeGrowthGlobalX128: zeroForOne ? feeGrowthGlobal0X128 : feeGrowthGlobal1X128,
        protocolFee: 0,
        liquidity: cache.liquidityStart
    });
```

其中 `sqrtPriceX96` 和 `tick` 代表当前价格和 tick，而 `feeGrowthGlobalX128` 代表当前全局手续费情况。

接下来，我们进入 swap 的核心循环。第一步是确定 swap 循环退出的条件:

1. 将所有代币兑换完成
2. 将价格推动到 `sqrtPriceLimitX96` 

上述两个条件满足其一就可以退出循环，反之只有两个条件都不满足，那么就需要一直进行 swap 循环:

```solidity
while (state.amountSpecifiedRemaining != 0 && state.sqrtPriceX96 != sqrtPriceLimitX96) {
```

进入 swap 后，我们第一步是找到可供交易的流动性区间，那么首先调用 `tickBitmap.nextInitializedTickWithinOneWord` 就是一个好办法。然后调用 `computeSwapStep` 计算在当前流动性区间内进行交易，交易后到价格、交易需要的代币输入和代币输出以及交易的手续费:

```solidity
(state.sqrtPriceX96, step.amountIn, step.amountOut, step.feeAmount) = SwapMath.computeSwapStep(
    state.sqrtPriceX96,
    (zeroForOne ? step.sqrtPriceNextX96 < sqrtPriceLimitX96 : step.sqrtPriceNextX96 > sqrtPriceLimitX96)
        ? sqrtPriceLimitX96
        : step.sqrtPriceNextX96,
    state.liquidity,
    state.amountSpecifiedRemaining,
    fee
);
```

`SwapMath.computeSwapStep` 接受的参数如下:

```solidity
function computeSwapStep(
    uint160 sqrtRatioCurrentX96,
    uint160 sqrtRatioTargetX96,
    uint128 liquidity,
    int256 amountRemaining,
    uint24 feePips
)
```

其中第二个参数 `sqrtRatioTargetX96` 在 Pool 的 `swap` 函数内构建稍微复杂:

```solidity
(zeroForOne ? step.sqrtPriceNextX96 < sqrtPriceLimitX96 : step.sqrtPriceNextX96 > sqrtPriceLimitX96)
    ? sqrtPriceLimitX96
    : step.sqrtPriceNextX96,
```

上述三目表达式含义如下:

1. 在 `zeroForOne = true` 的情况下
   1. `step.sqrtPriceNextX96 < sqrtPriceLimitX96` 成立，此时返回 `sqrtPriceLimitX96`,
   2. `step.sqrtPriceNextX96 > sqrtPriceLimitX96` 成立，此时返回 `step.sqrtPriceNextX96`
2. 在 `zeroForOne = false` 的情况下
   1. `step.sqrtPriceNextX96 < sqrtPriceLimitX96` 成立，此时返回 `step.sqrtPriceNextX96`
   2. `step.sqrtPriceNextX96 > sqrtPriceLimitX96` 成立，此时返回 `sqrtPriceLimitX96`

简单来说，就是为了通过比较 `step.sqrtPriceNextX96` 和 `sqrtPriceLimitX96` 的大小，输出合理的目标价格。合理的目标价格满足:

1. 当 `zeroForOne = true` 时，`sqrtRatioTargetX96 = max(next, limit)`
2. 当 `zeroForOne = false` 时，`sqrtRatioTargetX96 = min(next, limit)`

我们先暂时跳过 `computeSwapStep` 内部的分析。继续阅读后续代码。后续代码中，我们首先更新了 `state.amountSpecifiedRemaining` 和 `state.amountCalculated` :

```solidity
if (exactInput) {
    state.amountSpecifiedRemaining -= (step.amountIn + step.feeAmount).toInt256();
    state.amountCalculated = state.amountCalculated.sub(step.amountOut.toInt256());
} else {
    state.amountSpecifiedRemaining += step.amountOut.toInt256();
    state.amountCalculated = state.amountCalculated.add((step.amountIn + step.feeAmount).toInt256());
}
```

上述更新逻辑中，我们要注意 `state.amountSpecifiedRemaining > 0` 代表 `exactInput` 模式，所以此处要使用 `-=` 进行计算。`state.amountCalculated` 代表计算出代币数量。注意 `state.amountCalculated` 也是存在符号的，我们认为为负数代表需要支出给用户的代币数量。在 `exactInput` 模式下，计算出的 `state.amountCalculated` 一定会支付给用户，所以此处使用了 `sub` 计算。对于 `exactOut` 同理，此时 `state.amountSpecifiedRemaining < 0` 所以使用 `+=` 计算，而 `state.amountCalculated` 代表用户支付给 Pool 的代币数量，此时使用 `add` 计算。

之后在 Pool 内进行 `feeProtocol` 计算，此部分在前文已有介绍。然后更新全局的 `feeGrowthGlobalX128`，在上文，我们已经提到 `feeGrowthGlobalX128` 代表单位流动性累计的手续费，所以计算方法如下:

```solidity
if (state.liquidity > 0)
    state.feeGrowthGlobalX128 += FullMath.mulDiv(step.feeAmount, FixedPoint128.Q128, state.liquidity);
```

最后，我们判断 `computeSwapStep` 输出的在当前流动性区间进行 swap 后的结果 `state.sqrtPriceX96` 与我们在最初使用 `nextInitializedTickWithinOneWord` 搜索到的 `step.sqrtPriceNextX96` 之间的关系。的一种关系是 `state.sqrtPriceX96 == step.sqrtPriceNextX96`，这说明我们已经耗尽了当前流动性区间的流动性，我们需要将移动 tick 进行新的搜索，核心代码如下:

```solidity
if (state.sqrtPriceX96 == step.sqrtPriceNextX96) {
    // if the tick is initialized, run the tick transition
    if (step.initialized) {
        // crosses an initialized tick
        int128 liquidityNet =
            ticks.cross(
                step.tickNext,
                (zeroForOne ? state.feeGrowthGlobalX128 : feeGrowthGlobal0X128),
                (zeroForOne ? feeGrowthGlobal1X128 : state.feeGrowthGlobalX128),
                cache.secondsPerLiquidityCumulativeX128,
                cache.tickCumulative,
                cache.blockTimestamp
            );
        // if we're moving leftward, we interpret liquidityNet as the opposite sign
        // safe because liquidityNet cannot be type(int128).min
        if (zeroForOne) liquidityNet = -liquidityNet;

        state.liquidity = LiquidityMath.addDelta(state.liquidity, liquidityNet);
    }

    state.tick = zeroForOne ? step.tickNext - 1 : step.tickNext;
} 
```

上述代码第一部分 `if (step.initialized)` 处理了要穿过已初始化的 tick 的 `cross` 过程，主要进行 `feeGrowth` 的更新，然后更新 `state.liquidity`，我们在上文刚刚完成这两部分的介绍。最后，修改 `state.tick` 的值，这里的逻辑与 tick 搜索的逻辑稍有关系。在上文，我们介绍

1. 对于向左搜索的情况，寻找小于或者等于当前 `tick` 的位于当前 `word` 的 next tick
2. 对于向右搜索的情况，寻找大于当前 `tick` 且位于当前 `word` 的 next ticl

由于要触发不包含当前 `step.tickNext` 的搜索，所以对于 `zeroForOne`(也就是向左搜索)，由于包含 tick 自身，所以必须要使用 `step.tickNext - 1` 更新 `state.tick` 的值，而对于向右搜索，搜索本身就会不包含当前 tick，所以直接使用 `step.tickNext` 即可。

对于另一种情况，即 `state.sqrtPriceX96 != step.sqrtPriceStartX96` 的情况，这种情况实际代表 swap 已经结束，因为当前的流动性区间已经可以满足用户所有需求，此时我们要进行的额外工作是 `state.tick = TickMath.getTickAtSqrtRatio(state.sqrtPriceX96);`。这是因为 `computeSwapStep` 内部只使用价格进行计算，而不考虑 tick，此时我们要使用价格计算出正确的 tick 以方便未来使用。

上述过程实际上就完成了 Swap 内的最核心的循环，然后我们就可以将大量处于内存中的中间状态写入存储，包括 `sqrtPriceX96` / `tick` / `liquidity` / `feeGrowthGlobal0X128` / `feeGrowthGlobal1X128` 等变量。以下所有的 `if` 其实都可以不存在，此处存在的唯一理由是为了避免重复写入导致的 gas 浪费。

```solidity
if (state.tick != slot0Start.tick) {
    (slot0.sqrtPriceX96, slot0.tick, slot0.observationIndex, slot0.observationCardinality) = (
        state.sqrtPriceX96,
        state.tick,
        observationIndex,
        observationCardinality
    );
} else {
    // otherwise just update the price
    slot0.sqrtPriceX96 = state.sqrtPriceX96;
}

// update liquidity if it changed
if (cache.liquidityStart != state.liquidity) liquidity = state.liquidity;

// update fee growth global and, if necessary, protocol fees
// overflow is acceptable, protocol has to withdraw before it hits type(uint128).max fees
if (zeroForOne) {
    feeGrowthGlobal0X128 = state.feeGrowthGlobalX128;
    if (state.protocolFee > 0) protocolFees.token0 += state.protocolFee;
} else {
    feeGrowthGlobal1X128 = state.feeGrowthGlobalX128;
    if (state.protocolFee > 0) protocolFees.token1 += state.protocolFee;
}
```

在 Swap 函数的最后，我们处理用户的代币转账问题:

```solidity
(amount0, amount1) = zeroForOne == exactInput
    ? (amountSpecified - state.amountSpecifiedRemaining, state.amountCalculated)
    : (state.amountCalculated, amountSpecified - state.amountSpecifiedRemaining);

// do the transfers and collect payment
if (zeroForOne) {
    if (amount1 < 0) TransferHelper.safeTransfer(token1, recipient, uint256(-amount1));

    uint256 balance0Before = balance0();
    IUniswapV3SwapCallback(msg.sender).uniswapV3SwapCallback(amount0, amount1, data);
    require(balance0Before.add(uint256(amount0)) <= balance0(), 'IIA');
} else {
    if (amount0 < 0) TransferHelper.safeTransfer(token0, recipient, uint256(-amount0));

    uint256 balance1Before = balance1();
    IUniswapV3SwapCallback(msg.sender).uniswapV3SwapCallback(amount0, amount1, data);
    require(balance1Before.add(uint256(amount1)) <= balance1(), 'IIA');
}

emit Swap(msg.sender, recipient, amount0, amount1, state.sqrtPriceX96, state.liquidity, state.tick);
slot0.unlocked = true;
```

对 `(amount0, amount1)` 的计算是一个难点，代码内的三目表达式的展开是：

```
// Set amount0 and amount1
// zero for one | exact input |
//    true      |    true     | amount 0 = specified - remaining (> 0)
//              |             | amount 1 = calculated            (< 0)
//    false     |    false    | amount 0 = specified - remaining (< 0)
//              |             | amount 1 = calculated            (> 0)
//    false     |    true     | amount 0 = calculated            (< 0)
//              |             | amount 1 = specified - remaining (> 0)
//    true      |    false    | amount 0 = calculated            (> 0)
//              |             | amount 1 = specified - remaining (< 0)
```

在本节的最后，我们介绍 Swap 中的 `computeSwapStep` 函数的具体实现。我们首先分析 `exactIn` 的情况，代码如下:

```solidity
uint256 amountRemainingLessFee = FullMath.mulDiv(uint256(amountRemaining), 1e6 - feePips, 1e6);
amountIn = zeroForOne
    ? SqrtPriceMath.getAmount0Delta(sqrtRatioTargetX96, sqrtRatioCurrentX96, liquidity, true)
    : SqrtPriceMath.getAmount1Delta(sqrtRatioCurrentX96, sqrtRatioTargetX96, liquidity, true);
if (amountRemainingLessFee >= amountIn) sqrtRatioNextX96 = sqrtRatioTargetX96;
else
    sqrtRatioNextX96 = SqrtPriceMath.getNextSqrtPriceFromInput(
        sqrtRatioCurrentX96,
        liquidity,
        amountRemainingLessFee,
        zeroForOne
    );
```

我们首先计算在手续费处理后的用户输入的代币数量 `amountRemainingLessFee`，然后使用 `getAmount0Delta` 或 `getAmount1Delta` 计算在 `sqrtRatioTargetX96` 与 `sqrtRatioCurrentX96` 之间的流动性等效的代币数量 `amountIn`。假如 `amountRemainingLessFee >= amountIn`，就说明用户输入的代币数量可以填满 `sqrtRatioTargetX96` 与 `sqrtRatioCurrentX96` 区间，所以 `sqrtRatioNextX96` 就是 `sqrtRatioTargetX96`。反之，则说明用户输入代币无法将价格推动到 `sqrtRatioTargetX96`，此时我们就会使用 `getNextSqrtPriceFromInput` 利用 `liquidity` 和 `amountRemainingLessFee` 以及 `sqrtRatioCurrentX96` 计算当前代币输入后的价格，具体的数学公式为:
$$
\begin{align*}
\sqrt{p_a} &= \sqrt{P} - \frac{y}{L} \\
\sqrt{p_b} &= L\frac{\sqrt{P}}{L - \sqrt{P} \cdot x}
\end{align*}
$$
其中 $\sqrt{p_b}$ 用于计算 `zeroForOne` 情况，此时输入代币为 token 0，计算结果是在当前 $L$ 和 $\sqrt{P}$ 下交易后的价格，具体对应 `getNextSqrtPriceFromAmount0RoundingUp` 函数。而 $\sqrt{p_a}$ 用于计算 `oneForZero` 的情况，对应函数为 `getNextSqrtPriceFromAmount1RoundingDown` 函数。限于篇幅，我们不再介绍具体的函数实现。

对于 `exactOut` 的模式，其实代码类似。我们首先计算 `sqrtRatioTargetX96` 与 `sqrtRatioCurrentX96` 价格区间内的代币数量 `amountOut` 。如果发现用户需要的 `amountRemaining` 大于等于 `amountOut`，那么我可以直接将 `sqrtRatioNextX96` 设置为价格区间的端点 `sqrtRatioTargetX96`。反之，我们则需要进行新的价格计算。使用的数学公式其实与上文一致。额外注意的是 `amountRemaining` 在 `exactOut` 情况下为负数。

```solidity
amountOut = zeroForOne
    ? SqrtPriceMath.getAmount1Delta(sqrtRatioTargetX96, sqrtRatioCurrentX96, liquidity, false)
    : SqrtPriceMath.getAmount0Delta(sqrtRatioCurrentX96, sqrtRatioTargetX96, liquidity, false);
if (uint256(-amountRemaining) >= amountOut) sqrtRatioNextX96 = sqrtRatioTargetX96;
else
    sqrtRatioNextX96 = SqrtPriceMath.getNextSqrtPriceFromOutput(
        sqrtRatioCurrentX96,
        liquidity,
        uint256(-amountRemaining),
        zeroForOne
    );
```

最后，我们会根据多种情况判断代币的真实输出。首先，我们引入 `bool max = sqrtRatioTargetX96 == sqrtRatioNextX96;`，这种情况其实代表当前价格区间被完全耗尽，在这种情况下，计算出的 `amountIn` 就是真实的 `amountIn`，反之，我们则需要利用 `sqrtRatioNextX96` 和 `sqrtRatioCurrentX96` 再次计算兑换的代币数量。最终，完整的条件判断如下，此处的一个难点是舍入问题，`getAmount0Delta` 和 `getAmount1Delta` 的最后的布尔参数代表是否需要 `roundUp`。

```solidity
// get the input/output amounts
if (zeroForOne) {
    amountIn = max && exactIn
        ? amountIn
        : SqrtPriceMath.getAmount0Delta(sqrtRatioNextX96, sqrtRatioCurrentX96, liquidity, true);
    amountOut = max && !exactIn
        ? amountOut
        : SqrtPriceMath.getAmount1Delta(sqrtRatioNextX96, sqrtRatioCurrentX96, liquidity, false);
} else {
    amountIn = max && exactIn
        ? amountIn
        : SqrtPriceMath.getAmount1Delta(sqrtRatioCurrentX96, sqrtRatioNextX96, liquidity, true);
    amountOut = max && !exactIn
        ? amountOut
        : SqrtPriceMath.getAmount0Delta(sqrtRatioCurrentX96, sqrtRatioNextX96, liquidity, false);
```

上述结果也并不是最终结果，我们需要对于 `exactOut` 的情况需要进行额外的控制，因为计算可能存在误差，这可能导致 `exactOut` 大于用户预期，对于这种情况，我们默认将额外的超额误差部分舍入:

```solidity
// cap the output amount to not exceed the remaining output amount
if (!exactIn && amountOut > uint256(-amountRemaining)) {
    amountOut = uint256(-amountRemaining);
}
```

最后，我们计算交易过程中的 `feeAmount`：

```solidity
if (exactIn && sqrtRatioNextX96 != sqrtRatioTargetX96) {
    // we didn't reach the target, so take the remainder of the maximum input as fee
    feeAmount = uint256(amountRemaining) - amountIn;
} else {
    feeAmount = FullMath.mulDivRoundingUp(amountIn, feePips, 1e6 - feePips);
}
```

对于 `exactIn && sqrtRatioNextX96 != sqrtRatioTargetX96` 其实就是 `exactIn` 模式下，代币在当前价格区间完成所有兑换。在之前计算时，我们使用了 `amountRemainingLessFee` 进行比较，所以此处直接使用 `feeAmount = uint256(amountRemaining) - amountIn;` 就可以计算获得最终结果。对于其他情况，我们都需要使用如下公式进行计算:
$$
\text{feeAmount} = \frac{\text{amountIn} \times \text{feePips}}{1 - \text{feePips}}
$$
上述公式的推导流程为:
$$
\begin{align*}
\text{total Amount In} &= \frac{\text{amountIn}}{1 - \text{feePips}}\\
\text{feeAmount} &= \text{total Amount In} \times \text{feePips} = \frac{\text{amountIn} \times \text{feePips}}{1 - \text{feePips}}
\end{align*}
$$
上述计算中我们认为给定的 `amountIn` 是已经扣完手续费后的净额，在计算 `feeAmount` 时，我们第一步是将 `amountIn` 还原为含手续费的全额，然后进行手续费计算。

## 总结

在本文中，我们介绍了关于 Uniswap v3 的大部分内容，但没有给出部分数学公式的计算方法，假如读者希望更加全面的认为 Uniswap v3，可以将笔者的另一篇 [博客](https://blog.wssh.dev/posts/uniswap-v3/) 也阅读一遍。本文忽略了所有关于 Oracle 的部分，实际上笔者的另一篇文章也没有介绍 Oracle，读者可以自行根据白皮书内容和代码理解这一部分。Uniswap v3 的 Oracle 带来的最有趣的 DeFi 原语就是流动性质押，假如读者的项目涉及该部分，可以研究一下 Uniswap v3 内的 Oracle 部分。

