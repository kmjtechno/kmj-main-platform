# apps/platform

Primary Main Platform application boundary.

Expected responsibilities: public/customer/operator/developer experiences, application composition, HTTP entry points and orchestration across domain modules.

Rules:
- Business authority stays in domain packages/services, not controllers or UI components.
- No direct Cloud Nexus dependency.
- No provider-specific AI or payment logic in domain code.
- Production runtime/framework versions are not pinned here until current supported releases are verified.
