# AI 日报 📡

> 自动聚合 AI 领域最新动态的本地新闻雷达 — 定时抓取、智能去重、突发预警、中文翻译、本地 Web 仪表盘一体化。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ 功能亮点

| 功能 | 说明 |
|------|------|
| 🌐 多源聚合 | Twitter/X、Hacker News、GitHub Trending、HuggingFace、Reddit、TechCrunch、The Verge、36氪、少数派等 |
| 🔥 突发预警 | 3 级实时预警（🔴紧急 / 🟠重要 / 🟡关注），自动检测模型发布、热门话题等 |
| 📰 今日日报 | 精选 Top-10，支持按推特 / GitHub / HuggingFace / 新闻 / 中文媒体分栏 |
| 🤖 AI 翻译 | 接入 DeepSeek / OpenAI / Ollama 等 LLM，自动翻译英文内容并生成中文摘要 |
| 🔔 桌面通知 | Windows 系统托盘后台运行，突发新闻弹窗提醒 |
| 💾 本地存储 | 全量数据保存到本地 SQLite，无隐私顾虑 |

---

## 📸 界面预览

```
侧边栏导航         主内容区
┌──────────────┐  ┌─────────────────────────────────┐
│ AI 日报       │  │ 今日精选 · 2026-04-19            │
│              │  │ 🔥精选 🐦推特 💻GitHub 🤗HF 📰新闻 │
│ 📰 今日日报   │  ├─────────────────────────────────┤
│ 🔥 突发新闻  │  │ 1. GPT-5 正式发布 · OpenAI       │
│ 📊 AI热点    │  │    "全新一代旗舰模型，推理能力..." │
│              │  │ 2. Qwen 3.6 开源...              │
│ 🐦 AI新闻推特 │  │    ★ 4.2k  ⏰ 2小时前           │
│ 💡 AI经验资源 │  └─────────────────────────────────┘
│ 📰 英文信息源 │  
│ 📰 中文信息源 │  突发新闻页
│              │  ┌─────────────────────────────────┐
│ ⭐ 我的收藏   │  │ 🔴 紧急                          │
│ ⚙️ 信息源管理 │  │   新模型发布: GPT-5 ...          │
└──────────────┘  │ 🟠 重要                          │
                  │   GitHub 2.8k★: transformers...  │
                  └─────────────────────────────────┘
```

---

## 🚀 快速开始

### 系统要求

- **操作系统**：Windows 10/11（系统托盘通知仅支持 Windows）
- **Python**：3.10 或以上
- **网络**：需要能访问 GitHub、HuggingFace、Nitter 等境外网站

### 1. 克隆并安装依赖

推荐使用虚拟环境，避免依赖冲突：

```bash
git clone https://github.com/koodfandan/ai-news-radar.git
cd ai-news-radar

# 创建并激活虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

```bash
copy config.example.yaml config.yaml   # Windows
# cp config.example.yaml config.yaml   # macOS/Linux
```

编辑 `config.yaml`，按需填入 LLM API（可选，不填则不翻译）：

```yaml
llm:
  api_base: "https://api.deepseek.com/v1"  # 支持 OpenAI 兼容接口
  api_key: "sk-your-key"
  model: "deepseek-chat"
```

> 支持的 LLM：DeepSeek、OpenAI、月之暗面 Kimi、阿里云通义、Ollama（本地）等任意 OpenAI 兼容接口。

### 3. 启动

```bash
python main.py
```

打开浏览器访问 **http://127.0.0.1:8080**

---

## 📡 信息源列表

| 平台 | 类型 | 说明 |
|------|------|------|
| Twitter/X (Nitter) | RSS | 跟踪 karpathy、Andrej、OpenAI 等 40+ AI 账号 |
| Hacker News | API | 热榜 Top 50，附评论数和分数 |
| GitHub Trending | 爬虫 | 每日/每周趋势仓库 |
| HuggingFace | 爬虫 | 热门模型 Top 20 |
| Reddit | JSON | r/MachineLearning、r/LocalLLM 等 |
| TechCrunch AI | RSS | AI 频道文章 |
| The Verge | RSS | AI 分类 |
| 36氪 | RSS | 中文科技资讯 |
| 少数派 | RSS | 中文产品评测 |
| 爱范儿 | RSS | 中文科技新闻 |
| 自定义 RSS | RSS | 可在设置页自由添加 |

---

## 🏗️ 项目结构

```
ai-news-radar/
├── main.py                 # 入口（启动 Web 服务器 + 调度器 + 托盘）
├── config.example.yaml     # 配置模板
├── requirements.txt        # 依赖
├── src/
│   ├── scheduler.py        # 轮询调度器
│   ├── database.py         # SQLite 数据库操作
│   ├── alert_detector.py   # 突发新闻检测（3 级分类）
│   ├── translator.py       # LLM 翻译模块
│   ├── models.py           # 数据模型
│   ├── dedup.py            # 内容去重
│   ├── fetchers/           # 各平台抓取器
│   │   ├── twitter.py      # Twitter/Nitter RSS
│   │   ├── hackernews.py   # HN Firebase API
│   │   ├── github.py       # GitHub Trending
│   │   ├── huggingface.py  # HuggingFace
│   │   ├── reddit.py       # Reddit JSON
│   │   └── rss.py          # 通用 RSS (TechCrunch, 36氪 等)
│   └── web/
│       ├── app.py          # FastAPI 路由
│       └── static/
│           ├── index.html  # 单页应用 HTML
│           ├── app.js      # 前端逻辑（~1000 行）
│           └── style.css   # 样式
└── tests/                  # 测试文件
```

---

## ⚙️ 配置说明

`config.yaml` 主要配置项：

```yaml
polling_interval_minutes: 15    # 轮询间隔（分钟）

llm:
  api_base: "..."               # LLM API 地址（OpenAI 兼容）
  api_key: "..."                # API Key
  model: "deepseek-chat"        # 模型名

web:
  host: "127.0.0.1"             # 绑定地址
  port: 8080                    # 端口

sources:
  twitter:
    enabled: true
    accounts:                   # 要跟踪的 Twitter 账号
      - karpathy
      - OpenAI
      # ...
```

---

## 📄 License

MIT © [koodfandan](https://github.com/koodfandan)

