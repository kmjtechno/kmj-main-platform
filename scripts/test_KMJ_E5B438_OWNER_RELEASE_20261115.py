"""Non-executing exact-source acceptance for KMJ E5B438 owner release.

Never starts a service, deploys, runs DB migrations, uploads backups,
downloads network source, or reads production credentials.
"""
from pathlib import Path
import re
import subprocess
import unittest

SRC=Path(__file__).with_name("KMJ_E5B438_OWNER_RELEASE_20261115.sh")
EXPECTED="e5b43872bc031eb4b074a1e318abd80949c321d8"
OLD="platform-e715829a56cc"
NEW="platform-e5b43872bc03"

def text():
    return SRC.read_text(encoding="utf-8")

class E5B438OwnerReleaseOffline(unittest.TestCase):
    def test_shell_syntax_exact(self):
        r=subprocess.run(["bash","-n",str(SRC)],capture_output=True,timeout=10,check=False)
        self.assertEqual(r.returncode,0,r.stderr.decode(errors="replace"))

    def test_exact_reviewed_main_sha_expected_live_and_rollback(self):
        s=text()
        self.assertIn("readonly SHA="+EXPECTED,s)
        self.assertIn("readonly SHORT=e5b43872bc03",s)
        self.assertIn("readonly OLD_RELEASE="+OLD,s)
        self.assertIn('readonly NEW_RELEASE="platform-$SHORT"',s)
        self.assertIn('rollback    : EMERGENCY ONLY:',s)
        self.assertIn("platform-e715829a56cc",s)
        self.assertNotIn("platform-dee472df5253",s)
        self.assertIn("readonly PREVIOUS_SHA=e715829a56cc77e7aa63418ca1539635ae24e446",s)

    def test_owner_root_identity_and_fixed_cli(self):
        s=text()
        self.assertIn('[[ "$#" -eq 1 ]]',s)
        self.assertIn('[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]]',s)
        self.assertIn("readonly APPROVAL=/etc/kmj-codebridge/main-platform-production-release.json",s)
        self.assertIn("readonly UNIT=kmj-main-platform-production-release.service",s)

    def test_stage_before_backup_then_publish_never_switch_before_approval(self):
        s=text()
        for marker in ("step_prepare()","step_storage()","step_materialize()",
                       "step_approve()","step_activate()"):
            self.assertIn(marker,s)
        self.assertIn("step_prepare; step_storage; step_materialize; step_approve; step_activate",s)
        p=s.index("step_prepare()")
        a=s.index("step_approve()")
        self.assertLess(p,a)
        self.assertIn("ONEPASS_SHA=0070697927babaa9a9035ebadcffe9a07311c12bcc4fbbd7a5a9d024cbc00dd3",s)
        self.assertIn("STAGED_BACKED_UP_OFFSITE",s)
        self.assertIn("BACKUP_WITNESS=PASS",s)
        self.assertIn("CANDIDATE_WRONG_SHA",s)

    def test_no_source_reset_clean_unauthorized_target_or_migration_run(self):
        s=text()
        for word in ("git reset","git clean","git push --force","--force-with-lease",
                     "php artisan migrate","composer update","npm install",
                     "rm -rf -- \"$ROOTDIR\"", "ln -sfn \"$CAND\" \"$CURRENT\""):
            self.assertNotIn(word,s)
        self.assertIn("PRODUCTION_MIGRATION_PENDING_UNEXPECTED",s)
        self.assertIn("PRODUCTION_MIGRATION_STATE=",s)

    def test_production_gate_requires_real_witness_migration_and_controller(self):
        s=text()
        a=s[s.index("step_approve()"):s.index("\nhealth()",s.index("step_approve()"))]
        self.assertIn('[[ "$(sha "$CTL")" == "$CTL_NEW" ]]',a)
        self.assertIn('[[ "$(pointer)" == "$OLD_RELEASE" ]]',a)
        self.assertIn("migration_state after",a)
        self.assertIn("verify_witness || fail BACKUP_WITNESS_NOT_VERIFIED",a)
        self.assertIn("verify_rollback_base",a)
        self.assertIn("ROLLBACK_BASE_SHA_DRIFT",s)
        self.assertIn("ROLLBACK_STORAGE_NOT_SHARED",s)
        self.assertIn("ROLLBACK_ENV_NOT_READY",s)
        self.assertIn('"approvedSha": sha, "expectedCurrentRelease": current',a)
        self.assertIn('"backupVerified": True, "rollbackVerified": True',a)
        self.assertIn("APPROVAL_PREVIOUS_KEPT",a)

    def test_activation_requires_exact_approval_and_own_health(self):
        s=text()
        a=s[s.index("step_activate()"):s.index("\nstep_rollback()",s.index("step_activate()"))]
        self.assertIn('[[ "$(sha "$CTL")" == "$CTL_NEW" ]]',a)
        self.assertIn("APPROVAL_NOT_E5B438_RUN_APPROVE",a)
        self.assertIn('systemctl start "$UNIT"',a)
        self.assertIn('"$(pointer)" != "$NEW_RELEASE"',a)
        self.assertIn("health || fail POST_ACTIVATION_HEALTH_FAILED_CONSIDER_ROLLBACK",a)
        self.assertIn("restart_queue",a)

    def test_rollback_requires_active_new_and_preserves_old(self):
        s=text()
        r=s[s.index("step_rollback()"):s.index("\nstep_status()",s.index("step_rollback()"))]
        self.assertIn('"$(pointer)" == "$NEW_RELEASE"',r)
        self.assertIn('"$ROOTDIR/releases/$OLD_RELEASE/apps/platform"',r)
        self.assertIn("RELEASE_LOCK_UNSAFE",s)
        self.assertIn("BACKUP_WITNESS=CHECKSUM_MISMATCH",s)
        self.assertIn("mark ROLLBACK DONE_TO_E71582",s)
        self.assertNotIn("DONE_TO_DEE472",s)

    def test_immutable_controller_materializer_and_storage_scanner_hashes(self):
        s=text()
        for pattern in (
            r"readonly CTL_NEW=[a-f0-9]{64}\b",
            r"readonly MATERIALIZER_SHA=[a-f0-9]{64}\b",
            r"readonly SCANNER_SHA=[a-f0-9]{64}\b",
            r"readonly ONEPASS_SHA=[a-f0-9]{64}\b",
        ):
            self.assertRegex(s,pattern)
        self.assertIn("MATERIALIZE_NOT_PASS",s)
        self.assertIn("CANDIDATE_STORAGE_NOT_SHARED",s)

if __name__=="__main__":
    unittest.main()
