from dataclasses import dataclass, field
from typing import Optional
import dataclasses
import yaml


@dataclass
class LLMConfig:
    api_base: str = ""
    api_key: str = ""
    model: str = ""


@dataclass
class QuietHours:
    start: str = "23:00"
    end: str = "07:00"


@dataclass
class NotificationConfig:
    enabled: bool = True
    quiet_hours: QuietHours = field(default_factory=QuietHours)


@dataclass
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8080


@dataclass
class TwitterConfig:
    enabled: bool = True
    nitter_instances: list[str] = field(default_factory=lambda: ["https://nitter.net", "https://xcancel.com"])
    accounts: list[str] = field(default_factory=list)
    categories: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class HackerNewsConfig:
    enabled: bool = True
    min_score: int = 50
    keywords: list[str] = field(default_factory=lambda: ["AI", "LLM", "GPT"])


@dataclass
class RedditConfig:
    enabled: bool = True
    subreddits: list[str] = field(default_factory=lambda: ["MachineLearning", "artificial", "LocalLLaMA"])
    min_score: int = 100


@dataclass
class GitHubConfig:
    enabled: bool = True
    languages: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=lambda: ["llm", "ai"])


@dataclass
class RSSFeed:
    name: str = ""
    url: str = ""


@dataclass
class RSSConfig:
    enabled: bool = True
    feeds: list[RSSFeed] = field(default_factory=list)


@dataclass
class ProductHuntConfig:
    enabled: bool = True


@dataclass
class HuggingFaceConfig:
    enabled: bool = True


@dataclass
class SourcesConfig:
    twitter: TwitterConfig = field(default_factory=TwitterConfig)
    hackernews: HackerNewsConfig = field(default_factory=HackerNewsConfig)
    reddit: RedditConfig = field(default_factory=RedditConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    rss: RSSConfig = field(default_factory=RSSConfig)
    producthunt: ProductHuntConfig = field(default_factory=ProductHuntConfig)
    huggingface: HuggingFaceConfig = field(default_factory=HuggingFaceConfig)


@dataclass
class AppConfig:
    polling_interval_minutes: int = 15
    llm: LLMConfig = field(default_factory=LLMConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    web: WebConfig = field(default_factory=WebConfig)
    sources: SourcesConfig = field(default_factory=SourcesConfig)
    custom_rss: list[RSSFeed] = field(default_factory=list)


def _build_dataclass(cls, data: dict):
    """Recursively build dataclass from dict."""
    if data is None:
        return cls()
    fields = {f.name: f for f in dataclasses.fields(cls)}
    kwargs = {}
    for k, v in data.items():
        if k in fields:
            ft = fields[k].type
            if dataclasses.is_dataclass(ft):
                kwargs[k] = _build_dataclass(ft, v)
            elif hasattr(ft, '__origin__') and ft.__origin__ is list:
                args = ft.__args__
                if dataclasses.is_dataclass(args[0]) and isinstance(v, list):
                    kwargs[k] = [_build_dataclass(args[0], item) if isinstance(item, dict) else item for item in v]
                else:
                    kwargs[k] = v
            else:
                kwargs[k] = v
    return cls(**kwargs)


def load_config(path: str) -> AppConfig:
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return _build_dataclass(AppConfig, data)
