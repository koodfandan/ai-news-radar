from src.fetchers.base import BaseFetcher
from src.models import NewsItem
from datetime import datetime, timezone
import asyncio
import time
import httpx
import feedparser
from time import mktime
import logging

logger = logging.getLogger(__name__)

DEFAULT_NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacyredirect.com",
    "https://lightbrd.com",
    "https://nitter.poast.org",
    "https://xcancel.com",
    "https://nuku.trabun.org",
]

# Global health cache: {instance: (ok: bool, checked_at: float)}
_instance_health: dict[str, tuple[bool, float]] = {}
_account_failures: dict[str, tuple[int, float]] = {}
_HEALTH_TTL = 300
_ACCOUNT_FAILURE_LIMIT = 5
_ACCOUNT_COOLDOWN_SECONDS = 1800
_PROBE_ACCOUNT = "OpenAI"

MAX_PER_ACCOUNT = 10


class TwitterFetcher(BaseFetcher):
    source_name = "twitter"

    def __init__(self, accounts: list[str], nitter_instances: list[str] | None = None, **kwargs):
        self.accounts = accounts
        self.nitter_instances = nitter_instances or DEFAULT_NITTER_INSTANCES

    async def _probe_instance(self, instance: str) -> bool:
        """Probe the RSS endpoint directly so HTML landing pages do not count as healthy."""
        cached = _instance_health.get(instance)
        if cached and time.time() - cached[1] < _HEALTH_TTL:
            return cached[0]
        try:
            async with httpx.AsyncClient(
                timeout=8,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-News-Radar/1.0",
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                },
            ) as client:
                resp = await client.get(f"{instance}/{_PROBE_ACCOUNT}/rss")
                ok = (
                    resp.status_code < 400
                    and ('<item>' in resp.text or '<entry>' in resp.text)
                    and 'RSS reader not yet whitelisted' not in resp.text
                )
        except Exception:
            ok = False
        _instance_health[instance] = (ok, time.time())
        logger.debug(f"[twitter] Nitter probe {instance}: {'ok' if ok else 'dead'}")
        return ok

    async def _get_live_instances(self) -> list[str]:
        """Return instances that passed health check, ordered by original priority."""
        results = await asyncio.gather(*[self._probe_instance(i) for i in self.nitter_instances])
        live = [inst for inst, ok in zip(self.nitter_instances, results) if ok]
        if not live:
            logger.warning("[twitter] All Nitter instances appear down, using all as fallback")
            return self.nitter_instances
        return live

    async def _fetch_rss(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                }
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            logger.warning(f"[{self.source_name}] Failed to fetch {url}: {e}")
            return None

    async def fetch(self) -> list[NewsItem]:
        live_instances = await self._get_live_instances()
        sem = asyncio.Semaphore(5)

        async def fetch_with_sem(account):
            async with sem:
                return await self._fetch_account(account, live_instances)

        results = await asyncio.gather(*[fetch_with_sem(a) for a in self.accounts], return_exceptions=True)
        items = []
        for r in results:
            if isinstance(r, list):
                items.extend(r)
        return items

    def _should_skip_account(self, account: str) -> bool:
        state = _account_failures.get(account.lower())
        if not state:
            return False
        failures, retry_after = state
        if failures < _ACCOUNT_FAILURE_LIMIT:
            return False
        if time.time() >= retry_after:
            _account_failures.pop(account.lower(), None)
            return False
        return True

    def _record_account_failure(self, account: str):
        key = account.lower()
        failures, _ = _account_failures.get(key, (0, 0.0))
        failures += 1
        retry_after = time.time() + _ACCOUNT_COOLDOWN_SECONDS if failures >= _ACCOUNT_FAILURE_LIMIT else 0.0
        _account_failures[key] = (failures, retry_after)

    def _clear_account_failure(self, account: str):
        _account_failures.pop(account.lower(), None)

    async def _fetch_account(self, account: str, instances: list[str]) -> list[NewsItem]:
        if self._should_skip_account(account):
            logger.warning(f"[twitter] Skipping @{account} after repeated fetch failures")
            return []

        for instance in instances:
            url = f"{instance}/{account}/rss"
            text = await self._fetch_rss(url)
            if not text or ('<item>' not in text and '<entry>' not in text):
                # Mark as dead for next cycle
                _instance_health[instance] = (False, time.time())
                continue
            parsed = feedparser.parse(text)
            if not parsed.entries:
                continue
            results = []
            for entry in parsed.entries[:MAX_PER_ACCOUNT]:
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
                link = entry.get("link", "")
                for inst in self.nitter_instances:
                    link = link.replace(inst, "https://x.com")
                title = entry.get("title", "")[:200]
                content = entry.get("summary", entry.get("description", ""))[:500]
                results.append(NewsItem.new(
                    source=f"twitter/@{account}",
                    source_url=link,
                    title=title if title else content[:100],
                    content=content,
                    author=entry.get("dc_creator", f"@{account}").lstrip("@"),
                    created_at=pub_date,
                ))
            logger.info(f"[twitter] {instance} fetched {len(results)} tweets for @{account}")
            self._clear_account_failure(account)
            return results
        self._record_account_failure(account)
        logger.error(f"[twitter] All instances failed for @{account}")
        return []
