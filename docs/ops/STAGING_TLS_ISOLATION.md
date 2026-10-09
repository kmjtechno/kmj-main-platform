# Staging DNS/TLS isolation preflight

The public marketing release must **not** use the production app as a stand-in for staging. No TLS bypass, host-header spoofing, production credential copy, or deployment to the live production directory is permitted.

Run this read-only diagnostic on an authorized machine:

```sh
python3 ops/staging/preflight_origin.py
python3 -m unittest discover -s tests -p 'test_staging_origin_preflight.py' -v
```

Exit code 0 means only that DNS resolves to separate address sets and Python's system-trusted TLS handshake validated the staging hostname. Exit code 2 blocks the release, returning fixed reason codes. **A PASS does not prove application, database, account, queue, storage, secret or network isolation.**

As of October 9, 2026, `staging.kmjtechno.com` resolves to the public production IP `151.243.146.95` and the presented certificate does not include that staging hostname. The preflight must therefore FAIL until separate infrastructure and a trusted staging certificate are established.

Before accepting staging, verify an approved isolated staging host, dedicated configuration and database, exact deployment SHA, trusted HTTPS, access controls, and guest/signed-in browser testing. The existing [staging promotion policy](staging-promotion.md) and browser QA scripts remain in force. Make DNS/certificate changes only through the authorized infrastructure change process with rollback; do not change `kmjtechno.com` production records.
