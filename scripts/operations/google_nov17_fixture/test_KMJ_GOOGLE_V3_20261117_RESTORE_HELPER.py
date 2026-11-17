"""Only synthetic tar fixtures, never Google private key or production data."""
from __future__ import annotations
import contextlib,hashlib,importlib.util,io,os,tarfile,tempfile
from pathlib import Path
from unittest import TestCase,main,mock
SOURCE=Path(__file__).with_name("KMJ_GOOGLE_V3_20261117_RESTORE_HELPER.py")
spec=importlib.util.spec_from_file_location("kmj_google_fresh_restore_fixture",SOURCE)
assert spec and spec.loader
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def nested(*,bad_link=False,special=False):
    buff=io.BytesIO()
    with tarfile.open(fileobj=buff,mode="w:gz") as pack:
        for name in ("./","./nested"):
            entry=tarfile.TarInfo(name);entry.type=tarfile.DIRTYPE;pack.addfile(entry)
        file=tarfile.TarInfo("./nested/test.txt")
        data=b"synthetic storage"
        file.size=len(data);pack.addfile(file,io.BytesIO(data))
        link=tarfile.TarInfo("./nested/link")
        link.type=tarfile.SYMTYPE
        link.linkname="../../outside" if bad_link else "test.txt"
        pack.addfile(link)
        if special:
            s=tarfile.TarInfo("./nested/device")
            s.type=tarfile.CHRTYPE
            pack.addfile(s)
    return buff.getvalue()

def bundle(*,bad_digest=False,bad_metadata=False,bad_dump=False,bad_link=False,extra=False,special=False,dump_bytes=583129):
    dump=(b"BAD!!" if bad_dump else b"PGDMP")+b"z"*(dump_bytes-5)
    store=nested(bad_link=bad_link,special=special)
    metadata=(b"schema=kmj.offsite.fresh.x25519.v1\n"
              +(b"created_utc=20260101T010101Z\n" if bad_metadata else b"created_utc=20261117T100210Z\n")
              +b"contains=production_pg_dump_and_storage\n"
              +b"secrets_env=EXCLUDED\n")
    parts={"database.dump":dump,"storage.tar.gz":store,"metadata.txt":metadata}
    lines=[hashlib.sha256(parts[k]).hexdigest()+"  "+k for k in ("database.dump","storage.tar.gz","metadata.txt")]
    if bad_digest:lines[0]="0"*64+"  database.dump"
    parts["SHA256SUMS"]=("\n".join(lines)+"\n").encode("ascii")
    buff=io.BytesIO()
    with tarfile.open(fileobj=buff,mode="w:gz") as pack:
        for name,value in parts.items():
            e=tarfile.TarInfo(name);e.size=len(value)
            pack.addfile(e,io.BytesIO(value))
        if extra:
            e=tarfile.TarInfo("unapproved.txt");e.size=3;pack.addfile(e,io.BytesIO(b"bad"))
    buff.seek(0)
    return buff

class FreshRestoreTests(TestCase):
    def case(self,**flags):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                m.inspect_bundle(bundle(**flags),Path(tmp))
            return out.getvalue(), sorted(x.name for x in Path(tmp).iterdir())
    def test_four_exact_members_checksums_and_storage(self):
        output,names=self.case()
        self.assertIn("SOURCE_SHA256_MANIFEST=EXACT_ALL_THREE_PASS",output)
        self.assertIn("STORAGE_INNER_TAR=NONEXTRACTING_VALIDATION_PASS",output)
        self.assertIn("FRESH_PGDMP_BYTES=583129",output)
        self.assertEqual(names,["database.dump","storage.tar.gz"])
    def test_dynamic_valid_pg_dump_size_accepted_by_exact_manifest(self):
        result,names=self.case(dump_bytes=609317)
        self.assertIn("FRESH_PGDMP_BYTES=609317",result)
        self.assertEqual(names,["database.dump","storage.tar.gz"])

    def test_sender_created_utc_and_manifest_are_required(self):
        result,_=self.case()
        self.assertIn("FRESH_METADATA_DATE=20261117_VERIFIED",result)
        with self.assertRaisesRegex(m.Block,"SOURCE_MANIFEST_MISMATCH"):
            self.case(bad_digest=True)
    def test_date_boundary_and_storage_symlink_still_fail_closed(self):
        with self.assertRaisesRegex(m.Block,"FRESH_METADATA_SCHEMA_OR_DATE"):
            self.case(bad_metadata=True)
        with self.assertRaisesRegex(m.Block,"STORAGE_SYMLINK_ESCAPE"):
            self.case(bad_link=True)
    def test_exact_new_cipher_fingerprint_is_pinned(self):
        self.assertEqual(m.CIPHER_SHA,"6755926098fe9a6fc00d4669337025b4ad2d033d7ea039c0a5d6aef17421c87d")
        self.assertEqual(m.CIPHER_BYTES,442310)
        self.assertEqual(m.DUMP_SIZE_PROOF,"BOUNDED_AND_MANIFEST_ATTESTED")
        self.assertEqual(m.BACKUP_STAMP,"20261117T100210Z")

    def test_stale_nov15_cipher_not_admitted(self):
        self.assertNotEqual(m.CIPHER_SHA,"f65df6cdf5ee2a54c5eca1a1e0ad2b82a7c11b4a8997893108e2684c60c53a7e")
        self.assertNotEqual(m.CIPHER_BYTES,441334)

    def test_minimum_dump_size_rejected(self):
        with self.assertRaisesRegex(m.Block,"PGDMP_RECEIPT_SIZE"):
            self.case(dump_bytes=60)

    def test_oversized_dump_size_rejected_without_allocation(self):
        import types
        oversized=types.SimpleNamespace(name="database.dump",size=m.MAX_DUMP_BYTES+1,isfile=lambda:True)
        with self.assertRaisesRegex(m.Block,"PGDMP_RECEIPT_SIZE"):
            m.digest_extract(oversized,None,Path("/tmp"),"database.dump",True)

    def test_wrong_manifest_rejected(self):
        with self.assertRaisesRegex(m.Block,"SOURCE_MANIFEST_MISMATCH"):
            self.case(bad_digest=True)
    def test_old_metadata_date_rejected(self):
        with self.assertRaisesRegex(m.Block,"FRESH_METADATA_SCHEMA_OR_DATE"):
            self.case(bad_metadata=True)
    def test_invalid_pg_dump_magic_rejected(self):
        with self.assertRaisesRegex(m.Block,"FRESH_PGDMP_MAGIC"):
            self.case(bad_dump=True)
    def test_storage_symlink_escape_rejected(self):
        with self.assertRaisesRegex(m.Block,"STORAGE_SYMLINK_ESCAPE"):
            self.case(bad_link=True)
    def test_storage_special_entry_rejected(self):
        with self.assertRaisesRegex(m.Block,"STORAGE_UNSAFE_MEMBER"):
            self.case(special=True)
    def test_extra_outer_member_rejected(self):
        with self.assertRaisesRegex(m.Block,"OUTER_NAMES_OR_DUPLICATE"):
            self.case(extra=True)
    def test_selftest_does_not_touch_remote_source(self):
        with mock.patch.object(m,"source") as parent,contextlib.redirect_stdout(io.StringIO()) as out:
            m.selftest()
        parent.assert_not_called()
        self.assertIn("REAL_CIPHERTEXT_READ=NO",out.getvalue())
    def test_reject_bad_paths_and_output_values(self):
        for name in ("/etc/shadow","a/../b","../escape","a\\b"):
            with self.assertRaises(m.Block):m.archive_name(name)
        with self.assertRaises(m.Block):m.emit("SECRET","/root/private/key")
    def test_wrong_mode_blocked_before_import(self):
        with mock.patch.object(m.os,"geteuid",return_value=0),\
             mock.patch.object(m.sys,"argv",["helper","--extract","/tmp/random"]),\
             mock.patch.object(m,"source") as source,\
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(),2)
        source.assert_not_called()

if __name__=="__main__":main()
