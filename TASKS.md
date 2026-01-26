# Whale Hunter v3.1 - Task List

**Generated From:** IMPLEMENTATION_PLAN.md (Approved)  
**Source of Truth:** docs/POLICY.md, docs/GATES.md, docs/DATA_DICTIONARY.md, docs/API_REFERENCE.md, docs/IMPLEMENTATION_RULES.md, docs/THREAT_MODEL.md, docs/RUNBOOK.md, docs/EVENTS.pdf  
**Repository:** https://github.com/albarami/Whale_hunter

---

## Phase 0: Paper Trading (Observation Mode)

### 0.1 Project Setup

- [ ] **0.1.1** Initialize git repository and push to GitHub
- [ ] **0.1.2** Create directory structure: `src/`, `config/`, `scripts/`, `tests/`, `data/`, `logs/`
- [ ] **0.1.3** Create `requirements.txt` with pinned dependencies
- [ ] **0.1.4** Create `.env.example` with required environment variable templates
- [ ] **0.1.5** Add `.gitignore` (exclude `.env`, `data/*.db`, `logs/`, `__pycache__/`)
- [ ] **0.1.6** Obtain API keys: Helius, BirdEye (Solscan optional)
- [ ] **0.1.7** Create `config/settings.yaml` with phase-specific parameters

### 0.2 Database Layer (`src/database.py`)

- [ ] **0.2.1** Create SQLite database file: `data/wallet_graph.db`
- [ ] **0.2.2** Implement `wallets` table per DATA_DICTIONARY.md (address, first_seen, last_activity, total_trades, winning_trades, total_pnl_sol, tier, is_cex, confidence, last_confidence_update, metadata)
- [ ] **0.2.3** Implement `funding` table (id, source_wallet, target_wallet, amount_sol, timestamp, tx_signature, hop_distance)
- [ ] **0.2.4** Implement `signals` table (id, wallet_address, token_address, token_symbol, action, amount_usd, price_at_signal, timestamp, confidence, source_version, graph_boost, asset_class, veto_reason, processed, outcome, price_24h, notes)
- [ ] **0.2.5** Implement `trades` table (id, signal_id, execution_wallet, token_address, side, amount_sol, amount_tokens, price, slippage_bps, gas_lamports, tx_signature, timestamp, paper, pnl_sol, pnl_pct, exit_reason, cluster_id)
- [ ] **0.2.6** Implement `buys` table (legacy tracking)
- [ ] **0.2.7** Implement `kill_switch_events` table (id, trigger, timestamp, details, resolved_at, resolution_notes)
- [ ] **0.2.8** Implement `system_state` table (key, value, updated_at)
- [ ] **0.2.9** Create indexes: `idx_wallets_tier`, `idx_wallets_confidence`, `idx_funding_source`, `idx_funding_target`, `idx_funding_timestamp`, `idx_signals_timestamp`, `idx_signals_token`, `idx_signals_wallet`, `idx_signals_outcome`, `idx_trades_timestamp`, `idx_trades_signal`, `idx_trades_token`
- [ ] **0.2.10** Implement `WalletGraphDB` class with CRUD methods
- [ ] **0.2.11** Implement `store_system_state()` and `get_system_state()` methods
- [ ] **0.2.12** Implement `log_kill_switch_event()` method
- [ ] **0.2.13** Enable WAL mode for crash recovery
- [ ] **0.2.14** Write unit tests for all database operations
- [ ] **0.2.15** Verify fail-closed: all queries return BLOCK-compatible results on error

### 0.3 Configuration (`config/`)

- [ ] **0.3.1** Create `config/settings.yaml` with phase parameters (current_phase, capital thresholds, position limits)
- [ ] **0.3.2** Create `config/.env.example` with API key templates (HELIUS_API_KEY, BIRDEYE_API_KEY, SOLANA_RPC_URL) — **NOTE:** `.env` is local-only, never committed. Operator copies `.env.example` to `.env` and fills in real keys.
- [ ] **0.3.3** Ensure `.env` is in `.gitignore` — never commit secrets
- [ ] **0.3.4** Create `config/cex_blacklist.yaml` with known CEX wallet addresses
- [ ] **0.3.5** Implement config loader with environment variable override support
- [ ] **0.3.6** Add validation: reject startup if required API keys missing

### 0.4 Event Logger (`src/events.py`)

- [ ] **0.4.1** Implement base event structure per EVENTS.pdf (event_type, timestamp, severity, correlation_id, data)
- [ ] **0.4.2** Implement `emit_event()` helper function with ISO 8601 UTC timestamps
- [ ] **0.4.3** Implement correlation ID generation: `corr_{timestamp_ms}_{random6}`
- [ ] **0.4.4** Configure loguru with JSON serialization
- [ ] **0.4.5** Implement file rotation (100 MB) and retention (30 days)
- [ ] **0.4.6** Implement all Signal events: SIGNAL_DETECTED, SIGNAL_EXPIRED, SIGNAL_SKIPPED_ENTROPY
- [ ] **0.4.7** Implement all Veto events: VETO_KILL_SWITCH, VETO_CAPITAL_PRESERVATION, VETO_SIGNAL_STALE, VETO_TOKEN_AGE, VETO_SPREAD, VETO_LIQUIDITY, VETO_TAX, VETO_COOLDOWN, VETO_SIMULATION
- [ ] **0.4.8** Implement all Simulation events: SIM_STARTED, SIM_PASS, SIM_BLOCK_HONEYPOT, SIM_BLOCK_TAX, SIM_BLOCK_LIQUIDITY, SIM_ERROR
- [ ] **0.4.9** Implement all Trade events: TRADE_INTENT_CREATED, TRADE_EXECUTED, TRADE_FAILED, TRADE_PARTIAL_FILL
- [ ] **0.4.10** Implement all Exit events: EXIT_PANIC, EXIT_TIME_STOP, EXIT_WHALE_INACTIVITY, EXIT_TRAILING_STOP, EXIT_MANUAL, EXIT_KILL_SWITCH
- [ ] **0.4.11** Implement all Risk events: KILL_SWITCH_TRIGGERED, KILL_SWITCH_CLEARED, CAPITAL_PRESERVATION_ACTIVATED, CAPITAL_PRESERVATION_CLEARED, DRAWDOWN_WARNING
- [ ] **0.4.12** Implement all Graph events: GRAPH_DISABLED_OBSERVATION_MODE, GRAPH_RESUMED, MOTHER_WALLET_DISCOVERED, MOTHER_WALLET_DECAYED, CLUSTER_DETECTED, GRAPH_POISONING_SUSPECTED
- [ ] **0.4.13** Implement all System events: SYSTEM_STARTUP, SYSTEM_SHUTDOWN, API_ERROR, API_RATE_LIMITED, WALLET_ROTATED, PHASE_TRANSITION
- [ ] **0.4.14** Write unit tests for event emission and formatting

### 0.5 API Clients (`src/api_clients.py`)

- [ ] **0.5.1** Implement `src/api_clients.py` as single module with all client classes
- [ ] **0.5.2** Implement `HeliusClient` class:
  - [ ] Webhook setup (POST /v0/webhooks)
  - [ ] Enhanced transaction history (GET /v0/addresses/{address}/transactions)
  - [ ] RPC proxy (POST /v0/rpc)
  - [ ] Parse transaction (POST /v0/transactions)
  - [ ] Rate limiting: 10 req/sec enhanced, 50 req/sec RPC
- [ ] **0.5.3** Implement `BirdEyeClient` class:
  - [ ] Token price (GET /defi/price)
  - [ ] Token overview (GET /defi/token_overview)
  - [ ] Token list by wallet (GET /v1/wallet/token_list)
  - [ ] Rate limiting: 100 req/min (free tier)
- [ ] **0.5.4** Implement `JupiterClient` class:
  - [ ] Quote API (GET /quote)
  - [ ] Swap API (POST /swap)
  - [ ] Swap instructions (POST /swap-instructions)
  - [ ] Rate limiting: 600 req/min quote, 300 req/min swap
- [ ] **0.5.5** Implement `SolanaRPCClient` class:
  - [ ] simulateTransaction
  - [ ] getTransaction
  - [ ] getSignaturesForAddress
  - [ ] getBalance
  - [ ] Rate limiting per provider
- [ ] **0.5.6** Implement `DexScreenerClient` class (optional/fallback):
  - [ ] Token info (GET /latest/dex/tokens/{tokenAddress})
  - [ ] Search pairs (GET /latest/dex/search/)
  - [ ] Mark as non-authoritative in code comments
- [ ] **0.5.7** Implement token bucket rate limiter for all clients
- [ ] **0.5.8** Implement exponential backoff retry logic
- [ ] **0.5.9** Implement API_ERROR and API_RATE_LIMITED event emission
- [ ] **0.5.10** Write unit tests with mocked responses
- [ ] **0.5.11** Verify fail-closed: timeout/error → return None (triggers BLOCK downstream)

### 0.6 Wallet Tracker (`src/wallet_tracker.py`)

- [ ] **0.6.1** Implement Helius webhook receiver endpoint
- [ ] **0.6.2** Implement transaction parser for SWAP transactions
- [ ] **0.6.3** Implement wallet tier classification (S/A/B/C) based on win rate and PnL
- [ ] **0.6.4** Implement confidence score calculation (0.0-1.0)
- [ ] **0.6.5** Implement confidence decay: `half_life = 30 days`, `new_confidence = old_confidence * 0.5^(days/30)`
- [ ] **0.6.6** Implement CEX wallet detection using blacklist
- [ ] **0.6.7** Implement funding relationship tracking (source → target)
- [ ] **0.6.8** Emit WALLET_DISCOVERED events
- [ ] **0.6.9** Write unit tests for tier classification and decay
- [ ] **0.6.10** Verify fail-closed: unknown wallet tier → default to lowest trust

### 0.7 Signal Processor (`src/signal_processor.py`)

- [ ] **0.7.1** Implement signal detection from whale wallet SWAP activity
- [ ] **0.7.2** Implement signal ID generation: `sig_{timestamp}_{random8}`
- [ ] **0.7.3** Implement asset class classification (meme_coin_low_cap, mid_cap, large_cap)
- [ ] **0.7.4** Implement signal freshness window enforcement per POLICY.md:
  - [ ] meme_coin_low_cap: 300s (5 min)
  - [ ] established_altcoin: 900s (15 min)
  - [ ] major_crypto_cex: 1800s (30 min)
- [ ] **0.7.5** Implement source_version tagging (v2/v25/v3)
- [ ] **0.7.6** Emit SIGNAL_DETECTED events with all required fields
- [ ] **0.7.7** Store signals in database with processed=false initially
- [ ] **0.7.8** Write unit tests for signal generation
- [ ] **0.7.9** Verify fail-closed: stale signal → emit SIGNAL_EXPIRED and skip

### 0.8 Veto Gates (`src/veto_gates.py`)

- [ ] **0.8.1** Implement sequential gate evaluation per POLICY.md order (first failure = rejection)
- [ ] **0.8.2** Implement Gate 1: Kill Switch check
- [ ] **0.8.3** Implement Gate 2: Capital Preservation mode check
- [ ] **0.8.4** Implement Gate 3: Signal Freshness check (per asset class)
- [ ] **0.8.5** Implement Gate 4: Token Age check:
  - [ ] meme_coin_low_cap: 3600s (1 hour) minimum
  - [ ] mid_cap: 1800s (30 min) minimum
  - [ ] large_cap: 0 minimum
- [ ] **0.8.6** Implement Gate 5: Spread check (veto if spread > 3%)
- [ ] **0.8.7** Implement Gate 6: Liquidity check:
  - [ ] meme_coin: $10,000 minimum
  - [ ] mid_cap: $50,000 minimum
  - [ ] large_cap: $100,000 minimum
- [ ] **0.8.8** Implement Gate 7: Tax check (veto if simulated_tax > 10%)
- [ ] **0.8.9** Implement Gate 8: Cooldown check:
  - [ ] Per Wallet: 3 trades / 24 hours
  - [ ] Per Token: 2 trades / 12 hours
  - [ ] Per Cluster: 5 trades / session
  - [ ] Global: 10 trades / 1 hour
- [ ] **0.8.10** Implement Gate 9: Simulation check (honeypot detection, tax verification)
- [ ] **0.8.11** Emit appropriate VETO_* event on each gate failure
- [ ] **0.8.12** Log all gates checked (pass/fail) per POLICY.md compliance
- [ ] **0.8.13** Write unit tests for each gate with edge cases
- [ ] **0.8.14** **CRITICAL:** Verify fail-closed - missing/null/stale data → BLOCK (no exceptions)
- [ ] **0.8.15** **CRITICAL:** No `pass` statements, no `return True` bypasses, no placeholders

### 0.9 Simulator (`src/simulator.py`)

- [ ] **0.9.1** Implement transaction simulation via Solana RPC simulateTransaction
- [ ] **0.9.2** Implement honeypot detection (sell reverts or >90% sell tax)
- [ ] **0.9.3** Implement buy/sell tax calculation from simulation results
- [ ] **0.9.4** Implement accuracy tracking: store (predicted_outcome, actual_outcome) pairs
- [ ] **0.9.5** Implement weighted accuracy calculation:
  - [ ] rug (100% weight)
  - [ ] modest loss (50% weight)
  - [ ] marginal loss (25% weight)
- [ ] **0.9.6** Emit SIM_STARTED, SIM_PASS, SIM_BLOCK_*, SIM_ERROR events
- [ ] **0.9.7** Write unit tests with mocked RPC responses
- [ ] **0.9.8** Verify fail-closed: simulation error → BLOCK

### 0.10 Risk Manager (`src/risk_manager.py`)

- [ ] **0.10.1** Implement position sizing per phase:
  - [ ] Phase 0: 0% (paper only)
  - [ ] Phase 1: 2% risk, 10% max position
  - [ ] Phase 2: 2.5% risk, 12% max position
  - [ ] Phase 3: 3% risk, 15% max position
  - [ ] Phase 4: 3.5% risk, 18% max position
- [ ] **0.10.2** Implement position size formula: `min(capital * risk / confidence, capital * max_position_pct)`
- [ ] **0.10.3** Implement Capital Preservation Mode activation (drawdown ≥ 15%)
- [ ] **0.10.4** Implement Capital Preservation Mode behavior:
  - [ ] Position size: 25% of normal
  - [ ] Confidence threshold: base + 0.15
  - [ ] Graph signals: disabled
  - [ ] Resume: manual only
- [ ] **0.10.5** Implement Kill Switch logic (full and graph variants)
- [ ] **0.10.6** Implement drawdown monitoring and DRAWDOWN_WARNING emission at 10%, 15%
- [ ] **0.10.7** Implement First 50 Trades rules:
  - [ ] Max position: 3% of capital
  - [ ] Signal source: V2.0 only
  - [ ] Max trades week 1: 5
  - [ ] Daily trade review required before 2nd daily trade
- [ ] **0.10.8** Emit CAPITAL_PRESERVATION_ACTIVATED, KILL_SWITCH_TRIGGERED events
- [ ] **0.10.9** Write unit tests for all risk calculations
- [ ] **0.10.10** Verify fail-closed: unknown phase → use most conservative limits

### 0.11 Trade Executor (`src/executor.py`)

- [ ] **0.11.1** Implement paper trade simulation (no actual execution)
- [ ] **0.11.2** Implement trade ID generation: `trade_{timestamp}_{random8}`
- [ ] **0.11.3** Implement Jupiter swap integration for live trades
- [ ] **0.11.4** Implement slippage handling (configurable slippageBps)
- [ ] **0.11.5** Implement transaction confirmation polling
- [ ] **0.11.6** Emit TRADE_INTENT_CREATED, TRADE_EXECUTED, TRADE_FAILED events
- [ ] **0.11.7** Store trade results in database
- [ ] **0.11.8** Write unit tests with mocked Jupiter responses
- [ ] **0.11.9** **Phase 0 only:** Ensure live execution is disabled (paper=true enforced)
- [ ] **0.11.10** **CRITICAL:** In Phase 0, live execution is hard-blocked even if API keys exist — phase check must occur before any transaction signing

### 0.12 Exit Manager (`src/exit_manager.py`)

- [ ] **0.12.1** Implement panic exit trigger: price drop >15% in <5 min AND liquidity shrink >30%
- [ ] **0.12.2** Implement time stops per asset class:
  - [ ] meme_coin: min 12h, max 24h
  - [ ] mid_cap: min 24h, max 48h
  - [ ] large_cap: min 48h, max 72h
- [ ] **0.12.3** Implement trailing stop:
  - [ ] Activation: +10% unrealized profit
  - [ ] Trail distance: 5% from peak
- [ ] **0.12.4** Implement whale inactivity exit: reduce 50% if whale inactive 24h
- [ ] **0.12.5** Emit EXIT_PANIC, EXIT_TIME_STOP, EXIT_TRAILING_STOP, EXIT_WHALE_INACTIVITY events
- [ ] **0.12.6** Write unit tests for all exit conditions
- [ ] **0.12.7** Verify: V2 exits (panic, time stops) cannot be disabled

### 0.13 Scripts (`scripts/`)

- [ ] **0.13.1** Implement `scripts/bootstrap.py`:
  - [ ] Database initialization/verification
  - [ ] API connectivity check
  - [ ] Config validation
  - [ ] Add verification mode flag (e.g., `--verify`) for health checks without modification
- [ ] **0.13.2** Implement `scripts/harvester.py`:
  - [ ] Trending token discovery via DexScreener (optional)
  - [ ] Whale wallet discovery
  - [ ] `--daemon` flag for background operation
- [ ] **0.13.3** Implement `scripts/phase0_logger.py`:
  - [ ] Paper trade logging
  - [ ] `--stats` flag for signal statistics
  - [ ] Win rate calculation
- [ ] **0.13.4** Implement `scripts/backtest.py`:
  - [ ] Historical signal analysis
  - [ ] `--start` and `--end` date parameters
  - [ ] `--go-no-go` flag for phase transition metrics
  - [ ] `--last-7-days`, `--last-30-days` shortcuts
- [ ] **0.13.5** Write script usage documentation

### 0.14 Main Entry Point (`src/main.py`)

- [ ] **0.14.1** Implement main trading loop
- [ ] **0.14.2** Emit SYSTEM_STARTUP event on start
- [ ] **0.14.3** Implement graceful shutdown with SYSTEM_SHUTDOWN event
- [ ] **0.14.4** Implement signal handler for SIGTERM
- [ ] **0.14.5** Verify phase 0 enforces paper trading only

### 0.15 Testing (Phase 0)

- [ ] **0.15.1** Create `tests/` directory structure mirroring `src/`
- [ ] **0.15.2** Write unit tests for database operations
- [ ] **0.15.3** Write unit tests for API clients with mocking
- [ ] **0.15.4** Write unit tests for signal detection logic
- [ ] **0.15.5** Write integration tests: signal detection → storage → paper logging
- [ ] **0.15.6** Write validation tests: all veto gates return BLOCK on None/missing data
- [ ] **0.15.7** Achieve 80% coverage on core modules
- [ ] **0.15.8** Set up pytest configuration

### 0.16 Phase 0 Exit Validation

- [ ] **0.16.1** Verify 100+ signals recorded in database
- [ ] **0.16.2** Verify observation period ≥8 weeks elapsed
- [ ] **0.16.3** Calculate paper win rate: must be ≥55% over ≥100 signals
- [ ] **0.16.4** Verify system ran 7 consecutive days without intervention
- [ ] **0.16.5** Run fail-closed validation suite
- [ ] **0.16.6** Verify $500+ SOL in execution wallet
- [ ] **0.16.7** Tag commit: `v3.1.0-phase0-complete`
- [ ] **0.16.8** Push to GitHub

---

## Phase 1: Live Trading ($500 - $2,000)

### 1.1 Live Execution Enablement

- [ ] **1.1.1** Update `config/settings.yaml`: set `current_phase: 1`
- [ ] **1.1.2** Enable live trade execution in `src/executor.py` (remove paper-only enforcement)
- [ ] **1.1.3** Configure execution wallet in `.env`
- [ ] **1.1.4** Verify Jupiter swap integration works with real transactions
- [ ] **1.1.5** Test with minimal amount (0.01 SOL) before full operation

### 1.2 First 50 Trades Enforcement

- [ ] **1.2.1** Implement trade counter in system_state
- [ ] **1.2.2** Enforce max position: 3% of capital when trade_count < 50
- [ ] **1.2.3** Enforce V2.0 signals only (graph_boost_enabled = false)
- [ ] **1.2.4** Enforce max 5 trades in week 1
- [ ] **1.2.5** Implement manual approval requirement for 2nd daily trade
- [ ] **1.2.6** Write tests for First 50 Trades rules

### 1.3 V2.0 Defensive Foundation Verification

- [ ] **1.3.1** Verify spread veto (3%) is always active
- [ ] **1.3.2** Verify liquidity minimums are always active
- [ ] **1.3.3** Verify tax veto (10%) is always active
- [ ] **1.3.4** Verify time stops are always active
- [ ] **1.3.5** Verify panic exit is always active
- [ ] **1.3.6** Verify cooldowns are always active
- [ ] **1.3.7** Write integration tests confirming V2.0 cannot be bypassed

### 1.4 Kill Switch Implementation

- [ ] **1.4.1** Implement manual kill switch activation via script
- [ ] **1.4.2** Implement automatic kill switch triggers:
  - [ ] 3+ consecutive losses
  - [ ] Win rate <40% over 20 trades
  - [ ] >20% drawdown in 24h
- [ ] **1.4.3** Implement kill switch position closure (close all open positions)
- [ ] **1.4.4** Implement kill switch resume (manual only)
- [ ] **1.4.5** Test kill switch activation/deactivation cycle

### 1.5 Testing (Phase 1)

- [ ] **1.5.1** Write unit tests for veto gate logic
- [ ] **1.5.2** Write unit tests for position sizing calculations
- [ ] **1.5.3** Write integration tests: signal → veto → execute → exit lifecycle
- [ ] **1.5.4** Manual verification: First 50 Trades enforcement
- [ ] **1.5.5** Achieve 85% coverage on safety-critical paths

### 1.6 Phase 1 Exit Validation

- [ ] **1.6.1** Verify 20+ non-paper trades in `trades` table
- [ ] **1.6.2** Calculate live win rate: must be ≥50%
- [ ] **1.6.3** Verify drawdown never exceeded 20%
- [ ] **1.6.4** Verify current capital ≥$2,000 USD equivalent
- [ ] **1.6.5** Verify 30+ days since first live trade
- [ ] **1.6.6** Tag commit: `v3.1.0-phase1-complete`
- [ ] **1.6.7** Push to GitHub

---

## Phase 2: Moderate Scaling ($2,000 - $5,000)

### 2.1 Position Sizing Update

- [ ] **2.1.1** Update `config/settings.yaml`: set `current_phase: 2`
- [ ] **2.1.2** Verify position sizing uses Phase 2 limits (2.5% risk, 12% max)
- [ ] **2.1.3** Verify First 50 Trades rules no longer apply (if trade_count ≥ 50)

### 2.2 Simulator Accuracy Tracking

- [ ] **2.2.1** Implement loser outcome classification (rug, modest, marginal)
- [ ] **2.2.2** Implement weighted accuracy calculation
- [ ] **2.2.3** Implement accuracy reporting in `scripts/backtest.py --go-no-go`
- [ ] **2.2.4** Store accuracy metrics in system_state

### 2.3 ROI Tracking

- [ ] **2.3.1** Implement infrastructure cost tracking
- [ ] **2.3.2** Implement net profit calculation (gross profit - infra costs)
- [ ] **2.3.3** Implement ROI reporting

### 2.4 Testing (Phase 2)

- [ ] **2.4.1** Write unit tests for simulator accuracy calculation
- [ ] **2.4.2** Write unit tests for drawdown tracking
- [ ] **2.4.3** Write integration tests for Capital Preservation mode activation
- [ ] **2.4.4** Run full regression (Phase 0/1 tests must pass)
- [ ] **2.4.5** Validate ROI calculation accuracy

### 2.5 Phase 2 Exit Validation

- [ ] **2.5.1** Verify 50+ live trades completed
- [ ] **2.5.2** Verify simulator accuracy tracking shows valid data
- [ ] **2.5.3** Verify loser outcome classification working
- [ ] **2.5.4** Tag commit: `v3.1.0-phase2-complete`
- [ ] **2.5.5** Push to GitHub

---

## Phase 2.5: Simulator Validation (Bridge Phase)

### 2.5.1 Accuracy Gate Enforcement

- [ ] **2.5.1.1** Implement 95% accuracy gate check
- [ ] **2.5.1.2** Implement 50 weighted samples minimum check
- [ ] **2.5.1.3** Implement gate status reporting
- [ ] **2.5.1.4** **CRITICAL:** Verify Assassin remains disabled until gate passes

### 2.5.2 V3 Preparation (Code Only, Not Enabled)

- [ ] **2.5.2.1** Implement `src/assassin.py` (disabled by default)
- [ ] **2.5.2.2** Implement graph boost calculation (not applied yet)
- [ ] **2.5.2.3** Write tests for Assassin with gate blocking

### 2.5.3 Graph Analysis Preparation

- [ ] **2.5.3.1** Implement `scripts/god_view.py` (observation mode only)
- [ ] **2.5.3.2** Implement mother wallet identification
- [ ] **2.5.3.3** Implement cluster detection
- [ ] **2.5.3.4** Emit MOTHER_WALLET_DISCOVERED, CLUSTER_DETECTED events (observation only)

### 2.5.4 Testing (Phase 2.5)

- [ ] **2.5.4.1** Write unit tests for weighted accuracy calculation
- [ ] **2.5.4.2** Write integration tests: Assassin gate blocks until 95%
- [ ] **2.5.4.3** Validate sample count verification
- [ ] **2.5.4.4** Audit accuracy calculation correctness

### 2.5.5 Phase 2.5 Exit Validation

- [ ] **2.5.5.1** Verify simulator accuracy ≥95% with ≥50 weighted samples
- [ ] **2.5.5.2** Verify V3/Assassin code complete and tested (but disabled)
- [ ] **2.5.5.3** Verify graph analysis pipeline validated in observation mode
- [ ] **2.5.5.4** Verify capital ≥$5,000
- [ ] **2.5.5.5** Tag commit: `v3.1.0-phase2.5-complete`
- [ ] **2.5.5.6** Push to GitHub

---

## Phase 3: Confident Operation ($5,000 - $10,000)

### 3.1 Assassin Enablement

- [ ] **3.1.1** Update `config/settings.yaml`: set `current_phase: 3`
- [ ] **3.1.2** Enable Assassin module (95% gate already passed)
- [ ] **3.1.3** Enable graph boost application to signals
- [ ] **3.1.4** Verify Position sizing uses Phase 3 limits (3% risk, 15% max)

### 3.2 Graph Kill Switch

- [ ] **3.2.1** Implement Graph Kill Switch triggers:
  - [ ] >10 new mothers in 24h
  - [ ] >5 clusters with >80% overlap (Jaccard similarity)
  - [ ] Win rate <40% across graph signals (7-day rolling)
- [ ] **3.2.2** Implement Graph Kill Switch response: graph_boost = 0, graph_signals_enabled = false
- [ ] **3.2.3** Implement manual resume requirement
- [ ] **3.2.4** Test Graph Kill Switch activation/deactivation

### 3.3 Entropy Injector (`src/entropy.py`)

- [ ] **3.3.1** Implement Ghost Mode
- [ ] **3.3.2** Implement random signal skipping (10% of valid signals)
- [ ] **3.3.3** Implement position size variation (±5%)
- [ ] **3.3.4** Implement delay jitter (5-30ms)
- [ ] **3.3.5** Emit SIGNAL_SKIPPED_ENTROPY events

### 3.4 Rust Sidecar (Optional Performance Enhancement)

- [ ] **3.4.1** Design Rust sidecar architecture
- [ ] **3.4.2** Implement low-latency execution path
- [ ] **3.4.3** Implement health monitoring
- [ ] **3.4.4** Verify P99 latency <100ms
- [ ] **3.4.5** Begin 30-day stability tracking

### 3.5 Testing (Phase 3)

- [ ] **3.5.1** Write unit tests for graph analysis, cluster detection
- [ ] **3.5.2** Write integration tests for Graph Kill Switch triggers
- [ ] **3.5.3** Write performance tests for Rust sidecar latency
- [ ] **3.5.4** Manual kill switch test (document results)

### 3.6 Phase 3 Exit Validation

- [ ] **3.6.1** Verify 100+ total live trades
- [ ] **3.6.2** Calculate 3-month rolling win rate: must be ≥55%
- [ ] **3.6.3** Verify graph-sourced signals show positive independent ROI
- [ ] **3.6.4** Verify Rust sidecar 30-day uptime
- [ ] **3.6.5** Verify capital ≥$10,000
- [ ] **3.6.6** Document kill switch manual test results
- [ ] **3.6.7** Verify 60+ days in Phase 3
- [ ] **3.6.8** Tag commit: `v3.1.0-phase3-complete`
- [ ] **3.6.9** Push to GitHub

---

## Phase 4: Full Operation ($10,000+)

### 4.1 Full Enablement

- [ ] **4.1.1** Update `config/settings.yaml`: set `current_phase: 4`
- [ ] **4.1.2** Verify position sizing uses Phase 4 limits (3.5% risk, 18% max)
- [ ] **4.1.3** Enable all V3 features at full capacity

### 4.2 Operational Validation

- [ ] **4.2.1** Validate full runbook procedures:
  - [ ] System start/stop
  - [ ] API key rotation
  - [ ] Execution wallet rotation
  - [ ] Manual kill switch activation/deactivation
  - [ ] Capital Preservation mode resume
- [ ] **4.2.2** Document emergency procedures tested

### 4.3 Testing (Phase 4)

- [ ] **4.3.1** Run load tests: system under high signal volume
- [ ] **4.3.2** Run chaos tests: API failures, rate limits, network partitions
- [ ] **4.3.3** Run full regression: complete test suite
- [ ] **4.3.4** Validate operational runbook procedures

### 4.4 Ongoing Operations

- [ ] **4.4.1** Establish daily operations checklist
- [ ] **4.4.2** Establish weekly maintenance checklist
- [ ] **4.4.3** Establish monthly key rotation schedule
- [ ] **4.4.4** Establish database backup verification
- [ ] **4.4.5** Tag commit: `v3.1.0-phase4-complete`
- [ ] **4.4.6** Push to GitHub

---

## Non-Negotiable Reminders

**Every task must comply with these rules:**

1. **Docs win** - If code conflicts with docs, fix the code
2. **Fail-closed** - Missing/null/stale/unknown data → BLOCK (never pass)
3. **95% gate** - Assassin disabled unless simulator accuracy ≥95% AND ≥50 samples
4. **No placeholders** - No TODO, FIXME, pass, return True bypasses in `src/`
5. **V2 never disabled** - Spread, liquidity, tax, time-stop, panic exit, cooldowns always enforced
6. **Tests required** - Every change includes tests; no "tests coming later"
7. **Log everything** - Every decision logged with reasoning; every veto includes reason

---

## Task Status Legend

- [ ] Not started
- [x] Completed
- [~] In progress
- [!] Blocked

---

**Document Version:** 1.0  
**Generated:** 2026-01-26  
**Next Review:** After Phase 0 completion
