from __future__ import annotations

from contextlib import asynccontextmanager
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiosqlite

from ai_news_spider.runtime import canonicalize_url


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
                    detail_status TEXT NOT NULL DEFAULT 'none',
                    detail_requested_at TEXT,
                    detail_fetched_at TEXT,
                    detail_error TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(site_id) REFERENCES crawl_site(id),
                    FOREIGN KEY(run_id) REFERENCES crawl_run(id),
                    UNIQUE(site_id, url_canonical)
                );

                CREATE TABLE IF NOT EXISTS article_detail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_item_id INTEGER NOT NULL UNIQUE,
                    site_id INTEGER NOT NULL,
                    source_url TEXT NOT NULL,
                    final_url TEXT NOT NULL,
                    content_html TEXT NOT NULL,
                    content_markdown TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(article_item_id) REFERENCES article_item(id),
                    FOREIGN KEY(site_id) REFERENCES crawl_site(id)
                );

                CREATE INDEX IF NOT EXISTS idx_article_item_site_id
                ON article_item(site_id);

                CREATE INDEX IF NOT EXISTS idx_article_item_published_at
                ON article_item(published_at);

                CREATE INDEX IF NOT EXISTS idx_article_item_run_id
                ON article_item(run_id);

                CREATE INDEX IF NOT EXISTS idx_article_item_first_seen_at
                ON article_item(first_seen_at);

                CREATE UNIQUE INDEX IF NOT EXISTS idx_article_detail_article_item_id
                ON article_detail(article_item_id);

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

                CREATE TABLE IF NOT EXISTS async_task (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    error_log TEXT NOT NULL,
                    site_id INTEGER,
                    version_id INTEGER,
                    run_id INTEGER,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    FOREIGN KEY(site_id) REFERENCES crawl_site(id),
                    FOREIGN KEY(version_id) REFERENCES crawler_version(id),
                    FOREIGN KEY(run_id) REFERENCES crawl_run(id)
                );
                """
            )
            await self._ensure_column(
                db,
                "article_item",
                "detail_status",
                "TEXT NOT NULL DEFAULT 'none'",
            )
            await self._ensure_column(
                db,
                "article_item",
                "detail_requested_at",
                "TEXT",
            )
            await self._ensure_column(
                db,
                "article_item",
                "detail_fetched_at",
                "TEXT",
            )
            await self._ensure_column(
                db,
                "article_item",
                "detail_error",
                "TEXT NOT NULL DEFAULT ''",
            )
            await db.execute(
                """
                UPDATE article_item
                SET detail_status = COALESCE(NULLIF(detail_status, ''), 'none'),
                    detail_error = COALESCE(detail_error, '')
                """
            )
            await db.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_article_item_detail_status
                ON article_item(detail_status);

                CREATE INDEX IF NOT EXISTS idx_article_item_site_detail_status
                ON article_item(site_id, detail_status);
                """
            )
            await db.commit()

    async def _ensure_column(
        self,
        db: aiosqlite.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        rows = await self.fetchall(db, f"PRAGMA table_info({table})")
        if any(row["name"] == column for row in rows):
            return
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    async def ping(self) -> bool:
        async with self.session() as db:
            row = await self.fetchone(db, "SELECT 1 AS ok")
        return bool(row and row["ok"] == 1)

    async def fetchone(
        self, db: aiosqlite.Connection, query: str, params: tuple[Any, ...] = ()
    ) -> aiosqlite.Row | None:
        cursor = await db.execute(query, params)
        return await cursor.fetchone()

    async def fetchall(
        self, db: aiosqlite.Connection, query: str, params: tuple[Any, ...] = ()
    ) -> list[aiosqlite.Row]:
        cursor = await db.execute(query, params)
        return await cursor.fetchall()

    def _pagination(self, page: int, page_size: int) -> tuple[int, int, int, int]:
        safe_page = max(page, 1)
        safe_page_size = max(1, min(page_size, 100))
        return (
            safe_page,
            safe_page_size,
            safe_page_size,
            (safe_page - 1) * safe_page_size,
        )

    async def _count_query(
        self,
        from_sql: str,
        params: tuple[Any, ...] = (),
    ) -> int:
        async with self.session() as db:
            row = await self.fetchone(
                db, f"SELECT COUNT(*) AS total {from_sql}", params
            )
        return int(row["total"]) if row else 0

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
                db,
                "SELECT * FROM crawl_site WHERE id = ?",
                (site_id,),
            )
        return dict(row) if row else {}

    async def update_site(
        self,
        site_id: int,
        *,
        name: str | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        existing = await self.get_site(site_id)
        if not existing:
            return {}
        async with self.session() as db:
            await db.execute(
                """
                UPDATE crawl_site
                SET name = ?, notes = ?, status = ?
                WHERE id = ?
                """,
                (
                    name if name is not None else existing["name"],
                    notes if notes is not None else existing["notes"],
                    status if status is not None else existing["status"],
                    site_id,
                ),
            )
            await db.commit()
        return await self.get_site(site_id)

    async def delete_site(self, site_id: int) -> bool:
        existing = await self.get_site(site_id)
        if not existing:
            return False

        async with self.session() as db:
            await db.execute("DELETE FROM async_task WHERE site_id = ?", (site_id,))
            await db.execute("DELETE FROM regen_feedback WHERE site_id = ?", (site_id,))
            await db.execute("DELETE FROM article_detail WHERE site_id = ?", (site_id,))
            await db.execute("DELETE FROM article_item WHERE site_id = ?", (site_id,))
            await db.execute("DELETE FROM crawl_run WHERE site_id = ?", (site_id,))
            await db.execute("DELETE FROM crawler_version WHERE site_id = ?", (site_id,))
            await db.execute("DELETE FROM crawl_site WHERE id = ?", (site_id,))
            await db.commit()

        return True

    async def update_site_notes(self, site_id: int, notes: str | None) -> None:
        async with self.session() as db:
            await db.execute(
                "UPDATE crawl_site SET notes = ? WHERE id = ?",
                (notes, site_id),
            )
            await db.commit()

    async def list_sites(
        self,
        *,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("cs.status = ?")
            params.append(status)
        if keyword:
            like = f"%{keyword.strip()}%"
            clauses.append("(cs.name LIKE ? OR cs.domain LIKE ? OR cs.seed_url LIKE ?)")
            params.extend([like, like, like])
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        page, page_size, limit, offset = self._pagination(page, page_size)
        total = await self._count_query(
            f"FROM crawl_site cs {where_sql}",
            tuple(params),
        )
        async with self.session() as db:
            today = datetime.now(UTC).date().isoformat()
            rows = await self.fetchall(
                db,
                f"""
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
                        SELECT status
                        FROM crawl_run cr
                        WHERE cr.site_id = cs.id
                        ORDER BY cr.id DESC
                        LIMIT 1
                    ) AS last_run_status,
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
                        WHERE ai.site_id = cs.id
                    ) AS article_count,
                    (
                        SELECT COUNT(*)
                        FROM article_item ai
                        WHERE ai.site_id = cs.id AND substr(ai.first_seen_at, 1, 10) = ?
                    ) AS today_new_count
                FROM crawl_site cs
                LEFT JOIN crawler_version cv ON cv.id = cs.approved_version_id
                {where_sql}
                ORDER BY cs.id DESC
                LIMIT ? OFFSET ?
                """,
                (today, *params, limit, offset),
            )
        return [dict(row) for row in rows], total, page, page_size

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

    async def count_articles_for_site(self, site_id: int) -> int:
        return await self._count_query(
            "FROM article_item WHERE site_id = ?",
            (site_id,),
        )

    async def get_latest_run_for_site(self, site_id: int) -> dict[str, Any] | None:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                """
                SELECT
                    cr.*,
                    cv.version_no AS version_no
                FROM crawl_run cr
                JOIN crawler_version cv ON cv.id = cr.version_id
                WHERE cr.site_id = ?
                ORDER BY cr.id DESC
                LIMIT 1
                """,
                (site_id,),
            )
        return dict(row) if row else None

    async def get_version(self, version_id: int) -> dict[str, Any]:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                "SELECT * FROM crawler_version WHERE id = ?",
                (version_id,),
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

    async def list_versions_for_site(
        self,
        site_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        page, page_size, limit, offset = self._pagination(page, page_size)
        total = await self._count_query(
            "FROM crawler_version WHERE site_id = ?",
            (site_id,),
        )
        async with self.session() as db:
            rows = await self.fetchall(
                db,
                """
                SELECT
                    cv.*,
                    (
                        SELECT id
                        FROM crawl_run cr
                        WHERE cr.version_id = cv.id
                        ORDER BY cr.id DESC
                        LIMIT 1
                    ) AS latest_run_id,
                    (
                        SELECT status
                        FROM crawl_run cr
                        WHERE cr.version_id = cv.id
                        ORDER BY cr.id DESC
                        LIMIT 1
                    ) AS latest_run_status,
                    (
                        SELECT finished_at
                        FROM crawl_run cr
                        WHERE cr.version_id = cv.id
                        ORDER BY cr.id DESC
                        LIMIT 1
                    ) AS latest_run_finished_at
                FROM crawler_version cv
                WHERE cv.site_id = ?
                ORDER BY cv.id DESC
                LIMIT ? OFFSET ?
                """,
                (site_id, limit, offset),
            )
        return [dict(row) for row in rows], total, page, page_size

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

    async def get_run(self, run_id: int) -> dict[str, Any]:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                "SELECT * FROM crawl_run WHERE id = ?",
                (run_id,),
            )
        return dict(row) if row else {}

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
                        (
                            site_id,
                            title,
                            url,
                            url_canonical,
                            published_at,
                            source_list_url,
                            first_seen_at,
                            last_seen_at,
                            run_id,
                            detail_status,
                            detail_requested_at,
                            detail_fetched_at,
                            detail_error
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'none', NULL, NULL, '')
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

    async def list_runs(
        self,
        *,
        site_id: int | None = None,
        version_id: int | None = None,
        run_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        clauses: list[str] = []
        params: list[Any] = []
        if site_id is not None:
            clauses.append("cr.site_id = ?")
            params.append(site_id)
        if version_id is not None:
            clauses.append("cr.version_id = ?")
            params.append(version_id)
        if run_type:
            clauses.append("cr.run_type = ?")
            params.append(run_type)
        if status:
            clauses.append("cr.status = ?")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        page, page_size, limit, offset = self._pagination(page, page_size)
        total = await self._count_query(
            f"FROM crawl_run cr {where_sql}",
            tuple(params),
        )
        async with self.session() as db:
            rows = await self.fetchall(
                db,
                f"""
                SELECT
                    cr.*,
                    cs.name AS site_name,
                    cv.version_no AS version_no
                FROM crawl_run cr
                JOIN crawl_site cs ON cs.id = cr.site_id
                JOIN crawler_version cv ON cv.id = cr.version_id
                {where_sql}
                ORDER BY cr.id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            )
        return [dict(row) for row in rows], total, page, page_size

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
        return dict(row) if row else {}

    async def list_articles(
        self,
        *,
        site_id: int | None = None,
        run_id: int | None = None,
        title: str | None = None,
        keyword: str | None = None,
        source_list_url: str | None = None,
        detail_status: str | None = None,
        published_from: str | None = None,
        published_to: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        clauses: list[str] = []
        params: list[Any] = []
        if site_id is not None:
            clauses.append("ai.site_id = ?")
            params.append(site_id)
        if run_id is not None:
            clauses.append("ai.run_id = ?")
            params.append(run_id)
        if title:
            clauses.append("ai.title LIKE ?")
            params.append(f"%{title.strip()}%")
        if keyword:
            like = f"%{keyword.strip()}%"
            clauses.append(
                "(ai.title LIKE ? OR ai.url LIKE ? OR ai.url_canonical LIKE ? OR ai.source_list_url LIKE ?)"
            )
            params.extend([like, like, like, like])
        if source_list_url:
            clauses.append("ai.source_list_url LIKE ?")
            params.append(f"%{source_list_url.strip()}%")
        if detail_status:
            clauses.append("ai.detail_status = ?")
            params.append(detail_status)
        if published_from:
            clauses.append("ai.published_at >= ?")
            params.append(published_from)
        if published_to:
            clauses.append("ai.published_at <= ?")
            params.append(published_to)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        page, page_size, limit, offset = self._pagination(page, page_size)
        total = await self._count_query(
            f"FROM article_item ai {where_sql}",
            tuple(params),
        )
        async with self.session() as db:
            rows = await self.fetchall(
                db,
                f"""
                SELECT
                    ai.*,
                    cs.name AS site_name,
                    CASE WHEN ad.id IS NULL THEN 0 ELSE 1 END AS has_detail
                FROM article_item ai
                JOIN crawl_site cs ON cs.id = ai.site_id
                LEFT JOIN article_detail ad ON ad.article_item_id = ai.id
                {where_sql}
                ORDER BY COALESCE(ai.published_at, ai.first_seen_at) DESC, ai.id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            )
        return [dict(row) for row in rows], total, page, page_size

    async def list_articles_for_site(
        self,
        site_id: int,
        *,
        run_id: int | None = None,
        title: str | None = None,
        keyword: str | None = None,
        source_list_url: str | None = None,
        detail_status: str | None = None,
        published_from: str | None = None,
        published_to: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        return await self.list_articles(
            site_id=site_id,
            run_id=run_id,
            title=title,
            keyword=keyword,
            source_list_url=source_list_url,
            detail_status=detail_status,
            published_from=published_from,
            published_to=published_to,
            page=page,
            page_size=page_size,
        )

    async def get_article_item(self, article_id: int) -> dict[str, Any]:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                """
                SELECT
                    ai.*,
                    cs.name AS site_name,
                    CASE WHEN ad.id IS NULL THEN 0 ELSE 1 END AS has_detail
                FROM article_item ai
                JOIN crawl_site cs ON cs.id = ai.site_id
                LEFT JOIN article_detail ad ON ad.article_item_id = ai.id
                WHERE ai.id = ?
                """,
                (article_id,),
            )
        return dict(row) if row else {}

    async def get_article_items_by_ids(self, article_ids: list[int]) -> list[dict[str, Any]]:
        if not article_ids:
            return []
        placeholders = ", ".join("?" for _ in article_ids)
        async with self.session() as db:
            rows = await self.fetchall(
                db,
                f"""
                SELECT
                    ai.*,
                    cs.name AS site_name,
                    CASE WHEN ad.id IS NULL THEN 0 ELSE 1 END AS has_detail
                FROM article_item ai
                JOIN crawl_site cs ON cs.id = ai.site_id
                LEFT JOIN article_detail ad ON ad.article_item_id = ai.id
                WHERE ai.id IN ({placeholders})
                ORDER BY ai.id
                """,
                tuple(article_ids),
            )
        return [dict(row) for row in rows]

    async def mark_articles_detail_pending(
        self,
        article_ids: list[int],
        *,
        force_refetch: bool = False,
    ) -> dict[str, Any]:
        if not article_ids:
            return {"updated_ids": [], "skipped_ids": [], "not_found_ids": []}
        rows = await self.get_article_items_by_ids(article_ids)
        row_map = {int(row["id"]): row for row in rows}
        updated_ids: list[int] = []
        skipped_ids: list[int] = []
        not_found_ids: list[int] = []
        now = utc_now()
        async with self.session() as db:
            for article_id in article_ids:
                row = row_map.get(article_id)
                if row is None:
                    not_found_ids.append(article_id)
                    continue
                current_status = row.get("detail_status") or "none"
                if current_status == "running":
                    skipped_ids.append(article_id)
                    continue
                if current_status == "succeeded" and not force_refetch:
                    skipped_ids.append(article_id)
                    continue
                if current_status == "pending" and not force_refetch:
                    skipped_ids.append(article_id)
                    continue
                await db.execute(
                    """
                    UPDATE article_item
                    SET detail_status = 'pending',
                        detail_requested_at = ?,
                        detail_fetched_at = NULL,
                        detail_error = ''
                    WHERE id = ?
                    """,
                    (now, article_id),
                )
                updated_ids.append(article_id)
            await db.commit()
        return {
            "updated_ids": updated_ids,
            "skipped_ids": skipped_ids,
            "not_found_ids": not_found_ids,
        }

    async def get_pending_detail_article_ids(self, article_ids: list[int]) -> list[int]:
        if not article_ids:
            return []
        placeholders = ", ".join("?" for _ in article_ids)
        async with self.session() as db:
            rows = await self.fetchall(
                db,
                f"""
                SELECT id
                FROM article_item
                WHERE id IN ({placeholders}) AND detail_status = 'pending'
                ORDER BY id
                """,
                tuple(article_ids),
            )
        return [int(row["id"]) for row in rows]

    async def mark_articles_detail_running(self, article_ids: list[int]) -> list[int]:
        if not article_ids:
            return []
        pending_ids = await self.get_pending_detail_article_ids(article_ids)
        if not pending_ids:
            return []
        placeholders = ", ".join("?" for _ in pending_ids)
        async with self.session() as db:
            await db.execute(
                f"""
                UPDATE article_item
                SET detail_status = 'running',
                    detail_error = ''
                WHERE id IN ({placeholders})
                """,
                tuple(pending_ids),
            )
            await db.commit()
        return pending_ids

    async def mark_article_detail_succeeded(self, article_id: int) -> None:
        async with self.session() as db:
            await db.execute(
                """
                UPDATE article_item
                SET detail_status = 'succeeded',
                    detail_fetched_at = ?,
                    detail_error = ''
                WHERE id = ?
                """,
                (utc_now(), article_id),
            )
            await db.commit()

    async def mark_article_detail_failed(self, article_id: int, error: str) -> None:
        async with self.session() as db:
            await db.execute(
                """
                UPDATE article_item
                SET detail_status = 'failed',
                    detail_error = ?
                WHERE id = ?
                """,
                (error, article_id),
            )
            await db.commit()

    async def upsert_article_detail(
        self,
        *,
        article_item_id: int,
        site_id: int,
        source_url: str,
        final_url: str,
        content_html: str,
        content_markdown: str,
    ) -> None:
        now = utc_now()
        async with self.session() as db:
            existing = await self.fetchone(
                db,
                "SELECT id FROM article_detail WHERE article_item_id = ?",
                (article_item_id,),
            )
            if existing is None:
                await db.execute(
                    """
                    INSERT INTO article_detail
                    (
                        article_item_id,
                        site_id,
                        source_url,
                        final_url,
                        content_html,
                        content_markdown,
                        fetched_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article_item_id,
                        site_id,
                        source_url,
                        final_url,
                        content_html,
                        content_markdown,
                        now,
                        now,
                    ),
                )
            else:
                await db.execute(
                    """
                    UPDATE article_detail
                    SET site_id = ?,
                        source_url = ?,
                        final_url = ?,
                        content_html = ?,
                        content_markdown = ?,
                        fetched_at = ?,
                        updated_at = ?
                    WHERE article_item_id = ?
                    """,
                    (
                        site_id,
                        source_url,
                        final_url,
                        content_html,
                        content_markdown,
                        now,
                        now,
                        article_item_id,
                    ),
                )
            await db.commit()

    async def get_article_detail(self, article_id: int) -> dict[str, Any]:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                """
                SELECT
                    ai.id AS article_id,
                    ai.site_id,
                    cs.name AS site_name,
                    ai.title,
                    ai.url AS source_url,
                    ai.detail_status,
                    ai.detail_requested_at,
                    ai.detail_fetched_at,
                    ai.detail_error,
                    ad.final_url,
                    ad.content_html,
                    ad.content_markdown,
                    ad.fetched_at,
                    ad.updated_at
                FROM article_item ai
                JOIN crawl_site cs ON cs.id = ai.site_id
                LEFT JOIN article_detail ad ON ad.article_item_id = ai.id
                WHERE ai.id = ?
                """,
                (article_id,),
            )
        return dict(row) if row else {}

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

    async def create_task(
        self,
        *,
        task_type: str,
        params_json: dict[str, Any],
        site_id: int | None = None,
        version_id: int | None = None,
        run_id: int | None = None,
    ) -> dict[str, Any]:
        async with self.session() as db:
            cursor = await db.execute(
                """
                INSERT INTO async_task
                (task_type, status, params_json, result_json, error_log, site_id, version_id, run_id, created_at)
                VALUES (?, 'pending', ?, '{}', '', ?, ?, ?, ?)
                """,
                (
                    task_type,
                    json.dumps(params_json, ensure_ascii=False),
                    site_id,
                    version_id,
                    run_id,
                    utc_now(),
                ),
            )
            await db.commit()
            task_id = cursor.lastrowid
        return await self.get_task(task_id)

    async def get_task(self, task_id: int) -> dict[str, Any]:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                "SELECT * FROM async_task WHERE id = ?",
                (task_id,),
            )
        return dict(row) if row else {}

    async def list_tasks(
        self,
        *,
        task_type: str | None = None,
        status: str | None = None,
        site_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        clauses: list[str] = []
        params: list[Any] = []
        if task_type:
            clauses.append("task_type = ?")
            params.append(task_type)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if site_id is not None:
            clauses.append("site_id = ?")
            params.append(site_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        page, page_size, limit, offset = self._pagination(page, page_size)
        total = await self._count_query(
            f"FROM async_task {where_sql}",
            tuple(params),
        )
        async with self.session() as db:
            rows = await self.fetchall(
                db,
                f"""
                SELECT *
                FROM async_task
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            )
        return [dict(row) for row in rows], total, page, page_size

    async def reset_running_tasks_to_pending(self) -> None:
        async with self.session() as db:
            await db.execute(
                """
                UPDATE async_task
                SET status = 'pending', started_at = NULL, finished_at = NULL
                WHERE status = 'running'
                """
            )
            await db.commit()

    async def claim_next_task(self) -> dict[str, Any] | None:
        async with self.session() as db:
            row = await self.fetchone(
                db,
                """
                SELECT *
                FROM async_task
                WHERE status = 'pending'
                ORDER BY id
                LIMIT 1
                """,
            )
            if row is None:
                return None
            cursor = await db.execute(
                """
                UPDATE async_task
                SET status = 'running', started_at = ?, finished_at = NULL, error_log = ''
                WHERE id = ? AND status = 'pending'
                """,
                (utc_now(), row["id"]),
            )
            await db.commit()
            if cursor.rowcount != 1:
                return None
        return await self.get_task(int(row["id"]))

    async def mark_task_succeeded(
        self,
        task_id: int,
        *,
        result_json: dict[str, Any],
        site_id: int | None = None,
        version_id: int | None = None,
        run_id: int | None = None,
    ) -> dict[str, Any]:
        existing = await self.get_task(task_id)
        async with self.session() as db:
            await db.execute(
                """
                UPDATE async_task
                SET status = 'succeeded',
                    result_json = ?,
                    error_log = '',
                    site_id = ?,
                    version_id = ?,
                    run_id = ?,
                    finished_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(result_json, ensure_ascii=False),
                    site_id if site_id is not None else existing.get("site_id"),
                    version_id
                    if version_id is not None
                    else existing.get("version_id"),
                    run_id if run_id is not None else existing.get("run_id"),
                    utc_now(),
                    task_id,
                ),
            )
            await db.commit()
        return await self.get_task(task_id)

    async def mark_task_failed(
        self,
        task_id: int,
        *,
        error_log: str,
        result_json: dict[str, Any] | None = None,
        site_id: int | None = None,
        version_id: int | None = None,
        run_id: int | None = None,
    ) -> dict[str, Any]:
        existing = await self.get_task(task_id)
        async with self.session() as db:
            await db.execute(
                """
                UPDATE async_task
                SET status = 'failed',
                    result_json = ?,
                    error_log = ?,
                    site_id = ?,
                    version_id = ?,
                    run_id = ?,
                    finished_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(result_json or {}, ensure_ascii=False),
                    error_log,
                    site_id if site_id is not None else existing.get("site_id"),
                    version_id
                    if version_id is not None
                    else existing.get("version_id"),
                    run_id if run_id is not None else existing.get("run_id"),
                    utc_now(),
                    task_id,
                ),
            )
            await db.commit()
        return await self.get_task(task_id)

    async def cancel_task(self, task_id: int) -> dict[str, Any] | None:
        async with self.session() as db:
            cursor = await db.execute(
                """
                UPDATE async_task
                SET status = 'cancelled', finished_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (utc_now(), task_id),
            )
            await db.commit()
            if cursor.rowcount != 1:
                return None
        return await self.get_task(task_id)
