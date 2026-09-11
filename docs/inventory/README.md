# Public Surface Inventory

`docs/inventory/public-surface.yaml` is the P0 source-of-truth inventory for the KMJ TECHNO Main Platform public surface.

It records externally addressable guest/public URLs, protected control surfaces, public web-root assets, and approved system facts. The inventory is intentionally limited to the Main Platform repository and must never be populated from KMJ Cloud Nexus.

## Change rule

Any change that adds, removes, or materially repurposes a public URL or public web-root asset must update the YAML inventory in the same pull request. Approved facts may only be changed when the corresponding locked boundary/source document changes.

## Verification

Run:

```bash
python scripts/verify_public_surface.py
```

CI runs the same verifier. It fails closed when required route markers, public assets, boundary facts, or the completed P0-02 backlog state drift from the inventory.
