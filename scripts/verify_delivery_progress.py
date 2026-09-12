from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / 'apps/platform/resources/js/data/delivery-progress.ts'
MATERIAL_PREFIXES = (
    'apps/platform/app/',
    'apps/platform/database/',
    'apps/platform/routes/',
    'packages/',
    'services/license-core/',
    'controller/',
    'contracts/',
)


def changed_files(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ['git', 'diff', '--name-only', f'{base}...{head}'],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    source = PROGRESS.read_text(encoding='utf-8')
    blocks = re.findall(r'\{\n(?P<body>.*?\n    \},)', source, flags=re.S)
    verified = [block for block in blocks if "state: 'verified'" in block]
    if not verified:
        raise SystemExit('delivery progress must contain verified milestones')
    for block in verified:
        if 'evidence:' not in block:
            raise SystemExit('every verified delivery milestone requires evidence')

    base = os.getenv('KMJ_PROGRESS_BASE_SHA', '').strip()
    head = os.getenv('KMJ_PROGRESS_HEAD_SHA', '').strip()
    if base and head:
        files = changed_files(base, head)
        material = any(path.startswith(MATERIAL_PREFIXES) for path in files)
        progress_changed = str(PROGRESS.relative_to(ROOT)).replace('\\', '/') in files
        if material and not progress_changed:
            raise SystemExit(
                'material platform capability changed without updating '
                'apps/platform/resources/js/data/delivery-progress.ts'
            )
    print(f'KMJ delivery progress verification PASS ({len(verified)} verified milestones)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
