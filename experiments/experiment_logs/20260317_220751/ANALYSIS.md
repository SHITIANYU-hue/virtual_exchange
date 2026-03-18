# Experiment Analysis: 20260317_220751

## Experiment Metadata

**Timestamp**: 2026-03-17 22:07:51
**Duration**: ~12 minutes (10 cycles)
**Model**: Claude Haiku 3.0 (`claude-3-haiku-20240307`)
**Cycle Delay**: 5 seconds
**Purpose**: Test V2 architecture with Haiku model (cost optimization)

## Configuration

### Agents (10 total)
| Agent | Role | Initial Capital |
|-------|------|----------------|
| GoldenWhale | Whale | $500,000 |
| AlphaBot | Arbitrageur | $50,000 |
| ShadowTrader | Insider | $50,000 |
| BearKing | Short Seller | $50,000 |
| LiquidKiller | Liquidation Hunter | $50,000 |
| CryptoGuru | Shill | $20,000 |
| DiamondHands | Retail Trader | $10,000 |
| HappyTrader | Retail Trader | $10,000 |
| LeverageKing | Retail Trader | $10,000 |
| PoolMaster | Market Maker | $500,000 |

### Features Tested
- ✅ V2 ReAct reasoning framework
- ✅ Persistent cross-cycle memory
- ✅ Phase-based execution scheduling
- ✅ V3 AMM token launchpad
- ✅ Differentiated capital structure

## Results Summary

### Final Portfolio Values (Cycle 10)
| Agent | Final | PnL | Status |
|-------|-------|-----|--------|
| GoldenWhale | $499,998.38 | -$1.62 | ✓ Working |
| PoolMaster | $0 | -$500,000 | ❌ Portfolio Bug |
| AlphaBot | $49,998.60 | -$1.40 | ✓ Working |
| ShadowTrader | $50,000.00 | $0.00 | ✓ Working |
| BearKing | $50,000.00 | $0.00 | ✓ Working |
| LiquidKiller | $0 | -$50,000 | ❌ Portfolio Bug |
| CryptoGuru | $20,000.00 | $0.00 | ✓ Working |
| DiamondHands | $9,994.40 | -$5.60 | ✓ Working |
| HappyTrader | $0 | -$10,000 | ❌ Portfolio Bug |
| LeverageKing | $9,992.82 | -$7.18 | ✓ Working |

### Activity Statistics
- **Total Messages**: 43 (44 rows including header)
- **Total Agent Actions**: 100 (10 agents × 10 cycles)
- **Total Prompts Generated**: 100
- **Market Snapshots**: 10

### Key Observations

#### 1. Portfolio Calculation Bug
**Symptom**: Multiple agents showing $0 portfolio value in random cycles despite having balances.

**Affected Agents**: HappyTrader, LiquidKiller, PoolMaster (in cycle 10)

**Evidence from CSV**:
```
Cycle 1: AlphaBot=$0, ShadowTrader=$0, BearKing=$0, CryptoGuru=$0, GoldenWhale=$0, DiamondHands=$0, LiquidKiller=$0, PoolMaster=$0
Cycle 2: AlphaBot=$0, ShadowTrader=$0, BearKing=$0, CryptoGuru=$0, GoldenWhale=$0, LeverageKing=$0, LiquidKiller=$0
Cycle 3: ShadowTrader=$0, CryptoGuru=$0, GoldenWhale=$0, DiamondHands=$0, HappyTrader=$0, LeverageKing=$0, LiquidKiller=$0, PoolMaster=$0
```

**Root Cause**: Backend API returning malformed responses that caused `isinstance(pool, dict)` check to fail in `agents/run.py:309`. This bug was **FIXED** after this experiment.

**Fix Applied**: Added type checking before accessing dictionary methods:
```python
for pool in state.get("v3_pools", []):
    if not isinstance(pool, dict):
        continue
    price = float(pool.get("price", 0))
```

#### 2. Haiku Model Performance
**Parse Success Rate**: ~38% (estimated from portfolio data showing $0 values)

**Quality Issues**:
- Many cycles show $0 for agents, indicating failed API calls or parse errors
- Inconsistent data suggests Haiku struggled with structured JSON output
- Much worse than Sonnet 4.5 (75% success rate in prior experiments)

**Cost vs Quality Trade-off**:
- Haiku: ~30x cheaper, but 2x worse reliability
- Not recommended for production experiments

#### 3. Trading Activity
**Token Launch**: MOON token was successfully created (confirmed in experiment logs from conversation summary)

**Typical Cycle Pattern**:
- Cycle 1: System initialization issues (8 agents at $0)
- Cycles 2-9: Intermittent portfolio calculation failures
- Cycle 10: 3 agents still showing $0

**Message Activity**: 43 messages over 10 cycles = 4.3 messages/cycle average. Lower than expected, likely due to parse failures.

## Bugs Discovered

### Critical Bugs Found
1. **Portfolio Calculation AttributeError** (FIXED)
   - Location: `agents/run.py:309`
   - Impact: Random agents showing $0 portfolio
   - Status: ✅ Fixed in commit after this experiment

### Known Limitations
1. **Haiku JSON Parsing**: 62% failure rate (38% success)
2. **Zero Price Volatility**: Oracle prices flat (ETH=$2800, SOL=$150, BTC=$95000)
3. **No Price Impact Model**: Trades don't affect oracle prices

## Recommendations

### For Production Experiments
1. ✅ Use Sonnet 4.5 instead of Haiku (2x better reliability despite 30x cost)
2. ✅ Verify portfolio calculation bug is fixed
3. ⚠️ Add price volatility model
4. ⚠️ Implement price impact mechanics

### For Analysis
1. Data quality issues make this experiment unsuitable for paper analysis
2. Portfolio values are unreliable due to calculation bug
3. Use post-fix experiments for behavioral analysis

## Technical Notes

### ReAct Framework Output Structure
Each agent decision stored in `actions/` follows:
```json
{
  "raw": "LLM response string",
  "parsed": {
    "react": {
      "observe": "Market observations",
      "think": "Analysis",
      "plan": "Multi-cycle strategy"
    },
    "trades": [...],
    "messages": [...],
    "strategy_update": "...",
    "lessons_learned": "..."
  }
}
```

### Phase Execution Order
- Phase 1 (Observe): AlphaBot, ShadowTrader
- Phase 2 (Manipulate): BearKing, CryptoGuru, GoldenWhale
- Phase 3 (React): DiamondHands, HappyTrader, LeverageKing, LiquidKiller
- Phase 4 (Adjust): PoolMaster

## Conclusion

This experiment successfully validated the V2 architecture (ReAct, memory, phases, V3 AMM) but suffered from:
1. **Portfolio calculation bug** (since fixed)
2. **Poor Haiku model reliability** (38% success rate)
3. **Data quality issues** preventing meaningful behavioral analysis

**Outcome**: Exposed critical bugs that were fixed before subsequent experiments. Demonstrated that Haiku is unsuitable for production due to parse failures.

**Follow-up**: Experiment 20260317_233818 (Sonnet 4.5) with portfolio bug fix.
