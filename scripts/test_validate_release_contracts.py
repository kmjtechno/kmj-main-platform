#!/usr/bin/env python3
"""Offline negative tests for the release contract validator."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "validate_release_contracts.py"
spec = importlib.util.spec_from_file_location("release_contracts", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GOOD = json.loads((Path(__file__).resolve().parents[1] / "release" / "contracts" / "main-platform.release.contract.json").read_text())


class ReleaseContractTests(unittest.TestCase):
    def errors(self, change):
        obj = copy.deepcopy(GOOD)
        change(obj)
        return mod.validate(obj, "main-platform.release.contract.json")

    def test_committed_contracts_are_valid(self):
        self.assertEqual(mod.main(), 0)

    def test_shell_commands_and_paths_are_never_accepted(self):
        for bad in ("npm test; rm -rf /", "../../etc/passwd", "$(id)", "/usr/bin/x", "a b"):
            self.assertTrue(self.errors(lambda o, b=bad: o["stage"].update(gate=b)), bad)
            self.assertTrue(self.errors(lambda o, b=bad: o["health"].update(probe=b)), bad)

    def test_unknown_and_missing_keys_fail(self):
        self.assertTrue(self.errors(lambda o: o.update(command="make")))
        self.assertTrue(self.errors(lambda o: o.update(target_sha="a" * 40)))
        self.assertTrue(self.errors(lambda o: o.pop("rollback")))
        self.assertTrue(self.errors(lambda o: o["stage"].update(extra="x")))

    def test_owner_approval_cannot_be_relaxed(self):
        for value in ("auto", "agent", "none", True, ""):
            self.assertTrue(self.errors(lambda o, v=value: o.update(approval=v)), value)

    def test_branch_repository_and_kind_are_pinned(self):
        self.assertTrue(self.errors(lambda o: o.update(default_branch="dev")))
        self.assertTrue(self.errors(lambda o: o.update(repository="someone/else")))
        self.assertTrue(self.errors(lambda o: o.update(kind="shell")))
        self.assertTrue(self.errors(lambda o: o.update(schema_version=True)))

    def test_required_checks_are_plain_unique_names(self):
        self.assertTrue(self.errors(lambda o: o.update(required_checks=[])))
        self.assertTrue(self.errors(lambda o: o.update(required_checks=["a;b"])))
        self.assertTrue(self.errors(lambda o: o.update(required_checks=["x", "x"])))
        self.assertTrue(self.errors(lambda o: o.update(required_checks=["x"] * 0 + [str(i) for i in range(21)])))

    def test_filename_must_match_project_and_duplicates_are_rejected(self):
        obj = copy.deepcopy(GOOD)
        self.assertTrue(mod.validate(obj, "other.release.contract.json"))
        with self.assertRaises(ValueError):
            mod.strict_load(b'{"a": 1, "a": 2}')
        with self.assertRaises(ValueError):
            mod.strict_load(b'{"a": NaN}')
        with self.assertRaises(ValueError):
            mod.strict_load(b"[" + b" " * 9000 + b"]")

    def test_destructive_requires_an_artifact_and_empty_dir_fails(self):
        self.assertTrue(self.errors(lambda o: o.update(data_risk="destructive", signing="none")))
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(mod.main(Path(td)), 1)


    def test_attestation_probes_are_optional_but_strict(self):
        self.assertFalse(self.errors(lambda o: o.update(staging_qa={"probe": "authenticated-surfaces"})))
        for bad in ("make test", "../x", "$(id)", "a b"):
            self.assertTrue(self.errors(lambda o, b=bad: o.update(staging_qa={"probe": b})), bad)
            self.assertTrue(self.errors(lambda o, b=bad: o.update(restore={"probe": b})), bad)
        self.assertTrue(self.errors(lambda o: o.update(restore={"probe": "x1", "cmd": "y"})))

    def test_data_changing_release_must_name_a_restore_probe(self):
        self.assertTrue(self.errors(lambda o: (o.update(data_risk="migrations"), o.pop("restore", None))))
        self.assertFalse(self.errors(lambda o: o.update(data_risk="migrations", restore={"probe": "disposable-pg-restore"})))
        self.assertFalse(self.errors(lambda o: o.update(data_risk="none")))


if __name__ == "__main__":
    unittest.main()
