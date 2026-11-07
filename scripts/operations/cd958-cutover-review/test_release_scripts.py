"""The recorded operator scripts parse and keep the exact pins they were executed with."""
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import unittest

RELEASE = Path(__file__).resolve().parent / "release"
PINS = {
    "KMJ_CD958_CUTOVER_OPERATOR_1A7F4A8_20261107.sh": "a13512c6c0bff8298ee7662b71946d970e868046d741f42a250c81a04d61f1de",
    "KMJ_CD958_MIGRATION_REHEARSAL_20261107.sh": "109c72763f316f90768389b3e0035e725e07b3aea798330b19645202e7242878",
    "KMJ_CD958_CONTROLLER_6D6D_TO_B192_20261107.patch": "fddf68837058c9d49db1c8489d196f6f4b351016352421a01a43739133c8f98b",
    "KMJ_CD958_RELEASE_FINISH_20261107.sh": "46955f9195cc3214db97e3d2ce39fdcc6a9e273075eaa17caca782f16dd18908",
}


class ReleaseRecordTests(unittest.TestCase):
    def test_recorded_bytes_are_exactly_what_ran(self):
        for name, pin in PINS.items():
            self.assertEqual(hashlib.sha256((RELEASE / name).read_bytes()).hexdigest(), pin, name)

    def test_readme_lists_every_pin(self):
        readme = (RELEASE / "README.md").read_text()
        for name, pin in PINS.items():
            self.assertIn(pin, readme, name)

    @unittest.skipUnless(shutil.which("bash"), "bash required")
    def test_shell_scripts_parse(self):
        for name in PINS:
            if name.endswith(".sh"):
                subprocess.run(["bash", "-n", str(RELEASE / name)], check=True)

    def test_embedded_python_compiles(self):
        for name in PINS:
            if not name.endswith(".sh"):
                continue
            text = (RELEASE / name).read_text()
            for tag, body in re.findall(r"<<'(\w+)'\n(.*?)\n\1\n", text, re.S):
                if not body.lstrip().startswith("<?php"):
                    compile(body, f"{name}:{tag}", "exec")

    def test_operator_pins_match_reviewed_runner_commit_and_bundle(self):
        text = (RELEASE / "KMJ_CD958_CUTOVER_OPERATOR_1A7F4A8_20261107.sh").read_text()
        self.assertIn("readonly COMMIT=1a7f4a883e57a45afd3afc57bb1bce3247107756", text)
        self.assertIn("readonly PIN=e64ec2f5ab3d0ed461d5140cd4eb91bdc743b7ae9080ac1fb78be4113a679999", text)

    def test_release_script_pins_controller_patch(self):
        text = (RELEASE / "KMJ_CD958_RELEASE_FINISH_20261107.sh").read_text()
        self.assertIn(PINS["KMJ_CD958_CONTROLLER_6D6D_TO_B192_20261107.patch"], text)
        self.assertIn("CTL_NEW=daa789f2fe9ddd3e39eb86b9dbc60416ecf3c9250cd7f77ba60222800750e56d", text)


if __name__ == "__main__":
    unittest.main()
