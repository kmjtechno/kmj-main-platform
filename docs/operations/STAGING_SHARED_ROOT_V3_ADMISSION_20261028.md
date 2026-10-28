# P0: Staging shared-root V3 read-only finding (2026-10-28)

This is **source-only diagnostic interpretation**, not a deployment, owner signature,
storage migration, or production approval.

The owner-run sanitized receipt
`work/qa/KMJ_STAGE_SHARED_ROOT_V3_20261028.txt`
(SHA-256 `a5113ce9235b23dee5499fa359904b106215f19b9ed76cc7673bdf0609294403`)
reports: `/home/kmjstage/shared` is an actual directory, not a symlink,
root UID/GID 0:0, mode 0755, canonical resolved scope exact.
`/home/kmjstage` is owned by the staging UID 995; its mode/sticky bit
and mount semantics were **not** attested. The old uploads still resolve
inside an older disposable release, not the shared tree.

The V2 diagnostic blocked because it required the shared root to be owned by
`kmjstage`. **Do not blindly chown the shared root:** root ownership may
be intentional and more restrictive. Conversely, root ownership of a child
inside a staging-user-owned parent is not by itself proof that the child
cannot be renamed or replaced. Verify the parent chain, mount identity,
ACLs, sticky bits, and intended writable subdirectory with trusted
root-only read-only evidence before choosing a design.

Run `python3 -B scripts/operations/assess_stage_shared_root_v3.py RECEIPT`
only against a sanitized copy. It always exits 2, returns
`staging_switch_authorized=false`, and never accesses server storage.

Before any migration, independently attest old/new release pointers,
all symlink/hardlink references, file counts/bytes/hashes, active writers,
the exact dedicated shared destination and free space. Preserve existing
product artwork. Obtain and independently restore encrypted database and
upload backups, then use an owner-reviewed lossless copy with no deletion
and a quiesced final checksum pass. Verify rollback without discarding
either copy. Only after exact HTTPS candidate SHA, owner MFA browser
Generate/Edit/Save/Reopen, offsite restore and a fresh protected manifest
matching the actual production pointer may guarded activation be considered.

Do not run stale 91FF activation against current GitHub main, mutate
production accounts, or infer a backup PASS from a diagnostic receipt.
No additional paid service is required.
