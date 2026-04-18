from src.fetchers.base import BaseFetcher
from src.models import NewsItem
from bs4 import BeautifulSoup
import asyncio
import logging

logger = logging.getLogger(__name__)


class GitHubTrendingFetcher(BaseFetcher):
    source_name = "github"

    def __init__(self, keywords: list[str] | None = None):
        self.keywords = [k.lower() for k in (keywords or ["llm", "ai", "gpt"])]

    async def fetch(self) -> list[NewsItem]:
        html = None
        for attempt in range(3):
            html = await self._get_text("https://github.com/trending?since=daily")
            if html:
                break
            logger.warning(f"[github] Retry {attempt + 1}/3...")
            await asyncio.sleep(2 ** attempt)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        items = []

        for repo in soup.select("article.Box-row"):
            name_el = repo.select_one("h2 a")
            if not name_el:
                continue
            name = name_el.text.strip().replace("\n", "").replace(" ", "")
            desc_el = repo.select_one("p")
            desc = desc_el.text.strip() if desc_el else ""

            if not self._matches(name, desc):
                continue

            stars_el = repo.select_one("span.d-inline-block.float-sm-right")
            stars_text = stars_el.text.strip() if stars_el else "0"

            url = f"https://github.com{name_el['href']}"
            items.append(NewsItem.new(
                source=self.source_name,
                source_url=url,
                title=name,
                content=desc,
                author=name.split("/")[0] if "/" in name else "",
                score=self._parse_stars(stars_text),
            ))
        return items

    def _matches(self, name: str, desc: str) -> bool:
        text = f"{name} {desc}".lower()
        return any(kw in text for kw in self.keywords)

    def _parse_stars(self, text: str) -> int:
        text = text.replace(",", "").strip().split()[0]
        try:
            return int(text)
        except ValueError:
            return 0
