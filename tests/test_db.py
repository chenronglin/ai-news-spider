from __future__ import annotations

import aiosqlite
import pytest

from ai_news_spider.db import Database


@pytest.mark.asyncio
async def test_init_migrates_legacy_article_item_before_creating_indexes(settings) -> None:
    settings.ensure_directories()

    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(
            """
            CREATE TABLE crawl_site (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                seed_url TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'draft',
                approved_version_id INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE crawler_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                version_no INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                spec_json TEXT NOT NULL,
                script_code TEXT NOT NULL,
                feedback_text TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(site_id) REFERENCES crawl_site(id)
            );

            CREATE TABLE crawl_run (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                version_id INTEGER NOT NULL,
                run_type TEXT NOT NULL,
                status TEXT NOT NULL,
                stats_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                error_log TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                FOREIGN KEY(site_id) REFERENCES crawl_site(id),
                FOREIGN KEY(version_id) REFERENCES crawler_version(id)
            );

            CREATE TABLE article_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                url_canonical TEXT NOT NULL,
                published_at TEXT,
                source_list_url TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                run_id INTEGER NOT NULL,
                FOREIGN KEY(site_id) REFERENCES crawl_site(id),
                FOREIGN KEY(run_id) REFERENCES crawl_run(id),
                UNIQUE(site_id, url_canonical)
            );
            """
        )
        await db.commit()

    database = Database(settings.db_path)
    await database.init()

    async with database.session() as db:
        columns = await database.fetchall(db, "PRAGMA table_info(article_item)")
        indexes = await database.fetchall(db, "PRAGMA index_list(article_item)")

    column_names = {column["name"] for column in columns}
    index_names = {index["name"] for index in indexes}

    assert "detail_status" in column_names
    assert "detail_requested_at" in column_names
    assert "detail_fetched_at" in column_names
    assert "detail_error" in column_names
    assert "idx_article_item_detail_status" in index_names
    assert "idx_article_item_site_detail_status" in index_names
