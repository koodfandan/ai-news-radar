import asyncio
import logging
import sys
import threading
from pathlib import Path

# 隐藏控制台窗口（Windows）
if sys.platform == 'win32' and getattr(sys, 'frozen', False):
    import ctypes
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE

from src.config import load_config
from src.database import Database
from src.scheduler import Radar
from src.web.app import create_app
from src.tray import create_tray

# 确定基础目录（PyInstaller frozen 时用 sys.executable 父目录）
if getattr(sys, 'frozen', False):
    _base_dir = Path(sys.executable).parent
else:
    _base_dir = Path(__file__).parent

import os as _os
_os.chdir(_base_dir)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        *([] if sys.stderr is None else [logging.StreamHandler()]),
        logging.FileHandler(str(_base_dir / "ai-radar.log"), encoding="utf-8"),
    ]
)
logger = logging.getLogger("ai-radar")


def run_backend(url: str):
    """在子线程中运行 asyncio 后端服务"""
    asyncio.run(main())


def launch_qt_window(url: str):
    """在主线程中启动 pywebview 桌面窗口（使用系统 WebView2，启动更快）"""
    try:
        import webview
        import threading
        import urllib.request
        import time

        # 先创建窗口（显示加载页面），后端就绪后再跳转
        _loading_html = """
        <html><head><meta charset="utf-8">
        <style>
        body { margin:0; background:#0a0e1a; display:flex; align-items:center; justify-content:center; height:100vh; flex-direction:column; font-family:sans-serif; }
        .spinner { width:48px; height:48px; border:4px solid #1e2a3a; border-top:4px solid #e94560; border-radius:50%; animation:spin 0.8s linear infinite; }
        @keyframes spin { to { transform:rotate(360deg); } }
        p { color:#8892a4; margin-top:16px; font-size:14px; }
        </style></head>
        <body><div class="spinner"></div><p>正在启动 AI 日报...</p></body></html>
        """

        window = webview.create_window(
            "AI 日报",
            html=_loading_html,
            width=1280,
            height=860,
            resizable=True,
        )

        def _wait_and_load():
            # 等待后端就绪，然后跳转
            for _ in range(60):
                try:
                    urllib.request.urlopen(url, timeout=1)
                    window.load_url(url)
                    return
                except Exception:
                    time.sleep(0.5)
            # 超时也尝试加载
            window.load_url(url)

        _t = threading.Thread(target=_wait_and_load, daemon=True)
        _t.start()

        webview.start()
    except Exception as e:
        logger.warning(f"pywebview 窗口失败，请手动打开浏览器: {e}")


async def main():
    import os
    # PyInstaller 打包后 sys.executable 指向 exe，未打包时用 __file__
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent
    os.chdir(base_dir)
    config_path = Path("config.yaml")
    if not config_path.exists():
        logger.error("config.yaml not found! Copy config.example.yaml to config.yaml and edit it.")
        sys.exit(1)

    config = load_config(str(config_path))
    db = Database("ai-radar.db")
    await db.init()

    radar = Radar(config, db)

    # Start web server first so UI is available immediately
    app = create_app(db, config)
    url = f"http://{config.web.host}:{config.web.port}"

    # Run initial poll in background, then start scheduler
    async def background_poll():
        logger.info("Running initial poll...")
        await radar.poll_once()
        radar.start()

    asyncio.create_task(background_poll())
    import uvicorn
    web_config = uvicorn.Config(
        app,
        host=config.web.host,
        port=config.web.port,
        log_level="warning",
        log_config=None,  # 禁用uvicorn内部日志配置（windowed模式兼容）
    )
    server = uvicorn.Server(web_config)

    # Start tray in separate thread
    tray_thread = threading.Thread(
        target=create_tray,
        args=(radar, url),
        daemon=True,
    )
    tray_thread.start()

    logger.info(f"AI Radar running! Dashboard: {url}")

    await server.serve()


if __name__ == "__main__":
    import os
    # PyInstaller 打包后 sys.executable 指向 exe，未打包时用 __file__
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent
    os.chdir(base_dir)

    # 先确定 URL
    try:
        from src.config import load_config as _lc
        _cfg = _lc("config.yaml")
        _url = f"http://{_cfg.web.host}:{_cfg.web.port}"
    except Exception:
        _url = "http://127.0.0.1:8080"

    # 后端在子线程中运行
    def run_backend_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(main())
        except Exception as e:
            logger.error(f"Backend thread error: {e}", exc_info=True)
        finally:
            loop.close()

    backend_thread = threading.Thread(target=run_backend_thread, daemon=True)
    backend_thread.start()

    # PyQt6 必须在主线程
    launch_qt_window(_url)

