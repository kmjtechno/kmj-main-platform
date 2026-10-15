"""Offline deterministic first-use client tests: no network, no secrets, no paid plan."""
import hashlib
import importlib.util
import pathlib
import unittest
from uuid import UUID

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "kmj_kslp_first_use",
    HERE.parent / "apps" / "platform" / "public" / "sdk" / "python" / "kmj_kslp_first_use.py",
)
kmj = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = kmj
SPEC.loader.exec_module(kmj)

LICENSE_KEY = "KMJ1-" + "A" * 43
LICENSE_ID = "22222222-2222-4222-8222-222222222222"
CHALLENGE_ID = "33333333-3333-4333-8333-333333333333"
ACTIVATION_ID = "44444444-4444-4444-8444-444444444444"
PUBLIC = bytes(range(32))
HASH = hashlib.sha256(b"random per-install salt stored privately").hexdigest()


class ActivationTests(unittest.TestCase):
    def mock_post(self, calls, signed_lease=False, product="DEVELOPER.APP"):
        def post(url, body):
            calls.append((url, body))
            if url.endswith("/challenge"):
                return {
                    "license_id": LICENSE_ID, "challenge_id": CHALLENGE_ID,
                    "nonce": "N" * 43, "product": product,
                }
            return {
                "activation_id": ACTIVATION_ID,
                "product": product,
                "device_registered": True,
                "signed_lease_issued": signed_lease,
            }
        return post

    def register(self, **changes):
        options = dict(
            license_key=LICENSE_KEY, product="DEVELOPER.APP",
            device_public_key=PUBLIC, machine_hash=HASH,
            sign=lambda payload: bytes([7]) * 64,
        )
        options.update(changes)
        return kmj.register_device(**options)

    def test_real_request_contract_no_entitlement_and_no_optional_metadata(self):
        calls = []
        receipt = self.register(post=self.mock_post(calls))
        self.assertEqual(receipt.activation_id, ACTIVATION_ID)
        self.assertTrue(receipt.device_registered)
        self.assertFalse(receipt.signed_lease_issued)
        self.assertFalse(receipt.grants_entitlement)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1]["server_identity"], "ed25519:" + kmj._b64u(PUBLIC))
        self.assertEqual(calls[1][1]["machine_hash"], HASH)
        self.assertIsNone(calls[1][1]["platform"])
        self.assertIsNone(calls[1][1]["app_version"])
        UUID(calls[1][1]["request_id"])
        self.assertEqual(calls[1][1]["signature"], kmj._b64u(bytes([7]) * 64))
        self.assertNotIn("private_key", repr(calls))

    def test_signing_bytes_are_exact_and_consent_is_opt_in(self):
        captured = []
        def sign(message):
            captured.append(message)
            return b"z" * 64
        calls = []
        self.register(
            sign=sign, platform="windows", app_version="1.0",
            metadata_consent=True, post=self.mock_post(calls),
        )
        self.assertEqual(captured, [
            ("KSLP-ACTIVATE-v1|" + LICENSE_ID + "|" + "N" * 43).encode()
        ])
        self.assertTrue(calls[1][1]["metadata_consent"])
        self.assertEqual(calls[1][1]["platform"], "windows")
        self.assertEqual(calls[1][1]["app_version"], "1.0")

    def test_fake_signed_lease_state_never_grants_access(self):
        calls = []
        with self.assertRaisesRegex(kmj.ActivationError, "UNEXPECTED_ACTIVATION_STATE"):
            self.register(post=self.mock_post(calls, signed_lease=True))

    def test_product_mismatch_never_reaches_complete(self):
        calls = []
        with self.assertRaisesRegex(kmj.ActivationError, "CHALLENGE_RESPONSE_INVALID"):
            self.register(post=self.mock_post(calls, product="OTHER.APP"))
        self.assertEqual(len(calls), 1)

    def test_validation_rejects_before_network_request(self):
        def fail_post(*_):
            self.fail("No network request permitted")
        failures = [
            (dict(base_url="http://kmjtechno.com"), "KSLP_HTTPS_ORIGIN_REQUIRED"),
            (dict(base_url="https://kmjtechno.com/evil"), "KSLP_HTTPS_ORIGIN_REQUIRED"),
            (dict(base_url="https://kmjtechno.com@evil.test"), "KSLP_HTTPS_ORIGIN_REQUIRED"),
            (dict(base_url="https://kmjtechno.com:abc"), "KSLP_HTTPS_ORIGIN_REQUIRED"),
            (dict(base_url="https://kmjtechno.com:8443"), "KSLP_HTTPS_ORIGIN_REQUIRED"),
            (dict(product="A" * 65), "PRODUCT_INVALID"),
            (dict(license_key="abc"), "LICENSE_KEY_FORMAT_INVALID"),
            (dict(product="../wrong"), "PRODUCT_INVALID"),
            (dict(device_public_key=b"short"), "ED25519_PUBLIC_KEY_REQUIRED"),
            (dict(machine_hash="serial-number"), "MACHINE_HASH_INVALID"),
            (dict(platform="windows xp"), "PLATFORM_INVALID"),
            (dict(metadata_consent=1), "CONSENT_INVALID"),
            (dict(app_version="A" * 100), "APP_VERSION_INVALID"),
            (dict(sign=lambda _: b"short"), "ED25519_SIGNATURE_INVALID"),
        ]
        for args, code in failures:
            with self.subTest(code=code, args=args):
                with self.assertRaisesRegex(kmj.ActivationError, code):
                    self.register(post=fail_post if code != "ED25519_SIGNATURE_INVALID"
                                  else self.mock_post([]), **args)


if __name__ == "__main__":
    unittest.main()
