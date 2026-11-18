use base64::{Engine as _, engine::general_purpose::URL_SAFE_NO_PAD};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::Deserialize;

pub const KSLP_V1: &str = "KSLP-v1";
const MAX_TOKEN_BYTES: usize = 16_384;

#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Header {
    pub alg: String,
    pub kid: String,
    pub typ: String,
}

#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Claims {
    pub protocol_version: String,
    pub license_id: String,
    pub customer_id: String,
    pub product: String,
    pub plan: String,
    pub server_identity: String,
    pub activation_id: String,
    pub features: serde_json::Value,
    pub limits: serde_json::Value,
    pub iat: i64,
    pub nbf: i64,
    pub exp: i64,
    pub sequence: u64,
    pub nonce: String,
    pub kid: String,
    pub jti: String,
    pub aud: String,
    pub grace_until: Option<i64>,
}

pub fn verify(
    token: &str,
    public_key: &[u8],
    expected_kid: &str,
    expected_product: &str,
    expected_server: &str,
    now: i64,
) -> Result<Claims, &'static str> {
    if token.is_empty() || token.len() > MAX_TOKEN_BYTES {
        return Err("KSLP_MALFORMED");
    }
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return Err("KSLP_MALFORMED");
    }
    let hb = URL_SAFE_NO_PAD
        .decode(parts[0])
        .map_err(|_| "KSLP_MALFORMED")?;
    let h: Header = serde_json::from_slice(&hb).map_err(|_| "KSLP_MALFORMED")?;
    if h.alg != "EdDSA" || h.typ != KSLP_V1 {
        return Err("KSLP_UNSUPPORTED_ALGORITHM");
    }
    if h.kid != expected_kid {
        return Err("KSLP_UNKNOWN_KID");
    }
    let kb: [u8; 32] = public_key.try_into().map_err(|_| "KSLP_UNKNOWN_KID")?;
    let key = VerifyingKey::from_bytes(&kb).map_err(|_| "KSLP_UNKNOWN_KID")?;
    let sb = URL_SAFE_NO_PAD
        .decode(parts[2])
        .map_err(|_| "KSLP_MALFORMED")?;
    let sig = Signature::from_slice(&sb).map_err(|_| "KSLP_MALFORMED")?;
    key.verify(format!("{}.{}", parts[0], parts[1]).as_bytes(), &sig)
        .map_err(|_| "KSLP_INVALID_SIGNATURE")?;
    let pb = URL_SAFE_NO_PAD
        .decode(parts[1])
        .map_err(|_| "KSLP_MALFORMED")?;
    let c: Claims = serde_json::from_slice(&pb).map_err(|_| "KSLP_MALFORMED")?;
    if c.protocol_version != KSLP_V1 || c.kid != h.kid {
        return Err("KSLP_MALFORMED");
    }
    if c.license_id.is_empty()
        || c.customer_id.is_empty()
        || c.plan.is_empty()
        || c.server_identity.is_empty()
        || c.activation_id.is_empty()
        || c.nonce.is_empty()
        || c.jti.is_empty()
        || c.kid.is_empty()
        || c.iat <= 0
        || c.nbf > c.iat
        || c.sequence == 0
    {
        return Err("KSLP_MALFORMED");
    }
    if c.product != expected_product {
        return Err("KSLP_WRONG_PRODUCT");
    }
    if c.aud != "kmj-cloudos" {
        return Err("KSLP_WRONG_AUDIENCE");
    }
    if c.server_identity != expected_server {
        return Err("KSLP_SERVER_MISMATCH");
    }
    if now < c.nbf {
        return Err("KSLP_NOT_YET_VALID");
    }
    if c.exp <= c.iat || now > c.exp {
        return Err("KSLP_EXPIRED");
    }
    Ok(c)
}

#[cfg(test)]
mod tests {
    use super::*;
    use base64::engine::general_purpose::STANDARD;
    use ed25519_dalek::{Signer, SigningKey};
    use serde_json::{Value, json};

    // Deterministic key is exclusively a synthetic test fixture, never an
    // issuer private key or a deployment value.
    fn fixture_claims() -> Value {
        json!({
            "protocol_version": "KSLP-v1",
            "license_id": "test-license",
            "customer_id": "test-customer",
            "product": "KMJ_CLOUDOS",
            "plan": "trial",
            "server_identity": "ed25519:test-device",
            "activation_id": "test-activation",
            "features": {"hosting": true},
            "limits": {"nodes": 1},
            "iat": 1800000000,
            "nbf": 1799999995,
            "exp": 1800003600,
            "sequence": 1,
            "nonce": "test-nonce",
            "kid": "unit-test-kid",
            "jti": "unit-test-jti",
            "aud": "kmj-cloudos",
            "grace_until": 1800007200
        })
    }

    fn sign_test_claims(value: &Value) -> (String, [u8; 32]) {
        let signing = SigningKey::from_bytes(&[13u8; 32]);
        let header = json!({"alg": "EdDSA", "kid": "unit-test-kid", "typ": "KSLP-v1"});
        let signed = format!(
            "{}.{}",
            URL_SAFE_NO_PAD.encode(serde_json::to_vec(&header).unwrap()),
            URL_SAFE_NO_PAD.encode(serde_json::to_vec(value).unwrap())
        );
        let signature = signing.sign(signed.as_bytes());
        let token = format!(
            "{}.{}",
            signed,
            URL_SAFE_NO_PAD.encode(signature.to_bytes())
        );
        (token, signing.verifying_key().to_bytes())
    }

    #[test]
    fn strict_signed_v1_claim_types_and_audience_fail_closed() {
        let mut claims = fixture_claims();
        let (good_token, pk) = sign_test_claims(&claims);
        assert!(
            verify(
                &good_token,
                &pk,
                "unit-test-kid",
                "KMJ_CLOUDOS",
                "ed25519:test-device",
                1800000000,
            )
            .is_ok()
        );

        let invalid = [
            ("aud", json!("kmj-omnidesk"), "KSLP_WRONG_AUDIENCE"),
            ("exp", json!("1800003600"), "KSLP_MALFORMED"),
            ("sequence", json!(0), "KSLP_MALFORMED"),
            ("nbf", json!(1800000001), "KSLP_MALFORMED"),
            ("license_id", json!(""), "KSLP_MALFORMED"),
            ("exp", json!(1799999999), "KSLP_EXPIRED"),
        ];
        for (field, bad, expected_error) in invalid {
            claims[field] = bad;
            let (token, key) = sign_test_claims(&claims);
            assert_eq!(
                verify(
                    &token,
                    &key,
                    "unit-test-kid",
                    "KMJ_CLOUDOS",
                    "ed25519:test-device",
                    1800000000
                ),
                Err(expected_error),
                "KSLP-v1 field {field} did not fail closed"
            );
            claims = fixture_claims();
        }

        claims["unsigned_entitlement_override"] = json!(true);
        let (extra_token, extra_pk) = sign_test_claims(&claims);
        assert_eq!(
            verify(
                &extra_token,
                &extra_pk,
                "unit-test-kid",
                "KMJ_CLOUDOS",
                "ed25519:test-device",
                1800000000
            ),
            Err("KSLP_MALFORMED")
        );
    }

    #[test]
    fn oversized_token_is_rejected_before_parsing_or_key_access() {
        assert_eq!(
            verify(
                &"A".repeat(MAX_TOKEN_BYTES + 1),
                &[],
                "unit-test-kid",
                "KMJ_CLOUDOS",
                "ed25519:test-device",
                1800000000
            ),
            Err("KSLP_MALFORMED")
        );
    }

    #[derive(Deserialize)]
    struct Vector {
        now: i64,
        server_identity: String,
        expected_product: String,
        public_key_b64: String,
        token: String,
        expected_claims: Claims,
    }
    fn vector() -> Vector {
        serde_json::from_str(include_str!(
            "../../../contracts/kslp-v1/golden-vector-001.json"
        ))
        .unwrap()
    }
    #[test]
    fn canonical_golden_vector_passes() {
        let v = vector();
        let pk = STANDARD.decode(v.public_key_b64).unwrap();
        let c = verify(
            &v.token,
            &pk,
            "golden-v1",
            &v.expected_product,
            &v.server_identity,
            v.now,
        )
        .unwrap();
        assert_eq!(c, v.expected_claims);
    }
    #[test]
    fn tamper_and_wrong_server_fail_closed() {
        let v = vector();
        let pk = STANDARD.decode(v.public_key_b64).unwrap();
        assert_eq!(
            verify(
                &v.token,
                &pk,
                "golden-v1",
                &v.expected_product,
                "ed25519:other",
                v.now
            ),
            Err("KSLP_SERVER_MISMATCH")
        );
        let mut t = v.token.into_bytes();
        let i = t.len() / 2;
        t[i] = if t[i] == b'A' { b'B' } else { b'A' };
        let t = String::from_utf8(t).unwrap();
        assert!(
            verify(
                &t,
                &pk,
                "golden-v1",
                &v.expected_product,
                &v.server_identity,
                v.now
            )
            .is_err()
        );
    }
}
