"""Session manager: recording, replay, and comparison analysis."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import MetricKey, MetricSample


@dataclass
class SessionMeta:
    """会话元数据。"""

    session_id: str
    started_at_ms: int
    ended_at_ms: int = 0
    device_id: str = ""
    app_id: str = ""
    profile_name: str = ""
    sample_count: int = 0
    tags: dict[str, str] = field(default_factory=dict)
    build_number: str = ""
    os_version: str = ""
    render_api: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at_ms": self.started_at_ms,
            "ended_at_ms": self.ended_at_ms,
            "device_id": self.device_id,
            "app_id": self.app_id,
            "profile_name": self.profile_name,
            "sample_count": self.sample_count,
            "tags": self.tags,
            "build_number": self.build_number,
            "os_version": self.os_version,
            "render_api": self.render_api,
        }


class SessionManager:
    """
    会话管理：记录、回放、对比分析。
    - 按 Session 保存原始流 + 聚合结果
    - 支持 CSV/JSON/HTML 报告
    - 同场景多版本对比
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._init_schema()
        self._current_session: SessionMeta | None = None

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                started_at_ms INTEGER NOT NULL,
                ended_at_ms INTEGER DEFAULT 0,
                device_id TEXT NOT NULL,
                app_id TEXT NOT NULL,
                profile_name TEXT DEFAULT '',
                sample_count INTEGER DEFAULT 0,
                tags_json TEXT NOT NULL DEFAULT '{}',
                build_number TEXT DEFAULT '',
                os_version TEXT DEFAULT '',
                render_api TEXT DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_device ON sessions(device_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_app ON sessions(app_id);
        """)
        self._conn.commit()

    # ── Session Lifecycle ─────────────────────────────────────────

    def start_session(
        self,
        device_id: str,
        app_id: str,
        profile_name: str = "",
        **tags: str,
    ) -> SessionMeta:
        """开始新会话。"""
        session_id = f"{device_id}_{app_id}_{int(time.time() * 1000)}"
        meta = SessionMeta(
            session_id=session_id,
            started_at_ms=int(time.time() * 1000),
            device_id=device_id,
            app_id=app_id,
            profile_name=profile_name,
            tags=tags,
        )
        self._conn.execute(
            """INSERT INTO sessions (session_id, started_at_ms, device_id, app_id,
               profile_name, tags_json) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                meta.session_id,
                meta.started_at_ms,
                meta.device_id,
                meta.app_id,
                meta.profile_name,
                json.dumps(meta.tags, ensure_ascii=True),
            ),
        )
        self._conn.commit()
        self._current_session = meta
        return meta

    def end_session(self, sample_count: int = 0) -> SessionMeta | None:
        """结束当前会话。"""
        if not self._current_session:
            return None
        now = int(time.time() * 1000)
        self._current_session.ended_at_ms = now
        self._current_session.sample_count = sample_count
        self._conn.execute(
            "UPDATE sessions SET ended_at_ms = ?, sample_count = ? WHERE session_id = ?",
            (now, sample_count, self._current_session.session_id),
        )
        self._conn.commit()
        meta = self._current_session
        self._current_session = None
        return meta

    def update_session_meta(self, **kwargs: str) -> None:
        """更新当前会话的元数据（如 build_number, os_version 等）。"""
        if not self._current_session:
            return
        for key, value in kwargs.items():
            if hasattr(self._current_session, key):
                setattr(self._current_session, key, value)
        self._conn.execute(
            """UPDATE sessions SET build_number = ?, os_version = ?, render_api = ?
               WHERE session_id = ?""",
            (
                self._current_session.build_number,
                self._current_session.os_version,
                self._current_session.render_api,
                self._current_session.session_id,
            ),
        )
        self._conn.commit()

    # ── Query ─────────────────────────────────────────────────────

    def list_sessions(self, device_id: str = "", app_id: str = "") -> list[SessionMeta]:
        """列出历史会话。"""
        where = []
        params: list[str] = []
        if device_id:
            where.append("device_id = ?")
            params.append(device_id)
        if app_id:
            where.append("app_id = ?")
            params.append(app_id)
        sql = "SELECT * FROM sessions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY started_at_ms DESC LIMIT 100"

        rows = self._conn.execute(sql, params).fetchall()
        return [
            SessionMeta(
                session_id=r[0],
                started_at_ms=r[1],
                ended_at_ms=r[2] or 0,
                device_id=r[3],
                app_id=r[4],
                profile_name=r[5] or "",
                sample_count=r[6] or 0,
                tags=json.loads(r[7]) if r[7] else {},
                build_number=r[8] or "",
                os_version=r[9] or "",
                render_api=r[10] or "",
            )
            for r in rows
        ]

    def get_session(self, session_id: str) -> SessionMeta | None:
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchall()
        if not rows:
            return None
        r = rows[0]
        return SessionMeta(
            session_id=r[0],
            started_at_ms=r[1],
            ended_at_ms=r[2] or 0,
            device_id=r[3],
            app_id=r[4],
            profile_name=r[5] or "",
            sample_count=r[6] or 0,
            tags=json.loads(r[7]) if r[7] else {},
            build_number=r[8] or "",
            os_version=r[9] or "",
            render_api=r[10] or "",
        )

    # ── Comparison ────────────────────────────────────────────────

    def compare_sessions(
        self, session_ids: list[str], metric_keys: list[MetricKey] | None = None
    ) -> dict[str, Any]:
        """对比多个会话的指标统计。"""
        if not session_ids:
            return {}

        placeholders = ",".join("?" for _ in session_ids)
        key_filter = ""
        params: list[str] = list(session_ids)
        if metric_keys:
            key_placeholders = ",".join("?" for _ in metric_keys)
            key_filter = f"AND metric_key IN ({key_placeholders})"
            params.extend([k.value for k in metric_keys])

        sql = f"""
            SELECT s.session_id, s.device_id, s.app_id, s.build_number,
                   ms.metric_key, ROUND(AVG(ms.value), 2), ROUND(MIN(ms.value), 2),
                   ROUND(MAX(ms.value), 2), COUNT(*)
            FROM sessions s
            JOIN metric_samples ms ON s.session_id = 'dummy'  -- placeholder
            WHERE s.session_id IN ({placeholders})
            GROUP BY s.session_id, ms.metric_key
            ORDER BY s.session_id, ms.metric_key
        """
        # 实际需要跨表 JOIN，但 sessions 和 metric_samples 在不同表
        # 简化实现：分别查询每个 session 的聚合
        result: dict[str, Any] = {"sessions": {}, "metrics": {}}
        for sid in session_ids:
            session = self.get_session(sid)
            if not session:
                continue
            result["sessions"][sid] = session.to_dict()
            # 从 metric_samples 表查询
            rows = self._conn.execute(
                """SELECT metric_key, ROUND(AVG(value), 2), ROUND(MIN(value), 2),
                          ROUND(MAX(value), 2), COUNT(*)
                   FROM metric_samples
                   WHERE device_id = ? AND app_id = ?
                   AND timestamp_ms BETWEEN ? AND ?
                   GROUP BY metric_key""",
                (
                    session.device_id,
                    session.app_id,
                    session.started_at_ms,
                    session.ended_at_ms or int(time.time() * 1000),
                ),
            ).fetchall()
            result["metrics"][sid] = {
                r[0]: {"avg": r[1], "min": r[2], "max": r[3], "count": r[4]}
                for r in rows
            }
        return result

    def close(self) -> None:
        self._conn.close()

    @property
    def current_session(self) -> SessionMeta | None:
        return self._current_session