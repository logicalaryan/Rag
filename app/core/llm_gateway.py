import asyncio
import hashlib
import logging
import random
import re
import time
from collections import OrderedDict, deque
from typing import Any, Callable, Coroutine, Dict, Optional, Tuple
from app.config import settings

_RETRY_IN_RE = re.compile(r"retry in (\d+(?:\.\d+)?)s", re.IGNORECASE)


class QuotaExhaustedError(RuntimeError):
    """Raised when Gemini returns a hard quota/rate limit error that cannot be recovered immediately."""


class GeminiGateway:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(settings.GEMINI_MAX_CONCURRENT_REQUESTS)
        self._request_timestamps: deque = deque()
        self._rate_lock = asyncio.Lock()

        # Tenant-isolated LRU + TTL cache: key -> (expires_at, payload_dict)
        self._cache: "OrderedDict[str, Tuple[float, Dict[str, Any]]]" = OrderedDict()
        # Single-flight map for identical concurrent queries: key -> asyncio.Future
        self._inflight: Dict[str, asyncio.Future] = {}

        # Per-client HTTP rate limit: client_key -> deque of timestamps
        self._client_requests: Dict[str, deque] = {}

    def check_client_rate_limit(self, client_key: str) -> Tuple[bool, float]:
        """Request-level rate limiter (#1). Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        window = 60.0
        q = self._client_requests.setdefault(client_key, deque())
        while q and now - q[0] >= window:
            q.popleft()
        if len(q) >= settings.CLIENT_RATE_LIMIT_PER_MINUTE:
            retry_after = max(1.0, window - (now - q[0]))
            return False, round(retry_after, 1)
        q.append(now)
        return True, 0.0

    def build_cache_key(
        self,
        tenant_id: str,
        kb_fingerprint: str,
        query: str,
        allow_web_search: bool,
    ) -> str:
        """
        Builds a cache key isolated by tenant_id and knowledge-base state (#5).
        Different tenants or updated document sets never share cache hits.
        """
        normalized_q = re.sub(r"\s+", " ", query.strip().lower())
        raw = f"t={tenant_id}|kb={kb_fingerprint}|web={int(allow_web_search)}|q={normalized_q}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        item = self._cache.get(key)
        if not item:
            return None
        expires_at, payload = item
        if time.monotonic() > expires_at:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return payload

    def set_cached(self, key: str, payload: Dict[str, Any]) -> None:
        now = time.monotonic()
        self._cache[key] = (now + settings.CACHE_TTL_SECONDS, payload)
        self._cache.move_to_end(key)
        while len(self._cache) > settings.CACHE_MAX_ENTRIES:
            self._cache.popitem(last=False)

    async def _acquire_rpm_slot(self) -> None:
        """Sliding-window rate limiter across all outbound Gemini calls."""
        async with self._rate_lock:
            now = time.monotonic()
            while self._request_timestamps and now - self._request_timestamps[0] >= 60.0:
                self._request_timestamps.popleft()

            if len(self._request_timestamps) >= settings.GEMINI_RPM_LIMIT:
                wait_for = 60.0 - (now - self._request_timestamps[0]) + 0.25
                if wait_for > 0:
                    await asyncio.sleep(wait_for)
                now = time.monotonic()
                while self._request_timestamps and now - self._request_timestamps[0] >= 60.0:
                    self._request_timestamps.popleft()

            self._request_timestamps.append(time.monotonic())

    @staticmethod
    def _parse_retry_after(exc: Exception) -> Tuple[bool, Optional[float]]:
        """
        Inspects a 429/503 exception.
        Returns (is_retryable, suggested_delay_seconds).
        Does NOT retry hard daily quota exhaustion or limit: 0 errors.
        """
        msg = str(exc)
        upper = msg.upper()
        is_rate_or_transient = any(code in upper for code in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"))
        if not is_rate_or_transient:
            return False, None

        # Hard quota check: do not retry daily quota exhaustion or zero-limit tiers
        if any(hard in msg for hard in ("PerDay", "limit: 0", "check your plan and billing details")):
            match = _RETRY_IN_RE.search(msg)
            if match:
                delay = float(match.group(1))
                return (delay <= 25.0), delay
            return False, None

        # Check HTTP Retry-After header if attached to the exception response
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None) or {}
        retry_header = headers.get("retry-after") or headers.get("Retry-After")
        if retry_header:
            try:
                return True, float(retry_header)
            except ValueError:
                pass

        match = _RETRY_IN_RE.search(msg)
        if match:
            return True, float(match.group(1))

        return True, None

    async def call(
        self,
        fn: Callable[[], Coroutine[Any, Any, Any]],
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Executes an async Gemini SDK call with:
        - Concurrency semaphore (#2)
        - RPM pacing (#1)
        - Timeout (#8)
        - Exponential backoff + jitter + Retry-After (#3, #4)
        """
        effective_timeout = timeout or settings.GEMINI_TIMEOUT_SECONDS
        last_exc: Optional[Exception] = None

        for attempt in range(settings.GEMINI_MAX_RETRIES + 1):
            await self._acquire_rpm_slot()
            try:
                async with self._semaphore:
                    return await asyncio.wait_for(fn(), timeout=effective_timeout)
            except asyncio.TimeoutError as exc:
                last_exc = exc
                if attempt >= settings.GEMINI_MAX_RETRIES:
                    break
                await asyncio.sleep(1.5 * (2 ** attempt) + random.uniform(0.1, 0.6))
            except Exception as exc:
                last_exc = exc
                retryable, retry_after = self._parse_retry_after(exc)
                if not retryable or attempt >= settings.GEMINI_MAX_RETRIES:
                    break
                if retry_after is not None:
                    delay = min(retry_after, 25.0) + random.uniform(0.2, 0.8)
                else:
                    delay = min(2.0 * (2 ** attempt), 16.0) + random.uniform(0.25, 1.0)
                logging.warning("Transient Gemini rate limit (attempt %d), sleeping %.1fs", attempt + 1, delay)
                await asyncio.sleep(delay)

        raise last_exc


gemini_gateway = GeminiGateway()
