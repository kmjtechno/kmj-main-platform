"""Offline fail-closed tests for review-only KMJ Main Platform health onepass.

Never contacts Google, starts systemd, opens live DB, or reads live secrets.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock

SOURCE=Path(__file__).with_name("KMJ_OFFSITE_V3_HEALTH_ONEPASS_OWNER_REVIEW_20261115.py")
spec=importlib.util.spec_from_file_location("kmj_owner_backup_onepass",SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class GuardedOnepassTests(unittest.TestCase):
    def sample_find(self,root,depth,glob):
        return ("find "+root+" -mindepth "+depth+" -maxdepth "+depth+
                " -name '"+glob+"' -type f -mtime -2 | grep -q .")

    def test_exact_original_daily_and_vault_find_shape(self):
        a=m.parse_exact_find(self.sample_find(str(m.DAILY),"2","*.tar.gz"))
        b=m.parse_exact_find(self.sample_find(str(m.VAULT),"1","*.age"))
        self.assertEqual(a,(str(m.DAILY),"2","2","*.tar.gz"))
        self.assertEqual(b,(str(m.VAULT),"1","1","*.age"))

    def test_find_rejects_loosened_freshness_and_bad_depth(self):
        src=self.sample_find(str(m.DAILY),"2","*.tar.gz")
        for bad in (src.replace("-mtime -2","-mtime -7"),
                    src.replace("-mtime -2","-mtime +2"),
                    src.replace("-maxdepth 2","-maxdepth 4"),
                    src.replace("-mindepth 2","-mindepth 1"),
                    src+" ; echo fake",
                    src.replace("-type f","-type l"),
                    src.replace("*.tar.gz","$(touch /tmp/unsafe)")):
            with self.subTest(bad=bad), self.assertRaises(m.Deny):
                m.parse_exact_find(bad) if "-mindepth 1" not in bad and "-maxdepth 4" not in bad else self.require_depth(bad)

    def require_depth(self,line):
        root,mind,maxd,glob=m.parse_exact_find(line)
        if (mind,maxd)!=("2","2"):
            raise m.Deny("DEPTH_CHANGED")

    def test_glob_acceptance_cannot_create_arbitrary_freshness(self):
        self.assertFalse(__import__("fnmatch").fnmatchcase("platform.dump","*.tar.gz"))
        self.assertTrue(__import__("fnmatch").fnmatchcase("storage.tar.gz","*.tar.gz"))
        self.assertFalse(__import__("fnmatch").fnmatchcase("20261115T120000Z.sha256","*.age"))
        self.assertTrue(__import__("fnmatch").fnmatchcase("20261115T120000Z.tar.age","*.age"))

    def test_preflight_is_root_gated_before_all_file_reads(self):
        with mock.patch.object(m,"root_owner",side_effect=m.Deny("NO_ROOT")):
            with mock.patch.object(m,"bundle_source") as source:
                with self.assertRaisesRegex(m.Deny,"NO_ROOT"):
                    m.runtime_sources()
                source.assert_not_called()

    def test_preflight_refuses_missing_complete_sources_before_writes(self):
        with mock.patch.object(m,"runtime_sources",side_effect=m.Deny("NO_CONFIG")):
            with mock.patch.object(m,"install_bundle") as install:
                with self.assertRaisesRegex(m.Deny,"NO_CONFIG"):
                    m.run_once()
                install.assert_not_called()

    def test_stable_original_health_contract_requires_real_artifact_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"nonempty"
            file.write_text("fixture",encoding="utf-8")
            lines=["# offline fixture"]*29
            lines[24]=self.sample_find(str(m.DAILY),"2","*.tar.gz")
            lines[26]="test -s "+str(file)
            lines[27]=self.sample_find(str(m.VAULT),"1","*.age")
            raw=("\n".join(lines)+"\n").encode()
            with mock.patch.object(m,"private_bytes",return_value=raw):
                self.assertTrue(m.health_contract.__code__.co_argcount==0)
                # Exact source verification requires 1840 bytes; the fake must
                # never be mistaken for the real installed Bash program.
                with self.assertRaisesRegex(m.Deny,"HEALTH_PINNED_SOURCE_CHANGED"):
                    m.health_contract()

    def test_health_service_cannot_claim_success_without_new_invocation(self):
        before=b"InvocationID=aaa\nResult=exit-code\nExecMainStatus=1\n"
        after=b"InvocationID=aaa\nResult=success\nExecMainStatus=0\n"
        def fake_run(argv,**kwargs):
            if argv[0]=="/usr/bin/systemctl" and argv[1]=="show":
                out=before if fake_run.calls==0 else after
                fake_run.calls+=1
                return types.SimpleNamespace(returncode=0,stdout=out)
            self.assertEqual(argv,["/usr/bin/systemctl","start",m.UNIT])
            return types.SimpleNamespace(returncode=0,stdout=b"")
        fake_run.calls=0
        with mock.patch.object(m.subprocess,"run",side_effect=fake_run):
            with self.assertRaisesRegex(m.Deny,"NATIVE_HEALTH_OWN_INVOCATION_NOT_PASS"):
                m.verify_health_service_once()

    def test_health_service_pass_requires_own_invocation_and_exit0(self):
        before=b"InvocationID=aaa\nResult=exit-code\nExecMainStatus=1\n"
        after=b"InvocationID=bbb\nResult=success\nExecMainStatus=0\n"
        def fake_run(argv,**kwargs):
            if argv[0]=="/usr/bin/systemctl" and argv[1]=="show":
                out=before if fake_run.calls==0 else after
                fake_run.calls+=1
                return types.SimpleNamespace(returncode=0,stdout=out)
            return types.SimpleNamespace(returncode=0,stdout=b"")
        fake_run.calls=0
        with mock.patch.object(m.subprocess,"run",side_effect=fake_run):
            self.assertTrue(m.verify_health_service_once())

    def test_rooted_bundle_identity_must_be_exact(self):
        self.assertEqual(len(m.PINS),6)
        self.assertEqual(m.PINS["KMJ_OFFSITE_V3_TRANSFER_BOUND_TRANSACTION_REVIEW_20261115.py"],
                         "cebc9366412ef689e4887d0ebac958989842c55fade1feff607f754c1bd209ea")
        self.assertTrue(all(len(x)==64 for x in m.PINS.values()))
        self.assertNotIn("install_service",m.__dict__)
        self.assertNotIn("install_timer",m.__dict__)

    def test_pinned_source_bytes_and_publisher_api_compatible(self):
        # Fail the SAME offline gate if any SHA-pinned module is missing,
        # modified, or the owner wrapper calls an incompatible keyword.
        import inspect
        for filename, expected in sorted(m.PINS.items()):
            with self.subTest(filename=filename):
                source = SOURCE.with_name(filename).read_bytes()
                self.assertEqual(hashlib.sha256(source).hexdigest(), expected)
        publisher_source = SOURCE.with_name(
            "KMJ_OFFSITE_V3_LOCAL_DAILY_PUBLISHER_REVIEW_20261115.py"
        )
        spec = importlib.util.spec_from_file_location(
            "kmj_v3_publisher_exact_source_compat", publisher_source
        )
        publisher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(publisher)
        self.assertIn("restricted", inspect.signature(publisher.regular).parameters)
        owner_source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(
            'daily.regular(fd,"SHA256SUMS",{0},restricted=True)',
            owner_source,
        )
        self.assertNotIn(
            'daily.regular(fd,"SHA256SUMS",{0},secret=True)',
            owner_source,
        )

    def certbot_mixed_source_fixture(self,root):
        root.mkdir(mode=0o700)
        live=root/"live"
        archive=root/"archive"
        live.mkdir(mode=0o700)
        archive.mkdir(mode=0o700)
        for i,lineage in enumerate(("kmj-alpha.test","kmj-beta.test","kmj-local-files.test")):
            here=live/lineage
            here.mkdir(mode=0o700)
            if i<2:
                archived=archive/lineage
                archived.mkdir(mode=0o700)
                for name in ("cert.pem","chain.pem","fullchain.pem","privkey.pem"):
                    filename=name[:-4]+"1.pem"
                    (archived/filename).write_bytes(("offline-"+name).encode())
                    (archived/filename).chmod(0o600)
                    (here/name).symlink_to("../../archive/"+lineage+"/"+filename)
            else:
                for name in ("cert.pem","chain.pem","fullchain.pem","privkey.pem"):
                    file=here/name
                    file.write_bytes(("offline-regular-"+name).encode())
                    file.chmod(0o600)
        return live,archive

    def pinned_publisher_bytes(self):
        return SOURCE.with_name("KMJ_OFFSITE_V3_LOCAL_DAILY_PUBLISHER_REVIEW_20261115.py").read_bytes()

    def test_mixed_three_lineage_certbot_preflight_reads_eight_links_four_regular(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"letsencrypt"
            self.certbot_mixed_source_fixture(root)
            with mock.patch.dict(m.CONFIG,{"letsencrypt":root}):
                with mock.patch("builtins.print") as info:
                    self.assertEqual(m.validate_certbot_live_matrix(
                        self.pinned_publisher_bytes(),expected_uid=os.geteuid()),12)
                messages=" ".join(str(x.args) for x in info.call_args_list)
                self.assertIn("CERTBOT_STANDARD_INTERNAL_LINKS=8_VERIFIED",messages)
                self.assertIn("CERTBOT_REGULAR_PEMS=4_VERIFIED",messages)
                self.assertNotIn("kmj-alpha.test",messages)
                self.assertNotIn("PRIVATE_KEY",messages)

    def test_mixed_certbot_preflight_rejects_world_writable_regular_pem(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"letsencrypt"
            live,_=self.certbot_mixed_source_fixture(root)
            file=live/"kmj-local-files.test"/"cert.pem"
            file.chmod(0o666)
            with mock.patch.dict(m.CONFIG,{"letsencrypt":root}):
                with self.assertRaisesRegex(m.Deny,"CERTBOT_REGULAR_PEM_METADATA_UNTRUSTED"):
                    m.validate_certbot_live_matrix(
                        self.pinned_publisher_bytes(),expected_uid=os.geteuid())

    def test_mixed_certbot_preflight_rejects_hardlinked_regular_pem(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"letsencrypt"
            live,_=self.certbot_mixed_source_fixture(root)
            file=live/"kmj-local-files.test"/"cert.pem"
            os.link(file,live/"kmj-local-files.test"/"hardlinked-copy.pem")
            with mock.patch.dict(m.CONFIG,{"letsencrypt":root}):
                with self.assertRaisesRegex(m.Deny,"CERTBOT_REGULAR_PEM_METADATA_UNTRUSTED"):
                    m.validate_certbot_live_matrix(
                        self.pinned_publisher_bytes(),expected_uid=os.geteuid())

    def test_mixed_certbot_preflight_rejects_external_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"letsencrypt"
            live,_=self.certbot_mixed_source_fixture(root)
            file=live/"kmj-alpha.test"/"cert.pem"
            file.unlink()
            file.symlink_to("/etc/passwd")
            with mock.patch.dict(m.CONFIG,{"letsencrypt":root}):
                with self.assertRaisesRegex(Exception,"CERTBOT_LINK_TARGET_NOT_PINNED_IN_TREE"):
                    m.validate_certbot_live_matrix(
                        self.pinned_publisher_bytes(),expected_uid=os.geteuid())

    def test_mixed_certbot_preflight_rejects_missing_expected_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"letsencrypt"
            live,_=self.certbot_mixed_source_fixture(root)
            (live/"kmj-local-files.test"/"cert.pem").unlink()
            with mock.patch.dict(m.CONFIG,{"letsencrypt":root}):
                with self.assertRaises(FileNotFoundError):
                    m.validate_certbot_live_matrix(
                        self.pinned_publisher_bytes(),expected_uid=os.geteuid())

    def test_mixed_certbot_preflight_rejects_wrong_lineage_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"letsencrypt"
            live,archive=self.certbot_mixed_source_fixture(root)
            more=archive/"kmj-local-files.test"
            more.mkdir(mode=0o700)
            file=live/"kmj-local-files.test"/"cert.pem"
            file.unlink()
            (more/"cert1.pem").write_bytes(b"offline-synthetic-cert")
            (more/"cert1.pem").chmod(0o600)
            file.symlink_to("../../archive/kmj-local-files.test/cert1.pem")
            with mock.patch.dict(m.CONFIG,{"letsencrypt":root}):
                with self.assertRaisesRegex(m.Deny,"CERTBOT_MIXED_SOURCE_MATRIX_DRIFT"):
                    m.validate_certbot_live_matrix(
                        self.pinned_publisher_bytes(),expected_uid=os.geteuid())

    def test_mixed_certbot_preflight_never_accepts_bad_owner_uid_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"letsencrypt"
            self.certbot_mixed_source_fixture(root)
            with mock.patch.dict(m.CONFIG,{"letsencrypt":root}):
                for invalid in (-1,65536,"0",True):
                    with self.subTest(value=invalid),self.assertRaisesRegex(
                            m.Deny,"CERTBOT_EXPECTED_UID_INVALID"):
                        m.validate_certbot_live_matrix(self.pinned_publisher_bytes(),
                                                       expected_uid=invalid)

    def test_selftest_offline_no_installed_sources(self):
        with mock.patch.object(m,"runtime_sources") as preflight:
            with mock.patch.object(m,"install_bundle") as install:
                self.assertEqual(m.selftest(),0)
                preflight.assert_not_called()
                install.assert_not_called()

if __name__=="__main__":
    unittest.main()
