#!/usr/bin/env python3
"""Fixed-unit, read-only diagnostic for KMJ offsite backup exit 3.

Source-only until separately pinned, reviewed and installed by an operator.
No caller-controlled paths/commands, backup execution, secret output or release approval.
"""
import json
import os
import re
import subprocess
import sys

UNIT = 'kmj-elite-offsite-backup.service'
SCHEMA = 'KMJ_OFFSITE_EXIT3_DIAGNOSTIC_V1'
PROPERTIES = ('LoadState', 'ActiveState', 'SubState', 'Result', 'ExecMainStatus', 'InvocationID')
SYSTEMCTL = '/usr/bin/systemctl'
JOURNALCTL = '/usr/bin/journalctl'
HEX32 = re.compile(r'(?i)^[0-9a-f]{32}$')
ENUM = re.compile(r'^[A-Za-z0-9_.-]{1,40}$')


def capture(runner, argv, limit=65536):
    try:
        result = runner(argv, capture_output=True, text=True, timeout=12, check=False)
        if result.returncode != 0 or not isinstance(result.stdout, str) or len(result.stdout) > limit:
            return None
        return result.stdout
    except (OSError, subprocess.TimeoutExpired, ValueError, UnicodeError):
        return None


def snapshot(runner):
    argv = [SYSTEMCTL, 'show', UNIT, '--no-pager'] + [f'--property={p}' for p in PROPERTIES]
    output = capture(runner, argv, 4096)
    if output is None:
        return None
    result = {}
    for line in output.splitlines():
        key, sep, value = line.partition('=')
        if not sep or key not in PROPERTIES or key in result:
            return None
        result[key] = value.strip()
    if set(result) != set(PROPERTIES):
        return None
    for key in PROPERTIES[:4]:
        if not ENUM.fullmatch(result[key]):
            return None
    if not re.fullmatch(r'(?:[0-9]{1,3}|unknown)', result['ExecMainStatus']):
        return None
    value = result['InvocationID']
    if value and not HEX32.fullmatch(value):
        return None
    return result


def classify(log):
    # Only fixed categories leave this function. Never echo matched text.
    if re.search(r'\b(?:KMJ_[A-Z0-9_]+|RESULT)\s*=\s*BLOCKED_[A-Z0-9_]+\b', log, re.I):
        return 'GUARDED_PREFLIGHT_REJECTED'
    if re.search(r'No space left on device|Disk quota exceeded|quota exceeded', log, re.I):
        return 'STORAGE_CAPACITY'
    if re.search(r'Permission denied \(publickey\)|Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED', log, re.I):
        return 'REMOTE_SSH_TRUST_OR_AUTH'
    if re.search(r'Connection refused|Connection timed out|Could not resolve host|Network is unreachable|No route to host', log, re.I):
        return 'REMOTE_CONNECTIVITY'
    if re.search(r'PGDMP|pg_dump: error|invalid archive|PostgreSQL dump', log, re.I):
        return 'DATABASE_DUMP_OR_INTEGRITY'
    if re.search(r'age: error|encryption failed|ciphertext.*(invalid|missing)', log, re.I):
        return 'ENCRYPTION_OR_CIPHER'
    if re.search(r'File exists|already exists|collision', log, re.I):
        return 'OUTPUT_COLLISION'
    if re.search(r'No such file or directory|command not found|ModuleNotFoundError', log, re.I):
        return 'MISSING_SOURCE_OR_TOOL'
    if re.search(r'Permission denied|Read-only file system|Operation not permitted', log, re.I):
        return 'LOCAL_PERMISSION_OR_FILESYSTEM'
    return 'UNKNOWN_EXIT3_CAUSE'


def diagnose(runner, getuid):
    base = {
        'schema': SCHEMA, 'unit': UNIT, 'exit_status': 'unknown',
        'journal_scope': 'UNAVAILABLE', 'journal_lines_scanned': 0,
        'failure_class': 'UNKNOWN_EXIT3_CAUSE', 'mutations': 'NONE',
        'backup_validity': 'NOT_ATTESTED', 'independent_restore': 'NOT_VERIFIED',
        'production_release': 'NOT_APPROVED', 'raw_journal_exposed': False,
    }
    if getuid() != 0:
        base['failure_class'] = 'ROOT_DIAGNOSTIC_REQUIRED'
        return base
    first = snapshot(runner)
    if first is None:
        base['failure_class'] = 'UNIT_METADATA_UNAVAILABLE'
        return base
    base['exit_status'] = first['ExecMainStatus']
    if first['Result'] != 'exit-code' or first['ExecMainStatus'] != '3':
        base['failure_class'] = 'NOT_EXIT3_INVOCATION'
        return base
    invocation = first['InvocationID']
    if not HEX32.fullmatch(invocation or '') or invocation == '0' * 32:
        return base
    log = capture(runner, [JOURNALCTL, '--no-pager', '-o', 'cat', '-n', '200',
                           f'_SYSTEMD_INVOCATION_ID={invocation}'])
    if log is None:
        return base
    second = snapshot(runner)
    # Do not classify logs from a different or changed service invocation.
    if second != first:
        base['failure_class'] = 'INVOCATION_CHANGED'
        return base
    base['journal_scope'] = 'EXACT_INVOCATION'
    base['journal_lines_scanned'] = min(200, len(log.splitlines()))
    base['failure_class'] = classify(log)
    return base


def main():
    if len(sys.argv) != 1:
        print('BLOCKED_NO_ARGUMENTS', file=sys.stderr)
        return 2
    report = diagnose(subprocess.run, os.geteuid)
    print(json.dumps(report, sort_keys=True, separators=(',', ':')))
    return 0 if report['journal_scope'] == 'EXACT_INVOCATION' else 3


if __name__ == '__main__':
    raise SystemExit(main())
