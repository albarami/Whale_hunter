# Trading Policy Contract

**Version:** 3.1.0  
**Status:** AUTHORITATIVE - Code must pass these rules  
**Philosophy:** Fail-closed. Any veto = no trade.

---

## 1. Entry Veto Order (Fail-Closed Gates)

Signals are processed through these gates **IN SEQUENCE**. First failure = rejection.

| Order | Gate | Veto Condition | Rationale |
|-------|------|----------------|------------|
| 1 | Kill Switch | System in KILL_SWITCH mode | Emergency halt |
| 2 | Capital Preservation | Mode active + confidence < threshold | Protect capital |
| 3 | Signal Freshness | Age > asset-class maximum | Stale data |
| 4 | Token Age | Token age < asset-class minimum | Rug risk |
| 5 | Spread | (ask-bid)/bid > 3% | Slippage risk |
| 6 | Liquidity | Pool < asset-class minimum | Exit risk |
| 7 | Tax | Simulated tax > 10% | Honeypot |
| 8 | Cooldown | Any saturation limit hit | Overexposure |
| 9 | Simulation | Honeypot detected OR tax > 10% | Final validation |

---

## 2. Token Age Tiers by Asset Class

| Asset Class | Minimum Age | Rationale |
|-------------|-------------|------------|
| meme_coin_low_cap | 3600s (1 hour) | Rug prevention |
| mid_cap | 1800s (30 min) | Moderate safety |
| large_cap | 0 | Established tokens |

**Enforcement:** Block entry if `token_creation_timestamp + min_age > now`

---

## 3. Signal Freshness Windows

| Asset Class | Max Signal Age | Rationale |
|-------------|----------------|------------|
| meme_coin_low_cap | 300s (5 min) | Fast-moving markets |
| established_altcoin | 900s (15 min) | Moderate volatility |
| major_crypto_cex | 1800s (30 min) | Slower price action |

**Enforcement:** Block if `now - signal_timestamp > max_age`

---

## 4. Spread Veto

```
spread_pct = (ask_price - bid_price) / bid_price
VETO if spread_pct > 0.03 (3%)
```

**Rationale:** High spread indicates low liquidity or manipulation.

---

## 5. Liquidity Minimums by Asset Class

| Asset Class | Minimum Pool Liquidity (USD) |
|-------------|-----------------------------|
| meme_coin | $10,000 |
| mid_cap | $50,000 |
| large_cap | $100,000 |

**Enforcement:** Block if `pool_liquidity_usd < minimum`

---

## 6. Tax Limit

```
VETO if simulated_tax > 10%
```

**Calculation:** Simulate buy+sell, measure actual received vs expected.

---

## 7. Exit Rules

### 7.1 Panic Exit
**Trigger:** Price drop > 15% in < 5 minutes AND liquidity shrinks > 30%

```python
if (price_change_5min < -0.15) and (liquidity_change_5min < -0.30):
    EXECUTE_IMMEDIATE_SELL()
```

### 7.2 Time Stops (Maximum Hold Duration)

| Asset Class | Min Hold | Max Hold |
|-------------|----------|----------|
| meme_coin | 12 hours | 24 hours |
| mid_cap | 24 hours | 48 hours |
| large_cap | 48 hours | 72 hours |

**Action:** Exit at max hold regardless of PnL.

### 7.3 Whale Inactivity Exit
**Trigger:** Tracked wallet shows no activity for 24 hours

```python
if whale_inactive_hours >= 24:
    REDUCE_POSITION(50%)  # Reduce by 50%
```

### 7.4 Trailing Stop
- **Activation:** Position reaches +10% unrealized profit
- **Trail Distance:** 5% from peak
- **Execution:** Sell when price drops 5% from highest point after activation

```python
if unrealized_pnl_pct >= 0.10:
    trailing_stop_active = True
    peak_price = max(peak_price, current_price)
    stop_price = peak_price * 0.95
    if current_price <= stop_price:
        EXECUTE_SELL()
```

---

## 8. Cooldown/Saturation Rules

| Scope | Window | Limit | Action on Breach |
|-------|--------|-------|------------------|
| Per Wallet | 24 hours | 3 trades | Skip signals from wallet |
| Per Token | 12 hours | 2 trades | Skip token signals |
| Per Cluster | Session | 5 trades | Skip cluster signals |
| Global | 1 hour | 10 trades | Pause all trading |

**Session Definition:** From system start until manual reset or kill switch.

---

## 9. Position Sizing by Phase

| Phase | Capital Range | Risk per Trade | Max Position | Notes |
|-------|---------------|----------------|--------------|-------|
| 0 | Any | 0% | 0% | Paper trading only |
| 1 | $500 - $2,000 | 2% | 10% | Conservative start |
| 2 | $2,000 - $5,000 | 2.5% | 12% | Gradual increase |
| 3 | $5,000 - $10,000 | 3% | 15% | Proven performance |
| 4 | $10,000+ | 3.5% | 18% | Full operation |

**Formula:**
```python
position_size = min(
    capital * risk_per_trade / confidence,
    capital * max_position_pct
)
```

---

## 10. First 50 Trades Special Rules

**Effective:** Until trade_count >= 50

| Rule | Value | Rationale |
|------|-------|------------|
| Max Position Size | 3% of capital | Limit exposure |
| Signal Source | V2.0 only (no graph boost) | Proven signals only |
| Max Trades Week 1 | 5 trades | Slow validation |
| Daily Trade Review | 24h review before 2nd daily trade | Human oversight |

**Enforcement:**
```python
if total_trades < 50:
    max_position = capital * 0.03
    graph_boost_enabled = False
    if days_since_start <= 7 and weekly_trades >= 5:
        VETO("First week trade limit")
    if daily_trades >= 1:
        REQUIRE_MANUAL_APPROVAL()
```

---

## 11. Capital Preservation Mode

**Trigger:** Drawdown >= 15% from peak capital

| Parameter | Normal | Capital Preservation |
|-----------|--------|---------------------|
| Position Size | 100% | 25% of normal |
| Confidence Threshold | Base | Base + 0.15 |
| Graph Signals | Enabled | Disabled |
| Resume | Automatic | Manual review required |

**Exit Condition:** Manual review + explicit command to resume normal operation.

```python
if current_capital < peak_capital * 0.85:
    ACTIVATE_CAPITAL_PRESERVATION()
    
def capital_preservation_position(normal_size):
    return normal_size * 0.25
    
def capital_preservation_threshold(base_threshold):
    return base_threshold + 0.15
```

---

## Policy Compliance Verification

Every trade attempt must log:
1. All gates checked (pass/fail)
2. First veto reason (if any)
3. Final decision with timestamp
4. Position size calculation
5. Active mode (NORMAL/CAPITAL_PRESERVATION/KILL_SWITCH)

**Audit Trail:** All decisions logged to `signals` table with `veto_reason` field.
