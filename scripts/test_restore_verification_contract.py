from __future__ import annotations

import io
import os
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify_backup_bundle.sh"
EXPECTED = ("database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS")


def executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def make_bundle(payload: Path, output: Path, *,
                extra_member: str | None = None,
                symlink: str | None = None,
                duplicate: bool = False) -> None:
    with tarfile.open(output, "w:gz") as bundle:
        for name in EXPECTED:
            if name == symlink:
                member = tarfile.TarInfo(name)
                member.type = tarfile.SYMTYPE
                member.linkname = "../../etc/passwd"
                bundle.addfile(member)
            else:
                bundle.add(payload / name, arcname=name)
        if duplicate:
            bundle.add(payload / "database.dump", arcname="database.dump")
        if extra_member is not None:
            data = b"never written outside temporary verification root"
            member = tarfile.TarInfo(extra_member)
            member.size = len(data)
            bundle.addfile(member, io.BytesIO(data))


def check_case(name: str, encrypted: Path, env: dict[str, str],
               expected_success: bool) -> None:
    run = subprocess.run(
        ["bash", str(VERIFY), str(encrypted)],
        env=env, text=True, capture_output=True, check=False,
        timeout=30,
    )
    output = run.stdout + run.stderr
    if expected_success:
        assert run.returncode == 0, f"{name}: {output}"
        assert "Backup verification PASS" in output, name
        assert "bounded backup archive member" in output, name
        assert "BACKUP_ARCHIVE_INTEGRITY=PASS" in output, name
        assert "INDEPENDENT_OFFSITE_RETRIEVAL=NOT_VERIFIED" in output, name
        assert "DATABASE_RESTORE=NOT_RUN" in output, name
        assert "APPLICATION_RECOVERY=NOT_VERIFIED" in output, name
        assert "DATABASE_RESTORE=PASS" not in output, name
    else:
        assert run.returncode != 0, f"{name}: invalid archive passed verification"
        assert "Backup verification PASS" not in output, name
        assert "BACKUP_ARCHIVE_INTEGRITY=PASS" not in output, name
    assert "AGE-SECRET-KEY-TEST" not in output, name


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_raw:
        tmp = Path(tmp_raw)
        fake_bin = tmp / "bin"
        payload = tmp / "payload"
        identity = tmp / "identity.txt"
        fake_bin.mkdir()
        payload.mkdir()
        identity.write_text("AGE-SECRET-KEY-TEST\n", encoding="utf-8")

        (payload / "database.dump").write_bytes(b"mock-postgres-archive")
        storage = payload / "storage.tar.gz"
        with tarfile.open(storage, "w:gz") as archive:
            data = b"restore-contract"
            member = tarfile.TarInfo("storage/app/proof.txt")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        (payload / "metadata.txt").write_text("git_sha=test\n", encoding="utf-8")
        with (payload / "SHA256SUMS").open("w", encoding="utf-8") as out:
            subprocess.run(
                ["sha256sum", "database.dump", "storage.tar.gz", "metadata.txt"],
                cwd=payload, text=True, stdout=out, check=True,
            )

        executable(
            fake_bin / "age",
            '#!/usr/bin/env bash\nset -euo pipefail\n'
            'out=""\nin=""\nwhile [ $# -gt 0 ]; do case "$1" in '
            '-d) shift;; -i) shift 2;; -o) out="$2"; shift 2;; '
            '*) in="$1"; shift;; esac; done\ncp "$in" "$out"\n',
        )
        executable(
            fake_bin / "pg_restore",
            '#!/usr/bin/env bash\nset -euo pipefail\n'
            '[ "$1" = "--list" ]\n[ -f "$2" ]\n',
        )
        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}:{env['PATH']}"
        env["BACKUP_AGE_IDENTITY"] = str(identity)

        valid = tmp / "valid.tar.gz.age"
        make_bundle(payload, valid)
        check_case("valid", valid, env, True)

        traversal = tmp / "traversal.tar.gz.age"
        make_bundle(payload, traversal, extra_member="../../outside.txt")
        check_case("outer path traversal", traversal, env, False)
        assert not (tmp.parent / "outside.txt").exists()

        link = tmp / "symlink.tar.gz.age"
        make_bundle(payload, link, symlink="database.dump")
        check_case("symlink payload", link, env, False)

        duplicate = tmp / "duplicate.tar.gz.age"
        make_bundle(payload, duplicate, duplicate=True)
        check_case("duplicate member", duplicate, env, False)

        original_manifest = (payload / "SHA256SUMS").read_text(encoding="utf-8")
        (payload / "SHA256SUMS").write_text(
            original_manifest.replace("database.dump", "../../etc/passwd"),
            encoding="utf-8",
        )
        invalid_manifest = tmp / "checksum-path.tar.gz.age"
        make_bundle(payload, invalid_manifest)
        check_case("checksum traversal", invalid_manifest, env, False)
        (payload / "SHA256SUMS").write_text(
            original_manifest, encoding="utf-8"
        )

        with tarfile.open(storage, "w:gz") as archive:
            m = tarfile.TarInfo("storage/app/escape")
            m.type = tarfile.SYMTYPE
            m.linkname = "../../../../etc/passwd"
            archive.addfile(m)
        with (payload / "SHA256SUMS").open("w", encoding="utf-8") as out:
            subprocess.run(
                ["sha256sum", "database.dump", "storage.tar.gz", "metadata.txt"],
                cwd=payload, text=True, stdout=out, check=True,
            )
        inner_link = tmp / "inner-link.tar.gz.age"
        make_bundle(payload, inner_link)
        check_case("storage symlink", inner_link, env, False)

    print("Restore verification contract test PASS (1 valid, 5 unsafe rejected)")


if __name__ == "__main__":
    main()
