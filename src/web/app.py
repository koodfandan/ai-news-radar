import json
import sys
import uuid
import yaml
from datetime import date, datetime
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path
from src.database import Database


# 确定配置文件路径（打包后在 exe 目录，开发时在项目根目录）
if getattr(sys, 'frozen', False):
    _base_dir = Path(sys.executable).parent
else:
    _base_dir = Path(__file__).parent.parent.parent

SUBSCRIPTIONS_FILE = _base_dir / "data" / "subscriptions.json"
CONFIG_FILE = _base_dir / "config.yaml"


class SubscriptionCreate(BaseModel):
    type: str  # twitter, reddit, rss, github, huggingface, producthunt
    value: str  # username, subreddit, rss url, etc.
    label: str = ""  # display name


def _load_subscriptions() -> list[dict]:
    if SUBSCRIPTIONS_FILE.exists():
        return json.loads(SUBSCRIPTIONS_FILE.read_text(encoding="utf-8"))
    return []


def _save_subscriptions(subs: list[dict]):
    SUBSCRIPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUBSCRIPTIONS_FILE.write_text(json.dumps(subs, ensure_ascii=False, indent=2), encoding="utf-8")


def create_app(db: Database, config=None) -> FastAPI:
    app = FastAPI(title="AI Radar")

    static_dir = Path(__file__).parent / "static"

    # Build twitter account → category mapping
    _twitter_categories = {}
    if config and hasattr(config, 'sources') and hasattr(config.sources, 'twitter'):
        for cat, accounts in (config.sources.twitter.categories or {}).items():
            for acc in accounts:
                _twitter_categories[acc.lower()] = cat

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = static_dir / "index.html"
        return html_path.read_text(encoding="utf-8")

    @app.get("/api/news")
    async def get_news(
        source: str | None = Query(None),
        q: str | None = Query(None),
        limit: int = Query(50, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        if q:
            items = await db.search(q, limit=limit)
        else:
            items = await db.get_recent(limit=limit, offset=offset, source=source)
        return {
            "items": [
                {
                    "id": i.id,
                    "source": i.source,
                    "source_url": i.source_url,
                    "title": i.title,
                    "title_zh": i.title_zh,
                    "content": i.content[:300],
                    "summary_zh": i.summary_zh,
                    "author": i.author,
                    "score": i.score,
                    "created_at": i.created_at.isoformat(),
                    "fetched_at": i.fetched_at.isoformat(),
                    "is_read": i.is_read,
                    "is_starred": i.is_starred,
                    "is_breaking": getattr(i, 'is_breaking', False),
                    "breaking_reason": getattr(i, 'breaking_reason', ''),
                    "breaking_level": getattr(i, 'breaking_level', 0),
                    "twitter_category": _twitter_categories.get(
                        i.source.split("/@")[-1].lower(), ""
                    ) if i.source.startswith("twitter/") else "",
                }
                for i in items
            ]
        }

    @app.post("/api/news/{item_id}/read")
    async def mark_read(item_id: str):
        await db.mark_read(item_id)
        return {"ok": True}

    @app.post("/api/news/{item_id}/star")
    async def toggle_star(item_id: str):
        await db.toggle_star(item_id)
        return {"ok": True}

    @app.get("/api/stats")
    async def stats():
        unread = await db.get_unread_count()
        sources = await db.get_sources()
        return {"unread_count": unread, "sources": sources}

    @app.get("/api/daily")
    async def daily_report(date_str: str = Query(None, alias="date")):
        target_date = date.today()
        if date_str:
            try:
                target_date = date.fromisoformat(date_str)
            except ValueError:
                pass

        items = await db.get_recent(limit=200, offset=0, source=None)

        # Filter by date
        day_items = []
        for i in items:
            item_date = i.created_at.date() if isinstance(i.created_at, datetime) else i.created_at
            if item_date == target_date:
                day_items.append(i)

        def serialize(item):
            return {
                "id": item.id,
                "source": item.source,
                "source_url": item.source_url,
                "title": item.title,
                "title_zh": item.title_zh,
                "content": item.content[:300] if item.content else "",
                "summary_zh": item.summary_zh,
                "author": item.author,
                "score": item.score,
                "created_at": item.created_at.isoformat(),
                "fetched_at": item.fetched_at.isoformat(),
                "is_read": item.is_read,
                "is_starred": item.is_starred,
                "is_breaking": getattr(item, 'is_breaking', False),
                "breaking_reason": getattr(item, 'breaking_reason', ''),
            }

        # Categorize
        categories = {
            "headlines": [],
            "twitter": [],
            "github": [],
            "news": [],
            "huggingface": [],
            "reddit": [],
            "producthunt": [],
        }

        for item in day_items:
            src = (item.source or "").lower()
            if src.startswith("twitter"):
                categories["twitter"].append(item)
            elif src == "github":
                categories["github"].append(item)
            elif src in ("rss", "techcrunch", "theverge"):
                categories["news"].append(item)
            elif src == "huggingface":
                categories["huggingface"].append(item)
            elif src.startswith("reddit"):
                categories["reddit"].append(item)
            elif src == "producthunt":
                categories["producthunt"].append(item)
            else:
                categories["news"].append(item)

        # Headlines: top 5 by score
        all_sorted = sorted(day_items, key=lambda x: (x.score or 0, x.created_at), reverse=True)
        categories["headlines"] = all_sorted[:5]

        return {
            "date": target_date.isoformat(),
            "total": len(day_items),
            "categories": {k: [serialize(i) for i in v] for k, v in categories.items()},
        }

    @app.get("/api/subscriptions")
    async def get_subscriptions():
        return {"items": _load_subscriptions()}

    @app.get("/api/breaking")
    async def get_breaking(limit: int = Query(20, ge=1, le=50)):
        items = await db.get_breaking(limit=limit)
        return {
            "items": [
                {
                    "id": i.id,
                    "source": i.source,
                    "source_url": i.source_url,
                    "title": i.title,
                    "title_zh": i.title_zh,
                    "content": (i.content or "")[:300],
                    "summary_zh": i.summary_zh,
                    "author": i.author,
                    "score": i.score,
                    "created_at": i.created_at.isoformat(),
                    "fetched_at": i.fetched_at.isoformat(),
                    "is_breaking": True,
                    "breaking_reason": getattr(i, 'breaking_reason', ''),
                    "breaking_level": getattr(i, 'breaking_level', 0),
                    "twitter_category": _twitter_categories.get(
                        i.source.split("/@")[-1].lower(), ""
                    ) if i.source.startswith("twitter/") else "",
                }
                for i in items
            ]
        }

    @app.get("/api/twitter-categories")
    async def get_twitter_categories():
        return {"categories": _twitter_categories}

    @app.post("/api/subscriptions")
    async def add_subscription(sub: SubscriptionCreate):
        subs = _load_subscriptions()
        new_sub = {
            "id": str(uuid.uuid4())[:8],
            "type": sub.type,
            "value": sub.value,
            "label": sub.label or sub.value,
            "created_at": datetime.now().isoformat(),
        }
        subs.append(new_sub)
        _save_subscriptions(subs)
        return {"ok": True, "item": new_sub}

    @app.delete("/api/subscriptions/{sub_id}")
    async def delete_subscription(sub_id: str):
        subs = _load_subscriptions()
        subs = [s for s in subs if s.get("id") != sub_id]
        _save_subscriptions(subs)
        return {"ok": True}

    # ---- LLM Settings ----
    class LlmSettings(BaseModel):
        api_base: str = ""
        api_key: str = ""
        model: str = ""

    @app.get("/api/settings/llm")
    async def get_llm_settings():
        try:
            cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
            llm = cfg.get("llm", {})
            key = llm.get("api_key", "")
            # Mask API key for security
            masked = key[:6] + "..." + key[-4:] if len(key) > 10 else ("***" if key and key != "your-api-key-here" else "")
            return {"api_base": llm.get("api_base", ""), "api_key_masked": masked, "model": llm.get("model", ""), "configured": bool(key and key != "your-api-key-here")}
        except Exception:
            return {"api_base": "", "api_key_masked": "", "model": "", "configured": False}

    @app.post("/api/settings/llm")
    async def save_llm_settings(settings: LlmSettings):
        try:
            cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
            if "llm" not in cfg:
                cfg["llm"] = {}
            if settings.api_base:
                cfg["llm"]["api_base"] = settings.api_base
            if settings.api_key:
                cfg["llm"]["api_key"] = settings.api_key
            if settings.model:
                cfg["llm"]["model"] = settings.model
            CONFIG_FILE.write_text(yaml.dump(cfg, allow_unicode=True, default_flow_style=False), encoding="utf-8")
            return {"ok": True, "message": "保存成功，重启后生效"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    @app.post("/api/settings/llm/test")
    async def test_llm_connection():
        import httpx
        try:
            cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
            llm = cfg.get("llm", {})
            api_base = llm.get("api_base", "").rstrip("/")
            api_key = llm.get("api_key", "")
            model = llm.get("model", "")
            if not api_key or api_key == "your-api-key-here":
                return {"ok": False, "message": f"请先配置 API Key（配置文件路径: {CONFIG_FILE}）"}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": [{"role": "user", "content": "Say hi"}], "max_tokens": 10},
                )
                if resp.status_code == 401:
                    return {"ok": False, "message": "API Key 无效（401 未授权）"}
                elif resp.status_code == 404:
                    return {"ok": False, "message": f"接口地址错误（404），请检查 API Base: {api_base}"}
                elif resp.status_code >= 400:
                    return {"ok": False, "message": f"请求失败 HTTP {resp.status_code}: {resp.text[:200]}"}
                resp.raise_for_status()
                return {"ok": True, "message": "连接成功！翻译功能将在下次轮询时自动运行"}
        except httpx.ConnectError as e:
            return {"ok": False, "message": f"无法连接到服务器，请检查 API Base 地址是否正确: {str(e)[:150]}"}
        except httpx.TimeoutException:
            return {"ok": False, "message": "连接超时（15秒），请检查网络或 API 地址"}
        except Exception as e:
            return {"ok": False, "message": f"连接失败: {str(e)[:200]}"}

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app
