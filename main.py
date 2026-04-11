from __future__ import annotations

import logging
import uvicorn

from ai_news_spider.app import build_app
from ai_news_spider.config import Settings


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> None:
    settings = Settings.from_env()
    setup_logging(settings.log_level)
    app = build_app(settings=settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
