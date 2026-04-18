import pystray
from PIL import Image, ImageDraw, ImageFont
import webbrowser
import logging

logger = logging.getLogger(__name__)


def _create_icon_image():
    """Create a simple radar icon."""
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw concentric circles
    draw.ellipse([8, 8, 56, 56], outline='#e94560', width=2)
    draw.ellipse([18, 18, 46, 46], outline='#e94560', width=2)
    draw.ellipse([28, 28, 36, 36], fill='#e94560')
    return img


def create_tray(radar, dashboard_url: str):
    """Create and run system tray icon. Blocks the calling thread."""

    def on_open_dashboard(icon, item):
        webbrowser.open(dashboard_url)

    def on_refresh(icon, item):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(radar.poll_once(), loop)
            else:
                loop.run_until_complete(radar.poll_once())
        except Exception as e:
            logger.error(f"Manual refresh failed: {e}")

    def on_toggle_pause(icon, item):
        paused = radar.toggle_pause()
        icon.title = "AI Radar (已暂停)" if paused else "AI Radar"

    def on_quit(icon, item):
        radar.stop()
        icon.stop()

    icon = pystray.Icon(
        "ai-radar",
        _create_icon_image(),
        "AI Radar",
        menu=pystray.Menu(
            pystray.MenuItem("打开仪表盘", on_open_dashboard, default=True),
            pystray.MenuItem("立即刷新", on_refresh),
            pystray.MenuItem("暂停/恢复", on_toggle_pause),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", on_quit),
        )
    )
    icon.run()
