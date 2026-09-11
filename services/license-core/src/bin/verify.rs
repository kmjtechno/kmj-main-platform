use kmj_license_core::{VerifyContext, verify_sandbox_license};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashSet,
    env,
    io::{self, Read},
};

#[derive(Debug, Deserialize)]
struct VerifyRequest {
    license: String,
    now: i64,
    expected_product_id: String,
    expected_entitlement_id: String,
    #[serde(default)]
    revoked_jtis: Vec<String>,
}

#[derive(Debug, Serialize)]
struct VerifyResponse<T> {
    valid: bool,
    reason: Option<&'static str>,
    claims: Option<T>,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("license verifier request failed: {error}");
        std::process::exit(2);
    }
}
fn run() -> Result<(), Box<dyn std::error::Error>> {
    let secret = env::var("KMJ_SANDBOX_LICENSE_SECRET")?;
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: VerifyRequest = serde_json::from_str(&input)?;
    let revoked = request.revoked_jtis.into_iter().collect::<HashSet<_>>();
    let context = VerifyContext {
        now: request.now,
        expected_product_id: &request.expected_product_id,
        expected_entitlement_id: &request.expected_entitlement_id,
        revoked_jtis: &revoked,
    };
    let result = verify_sandbox_license(&request.license, secret.as_bytes(), &context);
    let response = VerifyResponse {
        valid: result.valid,
        reason: result.reason,
        claims: result.claims,
    };
    println!("{}", serde_json::to_string(&response)?);
    Ok(())
}
