from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ai_news_spider.config import Settings
from ai_news_spider.db import Database

logger = logging.getLogger(__name__)


class CrawlScheduler:
    def __init__(self, settings: Settings, db: Database, run_prod_batch) -> None:
        self.settings = settings
        self.db = db
        self.run_prod_batch = run_prod_batch
        self.scheduler = AsyncIOScheduler(timezone=settings.timezone)
        self.job_id = "approved-sites-batch"

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def refresh_jobs(self) -> None:
        for job in list(self.scheduler.get_jobs()):
            self.scheduler.remove_job(job.id)
        self.scheduler.add_job(
            self.run_prod_batch,
            trigger=self._build_trigger(),
            id=self.job_id,
            replace_existing=True,
        )
        logger.info(
            "Registered scheduler batch job mode=%s description=%s",
            self.settings.scheduler_mode,
            self.settings.scheduler_description(),
        )

    def get_info(self) -> dict[str, object]:
        job = self.scheduler.get_job(self.job_id)
        next_run_time = None
        if job and job.next_run_time is not None:
            next_run_time = job.next_run_time.isoformat()
        return {
            "enabled": True,
            "running": self.scheduler.running,
            "job_id": self.job_id,
            "next_run_time": next_run_time,
            "description": self.settings.scheduler_description(),
            "mode": self.settings.scheduler_mode,
        }

    def _build_trigger(self) -> CronTrigger:
        if self.settings.scheduler_mode == "hourly":
            return CronTrigger(
                hour=f"*/{self.settings.scheduler_interval_hours}",
                minute=self.settings.scheduler_minute,
            )
        return CronTrigger(
            hour=self.settings.scheduler_hour,
            minute=self.settings.scheduler_minute,
        )
