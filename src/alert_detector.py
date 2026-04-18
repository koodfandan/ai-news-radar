"""突发AI新闻检测引擎"""
import re
import logging
from datetime import datetime, timedelta
from src.models import NewsItem

logger = logging.getLogger(__name__)

# 大模型公司名单（中英文）
COMPANY_KEYWORDS = [
    # 海外
    "openai", "chatgpt", "gpt-5", "gpt5", "o3", "o4",
    "anthropic", "claude",
    "google", "gemini", "deepmind",
    "meta ai", "llama",
    "xai", "grok",
    "mistral",
    "stability ai", "stable diffusion",
    "cohere",
    # 国内
    "百度", "文心", "ernie",
    "阿里", "通义", "qwen",
    "字节", "豆包", "doubao",
    "腾讯", "混元", "hunyuan",
    "智谱", "chatglm", "glm",
    "月之暗面", "kimi", "moonshot",
    "minimax",
    "百川", "baichuan",
    "零一万物", "yi-",
    "deepseek", "深度求索",
    "阶跃星辰", "step-",
    "讯飞", "星火", "spark",
]

# 发布/重大事件关键词
RELEASE_KEYWORDS = [
    # 英文
    "release", "released", "releasing",
    "launch", "launched", "launching",
    "announce", "announced", "announcing",
    "introducing", "introduces",
    "open source", "open-source", "opensource",
    "new model", "new version",
    "available now", "now available",
    # 中文
    "发布", "推出", "上线", "开源", "重磅",
    "正式发布", "全面开放", "公测", "内测",
    "新模型", "新版本", "升级",
]

# GitHub star 暴涨阈值
STAR_SURGE_THRESHOLD = 1000

# AI 相关关键词（用于过滤非AI内容）
AI_RELEVANCE_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "gemini", "llama", "model", "neural",
    "transformer", "diffusion", "embedding", "token", "inference", "training",
    "fine-tune", "finetune", "rlhf", "rag", "agent", "chatbot", "generative",
    "machine learning", "deep learning", "大模型", "人工智能", "机器学习",
    "tts", "text-to-speech", "speech", "vision", "multimodal",
    "api", "sdk", "benchmark", "reasoning", "coding", "code generation",
    *[kw for kw in COMPANY_KEYWORDS],  # company names count as AI-relevant
]


# 重点关注的推特账号
VIP_TWITTER_ACCOUNTS = [
    "openai", "anthropicai", "googledeepmind", "aiatmeta", "mistralai",
    "sama", "elonmusk", "amodei", "gregbrockman",
    "karpathy", "ylecun", "drjimfan", "_akhaliq",
]


# 新模型关键词（用于分类，不要太宽泛）
MODEL_KEYWORDS = [
    "model", "模型", "gpt-5", "gpt5", "o3", "o4", "claude", "gemini", "llama",
    "qwen", "deepseek", "kimi", "glm", "yi-", "mixtral", "phi-",
    "3.5", "4.0", "4.5", "5.0", "opus", "sonnet", "haiku",
    "checkpoint", "weights", "parameters", "billion param",
]

# 新功能/产品关键词
FEATURE_KEYWORDS = [
    "feature", "功能", "product", "产品", "api", "sdk", "tool", "agent",
    "plugin", "app", "service", "platform", "tts", "voice", "image",
    "video", "search", "code", "forge", "copilot", "assistant",
]


def classify_breaking(text: str, item_source: str, item_score: int) -> str:
    """分类突发新闻: new_model, new_feature, github_hot, major_news"""
    text_lower = text.lower()
    
    if item_source.lower() == "github":
        return "github_hot"
    
    # 检测是否是新模型
    if any(kw in text_lower for kw in MODEL_KEYWORDS):
        return "new_model"
    
    # 检测是否是新功能/产品
    if any(kw in text_lower for kw in FEATURE_KEYWORDS):
        return "new_feature"
    
    return "major_news"


def detect_breaking(item: NewsItem) -> tuple[bool, str, str, int]:
    """检测一条新闻是否为突发新闻。
    
    Returns:
        (is_breaking, reason, category, level) - 是否突发、原因、分类、等级(1=关注 2=重要 3=紧急)
    """
    # 跳过发布时间超过48小时的旧内容（临时放宽用于测试）
    from datetime import datetime, timezone, timedelta
    if item.created_at:
        try:
            created = datetime.fromisoformat(item.created_at.replace('Z', '+00:00'))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - created > timedelta(hours=48):
                return False, "", "", 0
        except (ValueError, TypeError):
            pass

    text = f"{item.title} {item.content or ''} {item.title_zh or ''} {item.summary_zh or ''}".lower()
    
    # 规则0: VIP 推特账号发的包含发布关键词的推文（且内容与AI相关）
    if item.source.lower().startswith("twitter"):
        account = item.source.split("/")[-1].lower() if "/" in item.source else ""
        if account.lstrip("@") in VIP_TWITTER_ACCOUNTS:
            has_release = any(release_kw.lower() in text for release_kw in RELEASE_KEYWORDS)
            has_ai = any(ai_kw.lower() in text for ai_kw in AI_RELEVANCE_KEYWORDS)
            if has_release and has_ai:
                cat = classify_breaking(text, item.source, item.score)
                reason = f"VIP推特: @{account}"
                # 官方账号发布新模型=紧急，其他=重要
                level = 3 if cat == 'new_model' and account in ('openai','anthropicai','googledeepmind','aiatmeta','mistralai') else 2
                logger.info(f"🔥 突发检测命中: {reason} [{cat}] L{level} | {item.title[:60]}")
                return True, reason, cat, level
    
    # 规则1: 大公司 + 发布关键词
    matched_company = None
    for company in COMPANY_KEYWORDS:
        if company.lower() in text:
            matched_company = company
            break
    
    if matched_company:
        for release_kw in RELEASE_KEYWORDS:
            if release_kw.lower() in text:
                cat = classify_breaking(text, item.source, item.score)
                reason = f"大公司动态: {matched_company} + {release_kw}"
                # 新模型发布=紧急，新功能=重要，其他=关注
                level = 3 if cat == 'new_model' else (2 if cat == 'new_feature' else 1)
                logger.info(f"🔥 突发检测命中: {reason} [{cat}] L{level} | {item.title[:60]}")
                return True, reason, cat, level
    
    # 规则2: GitHub star 暴涨
    if item.source.lower() == "github" and item.score >= STAR_SURGE_THRESHOLD:
        reason = f"GitHub 热门: {item.score} stars today"
        level = 2 if item.score >= 2000 else 1
        logger.info(f"🔥 突发检测命中: {reason} L{level} | {item.title[:60]}")
        return True, reason, "github_hot", level
    
    # 规则3: 极高分数的新闻（HackerNews 500+）
    if item.source.lower() == "hackernews" and item.score >= 500:
        ai_keywords = ["ai", "llm", "gpt", "claude", "model", "neural", "transformer",
                       "机器学习", "人工智能", "大模型"]
        if any(kw in text for kw in ai_keywords):
            cat = classify_breaking(text, item.source, item.score)
            reason = f"HackerNews 热门: {item.score} points"
            level = 2 if item.score >= 1000 else 1
            logger.info(f"🔥 突发检测命中: {reason} L{level} | {item.title[:60]}")
            return True, reason, cat, level
    
    return False, "", "", 0


def detect_batch(items: list[NewsItem]) -> list[tuple[NewsItem, str, str, int]]:
    """批量检测突发新闻，返回 [(item, reason, category, level), ...]"""
    breaking = []
    for item in items:
        is_breaking, reason, category, level = detect_breaking(item)
        if is_breaking:
            breaking.append((item, reason, category, level))
    return breaking
