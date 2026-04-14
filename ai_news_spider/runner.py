from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from ai_news_spider.config import Settings
from ai_news_spider.models import SiteSpec

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunnerExecution:
    result: dict[str, Any]
    script_code: str
    stderr: str = ""


class CandidateRunner:
    def __init__(self, settings: Settings) -> None:
        template_dir = settings.base_dir / "ai_news_spider" / "script_templates"
        self.settings = settings
        self.template_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=False,
        )

    def render_script(self, spec: SiteSpec) -> str:
        template = self.template_env.get_template("candidate_runner.py.j2")
        return template.render(spec_json=spec.model_dump_json(indent=2))

    def _resolve_python_executable(self) -> str:
        override = os.getenv("AI_NEWS_SPIDER_PYTHON_BIN", "").strip()
        candidate_paths = [
            Path(override) if override else None,
            Path(sys.executable) if sys.executable else None,
            self.settings.base_dir / ".venv" / "bin" / "python",
            self.settings.base_dir / ".venv" / "Scripts" / "python.exe",
        ]

        for candidate in candidate_paths:
            if candidate and candidate.exists():
                return str(candidate)

        for command in ("python3", "python"):
            resolved = shutil.which(command)
            if resolved:
                return resolved

        raise RuntimeError(
            "未找到可用的 Python 解释器。请通过 AI_NEWS_SPIDER_PYTHON_BIN 指定路径，"
            "或确保当前进程运行在可用的 Python/venv 中。"
        )

    async def run(
        self,
        spec: SiteSpec,
        payload: dict[str, Any],
    ) -> RunnerExecution:
        script_code = self.render_script(spec)
        script_path = self.settings.runtime_dir / f"candidate_{uuid.uuid4().hex}.py"
        script_path.write_text(script_code)
        try:
            logger.info(
                "Executing candidate runner script=%s run_type=%s max_pages=%s",
                script_path,
                payload.get("run_type"),
                payload.get("max_pages"),
            )
            python_executable = self._resolve_python_executable()
            env = os.environ.copy()
            env["PYTHONPATH"] = (
                str(self.settings.base_dir)
                if not env.get("PYTHONPATH")
                else f"{self.settings.base_dir}{os.pathsep}{env['PYTHONPATH']}"
            )
            completed = subprocess.run(
                [python_executable, str(script_path)],
                cwd=self.settings.base_dir,
                env=env,
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                logger.error(
                    "Candidate runner failed code=%s stderr=%s",
                    completed.returncode,
                    completed.stderr[:4000],
                )
                raise RuntimeError(
                    completed.stderr.strip() or "candidate runner failed"
                )
            try:
                parsed_result = json.loads(completed.stdout)
            except json.JSONDecodeError:
                logger.error(
                    "Candidate runner stdout is not valid JSON stdout=%s stderr=%s",
                    completed.stdout[:4000],
                    completed.stderr[:4000],
                )
                raise
            logger.info(
                "Candidate runner succeeded stdout_len=%s stderr_len=%s",
                len(completed.stdout),
                len(completed.stderr),
            )
            if completed.stderr.strip():
                logger.info("Candidate runner stderr=%s", completed.stderr[:4000])
            return RunnerExecution(
                result=parsed_result,
                script_code=script_code,
                stderr=completed.stderr.strip(),
            )
        finally:
            if script_path.exists():
                script_path.unlink()
