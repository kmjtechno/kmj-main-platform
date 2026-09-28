# KSLP protocol evolution

Status: locked architecture constraint.

KMJ Main Platform remains the authoritative commercial licensing control plane.

KSLP-v1 remains a supported compatibility contract during the v2 migration. Existing v1 verification behavior and golden interoperability vectors must remain valid and must not be silently reinterpreted.

KSLP-v2 targets a standards-based CWT/COSE entitlement envelope. Issuance and verification are version-explicit: unsupported or malformed versions fail closed, and there is no content sniffing or silent v1-to-v2 conversion.

Production v2 issuance is blocked until the v2 schema and algorithm profile are frozen, positive and negative interoperability vectors exist, dual-stack v1/v2 compatibility is verified, lifecycle and revocation behavior is covered, exact implementation evidence is recorded, and owner approval is given.

Until those gates pass, KSLP-v1 remains the production compatibility baseline and v2 work is non-production.
