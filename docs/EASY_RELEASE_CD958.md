# Easy release: cd958 proposal

Status: source proposal; not installed, not production approval, not a completed deployment.

The owner requested one simple deployment method with zero additional cost.
Use the existing protected release controller and systemd unit. A new deployment
engine or a dashboard that issues root commands would duplicate the safety logic.

The supplied `scripts/kmj_release.py` offers two actions:

* `check`: run the exact SHA-256-pinned existing readiness doctor from a root-private
  snapshot and print its blockers. No activation request.
* `deploy`: perform the same check, then request only the existing guarded release
  unit. The controller must independently recheck approval and pointer under its lock.

The interface is fixed to candidate cd9580701d3cea19d7d4e4c96ebe70c0553fbf37 and
current release platform-574e443a2c75. It rejects missing or duplicate gates,
nonzero doctor exit, explicit blockers, stale approvals and other candidates.
It never writes approval flags, migrates storage, runs database migrations itself,
copies runtime secrets or stops Nginx/FPM/queue/scheduler.

An activation request or successful unit exit is not live verification.
Timeout leaves the unit state unknown; inspect before retrying.
Offsite restore and authenticated QA are not attested by this launcher.

## Installation boundary

Do not execute this proposal as root until reviewed and installed through the
authorized operator workflow. No installer is included. The earlier privileged
storage-migration rejection remains in force. This facade does not resolve or
bypass that rejection and must not be used to bypass missing release evidence.

## One-time prerequisites still outstanding

1. Review the prior storage-staging rejection and establish an approved migration
   workflow. Quiesce production ingress and drain queue (120-second configured
   stop timeout); pause the scheduler timer and drain in-flight scheduler jobs.
   The production PHP pool uses 127.0.0.1:21084; staging uses a different socket
   under the same PHP 8.4 service. Do not stop the entire shared service blindly.
2. Preserve physical live and candidate storage directories for recovery; recheck
   persistent content after writers stop. Connect both to the reviewed shared
   target with crash-recovery and rollback evidence before restarting writers.
3. Run the existing hash-pinned materializer; verify env byte parity and privacy.
4. Complete exact-candidate migration/rollback rehearsal and authenticated QA.
5. Reconcile protected approval from actual evidence, not caller-reported PASS.
6. Review/install the facade, request guarded activation, and independently verify
   real deployed SHA, HTTPS, owner UI and rollback health.

These are prerequisites, not steps implemented by the facade.

## Validation

`python3 -m unittest discover -s tests -p test_easy_release.py -v`

Tests cover gate parsing, untrusted source rejection, check-only behavior,
blocked activation, nonroot rejection and unknown timeout state. These are local
launcher tests; they do not establish real-host deployment readiness.
