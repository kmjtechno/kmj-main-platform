import hashlib, json, os, re, shutil, subprocess, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "deploy/staging/kmj-main-platform-staging-deploy.sh"
UNIT = ROOT / "deploy/staging/kmj-main-platform-staging-deploy.service"
PROPOSAL = ROOT / "scripts/operations/build-staging-approval-proposal-20261031.py"
KEYS = {"schema", "approvedSha", "expectedCurrentSha", "expectedProductionRelease", "runnerSha256",
        "unitSha256", "backupVerified", "rollbackVerified", "storageVerified", "zeroAdditionalCostVerified"}
OLD, NEW, PROD = "a" * 40, "b" * 40, "platform-574e443a2c75"


class StaticContract(unittest.TestCase):
    def test_unit_is_fixed_and_not_installable(self):
        t = "\n".join(l for l in UNIT.read_text().splitlines() if not l.startswith("#")) + "\n"
        self.assertIn("ExecStart=/usr/bin/bash /usr/local/libexec/kmj-codebridge/kmj-main-platform-staging-deploy.sh\n", t)
        self.assertEqual(len(re.findall(r"^ExecStart=", t, re.M)), 1)
        self.assertNotIn("[Install]", t)
        for line in ("NoNewPrivileges=yes", "ProtectSystem=strict", "Type=oneshot"):
            self.assertIn(line, t)
        self.assertNotIn("/home/kmjprod", t)  # production is never writable from this unit

    def test_runner_has_no_dynamic_execution_or_network(self):
        raw = RUNNER.read_text()
        self.assertTrue(raw.startswith("#!/usr/bin/env bash\n"))
        t = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("#"))
        self.assertIn("set -Eeuo pipefail", t)
        for bad in ("eval ", "curl ", "wget ", "systemctl", "composer", "npm ", "git pull", "git fetch",
                    "rm -rf", "$@", "$*", "${1"):
            self.assertNotIn(bad, t, bad)
        self.assertIsNone(re.search(r"^\s*exec\s+\d*>", raw, re.M), "truncating lock open is forbidden")
        self.assertIn("noclobber", raw)
        self.assertNotIn("/home/kmjprod", re.sub(r"^(PROD=|.*\$PROD|.*prod_target|.*kmjprod/releases).*$", "", t, flags=re.M))

    def test_proposal_is_bound_but_never_approved(self):
        out = subprocess.run(["python3", "-I", str(PROPOSAL), "--approved-sha", NEW, "--expected-current-sha", OLD,
                              "--expected-production-release", PROD], capture_output=True, text=True, check=True).stdout
        p = json.loads(out)
        self.assertEqual(set(p), KEYS)
        self.assertEqual(p["runnerSha256"], hashlib.sha256(RUNNER.read_bytes()).hexdigest())
        self.assertEqual(p["unitSha256"], hashlib.sha256(UNIT.read_bytes()).hexdigest())
        for k in ("backupVerified", "rollbackVerified", "storageVerified", "zeroAdditionalCostVerified"):
            self.assertIs(p[k], False)
        bad = subprocess.run(["python3", "-I", str(PROPOSAL), "--approved-sha", OLD, "--expected-current-sha", OLD,
                              "--expected-production-release", PROD], capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)


class Sandbox(unittest.TestCase):
    """Runs a copy of the runner with its fixed constants pointed at a temp tree (non-root)."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="kmj-stage-"))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.me = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
        self.host = subprocess.run(["hostname", "-s"], capture_output=True, text=True).stdout.strip()
        (self.d / "etc").mkdir(mode=0o755)
        self.rel = self.d / "stage/releases"
        self.rel.mkdir(parents=True)
        (self.d / "stage/htdocs").mkdir()
        (self.d / "prod/releases" / PROD).mkdir(parents=True)
        os.symlink(self.d / "prod/releases" / PROD, self.d / "prod/current")
        self.OLD = self.make_release()
        self.NEW = self.make_release()
        os.symlink(self.rel / self.OLD / "apps/platform", self.d / "stage/htdocs/site")
        (self.d / "unitdir").mkdir(mode=0o755)
        self.unit = self.d / "unitdir/staging.service"
        shutil.copy(UNIT, self.unit)
        os.chmod(self.unit, 0o644)
        self.runner = self.d / "runner.sh"
        self.build_runner()
        self.write_approval()

    n = 0

    def make_release(self, *, env="APP_ENV=staging\nAPP_URL=https://staging.kmjtechno.com\n", manifest="{}"):
        """Create a prepared release dir NAMED by its real git commit sha (what the runner verifies)."""
        Sandbox.n += 1
        tmp = self.rel / f".tmp{Sandbox.n}"
        app = tmp / "apps/platform"
        (app / "public/build").mkdir(parents=True)
        (app / "artisan").write_text("x")
        (app / "public/build/manifest.json").write_text(manifest)
        (app / ".env").write_text(env)
        os.chmod(app / ".env", 0o600)
        subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty",
                        "-m", f"release {Sandbox.n}"], cwd=tmp, check=True)
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp, capture_output=True, text=True).stdout.strip()
        tmp.rename(self.rel / sha)
        return sha

    def build_runner(self):
        t = RUNNER.read_text()
        subs = {
            "APPROVAL=/etc/kmj-codebridge/main-platform-staging-approval.json": f"APPROVAL={self.d}/etc/approval.json",
            "SITE=/home/kmjstage/htdocs/staging.kmjtechno.com": f"SITE={self.d}/stage/htdocs/site",
            "PROD=/home/kmjprod/current": f"PROD={self.d}/prod/current",
            "RELEASES=/home/kmjstage/releases": f"RELEASES={self.rel}",
            "LOCKFILE=/run/lock/kmj-main-platform-staging-deploy.lock": f"LOCKFILE={self.d}/lock",
            "REQUIRE_UID=0": f"REQUIRE_UID={os.getuid()}",
            "ANCHOR=/\n": f"ANCHOR={self.d}\n",
            "UNIT_FILE=/etc/systemd/system/kmj-main-platform-staging-deploy.service": f"UNIT_FILE={self.unit}",
            "STAGE_USER=kmjstage": f"STAGE_USER={self.me}",
            "EXPECTED_HOST=KMJ-elite": f"EXPECTED_HOST={self.host}",
            '"/home/kmjprod/releases/': f'"{self.d}/prod/releases/',
        }
        for a, b in subs.items():
            self.assertIn(a, t, a)
            t = t.replace(a, b)
        self.runner.write_text(t)
        os.chmod(self.runner, 0o700)

    def write_approval(self, **over):
        v = {"schema": "kmj.main-platform.staging-approval.v1", "approvedSha": self.NEW, "expectedCurrentSha": self.OLD,
             "expectedProductionRelease": PROD,
             "runnerSha256": hashlib.sha256(self.runner.read_bytes()).hexdigest(),
             "unitSha256": hashlib.sha256(self.unit.read_bytes()).hexdigest(), "backupVerified": True, "rollbackVerified": True, "storageVerified": True,
             "zeroAdditionalCostVerified": True}
        v.update(over)
        p = self.d / "etc/approval.json"
        if p.exists() or p.is_symlink():
            p.unlink()
        p.write_text(json.dumps({k: v[k] for k in v if v[k] is not None}))
        os.chmod(p, 0o644)

    def run_runner(self, *args):
        r = subprocess.run(["bash", str(self.runner), *args], capture_output=True, text=True,
                           env={"PATH": os.environ["PATH"], "HOME": str(self.d)})
        return r.returncode, r.stdout.strip()

    def site(self):
        return os.readlink(self.d / "stage/htdocs/site")

    def assertBlocked(self, code, out, reason):
        self.assertEqual(code, 2, out)
        self.assertEqual(out, f"KMJ_STAGE_ACTIVATE=BLOCKED_{reason}")
        self.assertEqual(self.site(), str(self.rel / self.OLD / "apps/platform"))  # unchanged on every refusal

    def test_activates_exactly_the_approved_sha_and_is_idempotent(self):
        code, out = self.run_runner()
        self.assertEqual((code, out), (0, f"KMJ_STAGE_ACTIVATE=ACTIVATED sha={self.NEW} previous={self.OLD}"))
        self.assertEqual(self.site(), str(self.rel / self.NEW / "apps/platform"))
        self.assertEqual(self.run_runner(), (0, f"KMJ_STAGE_ACTIVATE=ALREADY_ACTIVE sha={self.NEW}"))
        self.assertEqual(os.readlink(self.d / "prod/current"), str(self.d / "prod/releases" / PROD))

    def test_arguments_are_refused(self):
        self.assertBlocked(*self.run_runner("--sha", self.NEW), "ARGUMENTS")

    def test_missing_symlinked_or_loose_approval(self):
        (self.d / "etc/approval.json").unlink()
        self.assertBlocked(*self.run_runner(), "APPROVAL_MISSING")
        self.write_approval()
        real = self.d / "etc/real.json"
        (self.d / "etc/approval.json").rename(real)
        os.symlink(real, self.d / "etc/approval.json")
        self.assertBlocked(*self.run_runner(), "APPROVAL_MISSING")  # O_NOFOLLOW
        (self.d / "etc/approval.json").unlink(); real.rename(self.d / "etc/approval.json")
        os.chmod(self.d / "etc/approval.json", 0o666)
        self.assertBlocked(*self.run_runner(), "APPROVAL_FILE")

    def test_approval_values_are_strict(self):
        for over, why in (({"approvedSha": self.OLD}, "APPROVAL_VALUES"), ({"backupVerified": False}, "APPROVAL_VALUES"),
                          ({"storageVerified": "true"}, "APPROVAL_VALUES"), ({"unitSha256": None}, "APPROVAL_KEYS"),
                          ({"approvedSha": "B" * 40}, "APPROVAL_VALUES")):
            self.write_approval(**over)
            self.assertBlocked(*self.run_runner(), why)

    def test_runner_must_match_attested_digest(self):
        self.write_approval(runnerSha256="d" * 64)
        self.assertBlocked(*self.run_runner(), "RUNNER_DIGEST")

    def test_production_drift_blocks(self):
        os.unlink(self.d / "prod/current")
        (self.d / "prod/releases/platform-other00000000").mkdir()
        os.symlink(self.d / "prod/releases/platform-other00000000", self.d / "prod/current")
        self.assertBlocked(*self.run_runner(), "PRODUCTION_DRIFT")

    def test_staging_baseline_drift_blocks(self):
        os.unlink(self.d / "stage/htdocs/site")
        other = self.make_release()
        os.symlink(self.rel / other / "apps/platform", self.d / "stage/htdocs/site")
        code, out = self.run_runner()
        self.assertEqual((code, out), (2, "KMJ_STAGE_ACTIVATE=BLOCKED_STAGING_BASELINE_DRIFT"))
        self.assertEqual(self.site(), str(self.rel / other / "apps/platform"))

    def approve(self, sha):
        self.NEW = sha
        self.write_approval(approvedSha=sha)

    def test_candidate_must_be_real_prepared_and_staging_configured(self):
        shutil.rmtree(self.rel / self.NEW)
        self.assertBlocked(*self.run_runner(), "CANDIDATE_MISSING")
        real = self.d / "elsewhere"; real.mkdir()
        os.symlink(real, self.rel / self.NEW)
        self.assertBlocked(*self.run_runner(), "CANDIDATE_MISSING")  # symlinked release dir
        os.unlink(self.rel / self.NEW)
        self.approve(self.make_release(env="APP_ENV=production\nAPP_URL=https://staging.kmjtechno.com\n"))
        self.assertBlocked(*self.run_runner(), "CANDIDATE_NOT_STAGING")
        self.approve(self.make_release(env="APP_ENV=staging\nAPP_URL=https://kmjtechno.com\n"))
        self.assertBlocked(*self.run_runner(), "CANDIDATE_URL")
        self.approve(self.make_release(manifest=""))
        self.assertBlocked(*self.run_runner(), "CANDIDATE_ARTIFACT")

    def test_candidate_git_head_must_equal_approved_sha(self):
        wrong = "f" * 40
        (self.rel / self.NEW).rename(self.rel / wrong)  # directory name no longer equals its git HEAD
        self.approve(wrong)
        self.assertBlocked(*self.run_runner(), "CANDIDATE_SHA")

    def test_loose_env_file_mode_is_refused(self):
        os.chmod(self.rel / self.NEW / "apps/platform/.env", 0o644)
        self.assertBlocked(*self.run_runner(), "CANDIDATE_ENV_MODE")

    # ---- review 6540683745 ----
    def lock(self):
        return self.d / "lock"

    def test_lock_symlink_is_never_followed_or_truncated(self):
        victim = self.d / "victim.txt"
        victim.write_text("precious")
        os.symlink(victim, self.lock())
        self.assertBlocked(*self.run_runner(), "LOCK")
        self.assertEqual(victim.read_text(), "precious")

    def test_lock_hardlink_and_loose_existing_lock(self):
        victim = self.d / "victim2.txt"
        victim.write_text("precious")
        os.link(victim, self.lock())
        self.assertBlocked(*self.run_runner(), "LOCK")
        self.assertEqual(victim.read_text(), "precious")
        os.unlink(self.lock())
        self.lock().write_text("")
        os.chmod(self.lock(), 0o666)  # existing regular lock with loose mode is tightened, run proceeds
        self.assertEqual(self.run_runner()[0], 0)
        self.assertEqual(oct(os.stat(self.lock()).st_mode & 0o777), "0o600")

    @unittest.skipUnless(os.getuid() == 0, "needs root to chown to a foreign uid")
    def test_lock_with_foreign_owner_is_refused(self):
        self.lock().write_text("")
        os.chown(self.lock(), 54321, 54321)
        self.assertBlocked(*self.run_runner(), "LOCK")

    def test_installed_unit_bytes_must_match_approved_digest(self):
        self.unit.write_text(self.unit.read_text() + "# tampered\n")
        self.assertBlocked(*self.run_runner(), "UNIT_DIGEST")

    def test_unit_dropin_extra_execstart_loose_mode_or_missing(self):
        (self.d / "unitdir/staging.service.d").mkdir()
        self.assertBlocked(*self.run_runner(), "UNIT_DROPIN")
        (self.d / "unitdir/staging.service.d").rmdir()
        os.chmod(self.unit, 0o666)
        self.assertBlocked(*self.run_runner(), "UNIT_FILE")
        os.chmod(self.unit, 0o644)
        self.unit.write_text(self.unit.read_text().replace("ExecStart=/usr/bin/bash", "ExecStart=/usr/bin/sh"))
        self.write_approval()  # digest now matches the tampered bytes, ExecStart still must be the fixed line
        self.assertBlocked(*self.run_runner(), "UNIT_EXEC")
        self.unit.unlink()
        self.assertBlocked(*self.run_runner(), "UNIT_FILE")

    def test_already_active_still_validates_the_selected_release(self):
        self.assertEqual(self.run_runner()[0], 0)  # activate NEW
        self.assertEqual(self.run_runner(), (0, f"KMJ_STAGE_ACTIVATE=ALREADY_ACTIVE sha={self.NEW}"))
        (self.rel / self.NEW / "apps/platform/.env").write_text("APP_ENV=production\nAPP_URL=https://staging.kmjtechno.com\n")
        code, out = self.run_runner()
        self.assertEqual((code, out), (2, "KMJ_STAGE_ACTIVATE=BLOCKED_CANDIDATE_NOT_STAGING"))
        (self.rel / self.NEW / "apps/platform/.env").write_text("APP_ENV=staging\nAPP_URL=https://staging.kmjtechno.com\n")
        shutil.rmtree(self.rel / self.NEW / "apps/platform/public/build")
        self.assertEqual(self.run_runner(), (2, "KMJ_STAGE_ACTIVATE=BLOCKED_CANDIDATE_MISSING"))

    def test_writable_or_linked_candidate_chain_is_refused(self):
        app = self.rel / self.NEW / "apps/platform"
        os.chmod(app, 0o777)
        self.assertBlocked(*self.run_runner(), "CANDIDATE_WRITABLE")
        os.chmod(app, 0o755)
        os.chmod(self.rel, 0o777)
        self.assertBlocked(*self.run_runner(), "RELEASES_CHAIN")
        os.chmod(self.rel, 0o755)
        os.chmod(self.d / "stage/htdocs", 0o777)
        self.assertBlocked(*self.run_runner(), "SITE_CHAIN")
        os.chmod(self.d / "stage/htdocs", 0o755)

    def test_symlinked_intermediate_component_is_refused(self):
        real = self.rel / self.NEW
        moved = self.d / "moved"
        real.rename(moved)
        os.symlink(moved, real)  # release dir is now a symlink to a real tree elsewhere
        self.assertBlocked(*self.run_runner(), "CANDIDATE_MISSING")

    def test_nothing_is_modified_outside_the_staging_link(self):
        before = {str(p): p.read_bytes() for p in (self.d / "etc").rglob("*") if p.is_file()}
        self.run_runner()
        after = {str(p): p.read_bytes() for p in (self.d / "etc").rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(os.readlink(self.d / "prod/current"), str(self.d / "prod/releases" / PROD))


if __name__ == "__main__":
    unittest.main()
