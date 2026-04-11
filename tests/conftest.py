from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_news_spider.config import Settings
from tests.helpers import FIXTURE_URL_1, FIXTURE_URL_2, FIXTURE_URL_3


@pytest.fixture
def fixture_map(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    page1 = """
    <html><head><title>示例站点</title></head><body>
      <div class="main_conRCb">
        <ul>
          <li><span>2026-04-10</span><a href="../info/1001.htm"><em>第一条新闻</em></a></li>
          <li><span>2026-04-09</span><a href="../info/1002.htm"><em>第二条新闻</em></a></li>
        </ul>
      </div>
      <div id="fanye270287">
        <a class="Next" href="list/1.htm">下页</a>
      </div>
    </body></html>
    """
    page2 = """
    <html><body>
      <div class="main_conRCb">
        <ul>
          <li><span>2026-04-08</span><a href="../info/1003.htm"><em>第三条新闻</em></a></li>
          <li><span>2026-04-07</span><a href="../info/1004.htm"><em>第四条新闻</em></a></li>
        </ul>
      </div>
      <div id="fanye270287">
        <a class="Next" href="../list/2.htm">下页</a>
      </div>
    </body></html>
    """
    page3 = """
    <html><body>
      <div class="main_conRCb">
        <ul>
          <li><span>2026-04-06</span><a href="../info/1004.htm"><em>第四条新闻</em></a></li>
          <li><span>2026-04-05</span><a href="../info/1005.htm"><em>第五条新闻</em></a></li>
        </ul>
      </div>
    </body></html>
    """
    mapping = {
        FIXTURE_URL_1: page1,
        FIXTURE_URL_2: page2,
        FIXTURE_URL_3: page3,
    }
    map_path = tmp_path / "fixture_map.json"
    map_path.write_text(json.dumps(mapping))
    monkeypatch.setenv("AI_NEWS_SPIDER_FIXTURE_MAP", str(map_path))
    return mapping


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime"
    return Settings(
        base_dir=Path(__file__).resolve().parent.parent,
        data_dir=data_dir,
        runtime_dir=runtime_dir,
        db_path=data_dir / "app.db",
        host="127.0.0.1",
        port=8000,
        timezone="Asia/Shanghai",
        scheduler_mode="daily",
        scheduler_hour=9,
        scheduler_minute=0,
        scheduler_interval_hours=1,
        log_level="INFO",
        base_url="https://yunwu.ai/v1",
        api_key="test-key",
        model_name="gpt-5-mini",
    )
