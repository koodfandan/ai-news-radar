from src.models import NewsItem
from src.database import Database


class Deduplicator:
    def __init__(self, db: Database):
        self.db = db

    async def filter(self, items: list[NewsItem]) -> list[NewsItem]:
        new_items = []
        seen_urls = set()
        for item in items:
            if item.source_url in seen_urls:
                continue
            if await self.db.url_exists(item.source_url):
                continue
            if await self.db.hash_exists(item.content_hash):
                continue
            seen_urls.add(item.source_url)
            new_items.append(item)
        return new_items
