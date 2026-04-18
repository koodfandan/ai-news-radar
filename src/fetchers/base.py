from abc import ABC, abstractmethod
from src.models import NewsItem
import httpx
import logging

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    source_name: str = "unknown"

    async def _get_json(self, url: str, **kwargs) -> dict | list | None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, **kwargs)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch {url}: {e}")
            return None

    async def _get_text(self, url: str, **kwargs) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, **kwargs)
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch {url}: {e}")
            return None

    @abstractmethod
    async def fetch(self) -> list[NewsItem]:
        ...
