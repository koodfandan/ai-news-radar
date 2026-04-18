import sqlite3, asyncio
from src.database import Database

async def test():
    db = await Database.create()
    # Query latest 5 items
    items = await db.get_recent(limit=5)
    if items:
        first = items[0]
        print(f"Marking as breaking: {first.title[:60]}")
        await db.mark_breaking(first.id, "[test] Test breaking news", 3)
        
        # Now query breaking news
        breaking = await db.get_breaking(limit=10)
        print(f"Breaking news count: {len(breaking)}")
        if breaking:
            b = breaking[0]
            print(f"Title: {b.title[:60]}")
            print(f"Reason: {b.breaking_reason}")
            print(f"Level: {b.breaking_level}")
    await db.close()

asyncio.run(test())
