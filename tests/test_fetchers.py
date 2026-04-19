import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from src.fetchers.reddit import RedditFetcher
from src.fetchers.rss import RSSFetcher
from src.fetchers.twitter import TwitterFetcher, _instance_health


class FetcherBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _instance_health.clear()

    async def test_reddit_fetcher_uses_old_reddit_rss_feed(self):
        feed = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'>
  <entry>
    <title>Fresh local model update</title>
    <link href='https://old.reddit.com/r/MachineLearning/comments/abc123/test/' />
    <author><name>/u/tester</name></author>
    <updated>2026-04-19T06:00:00+00:00</updated>
    <content type='html'>Useful summary</content>
  </entry>
</feed>
"""
        fetcher = RedditFetcher(["MachineLearning"])
        fetcher._get_text = AsyncMock(return_value=feed)

        items = await fetcher.fetch()

        fetcher._get_text.assert_awaited_once_with("https://old.reddit.com/r/MachineLearning/.rss")
        self.assertEqual(1, len(items))
        self.assertEqual("reddit/r/MachineLearning", items[0].source)
        self.assertEqual("Fresh local model update", items[0].title)

    async def test_rss_fetcher_filters_entries_older_than_48_hours(self):
        now = datetime.now(timezone.utc)
        fresh = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
        stale = (now - timedelta(days=4)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        feed = f"""<?xml version='1.0' encoding='UTF-8'?>
<rss version='2.0'>
  <channel>
    <item>
      <title>Fresh item</title>
      <link>https://example.com/fresh</link>
      <pubDate>{fresh}</pubDate>
      <description>fresh</description>
    </item>
    <item>
      <title>Old item</title>
      <link>https://example.com/old</link>
      <pubDate>{stale}</pubDate>
      <description>old</description>
    </item>
  </channel>
</rss>
"""
        fetcher = RSSFetcher([{"name": "Example", "url": "https://example.com/feed.xml"}])
        fetcher._get_text = AsyncMock(return_value=feed)

        items = await fetcher.fetch()

        self.assertEqual(["Fresh item"], [item.title for item in items])

    async def test_twitter_probe_requires_rss_content(self):
        fetcher = TwitterFetcher(["OpenAI"], nitter_instances=["https://bad.instance"])

        response = AsyncMock()
        response.status_code = 200
        response.text = "<html>login required</html>"

        client = AsyncMock()
        client.get.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None

        with patch("src.fetchers.twitter.httpx.AsyncClient", return_value=client):
            ok = await fetcher._probe_instance("https://bad.instance")

        self.assertFalse(ok)

    async def test_twitter_probe_rejects_whitelist_placeholder_feed(self):
        fetcher = TwitterFetcher(["OpenAI"], nitter_instances=["https://placeholder.instance"])

        response = AsyncMock()
        response.status_code = 200
        response.text = "<?xml version='1.0'?><rss><channel><title>RSS reader not yet whitelisted!</title></channel></rss>"

        client = AsyncMock()
        client.get.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None

        with patch("src.fetchers.twitter.httpx.AsyncClient", return_value=client):
            ok = await fetcher._probe_instance("https://placeholder.instance")

        self.assertFalse(ok)

    async def test_twitter_probe_rejects_whitelist_placeholder_item(self):
        fetcher = TwitterFetcher(["OpenAI"], nitter_instances=["https://placeholder.instance"])

        response = AsyncMock()
        response.status_code = 200
        response.text = "<?xml version='1.0'?><rss><channel><item><title>RSS reader not yet whitelisted!</title></item></channel></rss>"

        client = AsyncMock()
        client.get.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None

        with patch("src.fetchers.twitter.httpx.AsyncClient", return_value=client):
            ok = await fetcher._probe_instance("https://placeholder.instance")

        self.assertFalse(ok)

    async def test_twitter_skips_account_after_repeated_failures(self):
        fetcher = TwitterFetcher(["OpenAI"], nitter_instances=["https://xcancel.com"])
        fetcher._fetch_rss = AsyncMock(return_value=None)

        for _ in range(5):
            items = await fetcher._fetch_account("OpenAI", ["https://xcancel.com"])
            self.assertEqual([], items)

        attempts_before_skip = fetcher._fetch_rss.await_count
        items = await fetcher._fetch_account("OpenAI", ["https://xcancel.com"])

        self.assertEqual([], items)
        self.assertEqual(attempts_before_skip, fetcher._fetch_rss.await_count)


if __name__ == "__main__":
    unittest.main()