"""Source-only safety contract for reviewed KMJ staging V4 inventory."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parent / "operations" /
          "audit-staging-shared-root-v4-20261028.sh")
TEXT = SOURCE.read_text(encoding="utf-8")


class StagingV4InventoryContract(unittest.TestCase):
    def test_fixed_host_root_and_zero_arguments(self):
        self.assertIn('"$(hostname -s)" == KMJ-elite', TEXT)
        self.assertIn('"$(id -u)" -eq 0 && $# -eq 0', TEXT)

    def test_live_release_pointers_rechecked(self):
        self.assertIn("expected_prod=/home/kmjprod/releases/platform-8070dad72c55", TEXT)
        self.assertIn("old=9d15e14e39564ffb1e66085a483feb8331f9718f", TEXT)
        self.assertIn("PRODUCTION_POINTER_DRIFT", TEXT)
        self.assertIn("STAGING_POINTER_DRIFT", TEXT)

    def test_secure_root_parent_is_preserved(self):
        self.assertIn("'/home/kmjstage/shared'", TEXT.replace("shared=/home/kmjstage/shared", "'/home/kmjstage/shared'"))
        self.assertIn('== \'0:0:755\'', TEXT)
        self.assertIn("SHARED_PARENT_POLICY=PASS_ROOT_OWNED_0755", TEXT)

    def test_source_scope_and_no_dereferencing_symlinks(self):
        self.assertIn('readlink -f -- "$source_link"', TEXT)
        self.assertIn("/home/kmjstage/releases/*/apps/platform/storage/app", TEXT)
        self.assertIn("SOURCE_OUT_OF_SCOPE", TEXT)
        self.assertIn('! -L "$source_dir"', TEXT)

    def test_metadata_only_no_file_names_in_receipt(self):
        for cmd in ('find "$source_dir" -xdev -type f -printf', 'find "$source_dir" -xdev -type l -printf',
                    'du -sb -- "$source_dir"', 'SOURCE_RELEASE_REFERENCES='):
            self.assertIn(cmd, TEXT)
        self.assertNotIn('find "$source_dir" -print', TEXT)

    def test_fail_closed_on_unknown_target(self):
        self.assertIn('target_kind=SYMLINK_REVIEW', TEXT)
        self.assertIn('target_kind=DIRECTORY_OCCUPIED', TEXT)
        self.assertIn('target_kind=OTHER_OCCUPIED', TEXT)

    def test_only_receipt_mutation_allowed(self):
        for forbidden in ("chown ", "chgrp ", "rsync ", "systemctl ", "nginx -s ",
                          "mv -", "rm -rf", "unlink ", "ln -s ", "chmod -R",
                          "psql ", "pg_dump ", "curl ", "git reset", "--delete"):
            self.assertNotIn(forbidden, TEXT)
        self.assertIn('tmp="$(mktemp "$qa/', TEXT)
        self.assertIn('ln -- "$tmp" "$out"', TEXT)
        self.assertIn("OWNER_APPROVAL=NOT_ATTESTED", TEXT)
        self.assertIn("BACKUP_RESTORE=NOT_ATTESTED", TEXT)
        self.assertIn("CUSTOMER_FILES_MODIFIED=NO", TEXT)

    def test_receipt_no_clobber_and_restricted_location(self):
        self.assertIn("! -e \"$out\" && ! -L \"$out\"", TEXT)
        self.assertIn('out="$qa/KMJ_STAGE_SHARED_INVENTORY_V4_20261028.txt"', TEXT)


if __name__ == "__main__":
    unittest.main()
