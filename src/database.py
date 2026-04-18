import aiosqlite
from src.models import NewsItem
from datetime import datetime, timezone, timedelta


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def init(self):
        self.conn = await aiosqlite.connect(self.path)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_url TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                title_zh TEXT DEFAULT '',
                summary_zh TEXT DEFAULT '',
                author TEXT DEFAULT '',
                score INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                is_starred INTEGER DEFAULT 0,
                content_hash TEXT NOT NULL,
                is_breaking INTEGER DEFAULT 0,
                breaking_reason TEXT DEFAULT ''
            )
        """)
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_source_url ON news(source_url)")
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON news(content_hash)")
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_fetched_at ON news(fetched_at)")

        # alerts 表：记录已发送的通知，避免重复
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                news_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                notified_at TEXT NOT NULL,
                FOREIGN KEY (news_id) REFERENCES news(id)
            )
        """)

        # 兼容旧数据库：给 news 表添加新列（如果不存在）
        try:
            await self.conn.execute("ALTER TABLE news ADD COLUMN is_breaking INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            await self.conn.execute("ALTER TABLE news ADD COLUMN breaking_reason TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            await self.conn.execute("ALTER TABLE news ADD COLUMN breaking_level INTEGER DEFAULT 0")
        except Exception:
            pass

        # is_breaking 索引需要在列存在后创建
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_is_breaking ON news(is_breaking)")

        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def insert(self, item: NewsItem):
        await self.conn.execute(
            """INSERT OR IGNORE INTO news (
                id, source, source_url, title, content,
                title_zh, summary_zh, author, score,
                created_at, fetched_at, is_read, is_starred,
                content_hash, is_breaking, breaking_reason
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (item.id, item.source, item.source_url, item.title, item.content,
             item.title_zh, item.summary_zh, item.author, item.score,
             item.created_at.isoformat(), item.fetched_at.isoformat(),
             int(item.is_read), int(item.is_starred), item.content_hash,
             int(getattr(item, 'is_breaking', False)),
             getattr(item, 'breaking_reason', ''))
        )
        await self.conn.commit()

    async def url_exists(self, url: str) -> bool:
        cur = await self.conn.execute("SELECT 1 FROM news WHERE source_url=?", (url,))
        return await cur.fetchone() is not None

    async def hash_exists(self, content_hash: str) -> bool:
        cur = await self.conn.execute("SELECT 1 FROM news WHERE content_hash=?", (content_hash,))
        return await cur.fetchone() is not None

    async def get_recent(self, limit: int = 50, offset: int = 0, source: str | None = None) -> list[NewsItem]:
        q = "SELECT * FROM news"
        params: list = []
        if source:
            q += " WHERE source=?"
            params.append(source)
        q += " ORDER BY fetched_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cur = await self.conn.execute(q, params)
        rows = await cur.fetchall()
        return [self._row_to_item(r) for r in rows]

    async def get_by_id(self, item_id: str) -> NewsItem | None:
        cur = await self.conn.execute("SELECT * FROM news WHERE id=?", (item_id,))
        row = await cur.fetchone()
        return self._row_to_item(row) if row else None

    async def mark_read(self, item_id: str):
        await self.conn.execute("UPDATE news SET is_read=1 WHERE id=?", (item_id,))
        await self.conn.commit()

    async def toggle_star(self, item_id: str):
        await self.conn.execute("UPDATE news SET is_starred = 1 - is_starred WHERE id=?", (item_id,))
        await self.conn.commit()

    async def search(self, query: str, limit: int = 50) -> list[NewsItem]:
        safe_query = f"%{query}%"
        cur = await self.conn.execute(
            "SELECT * FROM news WHERE title LIKE ? OR content LIKE ? OR title_zh LIKE ? OR summary_zh LIKE ? ORDER BY fetched_at DESC LIMIT ?",
            (safe_query, safe_query, safe_query, safe_query, limit)
        )
        rows = await cur.fetchall()
        return [self._row_to_item(r) for r in rows]

    async def get_unread_count(self) -> int:
        cur = await self.conn.execute("SELECT COUNT(*) FROM news WHERE is_read=0")
        row = await cur.fetchone()
        return row[0]

    async def get_sources(self) -> list[str]:
        cur = await self.conn.execute("SELECT DISTINCT source FROM news ORDER BY source")
        rows = await cur.fetchall()
        return [r[0] for r in rows]

    def _row_to_item(self, row) -> NewsItem:
        item = NewsItem(
            id=row[0], source=row[1], source_url=row[2],
            title=row[3], content=row[4], title_zh=row[5],
            summary_zh=row[6], author=row[7], score=row[8],
            created_at=datetime.fromisoformat(row[9]),
            fetched_at=datetime.fromisoformat(row[10]),
            is_read=bool(row[11]), is_starred=bool(row[12]),
            content_hash=row[13],
        )
        # 新字段（兼容旧数据）
        if len(row) > 14:
            item.is_breaking = bool(row[14])
            item.breaking_reason = row[15] or ''
        if len(row) > 16:
            item.breaking_level = row[16] or 0
        return item

    async def mark_breaking(self, item_id: str, reason: str, level: int = 1):
        await self.conn.execute(
            "UPDATE news SET is_breaking=1, breaking_reason=?, breaking_level=? WHERE id=?",
            (reason, level, item_id)
        )
        await self.conn.commit()

    async def get_breaking(self, limit: int = 20, hours: int = 24) -> list[NewsItem]:
        cur = await self.conn.execute(
            "SELECT * FROM news WHERE is_breaking=1 AND created_at >= datetime('now', ? || ' hours') ORDER BY created_at DESC LIMIT ?",
            (f"-{hours}", limit,)
        )
        rows = await cur.fetchall()
        return [self._row_to_item(r) for r in rows]

    async def alert_exists(self, news_id: str) -> bool:
        cur = await self.conn.execute("SELECT 1 FROM alerts WHERE news_id=?", (news_id,))
        return await cur.fetchone() is not None

    async def insert_alert(self, news_id: str, reason: str):
        import uuid
        await self.conn.execute(
            "INSERT OR IGNORE INTO alerts VALUES (?,?,?,?)",
            (str(uuid.uuid4()), news_id, reason, datetime.now(timezone.utc).isoformat())
        )
        await self.conn.commit()

    async def get_alert_count_last_hour(self) -> int:
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE notified_at > ?", (one_hour_ago,)
        )
        row = await cur.fetchone()
        return row[0]
