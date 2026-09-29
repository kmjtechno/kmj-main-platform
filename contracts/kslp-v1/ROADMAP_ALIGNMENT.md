# KSLP-v1 Roadmap Alignment

Authoritative chain remains: Account -> Organization -> Subscription -> Entitlement -> License -> Device Activation.

Aligned now:
- Main Platform remains commercial/license authority; product clients have no database authority.
- Ed25519 asymmetric verification, server binding, renewable leases, revocation, key IDs and separate license/release/evidence trust domains.
- Native Rust verifier now consumes the canonical KSLP-v1 golden vector.
- Delegated own-product licensing is subscription-gated; a vendor subscription authorizes product registration/issuance policy, not an end-user entitlement by itself.
- Private signing keys remain outside application database, repository, frontend and customer artifacts.

Required before COMPLETE:
- Master roadmap names CWT/COSE as the target compact token encoding. Current KSLP-v1 compact JSON envelope uses standard Ed25519 but is not yet CWT/COSE. Treat the wire encoding as provisional until this is reconciled with an audited COSE/CBOR implementation and new cross-runtime vectors.
- Main Platform short offline grace is continuity protection. Extended/offline commercial mode must remain explicitly sold/approved, matching roadmap section 12.3.
- CloudOS must consume the native verifier through a thin wrapper or prove byte-for-byte compatible behavior against all canonical vectors.
- All 12 evidence gates and real Main Platform <-> real CloudOS E2E remain mandatory.
