from plyer import notification
from src.models import NewsItem
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, enabled: bool = True, quiet_start: str = "23:00", quiet_end: str = "07:00"):
        self.enabled = enabled
        self.quiet_start = quiet_start
        self.quiet_end = quiet_end

    def _is_quiet_time(self) -> bool:
        now = datetime.now().strftime("%H:%M")
        if self.quiet_start <= self.quiet_end:
            return self.quiet_start <= now <= self.quiet_end
        else:
            return now >= self.quiet_start or now <= self.quiet_end

    def notify(self, item: NewsItem):
        if not self.enabled or self._is_quiet_time():
            return
        try:
            title = item.title_zh or item.title
            message = item.summary_zh or item.content[:100]
            notification.notify(
                title=f"[{item.source}] {title[:60]}",
                message=message[:200],
                app_name="AI Radar",
                timeout=10,
            )
        except Exception as e:
            logger.error(f"Notification failed: {e}")

    def notify_batch(self, items: list[NewsItem]):
        if len(items) == 0:
            return
        if len(items) <= 3:
            for item in items:
                self.notify(item)
        else:
            try:
                notification.notify(
                    title=f"AI Radar: {len(items)} 条新消息",
                    message="\n".join(f"• {(i.title_zh or i.title)[:40]}" for i in items[:5]),
                    app_name="AI Radar",
                    timeout=10,
                )
            except Exception as e:
                logger.error(f"Batch notification failed: {e}")

    def notify_breaking(self, items: list[NewsItem]):
        """突发新闻专用通知，每条单独发送，带🔥标记"""
        if not self.enabled or self._is_quiet_time():
            return
        for item in items[:5]:  # 每小时最多5条
            try:
                title = item.title_zh or item.title
                message = item.summary_zh or (item.content or "")[:200]
                reason = getattr(item, 'breaking_reason', '')
                notification.notify(
                    title=f"🔥 突发 [{item.source}] {title[:50]}",
                    message=f"{reason}\n{message[:150]}",
                    app_name="AI Radar 突发",
                    timeout=15,
                )
            except Exception as e:
                logger.error(f"Breaking notification failed: {e}")
