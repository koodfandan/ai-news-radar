from src.fetchers.base import BaseFetcher
from src.models import NewsItem
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class HuggingFaceFetcher(BaseFetcher):
    source_name = "huggingface"

    async def fetch(self) -> list[NewsItem]:
        html = await self._get_text("https://huggingface.co/models?sort=trending")
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        items = []

        for card in soup.select("article")[:20]:
            link = card.select_one("a[href*='/']")
            if not link:
                continue
            href = link.get("href", "")
            if not href or href.startswith("http"):
                continue

            name = href.strip("/")
            desc_el = card.select_one("p")
            desc = desc_el.text.strip() if desc_el else ""

            items.append(NewsItem.new(
                source=self.source_name,
                source_url=f"https://huggingface.co{href}",
                title=name,
                content=desc,
                author=name.split("/")[0] if "/" in name else "",
            ))

        return items
