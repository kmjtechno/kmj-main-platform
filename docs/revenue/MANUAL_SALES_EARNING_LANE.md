# KMJ Manual Sales Earning Lane

This staging-first lane is the shortest governed path to accept a paid customer before a live payment-provider integration is activated.

## Flow

1. A passkey-gated Platform Owner activates a commercial product.
2. An organization owner or admin opens Purchase Center and submits an idempotent purchase request.
3. Payment is collected externally using an owner-approved channel outside this software.
4. A Platform Owner records the currency, amount in minor units, and external payment confirmation reference.
5. Payment confirmation changes only the commercial order state. It does not grant an entitlement or license.
6. The Platform Owner explicitly fulfills the confirmed order into an entitlement.
7. The existing governed licensing flow can then issue/validate/revoke product access.

## Safety boundary

- No payment-provider credentials are required by this lane.
- No live billing provider is activated by this lane.
- Customer users cannot confirm payment evidence.
- Organization membership/capability is rechecked server-side for purchase requests.
- Commercial product slugs are immutable facts: an existing slug cannot be silently rebound to another name/status.
- Payment confirmation remains separate from entitlement and license authority.

A live Razorpay/Stripe/provider adapter can be connected later after explicit owner approval without changing the authority boundary above.
