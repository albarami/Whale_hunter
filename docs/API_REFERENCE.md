# API Reference: Pinned Endpoints

**Version:** 3.1.0  
**Policy:** Only documented endpoints used. No invented APIs.

---

## Helius

**Base URL:** `https://api.helius.xyz`  
**Auth:** API key as query param `?api-key={KEY}`  
**Env Var:** `HELIUS_API_KEY`

### Webhooks Setup
```
POST /v0/webhooks
```
**Body:**
```json
{
  "webhookURL": "https://your-server.com/webhook",
  "transactionTypes": ["SWAP"],
  "accountAddresses": ["wallet1", "wallet2"],
  "webhookType": "enhanced"
}
```
**Rate Limit:** 10 requests/sec

### Enhanced Transaction History
```
GET /v0/addresses/{address}/transactions
```
**Params:** `?api-key={KEY}&type=SWAP&limit=100`  
**Rate Limit:** 10 requests/sec

### Account Info (RPC Proxy)
```
POST /v0/rpc?api-key={KEY}
```
**Body:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "getAccountInfo",
  "params": ["address", {"encoding": "jsonParsed"}]
}
```
**Rate Limit:** 50 requests/sec (RPC calls)

### Parse Transaction
```
POST /v0/transactions
```
**Body:**
```json
{
  "transactions": ["signature1", "signature2"]
}
```
**Rate Limit:** 10 requests/sec, max 100 txs per call

---

## BirdEye

**Base URL:** `https://public-api.birdeye.so`  
**Auth:** Header `X-API-KEY: {KEY}`  
**Env Var:** `BIRDEYE_API_KEY`

### Token Price
```
GET /defi/price
```
**Params:** `?address={token_address}`  
**Response:**
```json
{
  "data": {
    "value": 0.00123,
    "updateUnixTime": 1706198400
  }
}
```
**Rate Limit:** 100 requests/min (free), 1000/min (paid)

### Token Overview
```
GET /defi/token_overview
```
**Params:** `?address={token_address}`  
**Returns:** liquidity, volume, holders, creation time

### Trending Tokens
```
GET /defi/token_trending
```
**Params:** `?sort_by=rank&sort_type=asc&offset=0&limit=20`  
**Rate Limit:** 10 requests/min

### Token List by Wallet
```
GET /v1/wallet/token_list
```
**Params:** `?wallet={address}`  
**Rate Limit:** 50 requests/min

---

## Jupiter

**Base URL:** `https://quote-api.jup.ag/v6`  
**Auth:** None required (public API)  
**Env Var:** N/A

### Quote API
```
GET /quote
```
**Params:**
- `inputMint`: Source token address
- `outputMint`: Destination token address  
- `amount`: Amount in smallest unit (lamports for SOL)
- `slippageBps`: Slippage tolerance in basis points

**Example:**
```
/quote?inputMint=So11111111111111111111111111111111111111112&outputMint={TOKEN}&amount=1000000000&slippageBps=50
```
**Rate Limit:** 600 requests/min

### Swap API
```
POST /swap
```
**Body:**
```json
{
  "quoteResponse": { /* from /quote */ },
  "userPublicKey": "your_wallet_address",
  "wrapAndUnwrapSol": true
}
```
**Returns:** Serialized transaction for signing  
**Rate Limit:** 300 requests/min

### Swap Instructions
```
POST /swap-instructions
```
**Body:** Same as /swap  
**Returns:** Individual instructions for custom transaction building

---

## Solana RPC

**Endpoints:**
- Helius: `https://rpc.helius.xyz/?api-key={KEY}`
- Public: `https://api.mainnet-beta.solana.com` (rate limited)

**Env Var:** `SOLANA_RPC_URL`

### simulateTransaction
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "simulateTransaction",
  "params": [
    "base64_encoded_transaction",
    {
      "encoding": "base64",
      "commitment": "confirmed",
      "replaceRecentBlockhash": true
    }
  ]
}
```
**Use:** Honeypot detection, tax calculation  
**Rate Limit:** 100/sec (Helius), 10/sec (public)

### getTransaction
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "getTransaction",
  "params": [
    "transaction_signature",
    {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
  ]
}
```
**Use:** Verify execution, parse results

### getSignaturesForAddress
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "getSignaturesForAddress",
  "params": [
    "wallet_address",
    {"limit": 100, "before": "signature"}
  ]
}
```
**Use:** Fetch wallet transaction history  
**Rate Limit:** 5/sec (public), 50/sec (Helius)

### getBalance
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "getBalance",
  "params": ["wallet_address"]
}
```
**Returns:** Balance in lamports

---

## DexScreener

**Base URL:** `https://api.dexscreener.com`  
**Auth:** None required  
**Use:** Harvester trending token discovery

### Trending Tokens (Solana)
```
GET /latest/dex/tokens/{tokenAddress}
```
**Returns:** Pair info, liquidity, volume, price changes

### Search Pairs
```
GET /latest/dex/search/?q={query}
```
**Params:** Token symbol or address  
**Rate Limit:** 300 requests/min

### Boosted Tokens
```
GET /token-boosts/latest/v1
```
**Returns:** Currently boosted/promoted tokens  
**Use:** Identify potential pump targets

---

## Solscan (Backup)

**Base URL:** `https://pro-api.solscan.io/v1.0`  
**Auth:** Header `token: {KEY}`  
**Env Var:** `SOLSCAN_API_KEY`

### Account Transactions
```
GET /account/transactions
```
**Params:** `?account={address}&limit=50`  
**Rate Limit:** 20 requests/min (free), 100/min (pro)

### Account Transfers
```
GET /account/transfer
```
**Params:** `?account={address}&type=sol&limit=50`  
**Use:** Funding relationship discovery

---

## Rate Limit Summary

| Service | Endpoint Type | Free Tier | Paid Tier |
|---------|--------------|-----------|------------|
| Helius | RPC | 50/sec | 500/sec |
| Helius | Enhanced | 10/sec | 100/sec |
| BirdEye | Price | 100/min | 1000/min |
| Jupiter | Quote | 600/min | 600/min |
| Jupiter | Swap | 300/min | 300/min |
| Solana Public | All | 10/sec | N/A |
| DexScreener | All | 300/min | 300/min |

---

## Authentication Requirements

| Service | Method | Required |
|---------|--------|----------|
| Helius | Query param `api-key` | Yes |
| BirdEye | Header `X-API-KEY` | Yes |
| Jupiter | None | No |
| Solana RPC | Varies by provider | Depends |
| DexScreener | None | No |
| Solscan | Header `token` | Yes (for pro features) |

**Environment Variables:**
```bash
HELIUS_API_KEY=xxx
BIRDEYE_API_KEY=xxx
SOLSCAN_API_KEY=xxx
SOLANA_RPC_URL=https://rpc.helius.xyz/?api-key=xxx
```
