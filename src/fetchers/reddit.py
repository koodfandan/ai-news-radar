from src.fetchers.base import BaseFetcher
from src.models import NewsItem
from datetime import datetime, timezone
import httpx
import feedparser
from time import mktime
import logging

logger = logging.getLogger(__name__)


class RedditFetcher(BaseFetcher):
    source_name = "reddit"

    def __init__(self, subreddits: list[str] | None = None, min_score: int = 100):
        self.subreddits = subreddits or ["MachineLearning", "artificial", "LocalLLaMA"]
        self.min_score = min_score

    async def _fetch_rss(self, url: str) -> str | None:
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
            logger.error(f"[{self.source_name}] Failed to fetch {url}: {e}")
            return None

    async def fetch(self) -> list[NewsItem]:
        items = []
        for sub in self.subreddits:
            url = f"https://www.reddit.com/r/{sub}/hot.rss?limit=25"
            text = await self._fetch_rss(url)
            if not text or ('<entry>' not in text and '<item>' not in text):
                logger.warning(f"No RSS data for r/{sub}")
                continue

            parsed = feedparser.parse(text)
            for entry in parsed.entries[:25]:
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime.fromtimestamp(mktime(entry.updated_parsed), tz=timezone.utc)

                link = entry.get("link", "")
                title = entry.get("title", "")[:300]
                content = entry.get("summary", entry.get("description", ""))[:500]
                author = entry.get("author", entry.get("dc_creator", ""))

                items.append(NewsItem.new(
                    source=f"reddit/r/{sub}",
                    source_url=link,
                    title=title,
                    content=content,
                    author=author,
                    created_at=pub_date,
                ))
        return items
