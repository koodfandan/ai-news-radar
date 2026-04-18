from src.fetchers.rss import RSSFetcher
from src.models import NewsItem


class ProductHuntFetcher(RSSFetcher):
    source_name = "producthunt"

    def __init__(self, keywords: list[str] | None = None):
        super().__init__(feeds=[{
            "name": "Product Hunt",
            "url": "https://www.producthunt.com/feed",
        }])
        self.keywords = [k.lower() for k in keywords] if keywords else None

    async def fetch(self) -> list[NewsItem]:
        items = await super().fetch()
        if not self.keywords:
            return items
        return [i for i in items if self._matches(i)]

    def _matches(self, item: NewsItem) -> bool:
        text = f"{item.title} {item.content or ''}".lower()
        return any(kw in text for kw in self.keywords)
