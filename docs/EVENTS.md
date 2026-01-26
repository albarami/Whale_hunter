# Event Types Reference

**Version:** 3.1.0  
**Purpose:** Canonical list of all event types for logging, analytics, and policy auditing  
**Format:** JSON (structured logging)

---

## Log Format Standards

### JSON Structure

All events MUST follow this base structure:

```json
{
  "event_type": "EVENT_NAME",
  "timestamp": "2026-01-25T12:34:56.789Z",
  "severity": "INFO",
  "correlation_id": "corr_abc123",
  "data": {
    // Event-specific fields
  }
}
```

### Timestamp Format

- **Format:** ISO 8601 with milliseconds
- **Timezone:** Always UTC (suffix `Z`)
- **Example:** `2026-01-25T12:34:56.789Z`

### Severity Levels

| Level | Code | Usage |
|-------|------|-------|
| DEBUG | 10 | Detailed diagnostic information |
| INFO | 20 | Normal operational events |
| WARNING | 30 | Unusual but handled situations |
| ERROR | 40 | Errors requiring attention |
| CRITICAL | 50 | System-threatening failures |

### Correlation ID Format

- **Format:** `corr_{timestamp_ms}_{random6}`
- **Example:** `corr_1706198400123_x7y8z9`
- **Purpose:** Links related events across a signal's lifecycle

---

## Signal Events

### SIGNAL_DETECTED

Emitted when a whale wallet activity is detected and a signal is created.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Unique signal identifier |
| wallet_address | string | ✓ | Whale wallet address (base58) |
| token_address | string | ✓ | Token contract address (base58) |
| token_symbol | string | ✓ | Token ticker symbol |
| action | string | ✓ | BUY or SELL |
| amount_usd | number | ✓ | Trade amount in USD |
| price_usd | number | ✓ | Token price at detection |
| wallet_tier | string | ✓ | S/A/B/C |
| wallet_confidence | number | ✓ | 0.0-1.0 |
| asset_class | string | ✓ | meme_coin_low_cap/mid_cap/large_cap |
| source_version | string | ✓ | v2/v25/v3 |
| detection_latency_ms | number | ○ | Time from on-chain to detection |
| cluster_id | string | ○ | Associated cluster if applicable |

**Severity:** INFO

**When Emitted:** Upon detection of qualifying whale transaction via Helius webhook or polling.

**Example:**
```json
{
  "event_type": "SIGNAL_DETECTED",
  "timestamp": "2026-01-25T12:34:56.789Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "wallet_address": "7xKLm9...",
    "token_address": "EPjFWdd...",
    "token_symbol": "BONK",
    "action": "BUY",
    "amount_usd": 5000.00,
    "price_usd": 0.00002341,
    "wallet_tier": "S",
    "wallet_confidence": 0.87,
    "asset_class": "meme_coin_low_cap",
    "source_version": "v3",
    "detection_latency_ms": 450,
    "cluster_id": "cluster_7xKL..."
  }
}
```

---

### SIGNAL_EXPIRED

Emitted when a signal exceeds maximum freshness window without processing.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| wallet_address | string | ✓ | Source wallet address |
| token_address | string | ✓ | Token address |
| age_seconds | number | ✓ | Signal age at expiration |
| max_freshness_seconds | number | ✓ | Configured max freshness |
| asset_class | string | ✓ | Asset class of token |

**Severity:** WARNING

**When Emitted:** When signal processor finds signal exceeds freshness window.

**Example:**
```json
{
  "event_type": "SIGNAL_EXPIRED",
  "timestamp": "2026-01-25T12:35:30.000Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "wallet_address": "7xKLm9...",
    "token_address": "EPjFWdd...",
    "age_seconds": 35,
    "max_freshness_seconds": 30,
    "asset_class": "meme_coin_low_cap"
  }
}
```

---

### SIGNAL_SKIPPED_ENTROPY

Emitted when Ghost Mode randomly skips a valid signal for pattern obfuscation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| wallet_address | string | ✓ | Source wallet address |
| token_address | string | ✓ | Token address |
| skip_probability | number | ✓ | Configured skip probability |
| random_value | number | ✓ | Random value that triggered skip |
| confidence | number | ✓ | Signal confidence score |

**Severity:** INFO

**When Emitted:** When EntropyInjector decides to skip a signal.

**Example:**
```json
{
  "event_type": "SIGNAL_SKIPPED_ENTROPY",
  "timestamp": "2026-01-25T12:34:57.100Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "wallet_address": "7xKLm9...",
    "token_address": "EPjFWdd...",
    "skip_probability": 0.10,
    "random_value": 0.07,
    "confidence": 0.82
  }
}
```

---

## Veto Events

### VETO_KILL_SWITCH

Emitted when signal is rejected due to active kill switch.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| kill_switch_type | string | ✓ | FULL/GRAPH |
| trigger_reason | string | ✓ | Original trigger reason |
| activated_at | string | ✓ | ISO 8601 activation time |

**Severity:** WARNING

**When Emitted:** During veto check when kill switch is active.

**Example:**
```json
{
  "event_type": "VETO_KILL_SWITCH",
  "timestamp": "2026-01-25T12:34:56.800Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "kill_switch_type": "FULL",
    "trigger_reason": "CONSECUTIVE_LOSSES",
    "activated_at": "2026-01-25T10:00:00.000Z"
  }
}
```

---

### VETO_CAPITAL_PRESERVATION

Emitted when signal is rejected due to Capital Preservation Mode.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| current_drawdown_pct | number | ✓ | Current drawdown percentage |
| mode_activated_at | string | ✓ | ISO 8601 activation time |
| capital_sol | number | ✓ | Current capital in SOL |
| peak_capital_sol | number | ✓ | Peak capital in SOL |

**Severity:** WARNING

**When Emitted:** During veto check when Capital Preservation Mode is active.

**Example:**
```json
{
  "event_type": "VETO_CAPITAL_PRESERVATION",
  "timestamp": "2026-01-25T12:34:56.800Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "current_drawdown_pct": 18.5,
    "mode_activated_at": "2026-01-25T08:00:00.000Z",
    "capital_sol": 8.15,
    "peak_capital_sol": 10.00
  }
}
```

---

### VETO_SIGNAL_STALE

Emitted when signal is rejected due to exceeding freshness window.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| signal_age_seconds | number | ✓ | Age of signal in seconds |
| max_freshness_seconds | number | ✓ | Maximum allowed freshness |
| asset_class | string | ✓ | Asset class |
| token_address | string | ✓ | Token address |

**Severity:** INFO

**When Emitted:** During freshness gate check.

**Example:**
```json
{
  "event_type": "VETO_SIGNAL_STALE",
  "timestamp": "2026-01-25T12:34:56.800Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "signal_age_seconds": 45,
    "max_freshness_seconds": 30,
    "asset_class": "meme_coin_low_cap",
    "token_address": "EPjFWdd..."
  }
}
```

---

### VETO_TOKEN_AGE

Emitted when signal is rejected due to token being too new.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| token_address | string | ✓ | Token address |
| token_age_minutes | number | ✓ | Token age in minutes |
| min_age_minutes | number | ✓ | Required minimum age |
| asset_class | string | ✓ | Asset class |

**Severity:** INFO

**When Emitted:** During token age gate check.

**Example:**
```json
{
  "event_type": "VETO_TOKEN_AGE",
  "timestamp": "2026-01-25T12:34:56.800Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "NewToken...",
    "token_age_minutes": 8,
    "min_age_minutes": 10,
    "asset_class": "meme_coin_low_cap"
  }
}
```

---

### VETO_SPREAD

Emitted when signal is rejected due to excessive bid-ask spread.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| token_address | string | ✓ | Token address |
| spread_pct | number | ✓ | Observed spread percentage |
| max_spread_pct | number | ✓ | Maximum allowed spread (3%) |
| bid_price | number | ○ | Best bid price |
| ask_price | number | ○ | Best ask price |

**Severity:** INFO

**When Emitted:** During spread gate check.

**Example:**
```json
{
  "event_type": "VETO_SPREAD",
  "timestamp": "2026-01-25T12:34:56.800Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "EPjFWdd...",
    "spread_pct": 4.5,
    "max_spread_pct": 3.0,
    "bid_price": 0.00002200,
    "ask_price": 0.00002310
  }
}
```

---

### VETO_LIQUIDITY

Emitted when signal is rejected due to insufficient liquidity.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| token_address | string | ✓ | Token address |
| liquidity_usd | number | ✓ | Available liquidity in USD |
| min_liquidity_usd | number | ✓ | Required minimum liquidity |
| position_size_usd | number | ✓ | Intended position size |

**Severity:** INFO

**When Emitted:** During liquidity gate check.

**Example:**
```json
{
  "event_type": "VETO_LIQUIDITY",
  "timestamp": "2026-01-25T12:34:56.800Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "EPjFWdd...",
    "liquidity_usd": 15000,
    "min_liquidity_usd": 25000,
    "position_size_usd": 500
  }
}
```

---

### VETO_TAX

Emitted when signal is rejected due to excessive token tax.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| token_address | string | ✓ | Token address |
| buy_tax_pct | number | ✓ | Buy tax percentage |
| sell_tax_pct | number | ✓ | Sell tax percentage |
| total_tax_pct | number | ✓ | Combined tax percentage |
| max_tax_pct | number | ✓ | Maximum allowed (10%) |

**Severity:** INFO

**When Emitted:** During tax gate check.

**Example:**
```json
{
  "event_type": "VETO_TAX",
  "timestamp": "2026-01-25T12:34:56.800Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "TaxToken...",
    "buy_tax_pct": 5.0,
    "sell_tax_pct": 8.0,
    "total_tax_pct": 13.0,
    "max_tax_pct": 10.0
  }
}
```

---

### VETO_COOLDOWN

Emitted when signal is rejected due to active cooldown.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| cooldown_type | string | ✓ | WALLET/TOKEN/CLUSTER/GLOBAL |
| cooldown_target | string | ✓ | Address or identifier |
| cooldown_remaining_seconds | number | ✓ | Seconds until cooldown ends |
| cooldown_started_at | string | ✓ | ISO 8601 cooldown start |

**Severity:** INFO

**When Emitted:** During cooldown/saturation gate check.

**Example:**
```json
{
  "event_type": "VETO_COOLDOWN",
  "timestamp": "2026-01-25T12:34:56.800Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "cooldown_type": "WALLET",
    "cooldown_target": "7xKLm9...",
    "cooldown_remaining_seconds": 1800,
    "cooldown_started_at": "2026-01-25T12:04:56.000Z"
  }
}
```

---

### VETO_SIMULATION

Emitted when signal is rejected due to failed simulation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| token_address | string | ✓ | Token address |
| simulation_result | string | ✓ | HONEYPOT/HIGH_TAX/LIQUIDITY_TRAP/ERROR |
| simulated_buy_tax_pct | number | ○ | Detected buy tax |
| simulated_sell_tax_pct | number | ○ | Detected sell tax |
| error_message | string | ○ | Error details if applicable |

**Severity:** WARNING

**When Emitted:** After simulation fails safety checks.

**Example:**
```json
{
  "event_type": "VETO_SIMULATION",
  "timestamp": "2026-01-25T12:34:57.500Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "ScamToken...",
    "simulation_result": "HONEYPOT",
    "simulated_buy_tax_pct": 0.5,
    "simulated_sell_tax_pct": 99.0
  }
}
```

---

## Simulation Events

### SIM_STARTED

Emitted when transaction simulation begins.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| token_address | string | ✓ | Token address |
| simulation_type | string | ✓ | BUY/SELL/BOTH |
| amount_sol | number | ✓ | Amount being simulated |

**Severity:** DEBUG

**When Emitted:** At start of simulation process.

**Example:**
```json
{
  "event_type": "SIM_STARTED",
  "timestamp": "2026-01-25T12:34:57.000Z",
  "severity": "DEBUG",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "EPjFWdd...",
    "simulation_type": "BOTH",
    "amount_sol": 0.1
  }
}
```

---

### SIM_PASS

Emitted when simulation passes all safety checks.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| token_address | string | ✓ | Token address |
| buy_tax_pct | number | ✓ | Detected buy tax |
| sell_tax_pct | number | ✓ | Detected sell tax |
| total_tax_pct | number | ✓ | Combined tax |
| expected_output_tokens | number | ✓ | Expected tokens from buy |
| simulation_latency_ms | number | ✓ | Simulation duration |

**Severity:** INFO

**When Emitted:** After successful simulation completion.

**Example:**
```json
{
  "event_type": "SIM_PASS",
  "timestamp": "2026-01-25T12:34:57.450Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "EPjFWdd...",
    "buy_tax_pct": 0.5,
    "sell_tax_pct": 0.5,
    "total_tax_pct": 1.0,
    "expected_output_tokens": 4250000,
    "simulation_latency_ms": 450
  }
}
```

---

### SIM_BLOCK_HONEYPOT

Emitted when simulation detects honeypot characteristics.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| token_address | string | ✓ | Token address |
| sell_reverted | boolean | ✓ | Whether sell simulation reverted |
| sell_tax_pct | number | ○ | Detected sell tax if not reverted |
| revert_reason | string | ○ | Revert error message |

**Severity:** WARNING

**When Emitted:** When sell simulation reverts or shows >90% tax.

**Example:**
```json
{
  "event_type": "SIM_BLOCK_HONEYPOT",
  "timestamp": "2026-01-25T12:34:57.450Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "HoneyPot...",
    "sell_reverted": true,
    "revert_reason": "Transfer failed: insufficient balance"
  }
}
```

---

### SIM_BLOCK_TAX

Emitted when simulation detects excessive tax.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| token_address | string | ✓ | Token address |
| buy_tax_pct | number | ✓ | Detected buy tax |
| sell_tax_pct | number | ✓ | Detected sell tax |
| total_tax_pct | number | ✓ | Combined tax |
| threshold_pct | number | ✓ | Tax threshold (10%) |

**Severity:** WARNING

**When Emitted:** When combined tax exceeds threshold.

**Example:**
```json
{
  "event_type": "SIM_BLOCK_TAX",
  "timestamp": "2026-01-25T12:34:57.450Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "HighTax...",
    "buy_tax_pct": 5.0,
    "sell_tax_pct": 8.0,
    "total_tax_pct": 13.0,
    "threshold_pct": 10.0
  }
}
```

---

### SIM_BLOCK_LIQUIDITY

Emitted when simulation detects liquidity issues.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| token_address | string | ✓ | Token address |
| available_liquidity_usd | number | ✓ | Detected liquidity |
| required_liquidity_usd | number | ✓ | Minimum required |
| price_impact_pct | number | ○ | Estimated price impact |

**Severity:** WARNING

**When Emitted:** When liquidity is insufficient for position size.

**Example:**
```json
{
  "event_type": "SIM_BLOCK_LIQUIDITY",
  "timestamp": "2026-01-25T12:34:57.450Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "LowLiq...",
    "available_liquidity_usd": 5000,
    "required_liquidity_usd": 25000,
    "price_impact_pct": 15.5
  }
}
```

---

### SIM_ERROR

Emitted when simulation encounters an error.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | ✓ | Signal identifier |
| token_address | string | ✓ | Token address |
| error_type | string | ✓ | RPC_ERROR/TIMEOUT/INVALID_RESPONSE |
| error_message | string | ✓ | Error details |
| retry_count | number | ✓ | Number of retries attempted |

**Severity:** ERROR

**When Emitted:** When simulation fails due to technical error.

**Example:**
```json
{
  "event_type": "SIM_ERROR",
  "timestamp": "2026-01-25T12:34:58.000Z",
  "severity": "ERROR",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "EPjFWdd...",
    "error_type": "RPC_ERROR",
    "error_message": "Node behind by 15 slots",
    "retry_count": 3
  }
}
```

---

## Trade Events

### TRADE_INTENT_CREATED

Emitted when a trade intent passes all veto gates and is ready for execution.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trade_id | string | ✓ | Unique trade identifier |
| signal_id | string | ✓ | Source signal identifier |
| token_address | string | ✓ | Token address |
| token_symbol | string | ✓ | Token ticker |
| side | string | ✓ | BUY/SELL |
| amount_sol | number | ✓ | Position size in SOL |
| execution_wallet | string | ✓ | Wallet to execute trade |
| expected_slippage_bps | number | ✓ | Expected slippage |
| confidence | number | ✓ | Final confidence score |
| paper | boolean | ✓ | Paper trade flag |

**Severity:** INFO

**When Emitted:** After signal passes all gates, before execution.

**Example:**
```json
{
  "event_type": "TRADE_INTENT_CREATED",
  "timestamp": "2026-01-25T12:34:58.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "trade_id": "trade_1706198498_e5f6g7h8",
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "EPjFWdd...",
    "token_symbol": "BONK",
    "side": "BUY",
    "amount_sol": 0.05,
    "execution_wallet": "ExecWal...",
    "expected_slippage_bps": 150,
    "confidence": 0.78,
    "paper": false
  }
}
```

---

### TRADE_EXECUTED

Emitted when a trade is successfully executed on-chain.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trade_id | string | ✓ | Trade identifier |
| signal_id | string | ✓ | Source signal identifier |
| tx_signature | string | ✓ | Transaction signature (base58) |
| token_address | string | ✓ | Token address |
| side | string | ✓ | BUY/SELL |
| amount_sol | number | ✓ | SOL amount |
| amount_tokens | number | ✓ | Tokens received/sent |
| price_usd | number | ✓ | Execution price |
| actual_slippage_bps | number | ✓ | Actual slippage |
| gas_lamports | number | ✓ | Transaction fee |
| execution_latency_ms | number | ✓ | Time from intent to confirm |
| paper | boolean | ✓ | Paper trade flag |
| execution_wallet | string | ○ | Wallet used |
| block_slot | number | ○ | Block slot of execution |

**Severity:** INFO

**When Emitted:** After transaction confirmation.

**Example:**
```json
{
  "event_type": "TRADE_EXECUTED",
  "timestamp": "2026-01-25T12:34:59.500Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "trade_id": "trade_1706198498_e5f6g7h8",
    "signal_id": "sig_1706198400_a1b2c3d4",
    "tx_signature": "5KtPn7S...",
    "token_address": "EPjFWdd...",
    "side": "BUY",
    "amount_sol": 0.05,
    "amount_tokens": 2134500,
    "price_usd": 0.00002345,
    "actual_slippage_bps": 120,
    "gas_lamports": 5000,
    "execution_latency_ms": 1500,
    "paper": false,
    "execution_wallet": "ExecWal...",
    "block_slot": 245678901
  }
}
```

---

### TRADE_FAILED

Emitted when a trade execution fails.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trade_id | string | ✓ | Trade identifier |
| signal_id | string | ✓ | Source signal identifier |
| token_address | string | ✓ | Token address |
| side | string | ✓ | BUY/SELL |
| failure_reason | string | ✓ | Reason for failure |
| error_code | string | ○ | RPC error code |
| tx_signature | string | ○ | Failed tx signature if available |
| retry_count | number | ✓ | Retries attempted |
| will_retry | boolean | ✓ | Whether retry is planned |

**Severity:** ERROR

**When Emitted:** After trade execution fails.

**Example:**
```json
{
  "event_type": "TRADE_FAILED",
  "timestamp": "2026-01-25T12:35:00.000Z",
  "severity": "ERROR",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "trade_id": "trade_1706198498_e5f6g7h8",
    "signal_id": "sig_1706198400_a1b2c3d4",
    "token_address": "EPjFWdd...",
    "side": "BUY",
    "failure_reason": "SLIPPAGE_EXCEEDED",
    "error_code": "0x1771",
    "retry_count": 2,
    "will_retry": false
  }
}
```

---

### TRADE_PARTIAL_FILL

Emitted when a trade is only partially filled.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trade_id | string | ✓ | Trade identifier |
| signal_id | string | ✓ | Source signal identifier |
| tx_signature | string | ✓ | Transaction signature |
| token_address | string | ✓ | Token address |
| intended_amount_sol | number | ✓ | Intended position size |
| filled_amount_sol | number | ✓ | Actually filled amount |
| fill_percentage | number | ✓ | Percentage filled |
| reason | string | ○ | Reason for partial fill |

**Severity:** WARNING

**When Emitted:** When trade executes but not fully filled.

**Example:**
```json
{
  "event_type": "TRADE_PARTIAL_FILL",
  "timestamp": "2026-01-25T12:34:59.500Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "trade_id": "trade_1706198498_e5f6g7h8",
    "signal_id": "sig_1706198400_a1b2c3d4",
    "tx_signature": "5KtPn7S...",
    "token_address": "EPjFWdd...",
    "intended_amount_sol": 0.05,
    "filled_amount_sol": 0.032,
    "fill_percentage": 64.0,
    "reason": "Insufficient liquidity at target price"
  }
}
```

---

## Exit Events

### EXIT_PANIC

Emitted when position is closed due to panic exit threshold.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trade_id | string | ✓ | Trade identifier |
| token_address | string | ✓ | Token address |
| entry_price_usd | number | ✓ | Entry price |
| exit_price_usd | number | ✓ | Exit price |
| loss_pct | number | ✓ | Loss percentage |
| panic_threshold_pct | number | ✓ | Configured threshold (15%) |
| pnl_sol | number | ✓ | Realized P&L in SOL |
| hold_duration_seconds | number | ✓ | Time position was held |
| tx_signature | string | ✓ | Exit transaction signature |

**Severity:** WARNING

**When Emitted:** When position hits panic stop loss.

**Example:**
```json
{
  "event_type": "EXIT_PANIC",
  "timestamp": "2026-01-25T13:00:00.000Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "trade_id": "trade_1706198498_e5f6g7h8",
    "token_address": "EPjFWdd...",
    "entry_price_usd": 0.00002345,
    "exit_price_usd": 0.00001993,
    "loss_pct": 15.0,
    "panic_threshold_pct": 15.0,
    "pnl_sol": -0.0075,
    "hold_duration_seconds": 1502,
    "tx_signature": "ExitTx..."
  }
}
```

---

### EXIT_TIME_STOP

Emitted when position is closed due to time-based exit.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trade_id | string | ✓ | Trade identifier |
| token_address | string | ✓ | Token address |
| entry_price_usd | number | ✓ | Entry price |
| exit_price_usd | number | ✓ | Exit price |
| pnl_pct | number | ✓ | P&L percentage |
| pnl_sol | number | ✓ | Realized P&L in SOL |
| hold_duration_minutes | number | ✓ | Time position was held |
| max_hold_minutes | number | ✓ | Configured max hold time |
| tx_signature | string | ✓ | Exit transaction signature |

**Severity:** INFO

**When Emitted:** When position reaches maximum hold time.

**Example:**
```json
{
  "event_type": "EXIT_TIME_STOP",
  "timestamp": "2026-01-25T16:34:56.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "trade_id": "trade_1706198498_e5f6g7h8",
    "token_address": "EPjFWdd...",
    "entry_price_usd": 0.00002345,
    "exit_price_usd": 0.00002567,
    "pnl_pct": 9.5,
    "pnl_sol": 0.00475,
    "hold_duration_minutes": 240,
    "max_hold_minutes": 240,
    "tx_signature": "ExitTx..."
  }
}
```

---

### EXIT_WHALE_INACTIVITY

Emitted when position is closed due to whale wallet inactivity.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trade_id | string | ✓ | Trade identifier |
| token_address | string | ✓ | Token address |
| whale_wallet | string | ✓ | Tracked whale wallet |
| whale_last_activity | string | ✓ | ISO 8601 last activity |
| inactivity_minutes | number | ✓ | Minutes since last activity |
| inactivity_threshold_minutes | number | ✓ | Configured threshold |
| pnl_pct | number | ✓ | P&L percentage |
| pnl_sol | number | ✓ | Realized P&L in SOL |
| tx_signature | string | ✓ | Exit transaction signature |

**Severity:** INFO

**When Emitted:** When tracked whale becomes inactive.

**Example:**
```json
{
  "event_type": "EXIT_WHALE_INACTIVITY",
  "timestamp": "2026-01-25T14:34:56.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "trade_id": "trade_1706198498_e5f6g7h8",
    "token_address": "EPjFWdd...",
    "whale_wallet": "7xKLm9...",
    "whale_last_activity": "2026-01-25T13:04:56.000Z",
    "inactivity_minutes": 90,
    "inactivity_threshold_minutes": 60,
    "pnl_pct": 5.2,
    "pnl_sol": 0.0026,
    "tx_signature": "ExitTx..."
  }
}
```

---

### EXIT_TRAILING_STOP

Emitted when position is closed due to trailing stop trigger.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trade_id | string | ✓ | Trade identifier |
| token_address | string | ✓ | Token address |
| entry_price_usd | number | ✓ | Entry price |
| peak_price_usd | number | ✓ | Highest price reached |
| exit_price_usd | number | ✓ | Exit price |
| trailing_stop_pct | number | ✓ | Trailing stop percentage |
| drawdown_from_peak_pct | number | ✓ | Drawdown from peak |
| pnl_pct | number | ✓ | P&L percentage |
| pnl_sol | number | ✓ | Realized P&L in SOL |
| tx_signature | string | ✓ | Exit transaction signature |

**Severity:** INFO

**When Emitted:** When trailing stop is triggered.

**Example:**
```json
{
  "event_type": "EXIT_TRAILING_STOP",
  "timestamp": "2026-01-25T14:00:00.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "trade_id": "trade_1706198498_e5f6g7h8",
    "token_address": "EPjFWdd...",
    "entry_price_usd": 0.00002345,
    "peak_price_usd": 0.00003500,
    "exit_price_usd": 0.00002975,
    "trailing_stop_pct": 15.0,
    "drawdown_from_peak_pct": 15.0,
    "pnl_pct": 26.9,
    "pnl_sol": 0.01345,
    "tx_signature": "ExitTx..."
  }
}
```

---

### EXIT_MANUAL

Emitted when position is manually closed by operator.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trade_id | string | ✓ | Trade identifier |
| token_address | string | ✓ | Token address |
| entry_price_usd | number | ✓ | Entry price |
| exit_price_usd | number | ✓ | Exit price |
| pnl_pct | number | ✓ | P&L percentage |
| pnl_sol | number | ✓ | Realized P&L in SOL |
| operator_reason | string | ✓ | Reason provided by operator |
| tx_signature | string | ✓ | Exit transaction signature |

**Severity:** INFO

**When Emitted:** When operator manually closes position.

**Example:**
```json
{
  "event_type": "EXIT_MANUAL",
  "timestamp": "2026-01-25T15:00:00.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "trade_id": "trade_1706198498_e5f6g7h8",
    "token_address": "EPjFWdd...",
    "entry_price_usd": 0.00002345,
    "exit_price_usd": 0.00002800,
    "pnl_pct": 19.4,
    "pnl_sol": 0.0097,
    "operator_reason": "Taking profits before news event",
    "tx_signature": "ExitTx..."
  }
}
```

---

### EXIT_KILL_SWITCH

Emitted when position is forcefully closed due to kill switch activation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trade_id | string | ✓ | Trade identifier |
| token_address | string | ✓ | Token address |
| kill_switch_type | string | ✓ | FULL/GRAPH |
| kill_switch_trigger | string | ✓ | Trigger reason |
| entry_price_usd | number | ✓ | Entry price |
| exit_price_usd | number | ✓ | Exit price |
| pnl_pct | number | ✓ | P&L percentage |
| pnl_sol | number | ✓ | Realized P&L in SOL |
| tx_signature | string | ✓ | Exit transaction signature |

**Severity:** CRITICAL

**When Emitted:** When kill switch forces position closure.

**Example:**
```json
{
  "event_type": "EXIT_KILL_SWITCH",
  "timestamp": "2026-01-25T12:35:00.000Z",
  "severity": "CRITICAL",
  "correlation_id": "corr_1706198400123_x7y8z9",
  "data": {
    "trade_id": "trade_1706198498_e5f6g7h8",
    "token_address": "EPjFWdd...",
    "kill_switch_type": "FULL",
    "kill_switch_trigger": "CONSECUTIVE_LOSSES",
    "entry_price_usd": 0.00002345,
    "exit_price_usd": 0.00002100,
    "pnl_pct": -10.4,
    "pnl_sol": -0.0052,
    "tx_signature": "ExitTx..."
  }
}
```

---

## Risk Events

### KILL_SWITCH_TRIGGERED

Emitted when kill switch is activated.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| kill_switch_type | string | ✓ | FULL/GRAPH |
| trigger | string | ✓ | Trigger reason |
| details | object | ✓ | Trigger-specific details |
| open_positions_count | number | ✓ | Positions to be closed |
| capital_sol | number | ✓ | Current capital |

**Severity:** CRITICAL

**Trigger Reasons:**
- `CONSECUTIVE_LOSSES`: 3+ consecutive losses
- `MOTHER_EXPLOSION`: Mother wallet >30% down
- `WIN_RATE_COLLAPSE`: Win rate <40% over 20 trades
- `RAPID_DRAWDOWN`: >20% drawdown in 24h
- `GRAPH_POISONING`: Suspected graph poisoning
- `MANUAL`: Operator triggered

**When Emitted:** When any kill switch trigger condition is met.

**Example:**
```json
{
  "event_type": "KILL_SWITCH_TRIGGERED",
  "timestamp": "2026-01-25T12:35:00.000Z",
  "severity": "CRITICAL",
  "correlation_id": "corr_1706198500000_ks001",
  "data": {
    "kill_switch_type": "FULL",
    "trigger": "CONSECUTIVE_LOSSES",
    "details": {
      "consecutive_loss_count": 3,
      "total_loss_sol": 0.025,
      "losing_trades": [
        "trade_1706198000_abc1",
        "trade_1706198200_def2",
        "trade_1706198400_ghi3"
      ]
    },
    "open_positions_count": 2,
    "capital_sol": 4.85
  }
}
```

---

### KILL_SWITCH_CLEARED

Emitted when kill switch is deactivated.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| kill_switch_type | string | ✓ | FULL/GRAPH |
| activated_at | string | ✓ | ISO 8601 activation time |
| cleared_at | string | ✓ | ISO 8601 clear time |
| duration_minutes | number | ✓ | Duration of kill switch |
| cleared_by | string | ✓ | MANUAL/AUTO/TIMEOUT |
| resolution_notes | string | ○ | Operator notes |

**Severity:** INFO

**When Emitted:** When kill switch is cleared.

**Example:**
```json
{
  "event_type": "KILL_SWITCH_CLEARED",
  "timestamp": "2026-01-25T14:00:00.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198500000_ks001",
  "data": {
    "kill_switch_type": "FULL",
    "activated_at": "2026-01-25T12:35:00.000Z",
    "cleared_at": "2026-01-25T14:00:00.000Z",
    "duration_minutes": 85,
    "cleared_by": "MANUAL",
    "resolution_notes": "Reviewed losing trades, identified setup error"
  }
}
```

---

### CAPITAL_PRESERVATION_ACTIVATED

Emitted when Capital Preservation Mode is activated.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| drawdown_pct | number | ✓ | Current drawdown percentage |
| threshold_pct | number | ✓ | Activation threshold (15%) |
| capital_sol | number | ✓ | Current capital |
| peak_capital_sol | number | ✓ | Peak capital |
| positions_affected | number | ✓ | Open positions count |

**Severity:** WARNING

**When Emitted:** When drawdown exceeds 15%.

**Example:**
```json
{
  "event_type": "CAPITAL_PRESERVATION_ACTIVATED",
  "timestamp": "2026-01-25T12:35:00.000Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198500000_cp001",
  "data": {
    "drawdown_pct": 15.5,
    "threshold_pct": 15.0,
    "capital_sol": 8.45,
    "peak_capital_sol": 10.00,
    "positions_affected": 1
  }
}
```

---

### CAPITAL_PRESERVATION_CLEARED

Emitted when Capital Preservation Mode is cleared.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| activated_at | string | ✓ | ISO 8601 activation time |
| cleared_at | string | ✓ | ISO 8601 clear time |
| duration_hours | number | ✓ | Duration in hours |
| capital_sol_at_activation | number | ✓ | Capital when activated |
| capital_sol_at_clear | number | ✓ | Capital when cleared |
| cleared_by | string | ✓ | MANUAL only (requires approval) |
| approver_notes | string | ✓ | Required approval notes |

**Severity:** INFO

**When Emitted:** When Capital Preservation Mode is manually cleared.

**Example:**
```json
{
  "event_type": "CAPITAL_PRESERVATION_CLEARED",
  "timestamp": "2026-01-25T20:00:00.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198500000_cp001",
  "data": {
    "activated_at": "2026-01-25T12:35:00.000Z",
    "cleared_at": "2026-01-25T20:00:00.000Z",
    "duration_hours": 7.4,
    "capital_sol_at_activation": 8.45,
    "capital_sol_at_clear": 8.45,
    "cleared_by": "MANUAL",
    "approver_notes": "Reviewed position history, no systemic issues found"
  }
}
```

---

### DRAWDOWN_WARNING

Emitted at drawdown warning thresholds (10%, 15%).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| warning_level | string | ✓ | LEVEL_10/LEVEL_15 |
| drawdown_pct | number | ✓ | Current drawdown percentage |
| capital_sol | number | ✓ | Current capital |
| peak_capital_sol | number | ✓ | Peak capital |
| loss_since_peak_sol | number | ✓ | SOL lost since peak |
| open_positions | array | ✓ | List of open position IDs |

**Severity:** WARNING

**When Emitted:** When drawdown crosses 10% or 15% threshold.

**Example:**
```json
{
  "event_type": "DRAWDOWN_WARNING",
  "timestamp": "2026-01-25T12:30:00.000Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198400000_dw001",
  "data": {
    "warning_level": "LEVEL_10",
    "drawdown_pct": 10.2,
    "capital_sol": 8.98,
    "peak_capital_sol": 10.00,
    "loss_since_peak_sol": 1.02,
    "open_positions": ["trade_1706198300_xyz1"]
  }
}
```

---

## Graph Events

### GRAPH_DISABLED_OBSERVATION_MODE

Emitted when graph-based signals are disabled due to suspected poisoning.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trigger_reason | string | ✓ | Reason for observation mode |
| mother_wallets_24h | number | ✓ | New mother wallets in 24h |
| threshold | number | ✓ | Trigger threshold (10) |
| affected_clusters | array | ✓ | List of suspicious cluster IDs |
| v3_signals_blocked | boolean | ✓ | Whether V3 signals blocked |

**Severity:** WARNING

**When Emitted:** When >10 new mother wallets discovered in 24h.

**Example:**
```json
{
  "event_type": "GRAPH_DISABLED_OBSERVATION_MODE",
  "timestamp": "2026-01-25T12:35:00.000Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198500000_gr001",
  "data": {
    "trigger_reason": "EXCESSIVE_MOTHER_DISCOVERY",
    "mother_wallets_24h": 12,
    "threshold": 10,
    "affected_clusters": ["cluster_7xKL...", "cluster_9mNP..."],
    "v3_signals_blocked": true
  }
}
```

---

### GRAPH_RESUMED

Emitted when graph operations resume after observation mode.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| observation_started_at | string | ✓ | ISO 8601 start time |
| observation_ended_at | string | ✓ | ISO 8601 end time |
| duration_hours | number | ✓ | Duration in hours |
| resumed_by | string | ✓ | MANUAL/AUTO |
| review_notes | string | ○ | Operator review notes |

**Severity:** INFO

**When Emitted:** When graph observation mode is cleared.

**Example:**
```json
{
  "event_type": "GRAPH_RESUMED",
  "timestamp": "2026-01-26T12:00:00.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706198500000_gr001",
  "data": {
    "observation_started_at": "2026-01-25T12:35:00.000Z",
    "observation_ended_at": "2026-01-26T12:00:00.000Z",
    "duration_hours": 23.4,
    "resumed_by": "MANUAL",
    "review_notes": "False positive, new legitimate whale cluster"
  }
}
```

---

### MOTHER_WALLET_DISCOVERED

Emitted when a new mother wallet is identified.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| mother_address | string | ✓ | Mother wallet address |
| cluster_id | string | ✓ | Assigned cluster ID |
| children_count | number | ✓ | Number of funded children |
| winning_children | number | ✓ | Children with positive PnL |
| total_funding_sol | number | ✓ | Total SOL funded to children |
| trust_score | number | ✓ | Calculated trust score |
| discovery_method | string | ✓ | HARVESTER/MANUAL/BACKFILL |

**Severity:** INFO

**When Emitted:** When God View identifies new mother wallet.

**Example:**
```json
{
  "event_type": "MOTHER_WALLET_DISCOVERED",
  "timestamp": "2026-01-25T12:00:00.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706195200000_mw001",
  "data": {
    "mother_address": "MotherWal...",
    "cluster_id": "cluster_MotherWal...",
    "children_count": 15,
    "winning_children": 12,
    "total_funding_sol": 25.5,
    "trust_score": 0.85,
    "discovery_method": "HARVESTER"
  }
}
```

---

### MOTHER_WALLET_DECAYED

Emitted when mother wallet confidence decays below threshold.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| mother_address | string | ✓ | Mother wallet address |
| cluster_id | string | ✓ | Cluster ID |
| previous_confidence | number | ✓ | Confidence before decay |
| new_confidence | number | ✓ | Confidence after decay |
| days_inactive | number | ✓ | Days since last activity |
| demoted | boolean | ✓ | Whether demoted from tracking |

**Severity:** INFO

**When Emitted:** During daily confidence decay processing.

**Example:**
```json
{
  "event_type": "MOTHER_WALLET_DECAYED",
  "timestamp": "2026-01-25T00:00:00.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706140800000_decay",
  "data": {
    "mother_address": "OldMother...",
    "cluster_id": "cluster_OldMother...",
    "previous_confidence": 0.55,
    "new_confidence": 0.48,
    "days_inactive": 45,
    "demoted": true
  }
}
```

---

### CLUSTER_DETECTED

Emitted when a new wallet cluster is identified.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| cluster_id | string | ✓ | Cluster identifier |
| mother_address | string | ✓ | Source/mother wallet |
| member_count | number | ✓ | Number of cluster members |
| total_pnl_sol | number | ✓ | Aggregate cluster PnL |
| win_rate_pct | number | ✓ | Cluster win rate |
| detection_method | string | ✓ | FUNDING_TRACE/TIMING/BEHAVIOR |

**Severity:** INFO

**When Emitted:** When cluster analysis identifies new cluster.

**Example:**
```json
{
  "event_type": "CLUSTER_DETECTED",
  "timestamp": "2026-01-25T12:00:00.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706195200000_cl001",
  "data": {
    "cluster_id": "cluster_7xKL...",
    "mother_address": "7xKLm9...",
    "member_count": 8,
    "total_pnl_sol": 15.3,
    "win_rate_pct": 72.5,
    "detection_method": "FUNDING_TRACE"
  }
}
```

---

### GRAPH_POISONING_SUSPECTED

Emitted when potential graph poisoning is detected.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| suspicion_type | string | ✓ | FAKE_MOTHER/WASH_TRADING/SYBIL_ATTACK |
| evidence | object | ✓ | Evidence details |
| affected_clusters | array | ✓ | Potentially affected cluster IDs |
| confidence_level | string | ✓ | LOW/MEDIUM/HIGH |
| recommended_action | string | ✓ | Suggested response |

**Severity:** WARNING

**When Emitted:** When anti-poisoning heuristics trigger.

**Example:**
```json
{
  "event_type": "GRAPH_POISONING_SUSPECTED",
  "timestamp": "2026-01-25T12:35:00.000Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198500000_poison",
  "data": {
    "suspicion_type": "FAKE_MOTHER",
    "evidence": {
      "new_mothers_24h": 12,
      "avg_children_per_mother": 3.2,
      "funding_pattern": "UNIFORM_AMOUNTS",
      "activity_timing": "SYNCHRONIZED"
    },
    "affected_clusters": ["cluster_Fake1...", "cluster_Fake2..."],
    "confidence_level": "HIGH",
    "recommended_action": "ENABLE_OBSERVATION_MODE"
  }
}
```

---

## System Events

### SYSTEM_STARTUP

Emitted when the system starts.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| version | string | ✓ | System version |
| phase | number | ✓ | Current trading phase (0-4) |
| mode | string | ✓ | NORMAL/CAPITAL_PRESERVATION/KILL_SWITCH |
| capital_sol | number | ✓ | Starting capital |
| components_loaded | array | ✓ | List of loaded components |
| config_hash | string | ✓ | Hash of settings.yaml |

**Severity:** INFO

**When Emitted:** At system initialization.

**Example:**
```json
{
  "event_type": "SYSTEM_STARTUP",
  "timestamp": "2026-01-25T08:00:00.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706176800000_sys",
  "data": {
    "version": "3.1.0",
    "phase": 2,
    "mode": "NORMAL",
    "capital_sol": 5.0,
    "components_loaded": [
      "database",
      "wallet_tracker",
      "signal_processor",
      "simulator",
      "risk_manager",
      "entropy_injector"
    ],
    "config_hash": "sha256:abc123..."
  }
}
```

---

### SYSTEM_SHUTDOWN

Emitted when the system shuts down.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| shutdown_type | string | ✓ | GRACEFUL/FORCED/ERROR |
| open_positions_count | number | ✓ | Open positions at shutdown |
| positions_closed | boolean | ✓ | Whether positions were closed |
| capital_sol | number | ✓ | Final capital |
| uptime_hours | number | ✓ | System uptime |
| reason | string | ○ | Shutdown reason |

**Severity:** INFO (GRACEFUL) / ERROR (FORCED/ERROR)

**When Emitted:** At system shutdown.

**Example:**
```json
{
  "event_type": "SYSTEM_SHUTDOWN",
  "timestamp": "2026-01-25T23:59:59.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706233199000_sys",
  "data": {
    "shutdown_type": "GRACEFUL",
    "open_positions_count": 0,
    "positions_closed": true,
    "capital_sol": 5.25,
    "uptime_hours": 15.99,
    "reason": "Daily maintenance window"
  }
}
```

---

### API_ERROR

Emitted when an external API call fails.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| api_name | string | ✓ | HELIUS/BIRDEYE/JUPITER/SOLSCAN |
| endpoint | string | ✓ | API endpoint called |
| error_type | string | ✓ | TIMEOUT/HTTP_ERROR/PARSE_ERROR |
| http_status | number | ○ | HTTP status code |
| error_message | string | ✓ | Error details |
| retry_count | number | ✓ | Retries attempted |
| will_retry | boolean | ✓ | Whether retry is planned |

**Severity:** ERROR

**When Emitted:** When API call fails.

**Example:**
```json
{
  "event_type": "API_ERROR",
  "timestamp": "2026-01-25T12:34:56.000Z",
  "severity": "ERROR",
  "correlation_id": "corr_1706198400000_api",
  "data": {
    "api_name": "HELIUS",
    "endpoint": "/v0/addresses/{address}/transactions",
    "error_type": "HTTP_ERROR",
    "http_status": 503,
    "error_message": "Service temporarily unavailable",
    "retry_count": 2,
    "will_retry": true
  }
}
```

---

### API_RATE_LIMITED

Emitted when API rate limit is hit.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| api_name | string | ✓ | API that was rate limited |
| endpoint | string | ✓ | Endpoint that triggered limit |
| limit_type | string | ✓ | MINUTE/HOUR/DAY |
| limit_value | number | ✓ | Rate limit value |
| reset_at | string | ✓ | ISO 8601 reset time |
| requests_made | number | ✓ | Requests made in window |

**Severity:** WARNING

**When Emitted:** When 429 response received.

**Example:**
```json
{
  "event_type": "API_RATE_LIMITED",
  "timestamp": "2026-01-25T12:34:56.000Z",
  "severity": "WARNING",
  "correlation_id": "corr_1706198400000_rate",
  "data": {
    "api_name": "BIRDEYE",
    "endpoint": "/public/tokenlist",
    "limit_type": "MINUTE",
    "limit_value": 100,
    "reset_at": "2026-01-25T12:35:00.000Z",
    "requests_made": 102
  }
}
```

---

### WALLET_ROTATED

Emitted when execution wallet is rotated.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| old_wallet | string | ✓ | Previous wallet address |
| new_wallet | string | ✓ | New wallet address |
| rotation_reason | string | ✓ | SCHEDULED/COMPROMISED/ENTROPY |
| old_wallet_balance_sol | number | ✓ | Balance of old wallet |
| new_wallet_balance_sol | number | ✓ | Balance of new wallet |

**Severity:** INFO (SCHEDULED/ENTROPY) / WARNING (COMPROMISED)

**When Emitted:** When execution wallet changes.

**Example:**
```json
{
  "event_type": "WALLET_ROTATED",
  "timestamp": "2026-01-25T12:00:00.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706195200000_rot",
  "data": {
    "old_wallet": "OldExec...",
    "new_wallet": "NewExec...",
    "rotation_reason": "ENTROPY",
    "old_wallet_balance_sol": 0.5,
    "new_wallet_balance_sol": 0.5
  }
}
```

---

### PHASE_TRANSITION

Emitted when system transitions between trading phases.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| from_phase | number | ✓ | Previous phase (0-4) |
| to_phase | number | ✓ | New phase (0-4) |
| transition_reason | string | ✓ | Why transition occurred |
| metrics_at_transition | object | ✓ | Key metrics snapshot |
| auto_transitioned | boolean | ✓ | Whether automatic |
| operator_approval | string | ○ | Approver if manual |

**Severity:** INFO

**When Emitted:** When phase requirements are met and transition occurs.

**Example:**
```json
{
  "event_type": "PHASE_TRANSITION",
  "timestamp": "2026-01-25T12:00:00.000Z",
  "severity": "INFO",
  "correlation_id": "corr_1706195200000_phase",
  "data": {
    "from_phase": 1,
    "to_phase": 2,
    "transition_reason": "METRICS_ACHIEVED",
    "metrics_at_transition": {
      "signals_tracked": 150,
      "paper_win_rate_pct": 62.5,
      "capital_sol": 5.0,
      "simulator_accuracy_pct": 96.2
    },
    "auto_transitioned": false,
    "operator_approval": "Manual review completed"
  }
}
```

---

## Event Summary Table

| Event Type | Category | Severity | Key Fields |
|------------|----------|----------|------------|
| SIGNAL_DETECTED | Signal | INFO | signal_id, wallet, token, confidence |
| SIGNAL_EXPIRED | Signal | WARNING | signal_id, age_seconds |
| SIGNAL_SKIPPED_ENTROPY | Signal | INFO | signal_id, skip_probability |
| VETO_KILL_SWITCH | Veto | WARNING | signal_id, kill_switch_type |
| VETO_CAPITAL_PRESERVATION | Veto | WARNING | signal_id, drawdown_pct |
| VETO_SIGNAL_STALE | Veto | INFO | signal_id, signal_age_seconds |
| VETO_TOKEN_AGE | Veto | INFO | signal_id, token_age_minutes |
| VETO_SPREAD | Veto | INFO | signal_id, spread_pct |
| VETO_LIQUIDITY | Veto | INFO | signal_id, liquidity_usd |
| VETO_TAX | Veto | INFO | signal_id, total_tax_pct |
| VETO_COOLDOWN | Veto | INFO | signal_id, cooldown_type |
| VETO_SIMULATION | Veto | WARNING | signal_id, simulation_result |
| SIM_STARTED | Simulation | DEBUG | signal_id, simulation_type |
| SIM_PASS | Simulation | INFO | signal_id, total_tax_pct |
| SIM_BLOCK_HONEYPOT | Simulation | WARNING | signal_id, sell_reverted |
| SIM_BLOCK_TAX | Simulation | WARNING | signal_id, total_tax_pct |
| SIM_BLOCK_LIQUIDITY | Simulation | WARNING | signal_id, available_liquidity |
| SIM_ERROR | Simulation | ERROR | signal_id, error_type |
| TRADE_INTENT_CREATED | Trade | INFO | trade_id, signal_id, amount_sol |
| TRADE_EXECUTED | Trade | INFO | trade_id, tx_signature |
| TRADE_FAILED | Trade | ERROR | trade_id, failure_reason |
| TRADE_PARTIAL_FILL | Trade | WARNING | trade_id, fill_percentage |
| EXIT_PANIC | Exit | WARNING | trade_id, loss_pct |
| EXIT_TIME_STOP | Exit | INFO | trade_id, hold_duration |
| EXIT_WHALE_INACTIVITY | Exit | INFO | trade_id, inactivity_minutes |
| EXIT_TRAILING_STOP | Exit | INFO | trade_id, drawdown_from_peak |
| EXIT_MANUAL | Exit | INFO | trade_id, operator_reason |
| EXIT_KILL_SWITCH | Exit | CRITICAL | trade_id, kill_switch_trigger |
| KILL_SWITCH_TRIGGERED | Risk | CRITICAL | trigger, open_positions |
| KILL_SWITCH_CLEARED | Risk | INFO | duration_minutes, cleared_by |
| CAPITAL_PRESERVATION_ACTIVATED | Risk | WARNING | drawdown_pct, capital_sol |
| CAPITAL_PRESERVATION_CLEARED | Risk | INFO | duration_hours, approver_notes |
| DRAWDOWN_WARNING | Risk | WARNING | warning_level, drawdown_pct |
| GRAPH_DISABLED_OBSERVATION_MODE | Graph | WARNING | trigger_reason, mother_wallets_24h |
| GRAPH_RESUMED | Graph | INFO | duration_hours, resumed_by |
| MOTHER_WALLET_DISCOVERED | Graph | INFO | mother_address, children_count |
| MOTHER_WALLET_DECAYED | Graph | INFO | mother_address, new_confidence |
| CLUSTER_DETECTED | Graph | INFO | cluster_id, member_count |
| GRAPH_POISONING_SUSPECTED | Graph | WARNING | suspicion_type, confidence_level |
| SYSTEM_STARTUP | System | INFO | version, phase, capital_sol |
| SYSTEM_SHUTDOWN | System | INFO/ERROR | shutdown_type, uptime_hours |
| API_ERROR | System | ERROR | api_name, error_type |
| API_RATE_LIMITED | System | WARNING | api_name, reset_at |
| WALLET_ROTATED | System | INFO/WARNING | new_wallet, rotation_reason |
| PHASE_TRANSITION | System | INFO | from_phase, to_phase |

---

## Implementation Notes

### Logging Library

Recommended: `loguru` with JSON serialization

```python
from loguru import logger
import sys

logger.remove()
logger.add(
    sys.stdout,
    format="{message}",
    serialize=True,  # JSON output
    level="INFO"
)
logger.add(
    "logs/whale_hunter.log",
    format="{message}",
    serialize=True,
    rotation="100 MB",
    retention="30 days",
    level="DEBUG"
)
```

### Event Emission Helper

```python
import uuid
from datetime import datetime, timezone

def emit_event(event_type: str, severity: str, data: dict, correlation_id: str = None):
    """Emit a structured event."""
    event = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        "severity": severity,
        "correlation_id": correlation_id or f"corr_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:6]}",
        "data": data
    }
    logger.log(severity, event)
    return event
```

### Retention Policy

| Log Type | Retention | Storage |
|----------|-----------|---------|
| DEBUG | 7 days | Local only |
| INFO | 30 days | Local + backup |
| WARNING | 90 days | Local + backup |
| ERROR/CRITICAL | 1 year | Local + backup + archive |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 3.1.0 | 2026-01-25 | Initial event specification |
