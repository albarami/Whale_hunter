# Whale Hunter v3.1 Implementation Plan

## 1. Purpose

This document defines the phased implementation roadmap for the Whale Hunter v3.1 trading system. The system follows whale wallet activity on Solana to generate copy-trading signals, with a fail-closed architecture that prioritizes capital preservation over opportunity capture. All phases must be executed in strict sequential order. **No phase may be skipped.** Phase transitions require objective, measurable criteria as defined in [docs/GATES.md](docs/GATES.md). The authoritative documents (POLICY.md, GATES.md, DATA_DICTIONARY.md, API_REFERENCE.md, IMPLEMENTATION_RULES.md, THREAT_MODEL.md, RUNBOOK.md, EVENTS.pdf) govern all implementation decisions; if code conflicts with docs, docs win.

---

## 2. Phase Overview

### Phase 0: Paper Trading (Observation Mode)

**Intent:** Build infrastructure, collect signals, validate detection logic without risking capital.

**High-Level Outcomes:**

- Database schema established (SQLite: wallet_graph.db)
- API clients integrated (Helius, BirdEye, Jupiter; DexScreener optional/fallback)
- Signal detection pipeline operational
- Paper trade logging functional
- EVENTS-compliant structured logging operational (per EVENTS.pdf)
- Minimum 100 signals tracked over ≥8 weeks

### Phase 1: Live Trading ($500 - $2,000)

**Intent:** Execute real trades with conservative position sizing to validate system behavior under live market conditions.

**High-Level Outcomes:**

- V2.0 defensive foundation fully enforced
- Live trade execution via Jupiter swap API
- All veto gates operational (kill switch, capital preservation, spread, liquidity, tax, cooldowns, simulation)
- First 50 Trades special rules active
- Minimum 20 live trades completed

### Phase 2: Moderate Scaling ($2,000 - $5,000)

**Intent:** Increase position sizing and confidence thresholds as system proves profitable.

**High-Level Outcomes:**

- Position sizing increased per POLICY.md Phase 2 limits
- Simulator accuracy tracking established
- Minimum 50 live trades completed
- Positive ROI after infrastructure costs demonstrated

### Phase 2.5: Simulator Validation (Bridge Phase)

**Intent:** Achieve 95% simulator accuracy with 50+ weighted samples to unlock V3 features.

**High-Level Outcomes:**

- Simulator blocks ≥95% of losers (weighted: rug 100%, modest 50%, marginal 25%)
- Minimum 50 weighted loser samples collected
- Assassin module ready but NOT enabled until gate passes
- Graph boost preparation complete

### Phase 3: Confident Operation ($5,000 - $10,000)

**Intent:** Enable V3 features (graph boost, aggressive sizing) with proven simulator accuracy.

**High-Level Outcomes:**

- Rust sidecar healthy for 30 consecutive days
- Graph analysis (God View) operational
- V3 signal boost enabled
- Assassin enabled (95% accuracy verified)
- Kill switch tested within 7 days

### Phase 3+/Phase 4: Full Operation ($10,000+)

**Intent:** Maximum operational capacity with all features enabled and proven track record.

**High-Level Outcomes:**

- 100+ live trades completed
- Win rate ≥55% over 3 months
- Graph signal ROI independently positive
- Full Ghost Mode entropy injection active
- Complete operational runbook validated

---

## 3. Phase Preconditions

### Phase 0 Entry

- No capital requirements
- Development environment configured
- API keys obtained (Helius, BirdEye, optional: Solscan)
- Git repository initialized

### Phase 0 → Phase 1 Entry

- Signals Tracked: ≥100 (`SELECT COUNT(*) FROM signals`)
- Observation Period: ≥8 weeks
- Paper Win Rate: ≥55% over ≥100 signals spanning ≥8 weeks
- Capital Available: ≥$500 verified SOL balance
- System Uptime: 7 consecutive days without crashes or manual restarts
- All veto gates implemented and tested

### Phase 1 → Phase 2 Entry

- Live Trades: ≥20 (`SELECT COUNT(*) FROM trades WHERE paper=false`)
- Live Win Rate: ≥50%
- Max Drawdown: <20% peak-to-trough
- Capital: ≥$2,000 current SOL balance in USD
- Days Active: ≥30 since first live trade

### Phase 2 → Phase 2.5 Entry

- Live Trades: ≥50
- Simulator accuracy tracking operational
- Loser sample collection initiated

### Phase 2.5 → Phase 3 Entry

- Simulator Accuracy: ≥95% (blocked_losers / total_losers, weighted)
- Loser Samples: ≥50 weighted samples
- Live Win Rate: ≥52%
- Positive ROI: >0% after infrastructure costs
- Capital: ≥$5,000

### Phase 3 → Phase 4 Entry

- Live Trades: ≥100
- Live Win Rate: ≥55% over last 3 months
- Graph Signal ROI: Positive (V3 signals profitable independently)
- Capital: ≥$10,000
- Rust Sidecar: Healthy 30 days (<100ms p99 latency, no restarts)
- Kill Switch: Tested within 7 days
- Days in Phase 3: ≥60

---

## 4. Phase Exit Criteria

### Phase 0 Exit (Proceed to Phase 1)

- [ ] 100+ signals recorded in database
- [ ] Observation period ≥8 weeks elapsed
- [ ] Paper win rate ≥55% over ≥100 signals spanning ≥8 weeks
- [ ] System ran 7 consecutive days without intervention
- [ ] All fail-closed gates return BLOCK on missing/invalid data
- [ ] Verified $500+ SOL in execution wallet

### Phase 1 Exit (Proceed to Phase 2)

- [ ] 20+ non-paper trades in `trades` table
- [ ] Calculated win rate ≥50% on live trades
- [ ] Drawdown never exceeded 20%
- [ ] Current capital ≥$2,000 USD equivalent
- [ ] 30+ days since first live trade

### Phase 2 Exit (Proceed to Phase 2.5)

- [ ] 50+ live trades completed
- [ ] Simulator accuracy tracking shows valid data
- [ ] Loser outcome classification working

### Phase 2.5 Exit (Proceed to Phase 3)

- [ ] Simulator accuracy ≥95% with ≥50 weighted samples
- [ ] V3/Assassin code complete and tested (but disabled)
- [ ] Graph analysis pipeline validated in observation mode
- [ ] Capital ≥$5,000

### Phase 3 Exit (Proceed to Phase 4)

- [ ] 100+ total live trades
- [ ] 3-month rolling win rate ≥55%
- [ ] Graph-sourced signals show positive independent ROI
- [ ] Rust sidecar 30-day uptime verified
- [ ] Capital ≥$10,000
- [ ] Kill switch manually tested and documented
- [ ] 60+ days in Phase 3

---

## 5. Module Build Order (High Level)

Build modules in this sequence to ensure dependencies are satisfied:

1. **Database Layer** (`src/database.py`)
   - SQLite schema per DATA_DICTIONARY.md
   - Tables: wallets, funding, signals, trades, buys, kill_switch_events, system_state
   - Indexes as specified
   - System state management

2. **Configuration** (`config/`)
   - settings.yaml structure
   - .env for secrets (API keys)
   - CEX blacklist (cex_blacklist.yaml)

3. **API Clients** (`src/api_clients.py`)
   - HeliusClient (webhooks, enhanced transactions, RPC)
   - BirdEyeClient (price, token overview)
   - JupiterClient (quote, swap, swap-instructions)
   - SolanaRPCClient
   - DexScreenerClient (optional/fallback only; not authoritative; never required for trade execution)
   - Rate limiting and retry logic per API_REFERENCE.md limits

4. **Event Logger** (`src/events.py`)
   - Structured JSON logging per EVENTS.pdf
   - All event types implemented
   - Correlation ID generation
   - Severity levels enforced

5. **Wallet Tracker** (`src/wallet_tracker.py`)
   - Webhook ingestion
   - Transaction parsing
   - Wallet tier classification (S/A/B/C)
   - Confidence decay (30-day half-life)

6. **Signal Processor** (`src/signal_processor.py`)
   - Signal detection from whale activity
   - Asset class classification
   - Signal freshness enforcement
   - Signal ID generation

7. **Veto Gates** (`src/veto_gates.py`)
   - Sequential gate evaluation per POLICY.md order
   - Kill switch gate
   - Capital preservation gate
   - Signal freshness gate
   - Token age gate
   - Spread gate (3% max)
   - Liquidity gate (per asset class minimums)
   - Tax gate (10% max)
   - Cooldown gate (wallet/token/cluster/global)
   - Simulation gate

8. **Simulator** (`src/simulator.py`)
   - Transaction simulation via Solana RPC
   - Honeypot detection
   - Tax calculation
   - Accuracy tracking for Assassin gate

9. **Risk Manager** (`src/risk_manager.py`)
   - Position sizing per phase
   - Capital preservation mode
   - Kill switch logic (full and graph)
   - Drawdown monitoring
   - First 50 Trades rules

10. **Trade Executor** (`src/executor.py`)
    - Jupiter swap integration
    - Paper trade simulation
    - Live trade execution
    - Slippage handling
    - Transaction confirmation

11. **Exit Manager** (`src/exit_manager.py`)
    - Panic exit (15% drop + 30% liquidity shrink)
    - Time stops per asset class
    - Trailing stop (10% activation, 5% trail)
    - Whale inactivity exit

12. **Scripts** (`scripts/`)
    - bootstrap.py (initialization/verification)
    - harvester.py (trending token discovery)
    - phase0_logger.py (paper trade logging)
    - god_view.py (graph analysis - Phase 3)
    - backtest.py (performance analysis)

13. **Entropy Injector** (`src/entropy.py`) - Phase 3+
    - Ghost Mode implementation
    - Random signal skipping (10%)
    - Position size variation (±5%)
    - Delay jitter (5-30ms)

14. **Assassin Module** (`src/assassin.py`) - Phase 3+ (Locked until 95% accuracy)
    - Aggressive signal filtering
    - V3 graph boost application
    - Only enabled when gate passes

15. **Rust Sidecar** - Phase 3+
    - Low-latency execution path
    - P99 latency <100ms requirement

---

## 6. Testing Strategy (Per Phase)

### Phase 0 Testing

- **Unit Tests:** Database operations, API client mocking, signal detection logic
- **Integration Tests:** End-to-end signal flow (detection → storage → paper logging)
- **Validation:** All veto gates return BLOCK on None/missing data
- **Coverage Target:** 80% on core modules

### Phase 1 Testing

- **Unit Tests:** Veto gate logic, position sizing calculations
- **Integration Tests:** Full trade lifecycle (signal → veto → execute → exit)
- **Manual Verification:** First 50 Trades rule enforcement
- **Validation:** Kill switch activation/deactivation
- **Coverage Target:** 85% on safety-critical paths

### Phase 2 Testing

- **Unit Tests:** Simulator accuracy calculation, drawdown tracking
- **Integration Tests:** Capital preservation mode activation
- **Regression Tests:** All Phase 0/1 tests pass
- **Validation:** ROI calculation accuracy

### Phase 2.5 Testing

- **Unit Tests:** Weighted accuracy calculation (rug/modest/marginal)
- **Integration Tests:** Assassin gate blocking until 95% threshold
- **Validation:** Sample count verification, accuracy audit

### Phase 3 Testing

- **Unit Tests:** Graph analysis, cluster detection, mother wallet identification
- **Integration Tests:** Graph kill switch triggers
- **Performance Tests:** Rust sidecar latency verification
- **Validation:** 30-day sidecar stability, kill switch manual test

### Phase 4 Testing

- **Load Tests:** System under high signal volume
- **Chaos Tests:** API failures, rate limits, network partitions
- **Full Regression:** Complete test suite
- **Operational Tests:** Runbook procedures (key rotation, wallet rotation, emergency procedures)

---

## 7. Git Discipline

- Repository: https://github.com/albarami/Whale_hunter
- Each phase completion must result in clean commits pushed to GitHub
- Branch strategy: `main` for stable releases, `develop` for active work, feature branches as needed
- Commit messages must reference phase and component
- No commits containing:
  - API keys or secrets
  - TODO/FIXME/placeholder in `src/` directory
  - Failing tests
  - `pass` statements in veto gates
  - `return True` bypassing safety gates
- Phase transition commits must be tagged (e.g., `v3.1.0-phase1-complete`)
- Database backups committed to separate backup location (not main repo)

---

## 8. Explicit Non-Goals

The following are **explicitly forbidden** in early phases:

### Phase 0 Non-Goals

- Live trade execution (paper only)
- Real capital at risk
- V3 features (graph boost, Assassin)
- Rust sidecar development

### Phase 1 Non-Goals

- V3 graph boost signals
- Assassin module activation
- Rust sidecar integration
- Position sizes exceeding Phase 1 limits (2% risk, 10% max position)
- Skipping First 50 Trades rules

### Phase 2 Non-Goals

- Assassin activation (regardless of perceived accuracy)
- Graph-based signal boosting
- Bypassing simulator accuracy gate
- Position sizes exceeding Phase 2 limits

### Phase 2.5 Non-Goals

- Enabling Assassin below 95% accuracy threshold
- Enabling Assassin with fewer than 50 weighted samples
- Treating "close enough" (e.g., 94%) as acceptable

### All Phases Non-Goals (Never Allowed)

- Disabling V2 defensive foundation (spread, liquidity, tax, time-stop, panic exit, cooldowns)
- Weakening veto thresholds
- Adding override parameters to safety checks
- Skipping simulation "just this once"
- Commenting out kill switch checks
- Default-pass on missing/invalid/unknown data
- Placeholders in production paths (`src/`)
- Hardcoded test values that bypass checks

---

## Assumptions

1. **API Availability:** Helius, BirdEye, Jupiter, and Solana RPC endpoints remain available with documented rate limits (DexScreener is optional fallback only)
2. **SQLite Sufficiency:** SQLite is adequate for data storage; no migration to PostgreSQL needed in v3.1
3. **Single Operator:** System designed for single operator; no multi-user authentication required
4. **Solana Network Stability:** Solana mainnet operates normally; extended outages may require manual intervention
5. **Phase 2.5 Duration:** Bridge phase duration depends on loser sample collection rate; no fixed timeline

---

**Document Version:** 1.0  
**Approved:** 2026-01-26  
**Next Document:** TASKS.md (generated)
