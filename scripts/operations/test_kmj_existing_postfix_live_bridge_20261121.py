"""Offline-only safety checks: bash syntax and isolated dotenv editing fixtures."""
import pathlib, re, subprocess, tempfile, unittest

SCRIPT=pathlib.Path(__file__).with_name('kmj_existing_postfix_live_bridge_20261121.sh')
SRC=SCRIPT.read_text()
# Extract second embedded Python heredoc (only pure env transform, never host operations).
lines=SRC.splitlines()
BLOCKS=[]
for i,line in enumerate(lines):
    if "<<'PY'" in line:
        stop=lines.index('PY',i+1)
        BLOCKS.append('\n'.join(lines[i+1:stop]))
ENV_CODE=BLOCKS[-1] if BLOCKS else ''

class MailBridgeContract(unittest.TestCase):
    def test_bash_syntax(self):
        self.assertEqual(subprocess.run(['bash','-n',str(SCRIPT)],capture_output=True).returncode,0)

    def test_embedded_python_compiles(self):
        self.assertGreaterEqual(len(BLOCKS),2)
        for block in BLOCKS:compile(block, '<embedded>', 'exec')

    def edit(self,data):
        with tempfile.TemporaryDirectory() as d:
            src=pathlib.Path(d)/'.env'
            dst=pathlib.Path(d)/'out'
            src.write_bytes(data)
            r=subprocess.run(['python3','-I','-B','-c',ENV_CODE,str(src),str(dst)],capture_output=True)
            return r.returncode, dst.read_bytes() if dst.exists() else None

    def test_preserves_unrelated_credentials_and_chooses_loopback(self):
        rc,out=self.edit(b'APP_KEY=secret-value\nDB_PASSWORD=other-secret\n# KMJ\nMAIL_MAILER=log\nMAIL_FROM_ADDRESS="info@kmjtechno.com"\n')
        self.assertEqual(rc,0)
        for field in [b'APP_KEY=secret-value',b'DB_PASSWORD=other-secret',b'# KMJ',b'MAIL_MAILER=smtp',b'MAIL_HOST=127.0.0.1',b'MAIL_PORT=25',b'MAIL_SCHEME=smtp']:
            self.assertIn(field,out)
        self.assertEqual(out.count(b'MAIL_MAILER='),1)

    def test_duplicate_rejected(self):
        rc,out=self.edit(b'MAIL_MAILER=log\nMAIL_MAILER=smtp\n')
        self.assertNotEqual(rc,0)

    def test_foreign_sender_rejected(self):
        rc,out=self.edit(b'MAIL_FROM_ADDRESS=malicious@example.net\n')
        self.assertNotEqual(rc,0)

    def test_newline_and_interpolation_complex_rejected(self):
        for src in (b'MAIL_MAILER=log\r\n',b'export MAIL_MAILER=log\n',b'\x00'):
            self.assertNotEqual(self.edit(src)[0],0)

    def test_no_remote_mail_or_privileged_bypass(self):
        for token in ('systemctl start postfix','systemctl restart postfix','postconf -e','opendkim-genkey','ufw allow','artisan migrate','git reset','smtp-relay.brevo.com','curl | bash'):
            self.assertNotIn(token,SRC)
        for token in ('CURRENT_RELEASE=', 'EXISTING_POSTFIX=ACTIVE_LOOPBACK', 'ROLLBACK=ATTEMPTED_VERIFY_REQUIRED', 'MAIL_SENT=NO', 'LARAVEL_EXTERNAL_ATTEMPT=READY_NOT_INBOX_PROOF'):
            self.assertIn(token,SRC)

if __name__ == '__main__':unittest.main()
