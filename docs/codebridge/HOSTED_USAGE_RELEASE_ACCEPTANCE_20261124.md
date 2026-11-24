# CodeBridge hosted usage and HyperSpeed acceptance

Source changes are not activation. The current internal UTC ledger and receipt verifier are not a customer billing meter.

- Verify a device signing public key through authenticated enrollment and pin it to the activation. Never accept a receipt-supplied key.
- Resolve the exact active signed KSLP account or paid seat and plan from server authorization. Reserve once before dispatch; persist immutable execution UUID, project, request hash, device and seat binding.
- Sign the fixed receipt contract on the device, verify against the reservation and pinned public key. Settle exactly once, reconcile cancellations separately from uncertain delivery, reject revoked grants. Test rollover, replay, parallel last-slot reservations and retry.
- Expose counters only after integration is verified, with UTC reset and 80% warning. Do not enable paid checkout, automatic overage or paid AI fallback.
- Verify signed CodeBridge runtime and Main Platform candidate separately. Run native ChatGPT and Claude acceptance: icons, progress ordering, JSON fallback, UI where supported, worker handles and read-only diff navigation.
- Measure first SSE frame through nginx/CDN and final result integrity. Check cross-tenant denial and no credentials in logs or UI.
- Follow the current Elite release guide, exact owner approval, staging and production smoke gates. No live release is implied by CI.
