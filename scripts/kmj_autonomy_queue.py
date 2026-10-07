"""Operator CLI: enqueue explicit bounded tasks or inspect sanitized status."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
from controller.task_queue import TaskQueue

def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('status')
    add = sub.add_parser('enqueue')
    add.add_argument('--id', required=True)
    add.add_argument('--project', required=True)
    add.add_argument('--kind', choices=['plan', 'review', 'text', 'patch'], required=True)
    add.add_argument('--prompt-file', required=True)
    add.add_argument('--classification', choices=['confidential', 'public'], default='confidential')
    args = parser.parse_args()
    path = Path(args.db)
    if args.action == 'status':
        if not path.is_file():
            parser.error('queue database does not exist')
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute('SELECT id,project,state,attempts,max_attempts,not_before,lease_until,error FROM tasks ORDER BY rowid DESC LIMIT 100').fetchall()
        print(json.dumps([dict(row) for row in rows], indent=2))
        return
    prompt = Path(args.prompt_file).read_text()
    if not prompt.strip() or len(prompt.encode()) > 65536:
        parser.error('prompt must be nonempty and at most 65536 bytes')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    row = TaskQueue(path).enqueue(args.id, args.project, {'kind': args.kind, 'prompt': prompt, 'data_classification': args.classification})
    print(json.dumps({key: row[key] for key in ['id', 'project', 'state', 'attempts']}))

if __name__ == '__main__':
    main()
