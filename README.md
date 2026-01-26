# 🦈 Whale Hunter V3.1 - "Dark Forest" Architecture

**Autonomous Crypto Trading System - Production-Ready Implementation**

> A sophisticated whale tracking and signal execution system designed to identify insider activity, simulate transactions for honeypot detection, and execute trades with advanced risk management.

---

## ⚠️ Critical Warnings

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PARTIAL HYDRA WARNING:                                                  │
│  NEVER allow HEAD 3 (Assassin) to execute unless HEAD 2 (Simulator)     │
│  has blocked ≥95% of eventual losers in shadow mode.                    │
│  If simulation accuracy <95%, Assassin MUST stay disabled.              │
└─────────────────────────────────────────────────────────────────────────┘
```

- **You are NOT a wolf** - You're a scavenger with 500ms advantage over retail
- **Infrastructure cost must be <5% of capital annually**
- **This is for educational and personal use only**

---

## 📋 Table of Contents

1. [Quick Start](#-quick-start)
2. [Authoritative Documentation](#-authoritative-documentation)
3. [Architecture Overview](#-architecture-overview)
4. [Phase-by-Phase Guide](#-phase-by-phase-guide)
5. [Configuration](#-configuration)
6. [Scripts Reference](#-scripts-reference)
7. [Risk Management](#-risk-management)
8. [Troubleshooting](#-troubleshooting)

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Free API keys from:
  - [Helius](https://www.helius.dev/) - 100k requests/day free
  - [BirdEye](https://birdeye.so/api) - 50k requests/day free
  - [Solscan](https://solscan.io/apis) (optional)

### Installation

```bash
# Clone or navigate to project
cd /home/ubuntu/whale_hunter

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp config/.env.example config/.env
# Edit config/.env with your API keys

# Initialize system
python scripts/bootstrap.py
```

### First Run (Phase 0)

```bash
# Start logging signals manually
python scripts/phase0_logger.py

# In another terminal, harvest winner wallets
python scripts/harvester.py --tokens <TOKEN_ADDRESS>

# View your Black Book
python scripts/god_view.py
```

---

## 📚 Authoritative Documentation

The following specifications in `docs/` are the **single source of truth** for system behavior. Code must comply with these documents.

| Document | Purpose | When to Reference |
|----------|---------|-------------------|
| [**POLICY.md**](docs/POLICY.md) | Trading Policy Contract | Entry/exit rules, vetoes, position sizing |
| [**GATES.md**](docs/GATES.md) | Phase Gates + Non-Negotiables | Go/No-Go decisions, kill switch triggers |
| [**DATA_DICTIONARY.md**](docs/DATA_DICTIONARY.md) | Schemas + Units | Database queries, field meanings |
| [**API_REFERENCE.md**](docs/API_REFERENCE.md) | Pinned Endpoints | API integration, rate limits |
| [**THREAT_MODEL.md**](docs/THREAT_MODEL.md) | Adversarial Scenarios | Security review, failure handling |
| [**RUNBOOK.md**](docs/RUNBOOK.md) | Operations Manual | Daily/weekly tasks, emergencies |

### Key Policy Rules (from POLICY.md)

- **Veto Order:** Kill Switch → Capital Preservation → Freshness → Token Age → Spread → Liquidity → Tax → Cooldown → Simulation
- **Spread Veto:** Block if (ask-bid)/bid > 3%
- **Tax Limit:** Block if simulated tax > 10%
- **First 50 Trades:** 3% max position, V2.0 only, 24h review before 2nd daily trade

### Non-Negotiables (from GATES.md)

- **95% Simulator Accuracy** required before Assassin unlock
- **Infrastructure Cost < 5%** of capital annually
- **V2.0 Defensive Foundation** NEVER disabled
- **Graph Kill Switch** triggers on >10 new mothers/24h or win rate collapse

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     V3.1 "GHOST PREDATOR" ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐│
│ │                    COUNTER-ADAPTATION LAYER                             ││
│ │  • Signal Entropy Injection (random delays, probabilistic skipping)     ││
│ │  • Rotating Execution Wallets (3-5 wallet rotation)                     ││
│ │  • Graph Kill Switch (epistemic failure detection)                      ││
│ └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐          │
│   │   HEAD 1:       │   │   HEAD 2:       │   │   HEAD 3:       │          │
│   │  SYBIL HUNTER   │   │   SIMULATOR     │   │   ASSASSIN      │          │
│   │  (SQLite→Neo4j) │   │   (Local Fork)  │   │   (Jito Bundles)│          │
│   │                 │   │                 │   │                 │          │
│   │  + Decay 30d    │   │  + 95% accuracy │   │  + Rust Sidecar │          │
│   │  + CEX Blacklist│   │    REQUIRED     │   │    Pattern      │          │
│   │  + Poison Prot. │   │    before live  │   │                 │          │
│   └─────────────────┘   └─────────────────┘   └─────────────────┘          │
│                                                                             │
│   ═══════════════════════════════════════════════════════════════════════  │
│                                                                             │
│                    ┌─────────────────────────────────────┐                  │
│                    │  V2.0 DEFENSIVE FOUNDATION          │                  │
│                    │  (NEVER DISABLED)                   │                  │
│                    │  • Fail-closed gates                │                  │
│                    │  • Veto system (not weights)        │                  │
│                    │  • Risk limits & kill switch        │                  │
│                    └─────────────────────────────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Core Modules

| Module | Purpose | Phase |
|--------|---------|-------|
| `database.py` | SQLite operations with V3.1 schema | 0+ |
| `wallet_tracker.py` | Wallet reputation & decay | 0+ |
| `signal_processor.py` | Signal validation & veto system | 1+ |
| `simulator.py` | Honeypot simulation | 2+ |
| `risk_manager.py` | Position sizing, drawdown, kill switches | 1+ |
| `entropy.py` | Signal entropy injection (Ghost mode) | 3+ |
| `metrics.py` | False positive tracking, accuracy | 1+ |
| `api_clients.py` | Helius, BirdEye, Solscan clients | 0+ |

---

## 📈 Phase-by-Phase Guide

### Phase 0: Paper Trading (Months 1-3)

**Goal:** Build data, validate approach, zero risk

```bash
# 1. Log signals manually as you see them on Twitter/Discord
python scripts/phase0_logger.py

# Commands:
#   - Paste token address to log
#   - 'stats' - View statistics
#   - 'update <id>' - Update with outcome
#   - 'export' - Export to CSV

# 2. Harvest winning tokens after they moon
python scripts/harvester.py --tokens <TOKEN_THAT_10X>

# 3. Run daily decay and view Black Book
python scripts/god_view.py
```

**Checklist before Phase 1:**
- [ ] 50+ signals logged
- [ ] 20+ wallets harvested
- [ ] Backtest shows >50% win rate

### Phase 1: Live V2.0 ($500 capital, Months 4-8)

**Goal:** Defensive trading with proven V2.0 rules

```python
# Configuration for Phase 1
# config/settings.yaml
system:
  current_phase: 1
  mode: "live"

first_50_trades:
  enabled: true
  max_position_pct: 0.03  # 3% max
  no_graph_boost: true
  max_trades_first_week: 5
```

**Daily routine:**
1. Run `python scripts/harvester.py` on yesterday's winners
2. Check `python scripts/god_view.py` for new mother wallets
3. Log all signals, win or lose
4. Update outcomes after 24h

### Phase 2: + Simulator (Months 9-14)

**Goal:** Add simulation gate, track accuracy

```bash
# Run backtest to validate strategy
python scripts/backtest.py --days 90 --strategy v25

# Check simulator accuracy (must be >95% before Phase 3)
```

### Phase 2.5: Hybrid Mode (Months 15-18)

**Goal:** V2.0 + Simulation + Graph as confidence boost

```python
# V2.5 Configuration
# Graph signals BOOST confidence, don't create signals
confidence:
  graph_boost:
    s_tier_boost: 0.25
    a_tier_boost: 0.15
    b_tier_boost: 0.05
```

### Phase 3+: Full Hydra (Months 19+, requires $5000+ capital)

**Go/No-Go Checklist:**
- [ ] ≥50 signals tracked by simulator
- [ ] Simulator blocks ≥95% of eventual losers
- [ ] Capital ≥ $5,000
- [ ] Sustained win rate ≥55% over 3 months
- [ ] Positive ROI after infra + tips
- [ ] Graph Kill Switch tested manually

---

## ⚙️ Configuration

### Main Config (`config/settings.yaml`)

Key sections:

```yaml
# System phase
system:
  current_phase: 0  # 0=Paper, 1=Live V2.0, 2=+Simulator

# Signal freshness by asset class
signal_freshness:
  meme_coin:
    min_age_seconds: 3600  # Wait 1 hour for meme coins

# Position sizing
risk:
  position_sizing:
    capital_under_500:
      max_position_pct: 0.05
      
# Capital preservation (triggers at 15% drawdown)
capital_preservation:
  position_size_multiplier: 0.25
  confidence_increase: 0.15
  disable_graph_signals: true
```

### Environment Variables (`config/.env`)

```bash
# Required
HELIUS_API_KEY=your_key
BIRDEYE_API_KEY=your_key

# Capital
INITIAL_CAPITAL_USD=500
```

---

## 📜 Scripts Reference

| Script | Purpose | Usage |
|--------|---------|-------|
| `bootstrap.py` | Initialize system | `python scripts/bootstrap.py` |
| `phase0_logger.py` | Manual signal logging | `python scripts/phase0_logger.py` |
| `harvester.py` | Harvest winner wallets | `python scripts/harvester.py --tokens <ADDR>` |
| `god_view.py` | Generate Black Book | `python scripts/god_view.py --min-winners 3` |
| `backtest.py` | Historical replay | `python scripts/backtest.py --days 90` |

---

## 🛡️ Risk Management

### Kill Switch Triggers

| Trigger | Condition | Action |
|---------|-----------|--------|
| Drawdown | >15% | Capital Preservation Mode |
| Drawdown | >25% | Emergency Stop |
| Consecutive Losses | 5+ | Emergency Stop |
| Mother Explosion | >10 new in 24h | 72h Observation |
| Win Rate Collapse | <30% in 3+ clusters | Graph Kill Switch |

### First 50 Trades Rules

1. **Max position: 3%** (not 10%)
2. **No graph-boosted trades** (V2.0 only)
3. **24-hour review** before second trade each day
4. **Max 5 trades** in first week

### Capital Preservation Mode

When drawdown exceeds 15%:
- Position sizes reduced to 25% of normal
- Confidence thresholds increased by +0.15
- Graph-based signals disabled
- Manual review required to resume

---

## 🔧 Troubleshooting

### Common Issues

**"No signals found for backtest"**
```bash
# Log signals first
python scripts/phase0_logger.py
# Update outcomes
> update <signal_id>
```

**"API key missing"**
```bash
# Copy and edit environment file
cp config/.env.example config/.env
nano config/.env
```

**"Database locked"**
```bash
# Only one script should access DB at a time
# Kill other processes or wait
```

### Logs

```bash
# View recent logs
tail -f logs/whale_hunter.log

# Check for errors
grep ERROR logs/whale_hunter.log
```

---

## 📄 License

This software is provided for educational and personal use only. Trading cryptocurrencies involves substantial risk of loss. The authors are not responsible for any financial losses incurred through use of this software.

---

## 🙏 Credits

Built on the V3.1 "Dark Forest" architecture blueprint. Special thanks to the crypto trading community for insights on whale tracking, MEV protection, and risk management strategies.
