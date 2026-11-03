"""Static contract for babf906 synthetic owner browser QA. NOT actual signed owner acceptance."""
from pathlib import Path
import subprocess
import unittest
FILE=Path(__file__).resolve().parents[1]/"scripts/operations/qa-babf906-private-authenticated-owner-pg18-20261027.sh"
S=FILE.read_text()
class OwnerQASafety(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(["bash","-n",str(FILE)],check=True,timeout=10)
    def test_exact_release_and_guest_customer_owner_roles(self):
        for t in ("babf9060684d15b6188384386149466816140a98",
                  "platform-8070dad72c55","KMJ_OWNER_CURRENT_AUTH_BROWSER_20261027.mjs",
                  "84aeddbcb3bc3e40051d5077763870649f864e61b550eba1733f55d36ea4ca83",
                  "PRIVATE_OWNER_CUSTOMER=PASS","AUTHENTICATED_BROWSER=FAIL",
                  "REAL_OWNER_ACCEPTANCE=NOT_ATTESTED"):
            self.assertIn(t,S)
    def test_private_qa_and_no_production_mutation(self):
        for t in ("--auth-host=reject","listen_addresses=''","APP_ENV=testing",
                  "QA_MODE=EPHEMERAL_POSTGRESQL18_UNIX_SOCKET_ONLY",
                  "PRODUCTION_DB=NOT_CONNECTED","PRODUCTION_CUTOVER=NOT_ATTEMPTED",
                  "CANDIDATE_SECRET_CONFIG_PRESENT","PG18_EPHEMERAL_CLEANUP=PASS"):
            self.assertIn(t,S)
        for forbidden in ("git reset --hard","systemctl reload","systemctl restart",
                          "/etc/kmj-codebridge/main-platform-production-release.json",
                          "/home/kmjstage","MAIL_MAILER=smtp"):
            self.assertNotIn(forbidden,S)
if __name__=="__main__": unittest.main()
