from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import MetricSample


class SQLiteMetricStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metric_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ms INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                app_id TEXT NOT NULL,
                metric_key TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                tags_json TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def write(self, sample: MetricSample) -> None:
        self.conn.execute(
            """
            INSERT INTO metric_samples (
                timestamp_ms, device_id, app_id, metric_key, value, unit, source,
                confidence, sequence, tags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample.timestamp_ms,
                sample.device_id,
                sample.app_id,
                sample.metric_key.value,
                sample.value,
                sample.unit,
                sample.source.value,
                sample.confidence.value,
                sample.sequence,
                json.dumps(sample.tags, ensure_ascii=True),
            ),
        )
        self.conn.commit()

    def export_csv(self, out_path: Path) -> None:
        cursor = self.conn.execute(
            """
            SELECT timestamp_ms, device_id, app_id, metric_key, value, unit,
                   source, confidence, sequence, tags_json
            FROM metric_samples
            ORDER BY timestamp_ms ASC, id ASC
            """
        )
        header = (
            "timestamp_ms,device_id,app_id,metric_key,value,unit,"
            "source,confidence,sequence,tags_json\n"
        )
        rows = [header]
        for row in cursor.fetchall():
            normalized = [str(col).replace(",", ";") for col in row]
            rows.append(",".join(normalized) + "\n")
        out_path.write_text("".join(rows), encoding="utf-8")

    def export_json(self, out_path: Path) -> None:
        cursor = self.conn.execute(
            """
            SELECT timestamp_ms, device_id, app_id, metric_key, value, unit,
                   source, confidence, sequence, tags_json
            FROM metric_samples
            ORDER BY timestamp_ms ASC, id ASC
            """
        )
        payload: list[dict[str, object]] = []
        for row in cursor.fetchall():
            payload.append(
                {
                    "timestamp_ms": row[0],
                    "device_id": row[1],
                    "app_id": row[2],
                    "metric_key": row[3],
                    "value": row[4],
                    "unit": row[5],
                    "source": row[6],
                    "confidence": row[7],
                    "sequence": row[8],
                    "tags": json.loads(row[9]),
                }
            )
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def close(self) -> None:
        self.conn.close()
