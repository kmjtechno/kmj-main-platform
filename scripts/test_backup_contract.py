from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / "scripts" / "backup_platform.sh"


def executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_raw:
        tmp = Path(tmp_raw)
        fake_bin = tmp / "bin"
        app_root = tmp / "platform"
        storage = app_root / "storage" / "app"
        marker = tmp / "rclone.marker"
        fake_bin.mkdir()
        storage.mkdir(parents=True)
        (storage / "proof.txt").write_text("backup-contract", encoding="utf-8")

        executable(
            fake_bin / "pg_dump",
            "#!/usr/bin/env bash\nset -euo pipefail\nfor a in \"$@\"; do case \"$a\" in --file=*) printf 'mock-db' > \"${a#--file=}\";; esac; done\n",
        )
        executable(
            fake_bin / "age",
            "#!/usr/bin/env bash\nset -euo pipefail\nout=''\nin=''\nwhile [ $# -gt 0 ]; do case \"$1\" in -o) out=\"$2\"; shift 2;; -r) shift 2;; *) in=\"$1\"; shift;; esac; done\ncp \"$in\" \"$out\"\n",
        )
        executable(
            fake_bin / "rclone",
            "#!/usr/bin/env bash\nset -euo pipefail\nprintf '%s\\n' \"$*\" > \"$FAKE_REMOTE_MARKER\"\n",
        )

        secret = "postgresql://user:super-secret@example.invalid/kmj"
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "APP_ROOT": str(app_root),
                "BACKUP_DATABASE_URL": secret,
                "BACKUP_REMOTE": "mock:kmj-platform/staging",
                "BACKUP_AGE_RECIPIENT": "age1testrecipient",
                "BACKUP_TIER": "daily",
                "FAKE_REMOTE_MARKER": str(marker),
            }
        )

        run = subprocess.run(
            ["bash", str(BACKUP)], env=env, text=True, capture_output=True, check=False
        )
        output = run.stdout + run.stderr
        assert run.returncode == 0, output
        assert marker.exists(), output
        assert "mock:kmj-platform/staging/daily/" in marker.read_text(encoding="utf-8")
        assert secret not in output
        assert "super-secret" not in output
        assert "Backup uploaded successfully" in output

    print("Backup contract test PASS")


if __name__ == "__main__":
    main()
