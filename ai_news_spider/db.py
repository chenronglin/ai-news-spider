from __future__ import annotations

from contextlib import asynccontextmanager
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiosqlite

from ai_news_spider.runtime import canonicalize_url


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    async def connect(self) -> aiosqlite.Connection:
        connection = await aiosqlite.connect(self.db_path)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @asynccontextmanager
    async def session(self):
        connection = await self.connect()
        try:
            yield connection
        finally:
            await connection.close()

    async def init(self) -> None:
        async with self.session() as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS crawl_site (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    seed_url TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'draft',
                    approved_version_id INTEGER,
                    notes TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS crawler_version (
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

                CREATE TABLE IF NOT EXISTS crawl_run (
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

                CREATE TABLE IF NOT EXISTS article_item (
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

                CREATE TABLE IF NOT EXISTS regen_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id INTEGER NOT NULL,
                    version_id INTEGER NOT NULL,
                    run_id INTEGER,
                    feedback_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(site_id) REFERENCES crawl_site(id),
                    FOREIGN KEY(version_id) REFERENCES crawler_version(id),
                    FOREIGN KEY(run_id) REFERENCES crawl_run(id)
                );
                """
            )
            await db.commit()

    async def fetchone(
        self, db: aiosqlite.Connection, query: str, params: tuple = ()
    ) -> aiosqlite.Row | None:
        cursor = await db.execute(query, params)
        return await cursor.fetchone()

    async def fetchall(
        self, db: aiosqlite.Connection, query: str, params: tuple = ()
    ) -> list[aiosqlite.Row]:
        cursor = await db.execute(query, params)
        return await cursor.fetchall()

    async def upsert_site(
        self, seed_url: str, name: str | None, notes: str | None
    ) -> dict[str, Any]:
        domain = urlparse(seed_url).netloc
        now = utc_now()
        async with self.session() as db:
            row = await self.fetchone(
                db,
                "SELECT * FROM crawl_site WHERE seed_url = ?",
                (seed_url,),
            )
            if row is None:
                cursor = await db.execute(
                    """
                    INSERT INTO crawl_site (name, domain, seed_url, status, approved_version_id, notes, created_at)
                    VALUES (?, ?, ?, 'draft', NULL, ?, ?)
                    """,
                    (name or domain, domain, seed_url, notes, now),
                )
                await db.commit()
                site_id = cursor.lastrowid
            else:
                site_id = row["id"]
                await db.execute(
                    "UPDATE crawl_site SET name = ?, notes = ? WHERE id = ?",
                    (name or row["name"], notes, site_id),
                )
                await db.commit()
            return await self.get_site(site_id)

    async def get_site(self, site_id: int) -> dict[str, Any]:
        async with self.session() as db:
            row = await self.fetchone(
                db, "SELECT * FROM crawl_site WHERE id = ?", (site_id,)
            )
        return dict(row) if row else {}

    async def update_site_notes(self, site_id: int, notes: str | None) -> None:
        async with self.session() as db:
            await db.execute(
                "UPDATE crawl_site SET notes = ? WHERE id = ?",
                (notes, site_id),
            )
            await db.commit()

    async def get_version(self, version_id: int) -> dict[str, Any]:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                "SELECT * FROM crawler_version WHERE id = ?",
                (version_id,),
            )
        return dict(row) if row else {}

    async def get_run(self, run_id: int) -> dict[str, Any]:
        async with self.session() as db:
            row = await self.fetchone(
                db, "SELECT * FROM crawl_run WHERE id = ?", (run_id,)
            )
        return dict(row) if row else {}

    async def next_version_no(self, site_id: int) -> int:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                "SELECT COALESCE(MAX(version_no), 0) AS max_version FROM crawler_version WHERE site_id = ?",
                (site_id,),
            )
        return int(row["max_version"]) + 1

    async def create_version(
        self,
        site_id: int,
        *,
        feedback_text: str | None = None,
        spec_json: dict[str, Any] | None = None,
        script_code: str = "",
    ) -> dict[str, Any]:
        version_no = await self.next_version_no(site_id)
        now = utc_now()
        async with self.session() as db:
            cursor = await db.execute(
                """
                INSERT INTO crawler_version (site_id, version_no, status, spec_json, script_code, feedback_text, created_at)
                VALUES (?, ?, 'draft', ?, ?, ?, ?)
                """,
                (
                    site_id,
                    version_no,
                    json.dumps(spec_json or {}, ensure_ascii=False),
                    script_code,
                    feedback_text,
                    now,
                ),
            )
            await db.commit()
            version_id = cursor.lastrowid
        return await self.get_version(version_id)

    async def update_version_assets(
        self,
        version_id: int,
        *,
        spec_json: dict[str, Any],
        script_code: str,
    ) -> None:
        async with self.session() as db:
            await db.execute(
                "UPDATE crawler_version SET spec_json = ?, script_code = ? WHERE id = ?",
                (json.dumps(spec_json, ensure_ascii=False), script_code, version_id),
            )
            await db.commit()

    async def create_run(
        self, site_id: int, version_id: int, run_type: str
    ) -> dict[str, Any]:
        now = utc_now()
        async with self.session() as db:
            cursor = await db.execute(
                """
                INSERT INTO crawl_run (site_id, version_id, run_type, status, stats_json, result_json, error_log, started_at)
                VALUES (?, ?, ?, 'running', '{}', '{}', '', ?)
                """,
                (site_id, version_id, run_type, now),
            )
            await db.commit()
            run_id = cursor.lastrowid
        return await self.get_run(run_id)

    async def complete_run(
        self,
        run_id: int,
        *,
        status: str,
        stats_json: dict[str, Any],
        result_json: dict[str, Any],
        error_log: str = "",
    ) -> None:
        async with self.session() as db:
            await db.execute(
                """
                UPDATE crawl_run
                SET status = ?, stats_json = ?, result_json = ?, error_log = ?, finished_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(stats_json, ensure_ascii=False),
                    json.dumps(result_json, ensure_ascii=False),
                    error_log,
                    utc_now(),
                    run_id,
                ),
            )
            await db.commit()

    async def get_existing_canonical_urls(self, site_id: int) -> list[str]:
        async with self.session() as db:
            rows = await self.fetchall(
                db,
                "SELECT url_canonical FROM article_item WHERE site_id = ?",
                (site_id,),
            )
        return [row["url_canonical"] for row in rows]

    async def upsert_article_items(
        self,
        site_id: int,
        run_id: int,
        items: list[dict[str, Any]],
    ) -> tuple[int, int]:
        inserted = 0
        duplicated = 0
        now = utc_now()
        async with self.session() as db:
            for item in items:
                canonical = canonicalize_url(item["url"])
                existing = await self.fetchone(
                    db,
                    "SELECT id FROM article_item WHERE site_id = ? AND url_canonical = ?",
                    (site_id, canonical),
                )
                if existing is None:
                    inserted += 1
                    await db.execute(
                        """
                        INSERT INTO article_item
                        (site_id, title, url, url_canonical, published_at, source_list_url, first_seen_at, last_seen_at, run_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            site_id,
                            item["title"],
                            item["url"],
                            canonical,
                            item.get("published_at"),
                            item["source_list_url"],
                            now,
                            now,
                            run_id,
                        ),
                    )
                else:
                    duplicated += 1
                    await db.execute(
                        """
                        UPDATE article_item
                        SET title = ?, url = ?, published_at = ?, source_list_url = ?, last_seen_at = ?, run_id = ?
                        WHERE site_id = ? AND url_canonical = ?
                        """,
                        (
                            item["title"],
                            item["url"],
                            item.get("published_at"),
                            item["source_list_url"],
                            now,
                            run_id,
                            site_id,
                            canonical,
                        ),
                    )
            await db.commit()
        return inserted, duplicated

    async def record_feedback(
        self,
        site_id: int,
        version_id: int,
        run_id: int | None,
        feedback_text: str,
    ) -> None:
        async with self.session() as db:
            await db.execute(
                """
                INSERT INTO regen_feedback (site_id, version_id, run_id, feedback_text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (site_id, version_id, run_id, feedback_text, utc_now()),
            )
            await db.commit()

    async def latest_run_for_version(self, version_id: int) -> dict[str, Any] | None:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                """
                SELECT * FROM crawl_run
                WHERE version_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (version_id,),
            )
        return dict(row) if row else None

    async def approve_version(self, version_id: int) -> dict[str, Any]:
        version = await self.get_version(version_id)
        site_id = version["site_id"]
        async with self.session() as db:
            await db.execute(
                "UPDATE crawler_version SET status = 'rejected' WHERE site_id = ? AND status = 'approved'",
                (site_id,),
            )
            await db.execute(
                "UPDATE crawler_version SET status = 'approved' WHERE id = ?",
                (version_id,),
            )
            await db.execute(
                "UPDATE crawl_site SET approved_version_id = ?, status = 'active' WHERE id = ?",
                (version_id, site_id),
            )
            await db.commit()
        return await self.get_version(version_id)

    async def get_approved_version_for_site(
        self, site_id: int
    ) -> dict[str, Any] | None:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                """
                SELECT cv.*
                FROM crawler_version cv
                JOIN crawl_site cs ON cs.approved_version_id = cv.id
                WHERE cs.id = ?
                """,
                (site_id,),
            )
        return dict(row) if row else None

    async def get_run_detail(self, run_id: int) -> dict[str, Any]:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                """
                SELECT
                    cr.*,
                    cs.name AS site_name,
                    cs.seed_url AS seed_url,
                    cs.notes AS site_notes,
                    cv.version_no AS version_no,
                    cv.status AS version_status,
                    cv.spec_json AS spec_json
                FROM crawl_run cr
                JOIN crawl_site cs ON cs.id = cr.site_id
                JOIN crawler_version cv ON cv.id = cr.version_id
                WHERE cr.id = ?
                """,
                (run_id,),
            )
        detail = dict(row)
        detail["stats_json"] = json.loads(detail["stats_json"])
        detail["result_json"] = json.loads(detail["result_json"])
        detail["spec_json"] = json.loads(detail["spec_json"])
        return detail

    async def list_site_summaries(self) -> list[dict[str, Any]]:
        today = datetime.utcnow().date().isoformat()
        async with self.session() as db:
            rows = await self.fetchall(
                db,
                """
                SELECT
                    cs.*,
                    cv.version_no AS approved_version_no,
                    (
                        SELECT finished_at
                        FROM crawl_run cr
                        WHERE cr.site_id = cs.id
                        ORDER BY cr.id DESC
                        LIMIT 1
                    ) AS last_run_at,
                    (
                        SELECT error_log
                        FROM crawl_run cr
                        WHERE cr.site_id = cs.id AND cr.error_log <> ''
                        ORDER BY cr.id DESC
                        LIMIT 1
                    ) AS recent_error,
                    (
                        SELECT COUNT(*)
                        FROM article_item ai
                        WHERE ai.site_id = cs.id AND substr(ai.first_seen_at, 1, 10) = ?
                    ) AS today_new_count
                FROM crawl_site cs
                LEFT JOIN crawler_version cv ON cv.id = cs.approved_version_id
                ORDER BY cs.id DESC
                """,
                (today,),
            )
        return [dict(row) for row in rows]

    async def list_approved_sites(self) -> list[dict[str, Any]]:
        async with self.session() as db:
            rows = await self.fetchall(
                db,
                """
                SELECT cs.*, cv.id AS version_id
                FROM crawl_site cs
                JOIN crawler_version cv ON cv.id = cs.approved_version_id
                ORDER BY cs.id
                """,
            )
        return [dict(row) for row in rows]
