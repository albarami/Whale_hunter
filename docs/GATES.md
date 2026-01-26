# Phase Gates + Non-Negotiables

**Version:** 3.1.0  
**Purpose:** Single-page reference for phase transitions and system invariants

---

## Phase Progression: Go/No-Go Metrics

### Phase 0 → Phase 1 (Paper → Live $500)

| Metric | Threshold | Measurement |
|--------|-----------|-------------|
| Signals Tracked | ≥ 50 | `SELECT COUNT(*) FROM signals` |
| Paper Win Rate | ≥ 55% | Wins / (Wins + Losses) over 3 months |
| Capital Available | ≥ $500 | Verified SOL balance |
| System Uptime | 7 consecutive days | No crashes or manual restarts |

### Phase 1 → Phase 2 ($500-$2K → $2K-$5K)

| Metric | Threshold | Measurement |
|--------|-----------|-------------|
| Live Trades | ≥ 20 | `SELECT COUNT(*) FROM trades WHERE paper=false` |
| Live Win Rate | ≥ 50% | Actual trade outcomes |
| Max Drawdown | < 20% | Peak-to-trough capital |
| Capital | ≥ $2,000 | Current SOL balance in USD |
| Days Active | ≥ 30 | Since first live trade |

### Phase 2 → Phase 3 ($2K-$5K → $5K-$10K)

| Metric | Threshold | Measurement |
|--------|-----------|-------------|
| Live Trades | ≥ 50 | Total live trades |
| Live Win Rate | ≥ 52% | Actual trade outcomes |
| Simulator Accuracy | ≥ 95% | Blocked losers / Total losers |
| Positive ROI | > 0% after infra | Net profit - infrastructure costs |
| Capital | ≥ $5,000 | Current balance |
| Rust Sidecar | Healthy 30 days | No restarts, <100ms p99 latency |

### Phase 3 → Phase 4 ($5K-$10K → $10K+)

| Metric | Threshold | Measurement |
|--------|-----------|-------------|
| Live Trades | ≥ 100 | Total live trades |
| Live Win Rate | ≥ 55% | Over last 3 months |
| Graph Signal ROI | Positive | V3 signals profitable independently |
| Capital | ≥ $10,000 | Current balance |
| Kill Switch | Tested | Manual test within 7 days |
| Days in Phase 3 | ≥ 60 | Time at current phase |

---

## Non-Negotiable Rules

### 1. 95% Simulator Accuracy (Assassin Unlock)

```
Assassin Enabled = (blocked_losers / total_losers) >= 0.95
```

**Calculation:**
- Loser = Trade that would have resulted in loss
- Blocked = Simulator correctly vetoed the trade
- Weighted by magnitude: rug (100%), modest (50%), marginal (25%)

**Enforcement:** V3 features (graph boost, aggressive sizing) locked until achieved.

---

### 2. Infrastructure Cost < 5% Rule

```
annual_infra_cost < capital * 0.05
```

**Included Costs:**
- VPS hosting
- API subscriptions (Helius, BirdEye, etc.)
- RPC node costs
- Database hosting

**Action if Breached:** Alert + reduce API tier or pause non-essential services.

---

### 3. V2 Defensive Foundation Never Disabled

**Invariant:** Core V2.0 safety mechanisms always active:

| Component | Status | Override Allowed |
|-----------|--------|------------------|
| Spread veto (3%) | ALWAYS ON | NO |
| Liquidity minimums | ALWAYS ON | NO |
| Tax veto (10%) | ALWAYS ON | NO |
| Time stops | ALWAYS ON | NO |
| Panic exit | ALWAYS ON | NO |
| Cooldowns | ALWAYS ON | NO |

**V3 additions are OPTIONAL layers on top. V2 never bypassed.**

---

### 4. Graph Kill Switch

**Triggers (ANY activates):**

| Trigger | Threshold | Detection |
|---------|-----------|------------|
| Mother Wallet Explosion | >10 new mothers in 24h | `COUNT(*) WHERE discovered_at > now-24h` |
| Correlated Cluster Emergence | >5 clusters with >80% overlap | Jaccard similarity on wallet sets |
| Win Rate Collapse | <40% across graph signals | 7-day rolling window |

**Response:**
```python
if kill_switch_triggered:
    graph_boost = 0.0
    graph_signals_enabled = False
    log_kill_switch_event(trigger, timestamp)
    alert_operator("GRAPH KILL SWITCH ACTIVATED")
    # V2.0 signals continue normally
```

**Resume:** Manual operator command after investigation.

---

## Capital Thresholds Summary

| Phase | Min Capital | Max Capital | Risk Profile |
|-------|-------------|-------------|---------------|
| 0 | $0 | Any | Paper only |
| 1 | $500 | $2,000 | Conservative |
| 2 | $2,000 | $5,000 | Moderate |
| 3 | $5,000 | $10,000 | Confident |
| 4 | $10,000 | Unlimited | Full operation |

---

## Quick Reference: Go/No-Go Checklist

```
□ ≥50 signals tracked
□ Simulator blocks ≥95% losers (weighted)
□ Capital ≥ phase minimum
□ Win rate ≥55% over 3 months
□ Positive ROI after infrastructure costs
□ Rust sidecar healthy 30 days (Phase 3+)
□ Graph Kill Switch tested within 7 days (Phase 4)
□ No active kill switch or capital preservation mode
□ All API keys valid and rate limits adequate
□ Database backup < 24 hours old
```
