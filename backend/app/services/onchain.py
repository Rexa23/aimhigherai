"""
Onchain data client.
Pulls token data from Dexscreener (primary), Moralis (secondary), Covalent (tertiary).
All calls are rate-limit aware with exponential backoff via tenacity.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    retry, retry_if_exception_type, stop_after_attempt,
    wait_exponential, before_sleep_log,
)

from app.core.config import settings
from app.models.lead import Chain

logger = logging.getLogger(__name__)

# ── Supported chains → platform identifiers ───────────────────────────────────

CHAIN_DEXSCREENER: dict[Chain, str] = {
    Chain.ETHEREUM: "ethereum",
    Chain.BNB:      "bsc",
    Chain.SOLANA:   "solana",
    Chain.BASE:     "base",
}

CHAIN_MORALIS: dict[Chain, str] = {
    Chain.ETHEREUM: "eth",
    Chain.BNB:      "bsc",
    Chain.SOLANA:   "solana",
    Chain.BASE:     "base",
}

CHAIN_COVALENT: dict[Chain, int] = {
    Chain.ETHEREUM: 1,
    Chain.BNB:      56,
    Chain.BASE:     8453,
    # Solana not supported by Covalent EVM endpoint
}


# ── Token snapshot dataclass ──────────────────────────────────────────────────

@dataclass
class TokenSnapshot:
    chain: Chain
    contract_address: str
    token_symbol: str
    token_name: str
    market_cap_usd: float
    price_usd: float
    volume_24h_usd: float
    liquidity_usd: float
    price_change_24h: float
    dex_url: str
    source: str
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def in_target_range(self) -> bool:
        return settings.MARKET_CAP_MIN <= self.market_cap_usd <= settings.MARKET_CAP_MAX


# ── Retry decorator ───────────────────────────────────────────────────────────

def _http_retry():
    return retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


# ── Dexscreener client ────────────────────────────────────────────────────────

class DexscreenerClient:
    BASE = "https://api.dexscreener.com/latest"

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    @_http_retry()
    async def search_tokens(self, query: str) -> list[TokenSnapshot]:
        """Search by token name/symbol. Returns all results in market cap range."""
        resp = await self._client.get(
            f"{self.BASE}/dex/search",
            params={"q": query},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return self._parse_pairs(data.get("pairs") or [])

    @_http_retry()
    async def get_token_by_address(self, chain: Chain, address: str) -> TokenSnapshot | None:
        chain_id = CHAIN_DEXSCREENER.get(chain)
        if not chain_id:
            return None
        resp = await self._client.get(
            f"{self.BASE}/dex/tokens/{address}",
            timeout=15,
        )
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        # Pick highest liquidity pair
        pairs = [p for p in pairs if p.get("chainId") == chain_id]
        if not pairs:
            return None
        pairs.sort(key=lambda p: float(p.get("liquidity", {}).get("usd") or 0), reverse=True)
        snapshots = self._parse_pairs(pairs[:1])
        return snapshots[0] if snapshots else None

    @_http_retry()
    async def get_new_pairs(self, chain: Chain, min_age_minutes: int = 5, max_age_minutes: int = 1440) -> list[TokenSnapshot]:
        """Fetch recently listed pairs on a chain."""
        chain_id = CHAIN_DEXSCREENER.get(chain)
        if not chain_id:
            return []
        resp = await self._client.get(
            f"{self.BASE}/dex/tokens/new/{chain_id}",
            timeout=15,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        return self._parse_pairs(pairs)

    def _parse_pairs(self, pairs: list[dict]) -> list[TokenSnapshot]:
        results: list[TokenSnapshot] = []
        for pair in pairs:
            try:
                chain_str = pair.get("chainId", "")
                chain = self._map_chain(chain_str)
                if not chain:
                    continue

                market_cap = float(pair.get("marketCap") or pair.get("fdv") or 0)
                if market_cap <= 0:
                    continue

                snapshot = TokenSnapshot(
                    chain=chain,
                    contract_address=pair.get("baseToken", {}).get("address", ""),
                    token_symbol=pair.get("baseToken", {}).get("symbol", ""),
                    token_name=pair.get("baseToken", {}).get("name", ""),
                    market_cap_usd=market_cap,
                    price_usd=float(pair.get("priceUsd") or 0),
                    volume_24h_usd=float((pair.get("volume") or {}).get("h24") or 0),
                    liquidity_usd=float((pair.get("liquidity") or {}).get("usd") or 0),
                    price_change_24h=float((pair.get("priceChange") or {}).get("h24") or 0),
                    dex_url=pair.get("url", ""),
                    source="dexscreener",
                    raw=pair,
                )
                results.append(snapshot)
            except (KeyError, ValueError, TypeError) as e:
                logger.debug(f"Dexscreener parse error: {e}")
                continue
        return results

    @staticmethod
    def _map_chain(chain_str: str) -> Chain | None:
        mapping = {
            "ethereum": Chain.ETHEREUM,
            "bsc":      Chain.BNB,
            "solana":   Chain.SOLANA,
            "base":     Chain.BASE,
        }
        return mapping.get(chain_str.lower())


# ── Moralis client ────────────────────────────────────────────────────────────

class MoralisClient:
    BASE = "https://deep-index.moralis.io/api/v2.2"

    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._headers = {"X-API-Key": settings.MORALIS_API_KEY}

    @_http_retry()
    async def get_token_price(self, chain: Chain, address: str) -> dict[str, Any] | None:
        chain_id = CHAIN_MORALIS.get(chain)
        if not chain_id or chain == Chain.SOLANA:
            return None
        resp = await self._client.get(
            f"{self.BASE}/erc20/{address}/price",
            params={"chain": chain_id, "include": "percent_change"},
            headers=self._headers,
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    @_http_retry()
    async def get_token_metadata(self, chain: Chain, address: str) -> dict[str, Any] | None:
        chain_id = CHAIN_MORALIS.get(chain)
        if not chain_id or chain == Chain.SOLANA:
            return None
        resp = await self._client.get(
            f"{self.BASE}/erc20/metadata",
            params={"chain": chain_id, "addresses[]": address},
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else None

    @_http_retry()
    async def search_tokens_by_name(self, query: str, chain: Chain) -> list[dict[str, Any]]:
        chain_id = CHAIN_MORALIS.get(chain)
        if not chain_id or chain == Chain.SOLANA:
            return []
        resp = await self._client.get(
            f"{self.BASE}/tokens/search",
            params={"query": query, "chain": chain_id, "limit": 20},
            headers=self._headers,
            timeout=15,
        )
        if resp.status_code in (404, 400):
            return []
        resp.raise_for_status()
        return resp.json().get("result") or []

    async def enrich_snapshot(self, snapshot: TokenSnapshot) -> TokenSnapshot:
        """Attempt to enrich an existing snapshot with Moralis price data."""
        try:
            price_data = await self.get_token_price(snapshot.chain, snapshot.contract_address)
            if price_data and snapshot.market_cap_usd <= 0:
                # Estimate market cap from circulating supply if available
                supply = float(price_data.get("circulatingSupply") or 0)
                price = float(price_data.get("usdPrice") or 0)
                if supply > 0 and price > 0:
                    snapshot.market_cap_usd = supply * price
        except Exception as e:
            logger.debug(f"Moralis enrich failed for {snapshot.contract_address}: {e}")
        return snapshot


# ── Covalent client ────────────────────────────────────────────────────────────

class CovalentClient:
    BASE = "https://api.covalenthq.com/v1"

    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._auth = (settings.COVALENT_API_KEY, "")

    @_http_retry()
    async def get_token_holders_count(self, chain: Chain, address: str) -> int | None:
        chain_id = CHAIN_COVALENT.get(chain)
        if not chain_id:
            return None
        resp = await self._client.get(
            f"{self.BASE}/{chain_id}/tokens/{address}/token_holders_v2/",
            auth=self._auth,
            params={"page-size": 1},
            timeout=15,
        )
        if resp.status_code in (404, 400):
            return None
        resp.raise_for_status()
        data = resp.json()
        pagination = data.get("data", {}).get("pagination") or {}
        return pagination.get("total_count")

    @_http_retry()
    async def get_recent_transactions(self, chain: Chain, address: str, days: int = 7) -> int:
        """Return approximate tx count in last N days as activity proxy."""
        chain_id = CHAIN_COVALENT.get(chain)
        if not chain_id:
            return 0
        try:
            resp = await self._client.get(
                f"{self.BASE}/{chain_id}/address/{address}/transactions_v3/",
                auth=self._auth,
                params={"page-size": 100},
                timeout=20,
            )
            resp.raise_for_status()
            items = resp.json().get("data", {}).get("items") or []
            return len(items)
        except Exception:
            return 0


# ── Unified onchain aggregator ────────────────────────────────────────────────

class OnchainAggregator:
    """
    Combines Dexscreener (primary), Moralis (enrichment), Covalent (holder count).
    Returns TokenSnapshots filtered to the 30k–3M market cap window.
    """

    def __init__(self):
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
        self.dex      = DexscreenerClient(self._http)
        self.moralis  = MoralisClient(self._http)
        self.covalent = CovalentClient(self._http)

    async def close(self) -> None:
        await self._http.aclose()

    async def scan_new_tokens(self, chains: list[Chain] | None = None) -> list[TokenSnapshot]:
        """Scan all target chains for newly listed tokens in range."""
        target_chains = chains or list(Chain)
        tasks = [self.dex.get_new_pairs(chain) for chain in target_chains]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        snapshots: list[TokenSnapshot] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Chain scan error: {result}")
                continue
            snapshots.extend(t for t in result if t.in_target_range)

        return snapshots

    async def lookup_token(self, chain: Chain, address: str) -> TokenSnapshot | None:
        snapshot = await self.dex.get_token_by_address(chain, address)
        if snapshot and snapshot.in_target_range:
            snapshot = await self.moralis.enrich_snapshot(snapshot)
            return snapshot
        return None

    async def search(self, query: str) -> list[TokenSnapshot]:
        """Keyword search across Dexscreener."""
        results = await self.dex.search_tokens(query)
        return [t for t in results if t.in_target_range]

    async def get_holder_count(self, snapshot: TokenSnapshot) -> int | None:
        return await self.covalent.get_token_holders_count(
            snapshot.chain, snapshot.contract_address
        )

    async def get_tx_activity(self, snapshot: TokenSnapshot) -> int:
        return await self.covalent.get_recent_transactions(
            snapshot.chain, snapshot.contract_address
        )
