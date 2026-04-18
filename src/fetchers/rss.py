from src.fetchers.base import BaseFetcher
from src.models import NewsItem
from datetime import datetime, timezone
import feedparser
from time import mktime


class RSSFetcher(BaseFetcher):
    source_name = "rss"

    def __init__(self, feeds: list[dict]):
        """feeds: [{"name": "TechCrunch AI", "url": "https://..."}]"""
        self.feeds = feeds

    async def fetch(self) -> list[NewsItem]:
        items = []
        for feed_info in self.feeds:
            text = await self._get_text(feed_info["url"])
            if not text:
                continue
            parsed = feedparser.parse(text)
            for entry in parsed.entries[:20]:
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)

                items.append(NewsItem.new(
                    source=feed_info["name"],
                    source_url=entry.get("link", ""),
                    title=entry.get("title", ""),
                    content=entry.get("summary", "")[:500],
                    author=entry.get("author", ""),
                    created_at=pub_date,
                ))
        return items
