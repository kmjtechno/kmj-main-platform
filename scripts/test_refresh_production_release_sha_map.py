import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location(
    "refresh", Path(__file__).parent / "operations/refresh_production_release_sha_map.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TransactionTests(unittest.TestCase):
    def test_success(self):
        write, validate, reload = Mock(), Mock(), Mock()
        self.assertEqual(m.transaction("old", "new", lambda: True, write,
                                       validate, reload, lambda: True), "MAP_REFRESHED")
        write.assert_called_once_with("new")
        self.assertEqual(validate.call_count, 2)
        reload.assert_called_once()

    def test_initial_witness_blocks_write(self):
        write = Mock()
        with self.assertRaisesRegex(ValueError, "PREVIOUS_LIVE"):
            m.transaction("old", "new", lambda: True, write, Mock(), Mock(), lambda: False)
        write.assert_not_called()

    def test_failed_config_restores_previous(self):
        write, reload = Mock(), Mock()
        validate = Mock(side_effect=[None, RuntimeError("syntax"), None])
        with self.assertRaisesRegex(RuntimeError, "syntax"):
            m.transaction("old", "new", lambda: True, write, validate, reload, lambda: True)
        self.assertEqual([c.args for c in write.call_args_list], [("new",), ("old",)])
        reload.assert_called_once()

    def test_failed_post_witness_restores_previous(self):
        write, reload = Mock(), Mock()
        witness = Mock(side_effect=[True, False, True])
        with self.assertRaisesRegex(ValueError, "POST_MAP_WITNESS"):
            m.transaction("old", "new", lambda: True, write, Mock(), reload, witness)
        self.assertEqual([c.args for c in write.call_args_list], [("new",), ("old",)])
        self.assertEqual(reload.call_count, 2)

    def test_failed_rollback_is_not_pass(self):
        witness = Mock(side_effect=[True, False, False])
        with self.assertRaisesRegex(RuntimeError, "ROLLBACK_WITNESS"):
            m.transaction("old", "new", lambda: True, Mock(), Mock(), Mock(), witness)

    def test_idempotent_no_reload(self):
        write, reload = Mock(), Mock()
        self.assertEqual(m.transaction("old", "old", lambda: True, write, Mock(), reload, lambda: True),
                         "MAP_ALREADY_READY")
        write.assert_not_called()
        reload.assert_not_called()

if __name__ == "__main__":
    unittest.main()
