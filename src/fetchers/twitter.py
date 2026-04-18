from src.fetchers.base import BaseFetcher
from src.models import NewsItem
from datetime import datetime, timezone
import asyncio
import httpx
import feedparser
from time import mktime
import logging

logger = logging.getLogger(__name__)

# 经过验证的可用 Nitter 实例（2026年4月仍在运行）
DEFAULT_NITTER_INSTANCES = [
    "https://nitter.net",
    "https://xcancel.com",
    "https://nitter.privacyredirect.com",
    "https://nuku.trabun.org",
    "https://lightbrd.com",
    "https://nitter.poast.org",
]


class TwitterFetcher(BaseFetcher):
    source_name = "twitter"

    def __init__(self, accounts: list[str], nitter_instances: list[str] | None = None, **kwargs):
        self.accounts = accounts
        self.nitter_instances = nitter_instances or DEFAULT_NITTER_INSTANCES

    async def _fetch_rss(self, url: str) -> str | None:
        """Fetch RSS with proper headers and redirect following."""
        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
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
        sem = asyncio.Semaphore(5)  # 最多5个并发（避免被 Nitter 限流）

        async def fetch_with_sem(account):
            async with sem:
                return await self._fetch_account(account)

        results = await asyncio.gather(*[fetch_with_sem(a) for a in self.accounts], return_exceptions=True)
        items = []
        for r in results:
            if isinstance(r, list):
                items.extend(r)
        return items

    async def _fetch_account(self, account: str) -> list[NewsItem]:
        """Try Nitter instances to get Twitter/X user timeline RSS."""
        for instance in self.nitter_instances:
            url = f"{instance}/{account}/rss"
            text = await self._fetch_rss(url)
            if text and ('<item>' in text or '<entry>' in text):
                parsed = feedparser.parse(text)
                if not parsed.entries:
                    logger.warning(f"Nitter {instance} returned empty feed for @{account}")
                    continue
                results = []
                for entry in parsed.entries[:10]:
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
                    link = entry.get("link", "")
                    # 将 nitter URL 替换为 twitter URL
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
                logger.info(f"Nitter {instance} fetched {len(results)} tweets for @{account}")
                return results
            else:
                logger.warning(f"Nitter {instance} returned no RSS for @{account}, trying next")
        logger.error(f"All Nitter instances failed for @{account}")
        return []
