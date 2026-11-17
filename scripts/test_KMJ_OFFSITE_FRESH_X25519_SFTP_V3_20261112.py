"""Offline fixture/mock tests only, no production DB/SSH/SFTP/backup execution."""
from __future__ import annotations
import contextlib,importlib.util,io,os,stat,tempfile
from pathlib import Path
from unittest import TestCase,main,mock
HERE=Path(__file__).with_name("KMJ_OFFSITE_FRESH_X25519_SFTP_V3_20261112.py")
spec=importlib.util.spec_from_file_location("kmj_fresh_offsite_mock_tests",HERE)
assert spec and spec.loader
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class NewFreshOffsiteTests(TestCase):
    def test_php_dump_is_nonroot_and_argument_vector(self):
        php=m.DUMP_PHP
        self.assertIn(b"proc_open($cmd",php)
        self.assertIn(b"--format=custom",php)
        self.assertIn(b"PGPASSWORD",php)
        self.assertIn(b"DUMP=PASS",php)
        self.assertIn(b"NOT_PRODUCTION",php)
        self.assertNotIn(b"passthru(",php)
        self.assertNotIn(b"shell_exec(",php)

    def test_selftest_never_runs_backup(self):
        with mock.patch.object(m,"pinned_transport") as x,\
             mock.patch.object(m,"send") as y,\
             contextlib.redirect_stdout(io.StringIO()) as out:
            m.selftest()
        x.assert_not_called();y.assert_not_called()
        self.assertIn("BACKUP_EXECUTED=NO",out.getvalue())

    def test_private_dump_copy_roundtrip(self):
        with tempfile.TemporaryDirectory() as root:
            a,b=Path(root)/"in",Path(root)/"out"
            value=b"PGDMP"+b"\x03"*128
            a.write_bytes(value);a.chmod(0o600)
            self.assertEqual(m.copy_app_dump(a,b,os.geteuid()),len(value))
            self.assertEqual(b.read_bytes(),value)
            self.assertEqual(stat.S_IMODE(b.stat().st_mode),0o600)

    def test_dump_hardlink_denied(self):
        with tempfile.TemporaryDirectory() as root:
            a,b,c=(Path(root)/n for n in ("a","b","c"))
            a.write_bytes(b"PGDMP"+b"\0"*100);a.chmod(0o600)
            os.link(a,c)
            with self.assertRaisesRegex(m.Deny,"APP_DUMP_UNSAFE"):
                m.copy_app_dump(a,b,os.geteuid())

    def test_symlink_dump_denied(self):
        with tempfile.TemporaryDirectory() as root:
            a,b,c=(Path(root)/n for n in ("a","b","c"))
            a.write_bytes(b"PGDMP"+b"\0"*100);a.chmod(0o600)
            c.symlink_to(a)
            with self.assertRaises(OSError):
                m.copy_app_dump(c,b,os.geteuid())

    def test_private_file_rejects_group_read(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/"data"
            source.write_bytes(b"x"*44);source.chmod(0o640)
            with self.assertRaisesRegex(m.Deny,"PRIVATE_FILE_UNSAFE"):
                m.private_file(source,uid=os.geteuid())

    def test_output_does_not_leak_paths(self):
        with self.assertRaises(m.Deny):
            m.emit("PRIVATE_KEY","/root/.ssh/secret")
        with self.assertRaises(m.Deny):
            m.emit("PROD_PASSWORD","a password")

    def test_invalid_mode_denied_before_transport_load(self):
        with mock.patch.object(m.os,"geteuid",return_value=0),\
             mock.patch.object(m.socket,"gethostname",return_value="KMJ-elite"),\
             mock.patch.object(m.sys,"argv",["script","--install-unit"]),\
             mock.patch.object(m,"pinned_transport") as tx,\
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(),2)
        tx.assert_not_called()

    def test_host_denied_before_transport_load(self):
        with mock.patch.object(m.os,"geteuid",return_value=0),\
             mock.patch.object(m.socket,"gethostname",return_value="other-vps"),\
             mock.patch.object(m.sys,"argv",["script","--inspect"]),\
             mock.patch.object(m,"pinned_transport") as tx,\
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(),2)
        tx.assert_not_called()

    def test_exclusive_lock_only_new_fixture(self):
        with tempfile.TemporaryDirectory() as root:
            fake=Path(root)/"lock"
            with mock.patch.object(m,"LOCK",fake):
                f=m.exclusive_lock()
                self.assertTrue(fake.is_file())
                self.assertEqual(stat.S_IMODE(fake.stat().st_mode),0o600)
                os.close(f)

    def test_native_pg_restore_fallback_uses_supported_reader(self):
        with tempfile.TemporaryDirectory() as root:
            dump=Path(root)/"database.dump"
            dump.write_bytes(b"PGDMP"+b"x"*128);dump.chmod(0o600)
            candidates=[(18,Path("/usr/lib/postgresql/18/bin/pg_restore")),
                        (17,Path("/usr/lib/postgresql/17/bin/pg_restore"))]
            replies=[mock.Mock(returncode=1,stderr=b"unsupported version (1.16)"),
                     mock.Mock(returncode=0,stderr=b"")]
            with mock.patch.object(m,"native_pg_restore_candidates",return_value=candidates),\
                 mock.patch.object(m,"run",side_effect=replies) as runner,\
                 contextlib.redirect_stdout(io.StringIO()) as output:
                selected=m.verify_pg_dump_custom(dump)
            self.assertEqual(selected,17)
            self.assertEqual(runner.call_count,2)
            self.assertIn("PG_RESTORE_TOC=PASS",output.getvalue())

    def test_all_incompatible_readers_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            dump=Path(root)/"database.dump"
            dump.write_bytes(b"PGDMP"+b"x"*128);dump.chmod(0o600)
            with mock.patch.object(m,"native_pg_restore_candidates",return_value=[(15,Path("/bin/false"))]),\
                 mock.patch.object(m,"run",return_value=mock.Mock(returncode=1,stderr=b"unsupported version")),\
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(m.Deny,"FRESH_PGDMP_NO_COMPATIBLE_READER"):
                    m.verify_pg_dump_custom(dump)

    def test_non_pg_dump_magic_rejected_before_external_tool(self):
        with tempfile.TemporaryDirectory() as root:
            dump=Path(root)/"database.dump"
            dump.write_bytes(b"NOTDB"+b"x"*128);dump.chmod(0o600)
            with mock.patch.object(m,"run") as tool:\
                self.assertRaisesRegex(m.Deny,"FRESH_DUMP_NOT_PGDMP",m.verify_pg_dump_custom,dump)
            tool.assert_not_called()

    def test_no_native_postgres_reader_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            dump=Path(root)/"database.dump"
            dump.write_bytes(b"PGDMP"+b"x"*128);dump.chmod(0o600)
            with mock.patch.object(m,"native_pg_restore_candidates",return_value=[]),\
                 mock.patch.object(m,"run") as tool,\
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(m.Deny,"PG_RESTORE_NATIVE_MISSING"):
                    m.verify_pg_dump_custom(dump)
            tool.assert_not_called()

    def test_schedule_rejects_uninstalled_source(self):
        fake=mock.Mock()
        with mock.patch.object(m,"SCHEDULED",Path("/not/installed")):
            with self.assertRaisesRegex(m.Deny,"SCHEDULED_MODULE_NOT_INSTALLED"):
                m.schedule_unit_preflight(fake)
        fake.prop.assert_not_called()

    def test_schedule_rejects_unreviewed_dropin(self):
        fake=mock.Mock()
        attrs={"LoadState":"loaded","User":"","Type":"oneshot",
            "DropInPaths":"/etc/systemd/system/unreviewed.conf"}
        fake.prop.side_effect=lambda key: attrs[key]
        with mock.patch.object(m.Path,"resolve",return_value=m.SCHEDULED):
            with self.assertRaisesRegex(m.Deny,"SCHEDULED_DROPIN_UNREVIEWED"):
                m.schedule_unit_preflight(fake)

    def test_schedule_rejects_wrong_executable_argv(self):
        fake=mock.Mock()
        attrs={"LoadState":"loaded","User":"","Type":"oneshot",
            "DropInPaths":str(m.DROPIN),"ExecStart":
            "{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -I -B /tmp/wrong.py --scheduled-run ; }"}
        fake.prop.side_effect=lambda key: attrs[key]
        with mock.patch.object(m.Path,"resolve",return_value=m.SCHEDULED):
            with self.assertRaisesRegex(m.Deny,"SCHEDULED_ARGV_DRIFT"):
                m.schedule_unit_preflight(fake)

    def test_schedule_accepts_exact_identity_no_secret_print(self):
        fake=mock.Mock()
        attrs={"LoadState":"loaded","User":"","Type":"oneshot",
            "DropInPaths":str(m.DROPIN),"ExecStart":
            "{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -I -B "+str(m.SCHEDULED)+" --scheduled-run ; }",
            "ActiveState":"activating"}
        fake.prop.side_effect=lambda key: attrs[key]
        with mock.patch.object(m.Path,"resolve",return_value=m.SCHEDULED),\
             contextlib.redirect_stdout(io.StringIO()) as receipt:
            m.schedule_unit_preflight(fake)
        self.assertIn("SCHEDULED_UNIT_IDENTITY=EXACT_PINNED",receipt.getvalue())

    def test_v3_uses_separate_root_protected_install(self):
        self.assertEqual(m.SCHEDULED.name,"kmj-offsite-fresh-x25519-v3-20261112.py")
        self.assertEqual(m.PARENT,"KMJ_OFFSITE_SFTP_DNS_PINNED_V2_20261112.py")
        self.assertEqual(m.PARENT_SHA,"8f9165714774758a6bef05abff7bf72d655518ab7ed1c3cdd8dc588d3c85c13c")

    def test_v3_migration_from_exact_v2(self):
        probe=mock.Mock()
        values={"LoadState":"loaded","Type":"oneshot","User":"",
                "DropInPaths":str(m.DROPIN),"ActiveState":"inactive",
                "ExecStart":"{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -I -B /usr/local/libexec/kmj-offsite-fresh-x25519-v2-20261112.py --scheduled-run ; }"}
        probe.prop.side_effect=lambda k:values[k]
        probe.pinned_conf=mock.Mock()
        probe.dns_address=mock.Mock(return_value="34.63.5.14")
        probe.VAULT=Path("/var/backups/kmj-elite-offsite-encrypted")
        # Exercise migration unit gate without touching real app/runtime.
        with mock.patch.object(m,"check_tools"),mock.patch.object(m,"live_app",return_value=(None,None,None,None)),\
             mock.patch.object(m,"native_pg_restore_candidates",return_value=[(16,Path("/bin/true"))]),\
             mock.patch.object(m,"run",return_value=mock.Mock(returncode=0,stdout=b"pg_dump (PostgreSQL) 16.0")),\
             mock.patch.object(m.os,"statvfs",return_value=type("V",(),{"f_bavail":2097152,"f_frsize":4096})()),\
             mock.patch.object(Path,"lstat",return_value=type("S",(),{"st_mode":stat.S_IFDIR|0o700,"st_uid":0})()),\
             contextlib.redirect_stdout(io.StringIO()) as output:
            m.inspect(probe)
        probe.dns_address.assert_called_once()
        self.assertIn("GOOGLE_ENDPOINT=DNS_ONLY_STRICT_PINNED_HOSTKEY",output.getvalue())

    def test_v3_rejects_unexpected_current_exec(self):
        probe=mock.Mock()
        vals={"LoadState":"loaded","Type":"oneshot","User":"",
              "DropInPaths":str(m.DROPIN),"ActiveState":"inactive",
              "ExecStart":"{ argv[]=/usr/bin/python3 /tmp/malicious.py --scheduled-run ; }"}
        probe.prop.side_effect=lambda k:vals[k]
        with mock.patch.object(m,"check_tools"),\
             mock.patch.object(m,"live_app",return_value=(None,None,None,None)):
            with self.assertRaisesRegex(m.Deny,"MIGRATION_START_NOT_V2_OR_V3"):
                m.inspect(probe)

    def test_no_production_modification_contract(self):
        module=HERE.read_text()
        self.assertNotIn("systemctl start",module)
        self.assertNotIn("daemon-reload",module)
        self.assertNotIn("UPDATE ",module)
        self.assertNotIn("DROP TABLE",module)
        self.assertNotIn("ALTER SYSTEM",module)

if __name__=="__main__":main()
