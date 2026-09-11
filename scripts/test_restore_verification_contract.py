from __future__ import annotations

import os
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify_backup_bundle.sh"


def executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_raw:
        tmp = Path(tmp_raw)
        fake_bin = tmp / "bin"
        payload = tmp / "payload"
        identity = tmp / "identity.txt"
        encrypted = tmp / "backup.tar.gz.age"
        fake_bin.mkdir()
        payload.mkdir()
        identity.write_text("AGE-SECRET-KEY-TEST\n", encoding="utf-8")

        (payload / "database.dump").write_bytes(b"mock-postgres-archive")
        storage_source = tmp / "storage-source"
        storage_source.mkdir()
        (storage_source / "proof.txt").write_text("restore-contract", encoding="utf-8")
        with tarfile.open(payload / "storage.tar.gz", "w:gz") as archive:
            archive.add(storage_source / "proof.txt", arcname="storage/app/proof.txt")
        (payload / "metadata.txt").write_text("git_sha=test\n", encoding="utf-8")
        subprocess.run(
            ["sha256sum", "database.dump", "storage.tar.gz", "metadata.txt"],
            cwd=payload,
            text=True,
            stdout=(payload / "SHA256SUMS").open("w", encoding="utf-8"),
            check=True,
        )
        bundle = tmp / "bundle.tar.gz"
        with tarfile.open(bundle, "w:gz") as archive:
            for name in ("database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS"):
                archive.add(payload / name, arcname=name)
        encrypted.write_bytes(bundle.read_bytes())

        executable(
            fake_bin / "age",
            "#!/usr/bin/env bash\nset -euo pipefail\nout=''\nin=''\nwhile [ $# -gt 0 ]; do case \"$1\" in -d) shift;; -i) shift 2;; -o) out=\"$2\"; shift 2;; *) in=\"$1\"; shift;; esac; done\ncp \"$in\" \"$out\"\n",
        )
        executable(fake_bin / "pg_restore", "#!/usr/bin/env bash\nset -euo pipefail\n[ \"$1\" = '--list' ]\n[ -f \"$2\" ]\n")

        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}:{env['PATH']}"
        env["BACKUP_AGE_IDENTITY"] = str(identity)
        run = subprocess.run(
            ["bash", str(VERIFY), str(encrypted)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        output = run.stdout + run.stderr
        assert run.returncode == 0, output
        assert "Backup verification PASS" in output
        assert "AGE-SECRET-KEY-TEST" not in output

    print("Restore verification contract test PASS")


if __name__ == "__main__":
    main()
