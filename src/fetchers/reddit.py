from src.fetchers.base import BaseFetcher
from src.models import NewsItem
from datetime import datetime, timezone
import feedparser
import logging

logger = logging.getLogger(__name__)

MAX_PER_SUB = 25


class RedditFetcher(BaseFetcher):
    source_name = "reddit"

    def __init__(self, subreddits: list[str] | None = None, min_score: int = 50):
        self.subreddits = subreddits or ["MachineLearning", "artificial", "LocalLLaMA"]
        self.min_score = min_score

    async def fetch(self) -> list[NewsItem]:
        items = []
        for sub in self.subreddits:
            url = f"https://old.reddit.com/r/{sub}/.rss"
            text = await self._get_text(url)
            if not text:
                continue

            parsed = feedparser.parse(text)
            if not parsed.entries:
                logger.warning(f"[reddit] Unexpected response for r/{sub}")
                continue

            sub_items = []
            for entry in parsed.entries[:MAX_PER_SUB]:
                title = entry.get("title", "")[:300]
                author = (entry.get("author", "") or "").replace("/u/", "")
                content = entry.get("summary", entry.get("description", ""))[:500]

                created_at = None
                parsed_time = getattr(entry, "updated_parsed", None) or getattr(entry, "published_parsed", None)
                if parsed_time:
                    created_at = datetime(*parsed_time[:6], tzinfo=timezone.utc)

                sub_items.append(NewsItem.new(
                    source=f"reddit/r/{sub}",
                    source_url=entry.get("link", ""),
                    title=title,
                    content=content,
                    author=author,
                    score=0,
                    created_at=created_at,
                ))

            sub_items.sort(key=lambda x: x.created_at, reverse=True)
            items.extend(sub_items)

        return items
