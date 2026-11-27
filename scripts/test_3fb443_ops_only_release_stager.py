"""Static contract for immutable 3fb443 release when main advances operations-only."""
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/"scripts/operations/stage-3fb443-only-ops-main-advance-20261027.sh"
SOURCE=FILE.read_text(encoding="utf-8")

class OpsOnlyMainAdvance(unittest.TestCase):
    def test_syntax(self):
        subprocess.run(["bash","-n",str(FILE)],check=True,timeout=10)
    def test_exact_whitelisted_candidate_only(self):
        for part in (
            "3fb443d135f010a41f913b4e690289ab315769b8",
            "NOT_APPROVED_PRODUCT_STUDIO_SHA",
            "git -C \"$dest\" merge-base --is-ancestor \"$exact\" \"$main_head\"",
            "git -C \"$dest\" diff --name-only -z",
            "BLOCKED_APPLICATION_SOURCE_ADVANCED",
            "BLOCKED_MAIN_TOO_FAR_AHEAD",
            "MAIN_MOVED_DURING_BUILD",
            "KMJ_MAIN_OPS_ONLY_ADVANCE=PASS",
            "git -C \"$dest\" checkout --detach -q \"$exact\"",
            "refs/heads/main"):
            self.assertIn(part,SOURCE)
        self.assertNotIn("REMOTE_MAIN_SHA_CHANGED",SOURCE)
    def test_only_explicit_nonruntime_paths_allowed(self):
        self.assertIn("scripts/operations/*|scripts/test_*|tests/*|.github/workflows/*|docs/*",SOURCE)
        self.assertNotIn("apps/platform/*",SOURCE.split("case \"$advanced_path\" in",1)[1].split("esac",1)[0])
    def test_current_live_and_secret_integrity(self):
        for token in (
            '[[ "$(readlink -f "$LIVE")" == "$before" ]]',
            "RUNTIME_ENV_REQUIRES_REVIEW","CANDIDATE_DIRTY",
            "composer install --no-dev --no-interaction",
            "npm ci --ignore-scripts",
            "APPROVED_PRODUCTION_RELEASE"):
            if token == "APPROVED_PRODUCTION_RELEASE":
                self.assertNotIn(token,SOURCE)
            else:
                self.assertIn(token,SOURCE)
        for bad in ("ln -sfn","systemctl restart","systemctl reload",
                    "/etc/kmj-codebridge/main-platform-production-release.json",
                    "artisan migrate","git reset --hard","git clean -fd"):
            self.assertNotIn(bad,SOURCE)
if __name__=="__main__":unittest.main()
