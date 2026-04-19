from src.fetchers.base import BaseFetcher
from src.models import NewsItem
from datetime import datetime, timezone
import httpx
import logging

logger = logging.getLogger(__name__)

MAX_PER_SUB = 20  # top-N per subreddit


class RedditFetcher(BaseFetcher):
    source_name = "reddit"

    def __init__(self, subreddits: list[str] | None = None, min_score: int = 50):
        self.subreddits = subreddits or ["MachineLearning", "artificial", "LocalLLaMA"]
        self.min_score = min_score

    async def _fetch_json(self, url: str) -> dict | None:
        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                headers={
                    "User-Agent": "AI-News-Radar/1.0",
                    "Accept": "application/json",
                }
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch {url}: {e}")
            return None

    async def fetch(self) -> list[NewsItem]:
        items = []
        for sub in self.subreddits:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=50"
            data = await self._fetch_json(url)
            if not data:
                continue

            try:
                posts = data["data"]["children"]
            except (KeyError, TypeError):
                logger.warning(f"[reddit] Unexpected response for r/{sub}")
                continue

            sub_items = []
            for post in posts:
                p = post.get("data", {})
                score = p.get("score", 0)
                if score < self.min_score:
                    continue
                title = p.get("title", "")[:300]
                url_post = p.get("url", "")
                permalink = "https://www.reddit.com" + p.get("permalink", "")
                author = p.get("author", "")
                created_utc = p.get("created_utc")
                selftext = p.get("selftext", "")[:500]
                content = selftext if selftext else title

                created_at = None
                if created_utc:
                    created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)

                sub_items.append(NewsItem.new(
                    source=f"reddit/r/{sub}",
                    source_url=url_post or permalink,
                    title=title,
                    content=content,
                    author=author,
                    score=score,
                    created_at=created_at,
                ))

            # sort by score, take top-N
            sub_items.sort(key=lambda x: x.score or 0, reverse=True)
            items.extend(sub_items[:MAX_PER_SUB])

        return items
