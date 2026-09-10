# KMJ Main Platform Application Boundary

This directory contains the Main Platform application runtime.

Locked rules:
- Main Platform owns business/customer/product/licensing/release/automation authority.
- KMJ Cloud Nexus remains a separate engineering IDE and is not a runtime dependency here.
- Domain authority belongs in module packages/services, not UI visibility or provider SDKs.
- Product clients use versioned contracts and never direct database access.
- Generative AI remains cloud-only, verified-zero, with no paid fallback.
- Production deployment, DNS, billing and destructive data actions require explicit owner approval.

The Laravel starter source is imported from the exact upstream commit recorded in `bootstrap/runtime-source.yaml`.
