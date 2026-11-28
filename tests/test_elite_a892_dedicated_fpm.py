import importlib.util
from pathlib import Path
import tempfile
import unittest

P=Path(__file__).resolve().parents[1]/"scripts/operations/prepare-elite-a892-dedicated-fpm-20261128.py"
spec=importlib.util.spec_from_file_location("dedicated_fpm",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DedicatedFpmTests(unittest.TestCase):
    def test_standalone_pool_not_global(self):
        config=m.config_bytes().decode()
        self.assertIn("listen = "+str(m.SOCKET)+"\n",config)
        self.assertIn("php_admin_value[auto_prepend_file] = "+str(m.GUARD)+"\n",config)
        self.assertIn("user = kmjstage\n",config)
        self.assertNotIn("include",config)
        self.assertNotIn("/home/kmjprod",config)

    def test_candidate_specific_mount_dependency(self):
        unit=m.unit_bytes().decode()
        self.assertIn("BindsTo="+m.MOUNT+"\n",unit)
        self.assertIn("After="+m.MOUNT+"\n",unit)
        self.assertIn("RequiresMountsFor="+str(m.TARGET)+"\n",unit)
        self.assertIn("PrivateMounts=yes\n",unit)
        self.assertNotIn("php8.4-fpm.service",unit)

    def test_boot_guard_and_network_scope(self):
        unit=m.unit_bytes().decode()
        self.assertIn("ExecStartPre=/usr/sbin/runuser -u kmjstage",unit)
        self.assertIn("kmj_a892_storage_ready()",unit)
        self.assertIn("IPAddressDeny=any\nIPAddressAllow=localhost\n",unit)
        self.assertIn("--fpm-config "+str(m.CONF),unit)

    def test_no_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"config"
            m.create(p,b"original")
            with self.assertRaises(FileExistsError):
                m.create(p,b"replacement")
            self.assertEqual(p.read_bytes(),b"original")


if __name__=="__main__":
    unittest.main()
