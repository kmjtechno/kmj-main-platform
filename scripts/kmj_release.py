#!/usr/bin/env python3
"""Fixed cd958 check/deploy facade. Never repairs storage or writes approval.

Source proposal only: root installation and real-host review remain required.
Deployment delegates exclusively to the existing guarded release unit.
"""
import argparse
import hashlib
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile

TARGET = 'cd9580701d3cea19d7d4e4c96ebe70c0553fbf37'
CURRENT = 'platform-574e443a2c75'
DOCTOR = Path('/srv/kmj-codebridge-projects/kmj-main-platform/scripts/KMJ_CD958_RELEASE_READINESS_DOCTOR_V2_20261105.py')
DOCTOR_HASH = '2facb3090bcb38a8e8967fbc8d47a6a0a350bc0def1725e88cf0affc4bf9d481'
UNIT = 'kmj-main-platform-production-release.service'
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/nonexistent', 'LC_ALL': 'C'}
REQUIRED = {
    'TARGET_SHA': TARGET, 'CURRENT_RELEASE': CURRENT,
    'CANDIDATE': 'PASS', 'CANDIDATE_UI_BUNDLE': 'PASS',
    'CANDIDATE_RUNTIME_ENV': 'PRESENT', 'CANDIDATE_NGINX_ACCESS': 'PASS',
    'BACKUP_WITNESS': 'PASS', 'APPROVAL': 'PASS',
    'RELEASE_UNIT': 'INSTALLED', 'RELEASE_READINESS': 'READY_TO_ACTIVATE',
    'PRODUCTION_CHANGED': 'NO',
}

def ready(report, returncode):
    if returncode != 0:
        return False
    values = {}
    for line in report.splitlines():
        key, sep, value = line.partition('=')
        if not sep or key in values or key == 'BLOCKER':
            return False
        values[key] = value
    return all(values.get(key) == value for key, value in REQUIRED.items())

def verify_source(data):
    if hashlib.sha256(data).hexdigest() != DOCTOR_HASH:
        raise ValueError('READINESS_SOURCE_HASH_MISMATCH')
    return data

def check():
    # Hash the exact bytes copied to a root-private snapshot before execution;
    # no import, execution or trust of a mutable project path as root.
    fd = os.open(DOCTOR, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 131072:
            raise ValueError('READINESS_SOURCE_UNSAFE')
        data = verify_source(os.read(fd, 131073))
    finally:
        os.close(fd)
    with tempfile.TemporaryDirectory(prefix='kmj-release-check-', dir='/root') as temp:
        snapshot = Path(temp) / 'readiness.py'
        with snapshot.open('xb') as out:
            out.write(data)
        snapshot.chmod(0o600)
        result = subprocess.run(['/usr/bin/python3', '-I', '-B', str(snapshot), TARGET],
                                env=ENV, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=180, check=False)
    # Doctor emits fixed diagnostic enums. Never forward raw stderr or secrets.
    for line in result.stdout.splitlines():
        if line.startswith(('TARGET_SHA=', 'CURRENT_RELEASE=', 'CANDIDATE=',
                            'CANDIDATE_UI_BUNDLE=', 'CANDIDATE_RUNTIME_ENV=',
                            'CANDIDATE_NGINX_ACCESS=', 'BACKUP_WITNESS=',
                            'APPROVAL=', 'RELEASE_READINESS=', 'BLOCKER=')):
            print(line)
    allowed = ready(result.stdout, result.returncode)
    print('GUARDED_REQUEST_ALLOWED=' + ('YES' if allowed else 'NO'))
    if not allowed:
        print('NEXT=Resolve reported gates; storage cutover requires its separate reviewed operator workflow.')
    print('OFFSITE_AND_AUTHENTICATED_QA=NOT_ATTESTED_BY_THIS_LAUNCHER')
    return allowed

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'deploy'))
    args = parser.parse_args(argv)
    if os.geteuid() != 0 or socket.gethostname().split('.')[0] != 'KMJ-elite':
        print('RESULT=BLOCKED_ROOT_ON_KMJ_ELITE_REQUIRED')
        return 2
    os.umask(0o077)
    activation_requested = False
    try:
        if not check():
            return 2
        if args.action == 'check':
            print('RESULT=CHECK_PASSED_NO_DEPLOYMENT')
            return 0
        # No approval edits, override flags, root migration logic, arbitrary
        # command/target, reset or service bypass. The installed controller
        # rechecks protected approval, live pointer and evidence under its lock.
        activation_requested = True
        result = subprocess.run(['/usr/bin/systemctl', 'start', UNIT], env=ENV,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=600, check=False)
        if result.returncode:
            print('RESULT=GUARDED_UNIT_FAILED_VERIFY_CURRENT_STATE')
            return 3
        print('RESULT=GUARDED_UNIT_FINISHED_LIVE_HEALTH_NOT_YET_VERIFIED')
        print('NEXT=Verify deployed SHA, HTTPS, authenticated application and rollback health.')
        return 0
    except subprocess.TimeoutExpired:
        if not activation_requested:
            print('RESULT=READINESS_TIMEOUT_NO_ACTIVATION_REQUEST')
            return 2
        # Timing out systemctl does not prove the underlying unit stopped.
        print('RESULT=TIMEOUT_UNIT_STATE_UNKNOWN_DO_NOT_RETRY_BLINDLY')
        return 3
    except (OSError, ValueError, UnicodeError):
        print('RESULT=CHECK_FAILED_NO_ACTIVATION_REQUEST')
        return 2

if __name__ == '__main__':
    sys.exit(main())
