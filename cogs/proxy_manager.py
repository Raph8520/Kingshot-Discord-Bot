import os
import time
import heapq
import asyncio
from typing import Optional, List, Tuple, Dict


class ProxyPool:
    """
    ProxyPool with per-proxy throttling and optional sticky assignment.

    Features:
    - Read proxies from a file (one per line). Blank lines and lines starting
      with '#' are ignored.
    - Normalizes simple formats like 'host:port' or 'host:port:user:pass' into
      full URLs using PROXY_SCHEME (default 'socks5'). If a line already
      contains '://', it is used as-is.
    - Environment-configurable file path via PROXIES_PATH and min interval via
      PROXY_MIN_INTERVAL.
    - acquire(sticky_key=...) will try to return the same proxy for a given
      key if previously assigned.
    """

    def __init__(self, filepath: Optional[str] = None, min_interval: Optional[float] = None):
        env_path = os.getenv('PROXIES_PATH')
        env_min = os.getenv('PROXY_MIN_INTERVAL')

        self.filepath = filepath or env_path or 'proxies.txt'
        try:
            self.min_interval = float(min_interval) if min_interval is not None else (float(env_min) if env_min else 2.0)
        except Exception:
            self.min_interval = 2.0

        self._heap: List[Tuple[float, str]] = []  # (next_available_ts, proxy_url)
        self._proxy_set: set = set()
        self._lock = asyncio.Lock()
        self._sticky: Dict[str, str] = {}

        self._load_proxies()

    def _normalize(self, raw: str) -> str:
        raw = raw.strip()
        if not raw:
            return ''

        if '://' in raw:
            return raw

        parts = raw.split(':')
        scheme = os.getenv('PROXY_SCHEME', 'socks5')
        if len(parts) == 4:
            host, port, user, pwd = parts
            return f"{scheme}://{user}:{pwd}@{host}:{port}"
        if len(parts) == 2:
            host, port = parts
            return f"{scheme}://{host}:{port}"

        # unknown format, return raw
        return raw

    def _load_proxies(self):
        self._heap = []
        self._proxy_set = set()

        if not os.path.exists(self.filepath):
            return

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    raw = line.strip()
                    if not raw or raw.startswith('#'):
                        continue

                    proxy = self._normalize(raw)
                    if not proxy:
                        continue

                    if proxy in self._proxy_set:
                        continue

                    self._proxy_set.add(proxy)
                    heapq.heappush(self._heap, (0.0, proxy))
        except Exception:
            # Best-effort: don't raise on load; leave pool empty
            self._heap = []
            self._proxy_set = set()

    def reload(self):
        """Reload proxies from file and clear sticky assignments."""
        self._load_proxies()
        self._sticky.clear()

    def has_proxies(self) -> bool:
        return len(self._heap) > 0

    def size(self) -> int:
        return len(self._heap)

    async def acquire(self, sticky_key: Optional[str] = None) -> Optional[str]:
        """Acquire the next available proxy.

        If sticky_key is provided and a proxy was previously assigned to that key
        and is still known, attempt to use it (respecting availability).
        """
        async with self._lock:
            if not self._heap:
                return None

            now = time.time()

            # sticky path
            if sticky_key:
                assigned = self._sticky.get(sticky_key)
                if assigned and assigned in self._proxy_set:
                    # find it in heap
                    for i, (ts, p) in enumerate(self._heap):
                        if p == assigned:
                            next_ts, proxy = self._heap.pop(i)
                            heapq.heapify(self._heap)
                            wait = max(0.0, next_ts - now)
                            if wait > 0:
                                await asyncio.sleep(wait)
                            heapq.heappush(self._heap, (time.time() + self.min_interval, proxy))
                            return proxy

            # pop next available proxy
            next_ts, proxy = heapq.heappop(self._heap)
            wait = max(0.0, next_ts - now)
            if wait > 0:
                await asyncio.sleep(wait)

            # schedule next availability
            heapq.heappush(self._heap, (time.time() + self.min_interval, proxy))

            if sticky_key:
                self._sticky[sticky_key] = proxy

            return proxy

