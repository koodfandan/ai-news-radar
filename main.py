import asyncio
import logging
import sys
import threading
from pathlib import Path

from src.config import load_config
from src.database import Database
from src.scheduler import Radar
from src.web.app import create_app
from src.tray import create_tray

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ai-radar.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("ai-radar")


async def main():
    import os
    os.chdir(Path(__file__).parent)
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

    # Run initial poll in background, then start scheduler
    async def background_poll():
        logger.info("Running initial poll...")
        await radar.poll_once()
        radar.start()

    asyncio.create_task(background_poll())
    import uvicorn
    web_config = uvicorn.Config(app, host=config.web.host, port=config.web.port, log_level="warning")
    server = uvicorn.Server(web_config)

    # Start tray in separate thread
    tray_thread = threading.Thread(
        target=create_tray,
        args=(radar, f"http://{config.web.host}:{config.web.port}"),
        daemon=True,
    )
    tray_thread.start()

    logger.info(f"AI Radar running! Dashboard: http://{config.web.host}:{config.web.port}")

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
