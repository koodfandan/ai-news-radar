import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.config import AppConfig
from src.database import Database
from src.dedup import Deduplicator
from src.translator import Translator
from src.notifier import Notifier
from src.fetchers.hackernews import HackerNewsFetcher
from src.fetchers.reddit import RedditFetcher
from src.fetchers.twitter import TwitterFetcher
from src.fetchers.github import GitHubTrendingFetcher
from src.fetchers.rss import RSSFetcher
from src.fetchers.huggingface import HuggingFaceFetcher
from src.fetchers.producthunt import ProductHuntFetcher
from src.alert_detector import detect_batch

logger = logging.getLogger(__name__)


class Radar:
    def __init__(self, config: AppConfig, db: Database):
        self.config = config
        self.db = db
        self.dedup = Deduplicator(db)
        self.translator = Translator(
            api_base=config.llm.api_base,
            api_key=config.llm.api_key,
            model=config.llm.model,
        )
        self.notifier = Notifier(
            enabled=config.notifications.enabled,
            quiet_start=config.notifications.quiet_hours.start,
            quiet_end=config.notifications.quiet_hours.end,
        )
        self.fetchers = self._build_fetchers()
        self.scheduler = AsyncIOScheduler()
        self.paused = False

    def _build_fetchers(self):
        fetchers = []
        s = self.config.sources

        if s.hackernews.enabled:
            fetchers.append(HackerNewsFetcher(s.hackernews.min_score, s.hackernews.keywords))
        if s.reddit.enabled:
            fetchers.append(RedditFetcher(s.reddit.subreddits, s.reddit.min_score))
        if s.twitter.enabled:
            fetchers.append(TwitterFetcher(s.twitter.accounts, nitter_instances=s.twitter.nitter_instances))
        if s.github.enabled:
            fetchers.append(GitHubTrendingFetcher(s.github.keywords))
        if s.rss.enabled and s.rss.feeds:
            feeds = [{"name": f.name, "url": f.url} for f in s.rss.feeds]
            fetchers.append(RSSFetcher(feeds))
        if s.huggingface.enabled:
            fetchers.append(HuggingFaceFetcher())
        if s.producthunt.enabled:
            fetchers.append(ProductHuntFetcher())

        if self.config.custom_rss:
            custom_feeds = [{"name": f.name, "url": f.url} for f in self.config.custom_rss]
            fetchers.append(RSSFetcher(custom_feeds))

        return fetchers

    async def poll_once(self):
        if self.paused:
            return

        logger.info("Starting polling cycle...")
        all_items = []

        for fetcher in self.fetchers:
            try:
                items = await fetcher.fetch()
                logger.info(f"[{fetcher.source_name}] fetched {len(items)} items")
                all_items.extend(items)
            except Exception as e:
                logger.error(f"[{fetcher.source_name}] fetch failed: {e}")

        new_items = await self.dedup.filter(all_items)
        logger.info(f"After dedup: {len(new_items)} new items (from {len(all_items)} total)")

        if not new_items:
            return

        if self.config.llm.api_key and self.config.llm.api_key != "your-api-key-here":
            try:
                await self.translator.translate_batch(new_items)
            except Exception as e:
                logger.error(f"Translation failed: {e}")

        for item in new_items:
            await self.db.insert(item)

        # 突发新闻检测
        breaking_items = detect_batch(new_items)
        for item, reason, category, level in breaking_items:
            item.is_breaking = True
            item.breaking_reason = f"[{category}] {reason}"
            item.breaking_level = level
            await self.db.mark_breaking(item.id, item.breaking_reason, level)

        # 通知：突发新闻单独发，其他普通批量发
        if breaking_items:
            self.notifier.notify_breaking([item for item, _, _ in breaking_items])
        non_breaking = [i for i in new_items if not getattr(i, 'is_breaking', False)]
        if non_breaking:
            self.notifier.notify_batch(non_breaking)

        logger.info(f"Polling cycle complete: {len(new_items)} new items ({len(breaking_items)} breaking)")

    def start(self):
        self.scheduler.add_job(
            self.poll_once,
            'interval',
            minutes=self.config.polling_interval_minutes,
            id='poll_all',
            max_instances=1,
        )
        self.scheduler.start()
        logger.info(f"Scheduler started, polling every {self.config.polling_interval_minutes} minutes")

    def stop(self):
        self.scheduler.shutdown()

    def toggle_pause(self):
        self.paused = not self.paused
        state = "paused" if self.paused else "resumed"
        logger.info(f"Radar {state}")
        return self.paused
