# AI Radar 📡

AI 热点信息监控工具 — 自动抓取、翻译、推送 AI 领域最新动态。

## 功能

- 🔍 监控 7+ 信息源（Twitter、Hacker News、Reddit、GitHub Trending 等）
- 🌐 LLM 自动翻译英文内容为中文 + 一句话摘要
- 🔔 Windows 桌面弹窗通知
- 📊 本地 Web 仪表盘浏览历史信息
- 🖥️ 系统托盘后台运行
- ⚡ 定时轮询，自动去重

## 安装

```bash
cd ai-radar
pip install -r requirements.txt
```

## 配置

1. 复制配置模板：
```bash
copy config.example.yaml config.yaml
```

2. 编辑 `config.yaml`，填入你的 LLM API 信息：
```yaml
llm:
  api_base: "https://api.deepseek.com/v1"  # 或 OpenAI、Ollama 等兼容接口
  api_key: "your-api-key"
  model: "deepseek-chat"
```

3. 可选：调整信息源、轮询间隔、关注的 Twitter 账号等。

## 运行

```bash
python main.py
```

启动后：
- 系统托盘出现 AI Radar 图标
- 自动打开浏览器访问仪表盘
- 每隔 15 分钟自动轮询新消息
- 有新消息时弹出 Windows 桌面通知

## 仪表盘

默认地址：http://127.0.0.1:8080

- 按信息源过滤
- 搜索关键词
- 标记已读/收藏
- 自动刷新

## 信息源

| 平台 | 采集方式 |
|------|---------|
| Twitter/X | Nitter RSS |
| Hacker News | Firebase API |
| Reddit | JSON API |
| GitHub Trending | HTML 解析 |
| TechCrunch | RSS |
| The Verge | RSS |
| Product Hunt | RSS |
| Hugging Face | HTML 解析 |
| 自定义 | RSS |

## 系统托盘菜单

- **打开仪表盘** — 在浏览器中打开
- **立即刷新** — 手动触发一次轮询
- **暂停/恢复** — 暂停或恢复自动轮询
- **退出** — 停止程序
