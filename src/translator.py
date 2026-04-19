import asyncio
import httpx
import json
import logging

logger = logging.getLogger(__name__)


class Translator:
    def __init__(self, api_base: str, api_key: str, model: str):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def _call_llm(self, messages: list[dict]) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": messages, "temperature": 0.3},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    async def translate(self, title: str, content: str) -> tuple[str, str]:
        prompt = f"""将以下英文 AI 新闻翻译成中文，并生成一句话摘要。
返回 JSON 格式：{{"title_zh": "中文标题", "summary_zh": "一句话中文摘要"}}
只返回 JSON，不要其他内容。

标题: {title}
内容: {content[:1000]}"""

        messages = [{"role": "user", "content": prompt}]
        result = await self._call_llm(messages)
        if not result:
            return title, content[:200]

        try:
            text = result["choices"][0]["message"]["content"]
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = json.loads(text)
            return parsed.get("title_zh", title), parsed.get("summary_zh", content[:200])
        except (json.JSONDecodeError, KeyError, IndexError):
            logger.warning("Failed to parse LLM response, using original")
            return title, content[:200]

    async def translate_batch(self, items: list) -> list:
        """Translate a batch of NewsItems concurrently (max 5 parallel LLM calls)."""
        sem = asyncio.Semaphore(5)

        async def _translate_one(item):
            if item.title_zh:
                return
            async with sem:
                title_zh, summary_zh = await self.translate(item.title, item.content)
            item.title_zh = title_zh
            item.summary_zh = summary_zh

        await asyncio.gather(*[_translate_one(item) for item in items])
        return items
