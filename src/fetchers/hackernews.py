from src.fetchers.base import BaseFetcher
from src.models import NewsItem
from datetime import datetime, timezone
import asyncio

MAX_PER_POLL = 25  # top-N by score


class HackerNewsFetcher(BaseFetcher):
    source_name = "hackernews"
    BASE = "https://hacker-news.firebaseio.com/v0"

    def __init__(self, min_score: int = 50, keywords: list[str] | None = None):
        self.min_score = min_score
        self.keywords = [k.lower() for k in (keywords or ["AI", "LLM", "GPT"])]

    async def fetch(self) -> list[NewsItem]:
        ids = await self._get_json(f"{self.BASE}/topstories.json")
        if not ids:
            return []

        sem = asyncio.Semaphore(10)

        async def fetch_one(story_id):
            async with sem:
                data = await self._get_json(f"{self.BASE}/item/{story_id}.json")
            if not data or data.get("type") not in ("story",):
                return None
            score = data.get("score", 0)
            if score < self.min_score:
                return None
            title = data.get("title", "")
            # Pass if matches keywords OR is high-engagement Ask HN / Show HN
            comments = data.get("descendants", 0)
            is_ask_show = title.startswith(("Ask HN:", "Show HN:"))
            if not self._matches_keywords(title) and not (is_ask_show and comments >= 20):
                return None
            url = data.get("url", f"https://news.ycombinator.com/item?id={story_id}")
            return NewsItem.new(
                source=self.source_name,
                source_url=url,
                title=title,
                content=title,
                author=data.get("by", ""),
                score=score,
                created_at=datetime.fromtimestamp(data.get("time", 0), tz=timezone.utc),
            )

        results = await asyncio.gather(*[fetch_one(sid) for sid in ids[:100]], return_exceptions=True)
        items = [r for r in results if r is not None and not isinstance(r, Exception)]
        # Sort by score, take top-N
        items.sort(key=lambda x: x.score or 0, reverse=True)
        return items[:MAX_PER_POLL]

    def _matches_keywords(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.keywords)
