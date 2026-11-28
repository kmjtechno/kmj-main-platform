# Elite production SHA evidence automation

The public /login endpoint must return exactly one X-KMJ-Deploy-SHA
matching the activated release. The installed Nginx backend uses a regex
map keyed by the exact resolved document root and /login. Unknown roots
return no header. The reviewed map helper validates both the actual live
release and the protected approved candidate through the existing exact
Git verifier. It retains both entries, verifies the current public SHA
before and after a reload, and restores the original mapping on failure.

The admission broker drop-in requires the fixed SHA-map preparation service
before it can write an admission. The service has OR conditions for a real
admission intent or an exclusive root-only qualification marker, so idle
timer ticks do not perform repeated Git checks or Nginx work. This avoids starting a map service while
the autopublish launcher holds its release lock. The map service cannot
activate production, write approval or admission, or run arbitrary commands.
A successful preparation is not a deployment or a candidate HTTP witness.

Installation is opt-in and must pin the reviewed source for both Python
files, the service and the drop-in. The existing live regex map and backend
header directive are prerequisites; do not modify the shared checkout.
Before enabling the drop-in, verify systemd sandbox compatibility,
Nginx syntax, lock contention, exact current/candidate paths, stale
approval rejection, no-intent behavior and rollback on the Elite host.
An expired intent must be retried through the ordinary owner workflow.
Do not claim live acceptance solely from CI or from systemd unit startup.

The pinned installer creates the qualification marker only during a guarded
already-live check, requires a fresh root-attributed journal invocation with the exact already-live SHA map marker, and
removes the marker. A skipped unit is not a qualification success.

The existing already-live release remains untouched; the already-live
case validates its mapping and public identity without changing Nginx.
No extra server or paid service is needed.
