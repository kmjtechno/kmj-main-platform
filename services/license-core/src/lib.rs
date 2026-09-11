use base64::{Engine as _, engine::general_purpose::URL_SAFE_NO_PAD};
use hmac::{Hmac, Mac};
use serde::Deserialize;
use sha2::Sha256;
use std::collections::HashSet;

type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
pub struct SandboxClaims {
    pub environment: String,
    pub jti: String,
    pub organization_id: String,
    pub product_id: String,
    pub entitlement_id: String,
    pub issued_at: i64,
    pub expires_at: i64,
}

#[derive(Debug, Clone)]
pub struct VerifyContext<'a> {
    pub now: i64,
    pub expected_product_id: &'a str,
    pub expected_entitlement_id: &'a str,
    pub revoked_jtis: &'a HashSet<String>,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerifyResult {
    pub valid: bool,
    pub reason: Option<&'static str>,
    pub claims: Option<SandboxClaims>,
}

impl VerifyResult {
    fn invalid(reason: &'static str, claims: Option<SandboxClaims>) -> Self {
        Self {
            valid: false,
            reason: Some(reason),
            claims,
        }
    }
}

pub fn verify_sandbox_license(
    license: &str,
    secret: &[u8],
    context: &VerifyContext<'_>,
) -> VerifyResult {
    if secret.len() < 32 {
        return VerifyResult::invalid("invalid_verifier_secret", None);
    }

    let Some((encoded_payload, encoded_signature)) = license.split_once('.') else {
        return VerifyResult::invalid("malformed", None);
    };
    if encoded_signature.contains('.') {
        return VerifyResult::invalid("malformed", None);
    }
    let Ok(signature) = URL_SAFE_NO_PAD.decode(encoded_signature) else {
        return VerifyResult::invalid("malformed_signature", None);
    };
    let Ok(mut mac) = HmacSha256::new_from_slice(secret) else {
        return VerifyResult::invalid("invalid_verifier_secret", None);
    };
    mac.update(encoded_payload.as_bytes());
    if mac.verify_slice(&signature).is_err() {
        return VerifyResult::invalid("invalid_signature", None);
    }

    let Ok(payload) = URL_SAFE_NO_PAD.decode(encoded_payload) else {
        return VerifyResult::invalid("malformed_payload", None);
    };
    let Ok(claims) = serde_json::from_slice::<SandboxClaims>(&payload) else {
        return VerifyResult::invalid("invalid_payload", None);
    };

    if claims.environment != "sandbox" {
        return VerifyResult::invalid("wrong_environment", Some(claims));
    }
    if claims.jti.is_empty() {
        return VerifyResult::invalid("missing_claims", Some(claims));
    }
    if claims.expires_at <= context.now {
        return VerifyResult::invalid("expired", Some(claims));
    }
    if claims.product_id != context.expected_product_id {
        return VerifyResult::invalid("wrong_product", Some(claims));
    }
    if claims.entitlement_id != context.expected_entitlement_id {
        return VerifyResult::invalid("wrong_entitlement", Some(claims));
    }
    if context.revoked_jtis.contains(&claims.jti) {
        return VerifyResult::invalid("revoked", Some(claims));
    }

    VerifyResult {
        valid: true,
        reason: None,
        claims: Some(claims),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use pretty_assertions::assert_eq;

    const SECRET: &[u8] = b"kmj-sandbox-test-secret-32-bytes-minimum!";
    const VECTOR: &str = "eyJlbnZpcm9ubWVudCI6InNhbmRib3giLCJqdGkiOiIxMTExMTExMS0yMjIyLTMzMzMtNDQ0NC01NTU1NTU1NTU1NTUiLCJvcmdhbml6YXRpb25faWQiOiJvcmctMDAxIiwicHJvZHVjdF9pZCI6InByb2R1Y3QtMDAxIiwiZW50aXRsZW1lbnRfaWQiOiJlbnRpdGxlbWVudC0wMDEiLCJpc3N1ZWRfYXQiOjE3ODkwMDAwMDAsImV4cGlyZXNfYXQiOjE4OTM0NTYwMDB9.seV8O6qgsMDtnUMkUz--PLeevJcIsv9FDnG_ZFxG3xI";

    fn context<'a>(revoked: &'a HashSet<String>) -> VerifyContext<'a> {
        VerifyContext {
            now: 1_789_000_001,
            expected_product_id: "product-001",
            expected_entitlement_id: "entitlement-001",
            revoked_jtis: revoked,
        }
    }
    #[test]
    fn deterministic_vector_validates() {
        let revoked = HashSet::new();
        let result = verify_sandbox_license(VECTOR, SECRET, &context(&revoked));
        assert!(result.valid);
        assert_eq!(result.reason, None);
        assert_eq!(result.claims.unwrap().organization_id, "org-001");
    }

    #[test]
    fn product_binding_is_enforced() {
        let revoked = HashSet::new();
        let mut ctx = context(&revoked);
        ctx.expected_product_id = "product-other";
        let result = verify_sandbox_license(VECTOR, SECRET, &ctx);
        assert_eq!(result.reason, Some("wrong_product"));
    }

    #[test]
    fn revocation_is_enforced() {
        let revoked = HashSet::from(["11111111-2222-3333-4444-555555555555".to_string()]);
        let result = verify_sandbox_license(VECTOR, SECRET, &context(&revoked));
        assert_eq!(result.reason, Some("revoked"));
    }
    #[test]
    fn entitlement_binding_is_enforced() {
        let revoked = HashSet::new();
        let mut ctx = context(&revoked);
        ctx.expected_entitlement_id = "entitlement-other";
        let result = verify_sandbox_license(VECTOR, SECRET, &ctx);
        assert_eq!(result.reason, Some("wrong_entitlement"));
    }

    #[test]
    fn tampering_is_rejected() {
        let revoked = HashSet::new();
        let tampered = VECTOR.replacen("eyJ", "eyK", 1);
        let result = verify_sandbox_license(&tampered, SECRET, &context(&revoked));
        assert_eq!(result.reason, Some("invalid_signature"));
    }

    #[test]
    fn expiry_is_deterministic() {
        let revoked = HashSet::new();
        let mut ctx = context(&revoked);
        ctx.now = 1_893_456_000;
        let result = verify_sandbox_license(VECTOR, SECRET, &ctx);
        assert_eq!(result.reason, Some("expired"));
    }
}
