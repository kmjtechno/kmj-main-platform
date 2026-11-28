import importlib.util
from pathlib import Path
import unittest

P=Path(__file__).resolve().parents[1]/"scripts/operations/plan-elite-a892-stage-origin-20261128.py"
spec=importlib.util.spec_from_file_location("stage_origin",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def config():
    return f"""server {{
    server_name staging.kmjtechno.com;
    location = /register {{ return 403; }}
}}
server {{
    server_name staging.kmjtechno.com;
    root {m.MIRROR}/public;
    location / {{ try_files $uri $uri/ /index.php?$query_string; }}
    location = /index.php {{
        fastcgi_param SCRIPT_FILENAME {m.MIRROR}/code/public/index.php;
        fastcgi_pass unix:{m.OLD_SOCKET};
    }}
    location ~ \\.php$ {{ return 404; }}
    location ~ /\\. {{ deny all; }}
    location = /register {{ return 403; }}
}}
""".encode()


class OriginTests(unittest.TestCase):
    def test_exact_three_replacements(self):
        old=config()
        expected=(old.replace((m.MIRROR+"/public").encode(),str(m.APP/"public").encode())
                  .replace((m.MIRROR+"/code/public/index.php").encode(),str(m.APP/"public/index.php").encode())
                  .replace(m.OLD_SOCKET.encode(),m.NEW_SOCKET.encode()))
        self.assertEqual(m.proposal(old),expected)
        self.assertNotIn(b"X-KMJ-Deploy-SHA",expected)

    def test_refuse_unexpected_socket(self):
        with self.assertRaisesRegex(ValueError,"ROUTE_BASELINE_MISMATCH"):
            m.proposal(config().replace(m.OLD_SOCKET.encode(),b"/run/php/other.sock"))

    def test_refuse_duplicate_root(self):
        with self.assertRaisesRegex(ValueError,"ROUTE_BASELINE_MISMATCH"):
            m.proposal(config()+f"\nroot {m.MIRROR}/public;\n".encode())

    def test_refuse_registration_guard_loss(self):
        with self.assertRaisesRegex(ValueError,"REGISTER_DENIAL_SCOPE"):
            m.proposal(config().replace(b"return 403;",b"return 200;",1))

    def test_refuse_header_fabrication(self):
        with self.assertRaisesRegex(ValueError,"DEPLOY_HEADER_UNKNOWN_OR_HIDDEN"):
            m.proposal(config()+b"\nadd_header X-KMJ-Deploy-SHA fake always;\n")

    def test_exact_old_static_marker_removed_not_replaced(self):
        marker = f"    add_header X-KMJ-Deploy-SHA {m.OLD} always;\n".encode()
        original = config().replace(b"    location / {", marker+b"    location / {")
        proposed = m.proposal(original)
        self.assertNotIn(b"X-KMJ-Deploy-SHA", proposed)
        self.assertEqual(proposed.replace(b"\n\n    location / {", b"\n    location / {"), m.proposal(config()))

    def test_refuse_duplicate_or_hidden_marker(self):
        marker = f"\nadd_header X-KMJ-Deploy-SHA {m.OLD} always;\n".encode()
        with self.assertRaisesRegex(ValueError,"DEPLOY_HEADER_MULTIPLE_OR_HIDDEN"):
            m.proposal(config()+marker+b"fastcgi_hide_header X-KMJ-Deploy-SHA;\n")

    def test_refuse_dynamic_header(self):
        with self.assertRaisesRegex(ValueError,"DEPLOY_HEADER_UNKNOWN_OR_HIDDEN"):
            m.proposal(config()+b"\nadd_header X-KMJ-Deploy-SHA $upstream_http_x_kmj_deploy_sha always;\n")

    def test_refuse_storage_mapping_without_review(self):
        with self.assertRaisesRegex(ValueError,"STORAGE_ROUTE_REQUIRES_REVIEW"):
            m.proposal(config()+b"\nlocation ^~ /storage/ { alias /tmp/; }\n")

    def test_refuse_unexpected_stage_host_count(self):
        with self.assertRaisesRegex(ValueError,"STAGING_HOST_SCOPE"):
            m.proposal(config().replace(b"server_name staging.kmjtechno.com;",b"server_name kmjtechno.com;",1))


if __name__=="__main__":
    unittest.main()
