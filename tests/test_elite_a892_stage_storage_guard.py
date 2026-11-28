import shutil
import subprocess
from pathlib import Path
import unittest

GUARD = Path(__file__).resolve().parents[1] / "scripts/operations/elite-a892-stage-storage-prepend.php"


@unittest.skipUnless(shutil.which("php"), "PHP CLI required")
class StorageGuardTests(unittest.TestCase):
    def verdict(self, records):
        code = (
            'require $argv[1]; '
            'echo kmj_a892_mount_record_valid(stream_get_contents(STDIN), "/fixed/target") '
            '? "PASS" : "DENY";'
        )
        p = subprocess.run(["php", "-r", code, str(GUARD)], input=records,
                           text=True, capture_output=True, timeout=10, check=True)
        return p.stdout

    def test_valid_record(self):
        self.assertEqual(self.verdict("12 8 8:1 /source /fixed/target rw,nosuid,nodev,noexec - ext4 /dev/sda1 rw\n"), "PASS")

    def test_absent_record(self):
        self.assertEqual(self.verdict("12 8 8:1 /source /elsewhere rw,nosuid,nodev,noexec - ext4 /dev/sda1 rw\n"), "DENY")

    def test_missing_restrictions(self):
        self.assertEqual(self.verdict("12 8 8:1 /source /fixed/target rw,nosuid,nodev - ext4 /dev/sda1 rw\n"), "DENY")

    def test_duplicate_record(self):
        row = "12 8 8:1 /source /fixed/target rw,nosuid,nodev,noexec - ext4 /dev/sda1 rw\n"
        self.assertEqual(self.verdict(row + row), "DENY")

    def test_readonly_mount(self):
        self.assertEqual(self.verdict("12 8 8:1 /source /fixed/target ro,nosuid,nodev,noexec - ext4 /dev/sda1 ro\n"), "DENY")


if __name__ == "__main__":
    unittest.main()
