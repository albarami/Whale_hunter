# Data Dictionary: Schemas + Units

**Version:** 3.1.0  
**Database:** SQLite (wallet_graph.db)  
**Encoding:** UTF-8

---

## Table: wallets

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| address | TEXT | Solana address | Primary key, base58 encoded |
| first_seen | TEXT | ISO 8601 UTC | When wallet was first discovered |
| last_activity | TEXT | ISO 8601 UTC | Most recent transaction |
| total_trades | INTEGER | count | Number of trades observed |
| winning_trades | INTEGER | count | Trades with positive PnL |
| total_pnl_sol | REAL | SOL | Cumulative profit/loss |
| tier | TEXT | enum | S/A/B/C classification |
| is_cex | INTEGER | boolean (0/1) | CEX wallet flag |
| confidence | REAL | 0.0-1.0 | Current trust score |
| last_confidence_update | TEXT | ISO 8601 UTC | Last decay calculation |
| metadata | TEXT | JSON | Additional attributes |

**Indexes:** `idx_wallets_tier`, `idx_wallets_confidence`

---

## Table: funding

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| id | INTEGER | auto | Primary key |
| source_wallet | TEXT | Solana address | Funding source (FK → wallets) |
| target_wallet | TEXT | Solana address | Funded wallet (FK → wallets) |
| amount_sol | REAL | SOL | Amount transferred |
| timestamp | TEXT | ISO 8601 UTC | Transfer time |
| tx_signature | TEXT | base58 | Transaction signature |
| hop_distance | INTEGER | count | Hops from original source |

**Indexes:** `idx_funding_source`, `idx_funding_target`, `idx_funding_timestamp`

---

## Table: signals

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| id | TEXT | UUID | Primary key (signal_id format) |
| wallet_address | TEXT | Solana address | Wallet that generated signal |
| token_address | TEXT | Solana address | Token being traded |
| token_symbol | TEXT | string | Token ticker |
| action | TEXT | enum | BUY/SELL |
| amount_usd | REAL | USD | Trade size in USD |
| price_at_signal | REAL | USD | Token price when signal created |
| timestamp | TEXT | ISO 8601 UTC | Signal creation time |
| confidence | REAL | 0.0-1.0 | Calculated confidence score |
| source_version | TEXT | string | v2/v25/v3 |
| graph_boost | REAL | 0.0-0.3 | Boost from graph analysis |
| asset_class | TEXT | enum | meme_coin_low_cap/mid_cap/large_cap |
| veto_reason | TEXT | string | NULL if approved, else reason |
| processed | INTEGER | boolean (0/1) | Whether signal was acted upon |
| outcome | TEXT | enum | WIN/LOSS/PENDING/SKIPPED |
| price_24h | REAL | USD | Token price 24h after signal |
| notes | TEXT | string | Optional operator notes |

**Indexes:** `idx_signals_timestamp`, `idx_signals_token`, `idx_signals_wallet`, `idx_signals_outcome`

---

## Table: trades

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| id | TEXT | UUID | Primary key |
| signal_id | TEXT | UUID | FK → signals.id |
| execution_wallet | TEXT | Solana address | Wallet used for execution |
| token_address | TEXT | Solana address | Token traded |
| side | TEXT | enum | BUY/SELL |
| amount_sol | REAL | SOL | Amount in SOL |
| amount_tokens | REAL | tokens | Tokens received/sent |
| price | REAL | USD | Execution price |
| slippage_bps | INTEGER | basis points | Actual slippage |
| gas_lamports | INTEGER | lamports | Transaction fee |
| tx_signature | TEXT | base58 | Transaction signature |
| timestamp | TEXT | ISO 8601 UTC | Execution time |
| paper | INTEGER | boolean (0/1) | Paper trade flag |
| pnl_sol | REAL | SOL | Realized P&L (NULL if open) |
| pnl_pct | REAL | percentage | P&L as percentage |
| exit_reason | TEXT | enum | TRAILING_STOP/TIME_STOP/PANIC/MANUAL/WHALE_EXIT |
| cluster_id | TEXT | string | Associated cluster (if any) |

**Indexes:** `idx_trades_timestamp`, `idx_trades_signal`, `idx_trades_token`

---

## Table: buys (Legacy Tracking)

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| id | INTEGER | auto | Primary key |
| wallet_address | TEXT | Solana address | Buyer wallet |
| token_address | TEXT | Solana address | Token bought |
| amount_sol | REAL | SOL | Amount spent |
| timestamp | TEXT | ISO 8601 UTC | Purchase time |
| tx_signature | TEXT | base58 | Transaction signature |

---

## Table: kill_switch_events

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| id | INTEGER | auto | Primary key |
| trigger | TEXT | enum | Trigger type |
| timestamp | TEXT | ISO 8601 UTC | Activation time |
| details | TEXT | JSON | Additional context |
| resolved_at | TEXT | ISO 8601 UTC | Resolution time (NULL if active) |
| resolution_notes | TEXT | string | Operator notes on resolution |

---

## Table: system_state

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| key | TEXT | string | Primary key |
| value | TEXT | JSON | State value |
| updated_at | TEXT | ISO 8601 UTC | Last update |

**Standard Keys:**
- `capital_sol`: Current capital in SOL
- `peak_capital_sol`: Highest capital reached
- `current_phase`: 0-4
- `trade_count`: Total trades executed
- `mode`: NORMAL/CAPITAL_PRESERVATION/KILL_SWITCH
- `first_trade_date`: ISO 8601
- `last_backup`: ISO 8601

---

## Canonical ID Formats

| ID Type | Format | Example |
|---------|--------|----------|
| signal_id | `sig_{timestamp}_{random8}` | `sig_1706198400_a1b2c3d4` |
| cluster_id | `cluster_{mother_addr_prefix}` | `cluster_7xKL...` |
| trade_id | `trade_{timestamp}_{random8}` | `trade_1706198400_e5f6g7h8` |

---

## Units Clarification

| Concept | Storage Unit | Display Unit | Conversion |
|---------|--------------|--------------|-------------|
| SOL amounts | SOL (REAL) | SOL | 1:1 |
| Lamports | lamports (INTEGER) | SOL | ÷ 1,000,000,000 |
| Basis points | bps (INTEGER) | % | ÷ 100 |
| Percentages | decimal (REAL) | % | × 100 |
| Timestamps | ISO 8601 UTC | Local | TZ conversion |
| Addresses | base58 string | base58 | 1:1 |

**CRITICAL:** All timestamps stored in UTC. Convert for display only.

---

## Event Types (for logging)

| Event Type | Required Fields |
|------------|------------------|
| SIGNAL_CREATED | signal_id, wallet, token, confidence |
| SIGNAL_VETOED | signal_id, veto_reason |
| TRADE_EXECUTED | trade_id, signal_id, tx_signature |
| TRADE_CLOSED | trade_id, exit_reason, pnl_sol |
| KILL_SWITCH_ON | trigger, timestamp |
| KILL_SWITCH_OFF | timestamp, resolution_notes |
| CAPITAL_PRESERVATION_ON | drawdown_pct, timestamp |
| CAPITAL_PRESERVATION_OFF | timestamp, approval_by |
| WALLET_DISCOVERED | address, source, hop_distance |
| MOTHER_IDENTIFIED | address, children_count, trust_score |

---

## Confidence Decay Formula

```
half_life = 30 days
decay_factor = 0.5 ^ (days_since_update / half_life)
new_confidence = old_confidence * decay_factor
```

Applied daily via scheduled task.
