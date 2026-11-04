"""Synthetic Nginx vhost classifier and no-mutation safety contracts."""
import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/"scripts/operations/KMJ_STAGE_VHOST_ROUTE_PREFLIGHT_20261104.py"
spec=importlib.util.spec_from_file_location("kmj_route_audit",SOURCE)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

class VhostAuditTests(unittest.TestCase):
    def test_no_write_calls(self):
        code=SOURCE.read_text()
        compile(code,str(SOURCE),"exec")
        tree=ast.parse(code)
        seen=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Call):
                x=n.func
                if isinstance(x,ast.Attribute) and isinstance(x.value,ast.Name):
                    seen.append(x.value.id+"."+x.attr)
        for bad in (
            "os.chown","os.chmod","os.mkdir","os.unlink","os.symlink",
            "os.rename","os.replace","os.write","os.system","subprocess.Popen",
            "Path.write_text","Path.write_bytes","socket.socket"):
            self.assertNotIn(bad,seen)
        for bad in ("systemctl reload","systemctl restart","nginx -s reload",
                    "git reset","curl --data","shell=True","DROP DATABASE"):
            self.assertNotIn(bad,code)
        self.assertIn('"NGINX_CHANGE","NONE"',code)

    def test_canonical_scopes(self):
        self.assertEqual(str(m.VHOST),"/etc/nginx/sites-enabled/staging.kmjtechno.com.conf")
        self.assertEqual(str(m.TARGET),"/etc/nginx/sites-available/staging.kmjtechno.com.conf")
        self.assertEqual(m.SHA,"a9796a25a2801cd303a69f5ad468aa9a704e5fff")
        self.assertEqual(m.PROD_OLD,"platform-574e443a2c75")

    def test_vhost_routes_legacy_and_candidate(self):
        sample=b"""
        # server_name malicious.example; fastcgi_pass unix:/run/php/kmjstage-a979-php84-fpm.sock;
        server {
          listen 443 ssl;
          server_name staging.kmjtechno.com;
          ssl_certificate /etc/ssl/stage.crt;
          ssl_certificate_key /etc/ssl/stage.key;
          root /home/kmjstage/htdocs/staging.kmjtechno.com/public;
          location / { return 503; }
          location ~ \\.php$ { fastcgi_pass unix:/run/php/kmjstage-php84-fpm.sock; }
        }
        """
        p=m.patterns(sample)
        for key in ("host","placeholder","has_https","has_cert","has_key","fastcgi_old","root_old"):
            self.assertTrue(p[key],key)
        for key in ("fastcgi_new","root_new"):
            self.assertFalse(p[key],key)
        live=m.patterns(b"server_name staging.kmjtechno.com; root "+str(m.PUBLIC).encode()+b"; fastcgi_pass unix:"+str(m.SOCKET).encode()+b";")
        self.assertTrue(live["root_new"])
        self.assertTrue(live["fastcgi_new"])
        self.assertFalse(live["placeholder"])

    def test_classification_never_returns_raw_config(self):
        s=b"server_name staging.kmjtechno.com; # secret=password\n"
        self.assertTrue(m.patterns(s)["host"])
        self.assertNotIn("secret",repr(m.patterns(s)))

    def test_nonroot_and_wronghost_refuse_early(self):
        with patch.object(sys,"argv",["audit.py"]), \
             patch.object(m.os,"geteuid",return_value=1001), \
             patch.object(m,"read_vhost",side_effect=AssertionError("should not read")):
            self.assertEqual(m.main(),2)
        with patch.object(sys,"argv",["audit.py"]), \
             patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.socket,"gethostname",return_value="not-elite"), \
             patch.object(m,"read_vhost",side_effect=AssertionError("should not read")):
            self.assertEqual(m.main(),2)

    def test_failed_nginx_diagnostic_only_enum(self):
        with patch.object(m.subprocess,"run",side_effect=OSError("private")):
            self.assertFalse(m.service_check("/usr/sbin/nginx",["-t"]))

    def test_read_vhost_rejects_out_of_scope_link(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            real=root/"actual"
            link=root/"staging.conf"
            real.write_text("server_name staging.kmjtechno.com;")
            link.symlink_to(real)
            with patch.multiple(m,VHOST=link,TARGET=root/"other"), \
                 patch.object(m,"trusted_chain",return_value=True):
                contents,status=m.read_vhost()
                self.assertIsNone(contents)
                self.assertEqual(status,"SYMLINK_OUT_OF_SCOPE")

if __name__=="__main__":
    unittest.main()
