from src.fetchers.base import BaseFetcher
from src.models import NewsItem
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

MAX_PER_POLL = 20


class GitHubTrendingFetcher(BaseFetcher):
    source_name = "github"
    SEARCH_API = "https://api.github.com/search/repositories"

    def __init__(self, keywords: list[str] | None = None):
        self.keywords = keywords or ["llm", "ai", "gpt", "machine-learning"]

    async def fetch(self) -> list[NewsItem]:
        # Search repos created/pushed in the last 3 days with AI keywords, sorted by stars
        since = (datetime.now(tz=timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
        query = " OR ".join(self.keywords) + f" pushed:>{since}"
        params = {"q": query, "sort": "stars", "order": "desc", "per_page": MAX_PER_POLL}
        data = await self._get_json(self.SEARCH_API, params=params,
                                     headers={"Accept": "application/vnd.github+json",
                                              "X-GitHub-Api-Version": "2022-11-28"})
        if not data or "items" not in data:
            logger.warning("[github] Search API returned no data, falling back to trending page")
            return await self._fetch_trending_fallback()

        items = []
        for repo in data["items"]:
            pushed = repo.get("pushed_at") or repo.get("created_at")
            created_at = None
            if pushed:
                try:
                    created_at = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
                except ValueError:
                    pass
            items.append(NewsItem.new(
                source=self.source_name,
                source_url=repo.get("html_url", ""),
                title=repo.get("full_name", ""),
                content=repo.get("description", "") or "",
                author=repo.get("owner", {}).get("login", ""),
                score=repo.get("stargazers_count", 0),
                created_at=created_at,
            ))
        return items

    async def _fetch_trending_fallback(self) -> list[NewsItem]:
        """Fallback: scrape GitHub trending page if Search API fails."""
        from bs4 import BeautifulSoup
        import asyncio
        html = None
        for attempt in range(2):
            html = await self._get_text("https://github.com/trending?since=daily")
            if html:
                break
            await asyncio.sleep(2 ** attempt)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        items = []
        for repo in soup.select("article.Box-row")[:MAX_PER_POLL]:
            name_el = repo.select_one("h2 a")
            if not name_el:
                continue
            name = name_el.text.strip().replace("\n", "").replace(" ", "")
            desc_el = repo.select_one("p")
            desc = desc_el.text.strip() if desc_el else ""
            url = f"https://github.com{name_el['href']}"
            stars_el = repo.select_one("span.d-inline-block.float-sm-right")
            stars_text = stars_el.text.strip() if stars_el else "0"
            items.append(NewsItem.new(
                source=self.source_name,
                source_url=url,
                title=name,
                content=desc,
                author=name.split("/")[0] if "/" in name else "",
                score=self._parse_stars(stars_text),
            ))
        return items

    def _parse_stars(self, text: str) -> int:
        text = text.replace(",", "").strip().split()[0]
        try:
            return int(text)
        except ValueError:
            return 0
