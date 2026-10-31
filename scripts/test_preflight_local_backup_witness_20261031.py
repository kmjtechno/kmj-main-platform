import importlib.util, io, os, tempfile, unittest, contextlib
from pathlib import Path

spec = importlib.util.spec_from_file_location("pf", Path(__file__).resolve().parent / "operations/preflight-local-backup-witness-20261031.py")
pf = importlib.util.module_from_spec(spec); spec.loader.exec_module(pf)
SHA = "a" * 40
CUR = "platform-574e443a2c75"


class FakeEnv(pf.Env):
    def __init__(self, base, **o):
        self.root = base / "kmjprod"; self.backup_dir = base / "backups"; self.lock = base / "lock"
        self.pg_glob_dir = base / "pg"
        self.o = {**dict(root=True, host="KMJ-elite", head=SHA, active=True, free=99999999, tools=True), **o}
    def is_root(self): return self.o["root"]
    def hostname(self): return self.o["host"]
    def which(self, n): return "/usr/bin/" + n if self.o["tools"] else None
    def service_active(self, u): return self.o["active"]
    def free_kib(self, p): return self.o["free"]
    def candidate_head(self, d): return self.o["head"]


def build(base, **o):
    env = FakeEnv(base, **o)
    rel = env.root / "releases"
    (rel / CUR / "apps/platform/storage/app").mkdir(parents=True); (rel / CUR / "apps/platform/vendor").mkdir()
    (rel / CUR / "apps/platform/.env").write_text("x"); (rel / CUR / "apps/platform/vendor/autoload.php").write_text("x")
    (rel / ("platform-" + SHA[:12]) / ".git").mkdir(parents=True)
    os.symlink(rel / CUR, env.root / "current")
    env.backup_dir.mkdir(); env.pg_glob_dir.joinpath("16/bin").mkdir(parents=True)
    for b in pf.PG_BINS:
        p = env.pg_glob_dir / "16/bin" / b; p.write_text("#!/bin/sh\n"); p.chmod(0o755)
    return env


def run(env):
    return pf.build_record(env, SHA, CUR)


class Tests(unittest.TestCase):
    def setUp(self): self.d = tempfile.TemporaryDirectory(); self.base = Path(self.d.name)
    def tearDown(self): self.d.cleanup()

    def test_ready_when_everything_present(self):
        r = run(build(self.base))
        # backup_dir is owned by the test user, not uid 0, so only that check may fail when unprivileged
        expected_fail = [] if os.getuid() == 0 else ["backup_dir_real_root_owned"]
        self.assertEqual(r["failed"], expected_fail)
        self.assertFalse(r["backupCreated"] or r["restoreVerified"] or r["productionChanged"] or r["approvalImplied"])

    def test_each_blocker_is_reported(self):
        cases = [
            (dict(root=False), "root_user"), (dict(host="other"), "host_is_KMJ_elite"),
            (dict(head="b" * 40), "candidate_head_equals_sha"), (dict(active=False), "nginx_active"),
            (dict(free=1), "free_space_over_12GiB"), (dict(tools=False), "tool_git"),
        ]
        for opts, name in cases:
            with self.subTest(name):
                self.assertIn(name, run(build(Path(tempfile.mkdtemp()), **opts))["failed"])

    def test_existing_evidence_blocks(self):
        env = build(self.base)
        (env.backup_dir / ("pre-deploy-" + SHA[:12] + ".json")).write_text("{}")
        self.assertIn("witness_absent", run(env)["failed"])

    def test_wrong_current_release_blocks(self):
        env = build(self.base)
        self.assertIn("current_matches_expected_release", pf.build_record(env, SHA, "platform-000000000000")["failed"])

    def test_target_equal_current_blocks(self):
        self.assertIn("target_differs_from_current", pf.build_record(build(self.base), "574e443a2c75" + "0" * 28, CUR)["failed"])

    def test_current_symlink_escape_blocks(self):
        env = build(self.base)
        (env.root / "current").unlink(); os.symlink(self.base, env.root / "current")
        self.assertIn("current_inside_releases", run(env)["failed"])

    def test_lock_planted_symlink_or_foreign_owner_blocks(self):
        env = build(self.base); os.symlink(self.base, env.lock)
        self.assertIn("release_lock_absent_or_root_regular", run(env)["failed"])

    def test_nothing_is_written_next_to_production(self):
        env = build(self.base)
        before = sorted(p.relative_to(self.base) for p in self.base.rglob("*"))
        run(env)
        self.assertEqual(before, sorted(p.relative_to(self.base) for p in self.base.rglob("*")))

    def test_cli_rejects_bad_ids_and_never_writes_when_not_root(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(pf.main(["--candidate-sha", "xyz", "--expected-release", CUR]), 2)
            self.assertEqual(pf.main(["--candidate-sha", SHA, "--expected-release", "../x"]), 2)
            rc = pf.main(["--candidate-sha", SHA, "--expected-release", CUR, "--receipt", str(self.base / "r.json")], env=build(self.base, root=False))
        self.assertEqual(rc, 2); self.assertFalse((self.base / "r.json").exists())
        self.assertIn("CANDIDATE_SHA_INVALID", out.getvalue()); self.assertIn("EXPECTED_RELEASE_INVALID", out.getvalue())

    def test_source_has_no_mutating_commands(self):
        src = (Path(__file__).resolve().parent / "operations/preflight-local-backup-witness-20261031.py").read_text()
        for bad in ("systemctl restart", "systemctl start", "pg_dump(", "rmtree", "shell=True", "os.system", "curl", "ssh "):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
