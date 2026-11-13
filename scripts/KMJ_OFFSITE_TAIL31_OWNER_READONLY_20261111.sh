#!/bin/bash -p
set -Eeuo pipefail
umask 077
F=/srv/kmj-codebridge-projects/kmj-main-platform/scripts/KMJ_OFFSITE_LEGACY_SFTP_GUARDED_REPAIR_20261111.py
T=$(/usr/bin/mktemp /root/kmj-tail31-verified.XXXXXXXX)
trap '/usr/bin/rm -f -- "$T"' EXIT
/usr/bin/install -m 600 -- "$F" "$T"
printf '%s  %s\n' 142ea8eb22904ec8bf5f165a2ec04049893f4d85aff50967a185d62f7cf13249 "$T" | /usr/bin/sha256sum -c -
/usr/bin/python3 -I -B - "$T" <<'PY'
import importlib.util, os, re, socket, sys
from importlib.machinery import SourceFileLoader
if os.geteuid() != 0 or socket.gethostname().split('.')[0] != 'KMJ-elite':
    raise SystemExit('BLOCKED_ROOT_HOST')
# mktemp has no .py suffix. Use the explicit source loader only after
# sha256sum -c has verified these exact bytes above.
loader = SourceFileLoader('kmj_pinned_readonly', sys.argv[1])
spec = importlib.util.spec_from_loader(loader.name, loader)
if spec is None or spec.loader is None:
    raise SystemExit('BLOCKED_VERIFIED_SOURCE_LOADER')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    rows = module.check_legacy().decode('utf-8', 'strict').splitlines()
    if len(rows) != 31:
        raise ValueError('SOURCE_SHAPE')
    assign, transfer, trailing = (row.strip() for row in rows[28:31])
    varmatch = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)=(.*)', assign)
    if varmatch is None or not re.match(r'^(?:/usr/bin/)?rsync(?:\s|$)', transfer):
        raise ValueError('REMOTE_TAIL_SHAPE')
    variable, value = varmatch.groups()
    cmd = 'OTHER'
    for pattern, category in (
        (r'^(?:echo|printf)(?:\s|$)', 'STATUS_PRINT'),
        (r'^(?:exit|return)(?:\s|$)', 'EXIT_OR_RETURN'),
        (r'^(?:rm|rmdir|shred|unlink)(?:\s|$)', 'LOCAL_CLEANUP'),
        (r'^(?:sha256sum|stat|test)(?:\s|$)', 'READONLY_CHECK'),
        (r'^(?:ssh|rsync|scp|sftp)(?:\s|$)', 'REMOTE_COMMAND'),
        (r'^(?:if|then|fi|for|while|do|done|case|esac|trap)\b', 'SHELL_CONTROL'),
        (r'^[A-Za-z_][A-Za-z0-9_]*=', 'VARIABLE_ASSIGNMENT'),
    ):
        if re.match(pattern, trailing):
            cmd = category
            break
    if trailing in ('true', ':'):
        cmd = 'NOOP'
    report = {
        'LINE29_VARIABLE': 'SSH_NAMED' if re.search(r'SSH|RSYNC', variable, re.I) else 'OTHER_NAMED',
        'LINE29_COMMAND_SUBSTITUTION': 'YES' if '$(' in value or chr(96) in value else 'NO',
        'LINE30_USES_VARIABLE29': 'YES' if re.search(r'\$(?:\{' + re.escape(variable) + r'\}|\b' + re.escape(variable) + r'\b)', transfer) else 'NO',
        'LINE30_HAS_RSH_FLAG': 'YES' if re.search(r'(?<!\S)(?:-e|--rsh)(?:\s|=|$)', transfer) else 'NO',
        'LINE30_DELETE_FLAG': 'YES' if re.search(r'(?<!\S)--delete(?:\s|=|$)', transfer) else 'NO',
        'LINE31_CLASS': cmd,
        'LINE31_COMMAND_SUBSTITUTION': 'YES' if '$(' in trailing or chr(96) in trailing else 'NO',
        'LINE31_REFERENCES_EXIT_STATUS': 'YES' if re.search(r'\$\?|\bPIPESTATUS\b', trailing) else 'NO',
        'LINE31_REFERENCES_REMOTE': 'YES' if re.search(r'(?<![A-Za-z0-9_-])(?:ssh|rsync|sftp|scp)\b', trailing) else 'NO',
        'LINE31_HAS_SEPARATOR': 'YES' if any(x in trailing for x in (';', '|', '&&', '||')) else 'NO',
        'AUTO_APPLY': 'NOT_ALLOWED',
        'SERVICE_EXECUTION': 'NOT_RUN',
        'UNIT_MUTATION': 'NONE',
    }
    for key, item in report.items():
        assert re.fullmatch(r'[A-Z0-9_]+', key) and re.fullmatch(r'[A-Z0-9_]+', item)
        print(f'{key}={item}')
    # Also show the current EFFECTIVE unit shape, not its raw ExecStart,
    # because the latest service result has changed since the earlier audit.
    attrs = {key: module.prop(key) for key in
             ('LoadState', 'User', 'Type', 'DropInPaths', 'ExecStart',
              'ActiveState', 'Result', 'ExecMainStatus')}
    exec_text = attrs['ExecStart'] or ''
    paths = re.findall(r'\bpath=([^\s;]+)', exec_text)
    repair_argv = str(module.REPAIR_FILE) in exec_text and '--run' in exec_text
    current_executable = ('LEGACY' if len(paths) == 1 and paths[0] == str(module.LEGACY)
                          else 'REPAIR_CANDIDATE' if len(paths) == 1
                               and paths[0] == '/usr/bin/python3' and repair_argv
                          else 'UNKNOWN_OR_OTHER')
    state = {
        'CURRENT_UNIT_LOADED': 'YES' if attrs['LoadState'] == 'loaded' else 'NO_OR_UNKNOWN',
        'CURRENT_UNIT_ROOT': 'YES' if attrs['User'] in ('', 'root') else 'NO_OR_UNKNOWN',
        'CURRENT_UNIT_ONESHOT': 'YES' if attrs['Type'] == 'oneshot' else 'NO_OR_UNKNOWN',
        'CURRENT_DROPINS': 'NONE' if attrs['DropInPaths'] == '' else
                           'PRESENT' if attrs['DropInPaths'] else 'UNKNOWN',
        'CURRENT_EXECSTART': current_executable,
        'CURRENT_ACTIVE': 'FAILED' if attrs['ActiveState'] == 'failed' else
                          'INACTIVE' if attrs['ActiveState'] == 'inactive' else 'OTHER',
        'CURRENT_RESULT': 'EXIT_CODE' if attrs['Result'] == 'exit-code' else
                          'SUCCESS' if attrs['Result'] == 'success' else 'OTHER',
        'CURRENT_LAST_EXIT': str(attrs['ExecMainStatus']) if attrs['ExecMainStatus'] in ('0','3','255')
                             else 'OTHER_OR_UNKNOWN',
    }
    for key, item in state.items():
        if not re.fullmatch(r'[A-Z0-9_]+', item):
            raise ValueError('UNEXPECTED_PROPERTY_ENUM')
        print(f'{key}={item}')
    print('TAIL31=READ_ONLY_COMPLETE')
except (OSError, ValueError, UnicodeError):
    print('TAIL31=BLOCKED_PINNED_SOURCE_OR_SHAPE')
    raise SystemExit(3)
PY
