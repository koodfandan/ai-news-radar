from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import uuid


@dataclass
class NewsItem:
    id: str
    source: str
    source_url: str
    title: str
    content: str
    title_zh: str
    summary_zh: str
    author: str
    score: int
    created_at: datetime
    fetched_at: datetime
    is_read: bool = False
    is_starred: bool = False
    content_hash: str = ""
    is_breaking: bool = False
    breaking_reason: str = ""
    breaking_level: int = 0  # 0=none, 1=关注, 2=重要, 3=紧急

    def __post_init__(self):
        if not self.content_hash:
            text = f"{self.title}{self.content}{self.source_url}"
            self.content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

    @staticmethod
    def new(source: str, source_url: str, title: str, content: str,
            author: str = "", score: int = 0,
            created_at: datetime | None = None) -> "NewsItem":
        now = datetime.now(timezone.utc)
        return NewsItem(
            id=str(uuid.uuid4()),
            source=source,
            source_url=source_url,
            title=title,
            content=content,
            title_zh="",
            summary_zh="",
            author=author,
            score=score,
            created_at=created_at or now,
            fetched_at=now,
        )
