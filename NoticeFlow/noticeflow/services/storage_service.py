import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID
from collections.abc import Iterator

from noticeflow.core.models import ActionStatus, Notice


class StorageService:
    def __init__(self, database_path: str | Path = "data/noticeflow.db") -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS notices (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS actions (
                    id TEXT PRIMARY KEY,
                    notice_id TEXT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )

    def save_notice(self, notice: Notice) -> None:
        payload = notice.model_dump_json()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO notices (id, title, priority, created_at, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    priority=excluded.priority,
                    payload=excluded.payload
                """,
                (str(notice.id), notice.title, notice.priority.value, notice.created_at.isoformat(), payload),
            )
            connection.execute("DELETE FROM actions WHERE notice_id = ?", (str(notice.id),))
            connection.executemany(
                "INSERT INTO actions (id, notice_id, status, payload) VALUES (?, ?, ?, ?)",
                [
                    (str(action.id), str(notice.id), action.status.value, action.model_dump_json())
                    for action in notice.actions
                ],
            )

    def list_notices(self) -> list[Notice]:
        with self._connection() as connection:
            rows = connection.execute("SELECT payload FROM notices ORDER BY created_at DESC").fetchall()
        return [Notice.model_validate_json(row["payload"]) for row in rows]

    def get_notice(self, notice_id: UUID) -> Notice | None:
        with self._connection() as connection:
            row = connection.execute("SELECT payload FROM notices WHERE id = ?", (str(notice_id),)).fetchone()
        return Notice.model_validate_json(row["payload"]) if row else None

    def update_action_status(self, action_id: UUID, status: ActionStatus) -> Notice | None:
        with self._connection() as connection:
            action_row = connection.execute(
                "SELECT notice_id, payload FROM actions WHERE id = ?", (str(action_id),)
            ).fetchone()
            if action_row is None:
                return None
            action_payload = json.loads(action_row["payload"])
            action_payload["status"] = status.value
            connection.execute(
                "UPDATE actions SET status = ?, payload = ? WHERE id = ?",
                (status.value, json.dumps(action_payload), str(action_id)),
            )
            notice_row = connection.execute(
                "SELECT payload FROM notices WHERE id = ?", (action_row["notice_id"],)
            ).fetchone()
            if notice_row is None:
                return None
            notice_payload = json.loads(notice_row["payload"])
            for action in notice_payload["actions"]:
                if action["id"] == str(action_id):
                    action["status"] = status.value
                    break
            connection.execute(
                "UPDATE notices SET payload = ? WHERE id = ?",
                (json.dumps(notice_payload), action_row["notice_id"]),
            )
            return Notice.model_validate(notice_payload)
