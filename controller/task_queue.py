"""Local durable queue. Queue fencing protects state, not arbitrary external effects.

Keep this database on a local filesystem. All writers must use this API.
A worker must additionally hold a repository OS lock throughout any checkout
write: an expired lease does not terminate a paused process.
"""
from contextlib import contextmanager
import json
import math
from pathlib import Path
import secrets
import sqlite3
import time


class LeaseLost(RuntimeError):
    """The task is no longer owned by this claim."""


def _number(value, name, low=0, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name)
    if value < low or (high is not None and value > high):
        raise ValueError(name)
    return value


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(name)
    return value


def _json(value):
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode()) > 1_000_000:
        raise ValueError("JSON object too large")
    return encoded


def _decode(row):
    if row is None:
        return None
    result = dict(row)
    for field in ("payload", "checkpoint", "result"):
        result[field] = json.loads(result[field]) if result[field] is not None else None
    return result


class TaskQueue:
    def __init__(self, db_path, max_concurrency=2):
        if type(max_concurrency) is not int or not 1 <= max_concurrency <= 2:
            raise ValueError("max_concurrency must be 1 or 2")
        self.path = str(Path(db_path))
        self.max_concurrency = max_concurrency
        with self._tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, project TEXT NOT NULL, payload TEXT NOT NULL,
                state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL, not_before REAL NOT NULL,
                initial_not_before REAL NOT NULL, token TEXT, worker TEXT,
                lease_until REAL, checkpoint TEXT, result TEXT, error TEXT
            )""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_project_writer
                ON tasks(project) WHERE state='running'""")

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def enqueue(self, task_id, project, payload, *, max_attempts=3, not_before=0):
        _text(task_id, "task_id")
        _text(project, "project")
        encoded = _json(payload)
        if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts must be 1..10")
        _number(not_before, "not_before")
        with self._tx() as db:
            previous = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if previous is not None:
                if (previous["project"], previous["payload"], previous["max_attempts"],
                    previous["initial_not_before"]) != (project, encoded, max_attempts, not_before):
                    raise ValueError("task ID already exists with different content")
                return _decode(previous)
            db.execute("""INSERT INTO tasks
                (id,project,payload,state,max_attempts,not_before,initial_not_before)
                VALUES (?,?,?,'queued',?,?,?)""",
                (task_id, project, encoded, max_attempts, not_before, not_before))
            return _decode(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def get(self, task_id):
        with self._tx() as db:
            return _decode(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def claim(self, worker_id, *, lease_seconds=120, now=None):
        _text(worker_id, "worker_id")
        _number(lease_seconds, "lease_seconds", 1, 3600)
        with self._tx() as db:
            # Lock acquisition can outlast a lease; sample only after BEGIN succeeds.
            now = _number(time.time() if now is None else now, "now")
            db.execute("""UPDATE tasks SET
                state=CASE WHEN attempts>=max_attempts THEN 'failed' ELSE 'queued' END,
                token=NULL,worker=NULL,lease_until=NULL,error='LEASE_EXPIRED'
                WHERE state='running' AND lease_until<=?""", (now,))
            count = db.execute("SELECT count(*) FROM tasks WHERE state='running'").fetchone()[0]
            if count >= self.max_concurrency:
                return None
            row = db.execute("""SELECT * FROM tasks t WHERE state='queued'
                AND not_before<=? AND attempts<max_attempts
                AND NOT EXISTS (SELECT 1 FROM tasks r WHERE r.project=t.project AND r.state='running')
                ORDER BY rowid LIMIT 1""", (now,)).fetchone()
            if row is None:
                return None
            token = secrets.token_hex(24)
            db.execute("""UPDATE tasks SET state='running',attempts=attempts+1,
                token=?,worker=?,lease_until=? WHERE id=?""",
                (token, worker_id, now + lease_seconds, row["id"]))
            return _decode(db.execute("SELECT * FROM tasks WHERE id=?", (row["id"],)).fetchone())

    def _owned(self, db, task_id, token, now):
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if (row is None or row["state"] != "running" or not token
                or row["token"] != token or row["lease_until"] <= now):
            raise LeaseLost("task lease lost")
        return row

    def heartbeat(self, task_id, token, *, lease_seconds=120, now=None):
        _number(lease_seconds, "lease_seconds", 1, 3600)
        with self._tx() as db:
            # Lock acquisition can outlast a lease; sample only after BEGIN succeeds.
            now = _number(time.time() if now is None else now, "now")
            row = self._owned(db, task_id, token, now)
            db.execute("UPDATE tasks SET lease_until=? WHERE id=?",
                       (max(row["lease_until"], now + lease_seconds), task_id))
            return _decode(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def checkpoint(self, task_id, token, data, *, now=None):
        encoded = _json(data)
        with self._tx() as db:
            # Lock acquisition can outlast a lease; sample only after BEGIN succeeds.
            now = _number(time.time() if now is None else now, "now")
            self._owned(db, task_id, token, now)
            db.execute("UPDATE tasks SET checkpoint=? WHERE id=?", (encoded, task_id))
            return _decode(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def complete(self, task_id, token, result, *, now=None):
        encoded = _json(result)
        with self._tx() as db:
            # Lock acquisition can outlast a lease; sample only after BEGIN succeeds.
            now = _number(time.time() if now is None else now, "now")
            self._owned(db, task_id, token, now)
            db.execute("""UPDATE tasks SET state='completed',result=?,token=NULL,
                worker=NULL,lease_until=NULL WHERE id=?""", (encoded, task_id))
            return _decode(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def defer(self, task_id, token, error, *, retry_delay=300, now=None):
        """Return an unavailable-provider claim without spending generation budget.

        Only the trusted worker's no-route branch should use this operation.
        Invalid output and execution failures must use fail() instead.
        """
        _text(error, "error")
        _number(retry_delay, "retry_delay", 0, 86400)
        with self._tx() as db:
            now = _number(time.time() if now is None else now, "now")
            self._owned(db, task_id, token, now)
            db.execute("""UPDATE tasks SET state='queued',error=?,not_before=?,
                attempts=attempts-1,token=NULL,worker=NULL,lease_until=NULL WHERE id=?""",
                (error, now + retry_delay, task_id))
            return _decode(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def fail(self, task_id, token, error, *, retry_delay=30, now=None):
        _text(error, "error")
        _number(retry_delay, "retry_delay", 0, 86400)
        with self._tx() as db:
            # Lock acquisition can outlast a lease; sample only after BEGIN succeeds.
            now = _number(time.time() if now is None else now, "now")
            row = self._owned(db, task_id, token, now)
            state = "failed" if row["attempts"] >= row["max_attempts"] else "queued"
            db.execute("""UPDATE tasks SET state=?,error=?,not_before=?,
                token=NULL,worker=NULL,lease_until=NULL WHERE id=?""",
                (state, error, now + retry_delay, task_id))
            return _decode(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())
