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
            db.execute("""CREATE TABLE IF NOT EXISTS control_state (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                paused INTEGER NOT NULL DEFAULT 0,
                last_source_sha TEXT,
                last_applied_epoch REAL,
                last_error_code TEXT
            )""")
            db.execute("""INSERT OR IGNORE INTO control_state(singleton,paused)
                VALUES (1,0)""")
            db.execute("""CREATE TABLE IF NOT EXISTS control_commands (
                id TEXT PRIMARY KEY,
                repository TEXT NOT NULL,
                ref TEXT NOT NULL,
                source_sha TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                operation TEXT NOT NULL,
                applied_epoch REAL NOT NULL
            )""")

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
            if db.execute("SELECT paused FROM control_state WHERE singleton=1").fetchone()[0]:
                return None
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

    def control_snapshot(self):
        with self._tx() as db:
            row = db.execute("""SELECT paused,last_source_sha,last_applied_epoch,last_error_code
                FROM control_state WHERE singleton=1""").fetchone()
            return dict(row)

    def set_control_error(self, code):
        _text(code, "code")
        with self._tx() as db:
            db.execute("UPDATE control_state SET last_error_code=? WHERE singleton=1", (code,))

    def apply_control_batch(self, repository, ref, source_sha, commands, *, now=None):
        """Atomically apply a fully validated GitHub control batch."""
        _text(repository, "repository")
        _text(ref, "ref")
        _text(source_sha, "source_sha")
        if not isinstance(commands, list) or not commands:
            raise ValueError("CONTROL_BATCH_INVALID")
        now = _number(time.time() if now is None else now, "now")
        with self._tx() as db:
            prepared = []
            duplicate_ids = []
            for command in commands:
                if not isinstance(command, dict):
                    raise ValueError("CONTROL_COMMAND_INVALID")
                command_id = _text(command.get("id"), "command_id")
                operation = command.get("operation")
                content_hash = command.get("content_hash")
                if operation not in {"pause", "resume", "enqueue", "status"}:
                    raise ValueError("CONTROL_OPERATION_UNSUPPORTED")
                if (not isinstance(content_hash, str) or len(content_hash) != 64
                        or any(ch not in "0123456789abcdef" for ch in content_hash)):
                    raise ValueError("CONTROL_HASH_INVALID")
                previous = db.execute(
                    "SELECT repository,ref,content_hash,operation FROM control_commands WHERE id=?",
                    (command_id,),
                ).fetchone()
                if previous is not None:
                    if tuple(previous) != (repository, ref, content_hash, operation):
                        raise ValueError("CONTROL_REPLAY_CONFLICT")
                    duplicate_ids.append(command_id)
                    continue
                task_record = None
                if operation == "enqueue":
                    task = command.get("task")
                    if not isinstance(task, dict):
                        raise ValueError("CONTROL_TASK_INVALID")
                    task_id = _text(task.get("id"), "task_id")
                    project = _text(task.get("project"), "project")
                    payload = task.get("payload")
                    encoded = _json(payload)
                    max_attempts = task.get("max_attempts", 3)
                    if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
                        raise ValueError("CONTROL_MAX_ATTEMPTS_INVALID")
                    existing = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
                    if existing is not None:
                        if (existing["project"], existing["payload"], existing["max_attempts"],
                            existing["initial_not_before"]) != (project, encoded, max_attempts, 0):
                            raise ValueError("CONTROL_TASK_CONFLICT")
                    task_record = (task_id, project, encoded, max_attempts, existing is not None)
                prepared.append((command_id, operation, content_hash, task_record))

            applied_ids = []
            for command_id, operation, content_hash, task_record in prepared:
                if operation == "pause":
                    db.execute("UPDATE control_state SET paused=1 WHERE singleton=1")
                elif operation == "resume":
                    db.execute("UPDATE control_state SET paused=0 WHERE singleton=1")
                elif operation == "enqueue" and task_record is not None:
                    task_id, project, encoded, max_attempts, existed = task_record
                    if not existed:
                        db.execute("""INSERT INTO tasks
                            (id,project,payload,state,max_attempts,not_before,initial_not_before)
                            VALUES (?,?,?,'queued',?,0,0)""",
                            (task_id, project, encoded, max_attempts))
                db.execute("""INSERT INTO control_commands
                    (id,repository,ref,source_sha,content_hash,operation,applied_epoch)
                    VALUES (?,?,?,?,?,?,?)""",
                    (command_id, repository, ref, source_sha, content_hash, operation, now))
                applied_ids.append(command_id)
            db.execute("""UPDATE control_state SET last_source_sha=?,last_applied_epoch=?,
                last_error_code=NULL WHERE singleton=1""", (source_sha, now))
            paused = bool(db.execute(
                "SELECT paused FROM control_state WHERE singleton=1"
            ).fetchone()[0])
            return {"applied_ids": applied_ids, "duplicate_ids": duplicate_ids, "paused": paused}

    def sanitized_status(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit")
        with self._tx() as db:
            control = dict(db.execute("""SELECT paused,last_source_sha,last_applied_epoch,
                last_error_code FROM control_state WHERE singleton=1""").fetchone())
            rows = db.execute("""SELECT id,project,state,attempts,max_attempts,error,result
                FROM tasks ORDER BY rowid DESC LIMIT ?""", (limit,)).fetchall()
        tasks = []
        for row in rows:
            result = json.loads(row["result"]) if row["result"] else {}
            stage = row["state"]
            if stage == "completed":
                candidate = result.get("stage")
                stage = candidate if candidate in {"artifact_ready", "candidate_tested"} else "artifact_ready"
            error = row["error"]
            if error and (len(error) > 64 or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in error)):
                error = "INTERNAL_ERROR"
            tasks.append({
                "id": row["id"], "project": row["project"], "stage": stage,
                "attempts": row["attempts"], "max_attempts": row["max_attempts"],
                "failure_code": error,
                "tests_executed": bool(result.get("tests_executed", False)),
                "product_complete": False,
            })
        control["paused"] = bool(control["paused"])
        control["tasks"] = tasks
        return control
