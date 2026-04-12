from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal
from pathlib import Path

from dotenv import load_dotenv


SchedulerMode = Literal["daily", "hourly"]


@dataclass(slots=True)
class Settings:
    base_dir: Path
    data_dir: Path
    runtime_dir: Path
    db_path: Path
    host: str
    port: int
    timezone: str
    scheduler_mode: SchedulerMode
    scheduler_hour: int
    scheduler_minute: int
    scheduler_interval_hours: int
    log_level: str
    base_url: str | None
    api_key: str | None
    api_token: str | None
    model_name: str

    @classmethod
    def from_env(cls, base_dir: Path | None = None) -> "Settings":
        root = (base_dir or Path(__file__).resolve().parent.parent).resolve()
        load_dotenv(root / ".env", override=False)
        data_dir = root / "data"
        runtime_dir = data_dir / "runtime"
        return cls(
            base_dir=root,
            data_dir=data_dir,
            runtime_dir=runtime_dir,
            db_path=data_dir / "app.db",
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "8000")),
            timezone=os.getenv("TIMEZONE", "Asia/Shanghai"),
            scheduler_mode=cls.normalize_scheduler_mode(
                os.getenv("SCHEDULER_MODE", "daily")
            ),
            scheduler_hour=int(os.getenv("SCHEDULER_HOUR", "9")),
            scheduler_minute=int(os.getenv("SCHEDULER_MINUTE", "0")),
            scheduler_interval_hours=max(
                1, int(os.getenv("SCHEDULER_INTERVAL_HOURS", "1"))
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            base_url=cls.normalize_base_url(os.getenv("BASE_URL")),
            api_key=os.getenv("API_KEY"),
            api_token=os.getenv("API_TOKEN"),
            model_name=os.getenv("MODEL_NAME", "gpt-5-mini"),
        )

    @staticmethod
    def normalize_base_url(base_url: str | None) -> str | None:
        if not base_url:
            return None
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1"):
            return normalized
        return f"{normalized}/v1"

    @staticmethod
    def normalize_scheduler_mode(mode: str) -> SchedulerMode:
        normalized = mode.strip().lower()
        if normalized not in {"daily", "hourly"}:
            return "daily"
        return normalized  # type: ignore[return-value]

    def scheduler_description(self) -> str:
        if self.scheduler_mode == "hourly":
            unit = "小时" if self.scheduler_interval_hours == 1 else "小时"
            return f"每 {self.scheduler_interval_hours} {unit}执行一次，分钟={self.scheduler_minute:02d}"
        return f"每天 {self.scheduler_hour:02d}:{self.scheduler_minute:02d} 执行一次"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
