"""
V3.1 API Clients Module

Clients for:
- Helius API (Enhanced transactions, webhooks, RPC)
- BirdEye API (Price data, token info)
- Solscan API (Transaction history, wallet activity)
- Jupiter API (Quotes, swaps)

All clients implement rate limiting and error handling.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import os
import time
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """Simple rate limiter for API calls."""
    requests_per_second: float
    last_requests: deque = None
    
    def __post_init__(self):
        if self.last_requests is None:
            self.last_requests = deque(maxlen=int(self.requests_per_second * 2))
    
    async def wait(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()
        
        # Remove old requests
        while self.last_requests and now - self.last_requests[0] > 1.0:
            self.last_requests.popleft()
        
        # Check if we need to wait
        if len(self.last_requests) >= self.requests_per_second:
            wait_time = 1.0 - (now - self.last_requests[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        self.last_requests.append(time.time())


@dataclass
class TokenInfo:
    """Token information from APIs."""
    address: str
    symbol: str
    name: str
    decimals: int
    price_usd: float
    market_cap_usd: float
    liquidity_usd: float
    holder_count: int
    volume_24h: float
    creation_time: Optional[datetime] = None
    price_change_24h: float = 0.0


@dataclass
class WalletActivity:
    """Wallet activity record."""
    signature: str
    timestamp: datetime
    type: str  # SWAP, TRANSFER, etc.
    token_in: Optional[str] = None
    token_out: Optional[str] = None
    amount_in: float = 0.0
    amount_out: float = 0.0
    success: bool = True


class HeliusClient:
    """
    Helius API client for Solana.
    
    Features:
    - Enhanced transaction parsing
    - Webhook management
    - DAS (Digital Asset Standard) API
    - RPC with enhanced data
    """
    
    BASE_URL = "https://api.helius.xyz/v0"
    RPC_URL_TEMPLATE = "https://mainnet.helius-rpc.com/?api-key={api_key}"
    
    def __init__(self, api_key: str = None, requests_per_second: float = 10):
        self.api_key = api_key or os.getenv("HELIUS_API_KEY", "")
        self.rate_limiter = RateLimiter(requests_per_second=requests_per_second)
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def rpc_url(self) -> str:
        return self.RPC_URL_TEMPLATE.format(api_key=self.api_key)
    
    async def start(self):
        if not self._session:
            self._session = aiohttp.ClientSession()
    
    async def stop(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _request(self, method: str, endpoint: str, 
                       params: Dict = None, json_data: Dict = None) -> Dict:
        """Make API request with rate limiting."""
        await self.rate_limiter.wait()
        
        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["api-key"] = self.api_key
        
        try:
            if method == "GET":
                async with self._session.get(url, params=params) as resp:
                    return await resp.json()
            elif method == "POST":
                async with self._session.post(url, params=params, json=json_data) as resp:
                    return await resp.json()
        except Exception as e:
            logger.error(f"Helius API error: {e}")
            return {"error": str(e)}
    
    # =========================================================================
    # TRANSACTION PARSING
    # =========================================================================
    
    async def parse_transactions(self, signatures: List[str]) -> List[Dict]:
        """
        Parse transactions with enhanced data.
        Returns structured transaction information.
        """
        result = await self._request(
            "POST", "transactions",
            json_data={"transactions": signatures}
        )
        return result if isinstance(result, list) else []
    
    async def get_transaction_history(self, address: str, 
                                       limit: int = 100) -> List[Dict]:
        """
        Get parsed transaction history for an address.
        """
        result = await self._request(
            "GET", f"addresses/{address}/transactions",
            params={"limit": limit}
        )
        return result if isinstance(result, list) else []
    
    # =========================================================================
    # WEBHOOK MANAGEMENT
    # =========================================================================
    
    async def create_webhook(self, callback_url: str, 
                              addresses: List[str],
                              transaction_types: List[str] = None) -> Dict:
        """
        Create webhook to monitor addresses.
        
        Args:
            callback_url: URL to receive webhook events
            addresses: List of addresses to monitor
            transaction_types: Types to filter (e.g., ["SWAP", "TRANSFER"])
        """
        payload = {
            "webhookURL": callback_url,
            "accountAddresses": addresses,
            "transactionTypes": transaction_types or ["Any"],
            "webhookType": "enhanced"
        }
        
        return await self._request("POST", "webhooks", json_data=payload)
    
    async def get_webhooks(self) -> List[Dict]:
        """Get all configured webhooks."""
        return await self._request("GET", "webhooks")
    
    async def delete_webhook(self, webhook_id: str) -> Dict:
        """Delete a webhook."""
        await self.rate_limiter.wait()
        url = f"{self.BASE_URL}/webhooks/{webhook_id}?api-key={self.api_key}"
        
        async with self._session.delete(url) as resp:
            return {"success": resp.status == 200}
    
    # =========================================================================
    # RPC METHODS
    # =========================================================================
    
    async def rpc_call(self, method: str, params: List = None) -> Dict:
        """Make RPC call through Helius."""
        await self.rate_limiter.wait()
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or []
        }
        
        try:
            async with self._session.post(self.rpc_url, json=payload) as resp:
                return await resp.json()
        except Exception as e:
            logger.error(f"RPC error: {e}")
            return {"error": str(e)}
    
    async def get_balance(self, address: str) -> float:
        """Get SOL balance for address."""
        result = await self.rpc_call("getBalance", [address])
        lamports = result.get("result", {}).get("value", 0)
        return lamports / 1e9  # Convert to SOL
    
    async def get_token_accounts(self, address: str) -> List[Dict]:
        """Get token accounts for an address."""
        result = await self.rpc_call(
            "getTokenAccountsByOwner",
            [
                address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"}
            ]
        )
        return result.get("result", {}).get("value", [])


class BirdEyeClient:
    """
    BirdEye API client for token data.
    
    Features:
    - Token price and market data
    - Holder information
    - Trade history
    - DEX data
    """
    
    BASE_URL = "https://public-api.birdeye.so"
    
    def __init__(self, api_key: str = None, requests_per_second: float = 5):
        self.api_key = api_key or os.getenv("BIRDEYE_API_KEY", "")
        self.rate_limiter = RateLimiter(requests_per_second=requests_per_second)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        if not self._session:
            self._session = aiohttp.ClientSession()
    
    async def stop(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make API request."""
        await self.rate_limiter.wait()
        
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {"X-API-KEY": self.api_key}
        
        try:
            async with self._session.get(url, params=params, headers=headers) as resp:
                return await resp.json()
        except Exception as e:
            logger.error(f"BirdEye API error: {e}")
            return {"error": str(e)}
    
    # =========================================================================
    # TOKEN DATA
    # =========================================================================
    
    async def get_token_price(self, address: str) -> Optional[float]:
        """Get current token price in USD."""
        result = await self._request("public/price", {"address": address})
        return result.get("data", {}).get("value")
    
    async def get_token_info(self, address: str) -> Optional[TokenInfo]:
        """Get comprehensive token information."""
        # Get overview data
        overview = await self._request("public/token_overview", {"address": address})
        data = overview.get("data", {})
        
        if not data:
            return None
        
        # Get security data
        security = await self._request("public/token_security", {"address": address})
        sec_data = security.get("data", {})
        
        return TokenInfo(
            address=address,
            symbol=data.get("symbol", "UNKNOWN"),
            name=data.get("name", "Unknown Token"),
            decimals=data.get("decimals", 9),
            price_usd=data.get("price", 0),
            market_cap_usd=data.get("mc", 0),
            liquidity_usd=data.get("liquidity", 0),
            holder_count=sec_data.get("holderCount", 0),
            volume_24h=data.get("v24hUSD", 0),
            creation_time=datetime.fromtimestamp(data["createdAt"]) if data.get("createdAt") else None,
            price_change_24h=data.get("priceChange24h", 0)
        )
    
    async def get_token_creation_time(self, address: str) -> Optional[datetime]:
        """Get token creation timestamp."""
        result = await self._request("public/token_creation_info", {"address": address})
        data = result.get("data", {})
        
        if data.get("blockTime"):
            return datetime.fromtimestamp(data["blockTime"])
        return None
    
    async def get_token_holders(self, address: str, limit: int = 20) -> List[Dict]:
        """Get top token holders."""
        result = await self._request(
            "public/token_holder",
            {"address": address, "limit": limit}
        )
        return result.get("data", {}).get("items", [])
    
    # =========================================================================
    # TRADE DATA
    # =========================================================================
    
    async def get_recent_trades(self, address: str, limit: int = 50) -> List[Dict]:
        """Get recent trades for a token."""
        result = await self._request(
            "public/txs/token",
            {"address": address, "limit": limit, "tx_type": "swap"}
        )
        return result.get("data", {}).get("items", [])
    
    async def get_wallet_trades(self, wallet: str, limit: int = 50) -> List[Dict]:
        """Get recent trades for a wallet."""
        result = await self._request(
            "public/txs/wallet",
            {"wallet": wallet, "limit": limit, "tx_type": "swap"}
        )
        return result.get("data", {}).get("items", [])


class SolscanClient:
    """
    Solscan API client for transaction history.
    
    Features:
    - Transaction history
    - Account info
    - Token transfers
    """
    
    BASE_URL = "https://public-api.solscan.io"
    PRO_URL = "https://pro-api.solscan.io/v1.0"
    
    def __init__(self, api_key: str = None, requests_per_second: float = 3):
        self.api_key = api_key or os.getenv("SOLSCAN_API_KEY", "")
        self.rate_limiter = RateLimiter(requests_per_second=requests_per_second)
        self._session: Optional[aiohttp.ClientSession] = None
        self.use_pro = bool(self.api_key)
    
    async def start(self):
        if not self._session:
            self._session = aiohttp.ClientSession()
    
    async def stop(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make API request."""
        await self.rate_limiter.wait()
        
        base = self.PRO_URL if self.use_pro else self.BASE_URL
        url = f"{base}/{endpoint}"
        headers = {"token": self.api_key} if self.api_key else {}
        
        try:
            async with self._session.get(url, params=params, headers=headers) as resp:
                return await resp.json()
        except Exception as e:
            logger.error(f"Solscan API error: {e}")
            return {"error": str(e)}
    
    async def get_account_transactions(self, address: str, 
                                        limit: int = 50) -> List[Dict]:
        """Get transaction history for account."""
        result = await self._request(
            "account/transactions",
            {"account": address, "limit": limit}
        )
        return result if isinstance(result, list) else []
    
    async def get_account_tokens(self, address: str) -> List[Dict]:
        """Get token holdings for account."""
        result = await self._request(
            "account/tokens",
            {"account": address}
        )
        return result if isinstance(result, list) else []
    
    async def get_account_sol_transfers(self, address: str,
                                         limit: int = 50) -> List[Dict]:
        """Get SOL transfers for account (funding source tracing)."""
        result = await self._request(
            "account/solTransfers",
            {"account": address, "limit": limit}
        )
        return result.get("data", []) if isinstance(result, dict) else []
    
    async def get_token_meta(self, address: str) -> Dict:
        """Get token metadata."""
        return await self._request("token/meta", {"token": address})


class JupiterClient:
    """
    Jupiter API client for swap quotes and routing.
    
    Features:
    - Quote fetching
    - Swap transaction building
    - Price impact calculation
    """
    
    BASE_URL = "https://quote-api.jup.ag/v6"
    
    def __init__(self, requests_per_second: float = 10):
        self.rate_limiter = RateLimiter(requests_per_second=requests_per_second)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        if not self._session:
            self._session = aiohttp.ClientSession()
    
    async def stop(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _request(self, method: str, endpoint: str,
                       params: Dict = None, json_data: Dict = None) -> Dict:
        """Make API request."""
        await self.rate_limiter.wait()
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            if method == "GET":
                async with self._session.get(url, params=params) as resp:
                    return await resp.json()
            elif method == "POST":
                async with self._session.post(url, json=json_data) as resp:
                    return await resp.json()
        except Exception as e:
            logger.error(f"Jupiter API error: {e}")
            return {"error": str(e)}
    
    async def get_quote(self, input_mint: str, output_mint: str,
                        amount: int, slippage_bps: int = 300) -> Dict:
        """
        Get swap quote.
        
        Args:
            input_mint: Input token address
            output_mint: Output token address  
            amount: Amount in smallest unit (lamports/tokens)
            slippage_bps: Slippage in basis points (300 = 3%)
        """
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
            "slippageBps": slippage_bps
        }
        
        return await self._request("GET", "quote", params=params)
    
    async def get_swap_transaction(self, quote: Dict,
                                    user_public_key: str) -> Dict:
        """
        Get swap transaction from quote.
        """
        payload = {
            "quoteResponse": quote,
            "userPublicKey": user_public_key,
            "wrapAndUnwrapSol": True,
            "computeUnitPriceMicroLamports": 1000
        }
        
        return await self._request("POST", "swap", json_data=payload)
    
    async def estimate_price_impact(self, input_mint: str, output_mint: str,
                                     amount: int) -> float:
        """
        Estimate price impact for a swap.
        """
        quote = await self.get_quote(input_mint, output_mint, amount)
        return float(quote.get("priceImpactPct", 0))


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_api_clients() -> Dict[str, Any]:
    """
    Create all API clients with environment configuration.
    """
    return {
        "helius": HeliusClient(
            api_key=os.getenv("HELIUS_API_KEY"),
            requests_per_second=10
        ),
        "birdeye": BirdEyeClient(
            api_key=os.getenv("BIRDEYE_API_KEY"),
            requests_per_second=5
        ),
        "solscan": SolscanClient(
            api_key=os.getenv("SOLSCAN_API_KEY"),
            requests_per_second=3
        ),
        "jupiter": JupiterClient(
            requests_per_second=10
        )
    }


async def start_all_clients(clients: Dict[str, Any]) -> None:
    """Start all API client sessions."""
    for name, client in clients.items():
        await client.start()
        logger.info(f"Started {name} client")


async def stop_all_clients(clients: Dict[str, Any]) -> None:
    """Stop all API client sessions."""
    for name, client in clients.items():
        await client.stop()
        logger.info(f"Stopped {name} client")
