#!/usr/bin/env python3
"""Static, no live-host candidate staging contract."""
from pathlib import Path
import subprocess
import unittest

f = Path(__file__).resolve().parents[1] / "scripts/operations/stage-babf906-exact-main-no-activation-20261027.sh"
s = f.read_text(encoding="utf-8")
class StagingSafety(unittest.TestCase):
    def test_syntax(self):
        subprocess.run(["bash","-n",str(f)],check=True,timeout=10)
    def test_exact_main_check(self):
        for v in ("git ls-remote --exit-code", 'refs/heads/main', '"$remote" == "$sha"', 'verify "$dest"', 'flock -n 9', 'CANDIDATE_DIRTY', 'RUNTIME_ENV_REQUIRES_REVIEW', 'KMJ_PRODUCTION=UNCHANGED'):
            self.assertIn(v,s)
    def test_no_live_cutover(self):
        for v in ('ln -sfn', 'systemctl reload', 'systemctl restart', 'artisan migrate', 'rollbackVerified', 'backupVerified', '/home/kmjstage', 'git reset --hard'):
            self.assertNotIn(v,s)
    def test_main_commit_bound_on_source_only(self):
        self.assertIn('[[ "$remote" == "$sha" ]]',s)
        self.assertNotIn('APPROVED_PRODUCTION_RELEASE',s)
if __name__=="__main__": unittest.main()
