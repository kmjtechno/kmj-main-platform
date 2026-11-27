#!/usr/bin/python3
"""KMJ-elite exact-pinned installed V3 dual-local backup/health onepass.

--selftest is offline. --preflight is root-only and READ-ONLY.
--run-once is explicitly mutating: root-authenticates the ACTUAL installed
V3 source and pinned DNS/SFTP transport, creates a complete private daily
snapshot, generates fresh PostgreSQL+storage backup, sends a NEW X25519 archive
to the Google receiver with same-call SHA readback, then publishes a verified
local cipher+sidecar and daily snapshot with no-clobber atomic operations.
Only after all three backup locations succeed does it run unchanged health
unit once and require new own-invocation exit0.

Never alters existing backups, original health source, timer, release pointer,
production PostgreSQL data, DNS, firewall or SFTP keys. Incomplete phases
remain for review without falsely claiming backups. Actual receiver decrypt/
restore and production release approval are SEPARATE gates.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shlex
import socket
import stat
import subprocess
import sys
import tempfile
import types

BASE=Path("/usr/local/libexec/kmj-v3-owner-sources-certbot-20261115")
ROOT=Path("/usr/local/libexec/kmj-offsite-dual-local-v3-certbot-20261115")
DAILY=Path("/var/backups/kmj-elite-daily")
VAULT=Path("/var/backups/kmj-elite-offsite-encrypted")
STAGE=Path("/var/backups/kmj-v3-private-stage")
HEALTH=Path("/usr/local/sbin/kmj-elite-health-check")
HEALTH_SHA="2a8cb007acaea2ef8d240ee82a95b13314799dcea36c0cac594e7e5d32acca20"
UNIT="kmj-elite-health-check.service"
PINS={
 "KMJ_OFFSITE_V3_DUAL_ARTIFACT_POLICY_REVIEW_20261115.py":
  "2d3fdc5456c3ee7a75fdb133fdab5e7713e036ed659cc7008c5ec2a8df0139c7",
 "KMJ_OFFSITE_V3_LOCAL_CIPHER_PUBLISHER_REVIEW_20261115.py":
  "22c85a6a5e239055b69697d47c733e7afe07c9c5cd74cf70478d3577dc3ebc3f",
 "KMJ_OFFSITE_V3_LOCAL_DAILY_PUBLISHER_REVIEW_20261115.py":
  "58a5eb0c9d875620148cbe112e8d76793c103e9c413f1528023ea4523993e4de",
 "KMJ_OFFSITE_V3_DAILY_SOURCE_BUILDER_REVIEW_20261115.py":
  "ef310b88c2a2295c2fd7126f7e560372a164771c1baba872e5396755041a20fc",
 "KMJ_OFFSITE_V3_TRANSFER_BOUND_TRANSACTION_REVIEW_20261115.py":
  "cebc9366412ef689e4887d0ebac958989842c55fade1feff607f754c1bd209ea",
 "KMJ_OFFSITE_V3_PINNED_V2_ADMISSION_REVIEW_20261115.py":
  "a476833c2185f2271693ee5f957fc1434a782284a9c0050001ca3b2fd44594ed",
}
CONFIG={
 "letsencrypt":Path("/etc/letsencrypt"),
 "codebridge-stage":Path("/etc/systemd/system/kmj-codebridge-gateway-stage.service.d"),
 "sites-available":Path("/etc/nginx/sites-available"),
}
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LC_ALL":"C","LANG":"C","HOME":"/root"}
SHA=re.compile(r"[a-f0-9]{64}\Z")
STAMP=re.compile(r"20[0-9]{6}T[0-9]{6}Z\Z")

class Deny(Exception):
    pass

def private_bytes(path,digest,*,uid=None,maximum=131072):
    meta=os.lstat(path)
    if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink!=1
        or (uid is not None and meta.st_uid!=uid)
        or meta.st_mode&0o022 or not 128<=meta.st_size<=maximum):
        raise Deny("SOURCE_METADATA_UNTRUSTED")
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        seen=os.fstat(fd)
        body=os.read(fd,maximum+1)
        after=os.fstat(fd)
    finally:
        os.close(fd)
    ident=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    if ident(meta)!=ident(seen) or ident(seen)!=ident(after):
        raise Deny("SOURCE_RACED")
    if len(body)!=meta.st_size or hashlib.sha256(body).hexdigest()!=digest:
        raise Deny("SOURCE_SHA_UNVERIFIED")
    return body

def bundle_source():
    return {name:private_bytes(BASE/name,sha) for name,sha in PINS.items()}

# Immutable installed V3 source, not an unreviewed project checkout.
# SHA comes from the trusted V3 installed implementation receipt contract.
V3_INSTALLED=Path("/usr/local/libexec/kmj-offsite-fresh-x25519-v3-20261112.py")
V3_INSTALLED_SHA="2834ff3361027536bee0b971fae6dddb00677460f15adf3e8d81e7821853016f"
V3_PARENT_NAME="KMJ_OFFSITE_SFTP_DNS_PINNED_V2_20261112.py"
V3_PARENT_SHA="8f9165714774758a6bef05abff7bf72d655518ab7ed1c3cdd8dc588d3c85c13c"
V3_PARENT=V3_INSTALLED.with_name(V3_PARENT_NAME)


def admit_exact_installed_v3():
    """Root-authenticate deployed V3, its exact SFTP transport and live unit.

    Runtime can import code ONLY after exact SHA, owner, no-link and directory
    guards. No caller-controlled path, digest, arguments or environment.
    """
    root_owner()
    for ancestor in (Path("/usr"),Path("/usr/local"),Path("/usr/local/libexec")):
        st=os.lstat(ancestor)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:
            raise Deny("V3_RUNTIME_PARENT_UNTRUSTED")
    for path,pin in ((V3_INSTALLED,V3_INSTALLED_SHA),(V3_PARENT,V3_PARENT_SHA)):
        st=os.lstat(path)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid!=0
            or st.st_nlink!=1 or stat.S_IMODE(st.st_mode)!=0o600):
            raise Deny("V3_RUNTIME_METADATA_DRIFT")
        private_bytes(path,pin,uid=0)
    raw=private_bytes(V3_INSTALLED,V3_INSTALLED_SHA,uid=0)
    v3=types.ModuleType("kmj_installed_owner_exact_v3")
    v3.__file__=str(V3_INSTALLED)
    exec(compile(raw,str(V3_INSTALLED),"exec"),v3.__dict__)
    if (getattr(v3,"SCHEDULED",None)!=V3_INSTALLED
        or getattr(v3,"PARENT",None)!=V3_PARENT_NAME
        or getattr(v3,"PARENT_SHA",None)!=V3_PARENT_SHA
        or getattr(v3,"DROPIN",None)!=Path("/etc/systemd/system/kmj-elite-offsite-backup.service.d/97-kmj-offsite-fresh-x25519-20261112.conf")):
        raise Deny("V3_RUNTIME_IMPORT_CONTRACT_DRIFT")
    for name in ("pinned_transport","inspect","create_fresh","encrypt",
                 "exclusive_lock","schedule_unit_preflight"):
        if not callable(getattr(v3,name,None)):
            raise Deny("V3_RUNTIME_FUNCTION_MISSING")
    transport=v3.pinned_transport()
    for name in ("transfer","digest_cipher","host_key","pinned_conf","dns_address"):
        if not callable(getattr(transport,name,None)):
            raise Deny("V3_TRANSPORT_INTERFACE_DRIFT")
    v3.schedule_unit_preflight(transport)
    private_bytes(V3_INSTALLED,V3_INSTALLED_SHA,uid=0)
    private_bytes(V3_PARENT,V3_PARENT_SHA,uid=0)
    print("INSTALLED_V3_SOURCE=PINNED_EXACT")
    print("INSTALLED_V3_TRANSPORT=PINNED_EXACT")
    print("INSTALLED_V3_UNIT=EXACT_SCHEDULED")
    return v3,transport


def existing_private_directory(path):
    s=os.lstat(path)
    if (not stat.S_ISDIR(s.st_mode) or s.st_uid!=0
        or stat.S_IMODE(s.st_mode)!=0o700):
        raise Deny("PRIVATE_ROOT_DIRECTORY_UNTRUSTED")

def root_owner():
    if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        raise Deny("OWNER_ROOT_KMJ_ELITE_REQUIRED")

def parse_exact_find(line):
    if any(c in line for c in ("$(",chr(96),"\\","\r","\n")):
        raise Deny("HEALTH_SOURCE_SHELL_UNSUPPORTED")
    lex=shlex.shlex(line,posix=True,punctuation_chars=";&|()<>")
    lex.whitespace_split=True
    lex.commenters=""
    tok=list(lex)
    if len(tok)!=16 or tok[0]!="find" or tok[12:]!=["|","grep","-q","."]:
        raise Deny("HEALTH_FIND_PIPELINE_CHANGED")
    opts={tok[i]:tok[i+1] for i in (2,4,6,8,10)}
    if set(opts)!={"-mindepth","-maxdepth","-name","-type","-mtime"}:
        raise Deny("HEALTH_FIND_FLAGS_CHANGED")
    if opts["-type"]!="f" or opts["-mtime"]!="-2":
        raise Deny("HEALTH_FIND_FRESHNESS_CHANGED")
    if (opts["-mindepth"],opts["-maxdepth"]) not in (("1","1"),("2","2")):
        raise Deny("HEALTH_FIND_DEPTH_CHANGED")
    if not re.fullmatch(r"[A-Za-z0-9*?_.@+-]{1,120}",opts["-name"]):
        raise Deny("HEALTH_FIND_GLOB_UNSAFE")
    return (tok[1],opts["-mindepth"],opts["-maxdepth"],opts["-name"])

def health_contract():
    body=private_bytes(HEALTH,HEALTH_SHA,uid=0,maximum=2048)
    lines=body.decode("utf-8").splitlines()
    if len(lines)!=29 or len(body)!=1840:
        raise Deny("HEALTH_PINNED_SOURCE_CHANGED")
    a=parse_exact_find(lines[24])
    b=parse_exact_find(lines[27])
    if (a[:3]!=(str(DAILY),"2","2")
        or b[:3]!=(str(VAULT),"1","1")):
        raise Deny("HEALTH_ARCHIVE_PATH_OR_DEPTH_CHANGED")
    if not any(fnmatch.fnmatchcase(name,a[3]) for name in ("platform.dump","storage.tar.gz")):
        raise Deny("HEALTH_DAILY_GLOB_NOT_SATISFIED_BY_REAL_SNAPSHOT")
    if not fnmatch.fnmatchcase("20261115T120000Z.tar.age",b[3]):
        raise Deny("HEALTH_VAULT_GLOB_NOT_SATISFIED")
    t=shlex.split(lines[26])
    if len(t)!=3 or t[:2]!=["test","-s"] or not t[2].startswith("/"):
        raise Deny("HEALTH_METADATA_SOURCE_CHANGED")
    file=os.lstat(t[2])
    if not stat.S_ISREG(file.st_mode) or file.st_nlink!=1 or file.st_size<1:
        raise Deny("HEALTH_METADATA_NOT_NONEMPTY_FILE")
    return True

def trusted_dir(path,owners):
    obj=Path(path)
    if not obj.is_absolute() or ".." in obj.parts:
        raise Deny("SOURCE_DIRECTORY_PATH_UNSAFE")
    part=Path("/")
    for component in obj.parts[1:]:
        part=part/component
        s=os.lstat(part)
        if not stat.S_ISDIR(s.st_mode) or s.st_uid not in set(owners)|{0} or s.st_mode&0o022:
            raise Deny("SOURCE_DIRECTORY_UNTRUSTED")
    return obj

def validate_certbot_live_matrix(publisher_raw, *, expected_uid=0):
    if type(expected_uid) is not int or not 0<=expected_uid<=65535:
        raise Deny("CERTBOT_EXPECTED_UID_INVALID")
    """Read-only: three owner-pinned lineages, eight symlinks plus four regular PEMs.

    This runs on --preflight BEFORE pg_dump or creating local backup trees.
    Whitelist and O_NOFOLLOW target checks are furnished by the exact pinned
    daily publisher source; no link target, secret or source name is printed.
    """
    name="KMJ_OFFSITE_V3_LOCAL_DAILY_PUBLISHER_REVIEW_20261115.py"
    module=types.ModuleType("kmj_exact_certbot_source_guard")
    module.__file__=str(BASE/name)
    exec(compile(publisher_raw,str(BASE/name),"exec"),module.__dict__)
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC
    rootfd=os.open(CONFIG["letsencrypt"],flags)
    count=0
    links=0
    regular_files=0
    lineages=0
    try:
        rs=os.fstat(rootfd)
        if (not stat.S_ISDIR(rs.st_mode) or rs.st_uid!=expected_uid or rs.st_mode&0o022):
            raise Deny("CERTBOT_ROOT_SOURCE_UNTRUSTED")
        livefd=os.open("live",flags,dir_fd=rootfd)
        try:
            live_root=os.fstat(livefd)
            if (not stat.S_ISDIR(live_root.st_mode) or live_root.st_uid!=expected_uid
                    or live_root.st_mode&0o022):
                raise Deny("CERTBOT_LIVE_ROOT_UNTRUSTED")
            for lineage in os.listdir(livefd):
                state=os.stat(lineage,dir_fd=livefd,follow_symlinks=False)
                if stat.S_ISREG(state.st_mode):
                    # Standard Certbot live/README is not a certificate link.
                    if lineage!="README" or state.st_uid!=expected_uid or state.st_mode&0o022:
                        raise Deny("CERTBOT_LIVE_NONSTANDARD_FILE")
                    continue
                if (not stat.S_ISDIR(state.st_mode) or state.st_uid!=expected_uid
                        or state.st_mode&0o022):
                    raise Deny("CERTBOT_LIVE_LINEAGE_UNTRUSTED")
                fd=os.open(lineage,flags,dir_fd=livefd)
                try:
                    observed=os.fstat(fd)
                    if (observed.st_dev,observed.st_ino)!=(state.st_dev,state.st_ino):
                        raise Deny("CERTBOT_LINEAGE_DIRECTORY_RACE")
                    names=os.listdir(fd)
                    if len(names)>32:
                        raise Deny("CERTBOT_LINEAGE_ENTRY_LIMIT")
                    for entry in names:
                        est=os.stat(entry,dir_fd=fd,follow_symlinks=False)
                        if stat.S_ISLNK(est.st_mode) and entry not in module.CERTBOT_FILES:
                            raise Deny("CERTBOT_UNEXPECTED_LINK")
                    lineages+=1
                    for expected in module.CERTBOT_FILES:
                        before=os.stat(expected,dir_fd=fd,follow_symlinks=False)
                        if stat.S_ISLNK(before.st_mode):
                            module.certbot_link_target(rootfd,fd,"live/"+lineage,expected,{expected_uid})
                            links+=1
                        elif stat.S_ISREG(before.st_mode):
                            # Real owner inventory: four root-owned regular PEM
                            # entries across three certificate lineages.
                            # Do not treat regular files as failed symlinks,
                            # but never accept hardlinks, unsafe modes, or
                            # files that change during bounded verification.
                            if (before.st_uid!=expected_uid or before.st_nlink!=1
                                    or before.st_mode&0o022
                                    or not 1<=before.st_size<=1048576):
                                raise Deny("CERTBOT_REGULAR_PEM_METADATA_UNTRUSTED")
                            handle=os.open(expected,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,
                                           dir_fd=fd)
                            try:
                                initial=os.fstat(handle)
                                digest=hashlib.sha256()
                                amount=0
                                while True:
                                    part=os.read(handle,131072)
                                    if not part:break
                                    amount+=len(part)
                                    if amount>1048576:
                                        raise Deny("CERTBOT_REGULAR_PEM_SIZE_LIMIT")
                                    digest.update(part)
                                after=os.fstat(handle)
                                ident=lambda s:(s.st_dev,s.st_ino,s.st_size,
                                                s.st_mtime_ns,s.st_ctime_ns)
                                if (not stat.S_ISREG(initial.st_mode)
                                        or amount!=initial.st_size
                                        or ident(before)!=ident(initial)
                                        or ident(initial)!=ident(after)):
                                    raise Deny("CERTBOT_REGULAR_PEM_CHANGED")
                            finally:
                                os.close(handle)
                            regular_files+=1
                        else:
                            raise Deny("CERTBOT_LIVE_NONSTANDARD_ENTRY")
                        count+=1
                finally:os.close(fd)
        finally:os.close(livefd)
    finally:os.close(rootfd)
    if (lineages!=3 or count!=12 or links!=8 or regular_files!=4):
        raise Deny("CERTBOT_MIXED_SOURCE_MATRIX_DRIFT")
    print("CERTBOT_LINEAGES=3_VERIFIED")
    print("CERTBOT_STANDARD_INTERNAL_LINKS=8_VERIFIED")
    print("CERTBOT_REGULAR_PEMS=4_VERIFIED")
    print("CERTBOT_LINK_TARGETS=NOFOLLOW_SAME_LINEAGE_SHA256_PASS")
    return count


def runtime_sources():
    root_owner()
    buf=bundle_source()
    health_contract()
    existing_private_directory(DAILY)
    # Vault mode need not be exactly 0700; V2 and V3 pin root ownership
    # and prohibit group/world writes. Keep its existing mode unchanged.
    v3,transport=admit_exact_installed_v3()
    user,release,app,storage=v3.inspect(transport,scheduled=True)
    root_storage=trusted_dir(storage.parent,{user.pw_uid})
    for part in ("app","framework","logs"):
        trusted_dir(root_storage/part,{user.pw_uid})
    for path in CONFIG.values():
        trusted_dir(path,{0})
    validate_certbot_live_matrix(buf["KMJ_OFFSITE_V3_LOCAL_DAILY_PUBLISHER_REVIEW_20261115.py"])
    env_source=(app/".env").resolve(strict=True)
    if not env_source.is_relative_to("/home/kmjprod/"):
        raise Deny("APP_ENV_OUTSIDE_OWNER_HOME")
    s=os.lstat(env_source)
    if (not stat.S_ISREG(s.st_mode) or s.st_uid not in (0,user.pw_uid)
        or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1):
        raise Deny("APP_ENV_PRIVATE_SOURCE_UNTRUSTED")
    parent=trusted_dir(env_source.parent,{0,user.pw_uid})
    assert parent==env_source.parent
    if ROOT.exists():
        existing_private_directory(ROOT)
        for name,sha in PINS.items():
            private_bytes(ROOT/name,sha,uid=0)
    print("KMJ_HEALTH_ORIGINAL_SOURCE=PINNED_UNCHANGED")
    print("V3_AUTHENTICATED_UNIT_AND_TRANSPORT=PINNED")
    print("LOCAL_SOURCE_ROOTS=GUARDED")
    print("REMOTE_RESTORE=NOT_ATTESTED")
    return buf,v3,transport,user,release,app,storage,env_source

def install_bundle(buf):
    if not ROOT.exists():
        os.mkdir(ROOT,0o700)
    existing_private_directory(ROOT)
    fd=os.open(ROOT,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        for name,sha in PINS.items():
            target=ROOT/name
            if os.path.lexists(target):
                private_bytes(target,sha,uid=0)
                continue
            out=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
                        0o600,dir_fd=fd)
            try:
                os.fchmod(out,0o600)
                os.fchown(out,0,0)
                data=buf[name]
                start=0
                while start<len(data):
                    done=os.write(out,data[start:])
                    if done<1:raise Deny("PRIVATE_BUNDLE_SHORT_WRITE")
                    start+=done
                os.fsync(out)
            finally:
                os.close(out)
            private_bytes(target,sha,uid=0)
        os.fsync(fd)
    finally:
        os.close(fd)

def imported(name,label):
    path=ROOT/name
    private_bytes(path,PINS[name],uid=0)
    spec=importlib.util.spec_from_file_location(label,path)
    if spec is None or spec.loader is None:
        raise Deny("PINNED_RUNTIME_IMPORT_UNAVAILABLE")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    private_bytes(path,PINS[name],uid=0)
    return m

def prepare_stage():
    if not STAGE.exists():
        os.mkdir(STAGE,0o700)
    existing_private_directory(STAGE)
    if os.stat(STAGE).st_dev!=os.stat(DAILY).st_dev:
        raise Deny("STAGE_DAILY_FILESYSTEM_DIFFER")

def attach_full_v2_storage_archive(builder,daily,stamp,work):
    stage=STAGE/("stage-"+stamp)
    fd=daily.private_dir_fd(stage,0)
    try:
        counts={"bytes":0}
        digest=builder.copy_file(work/"storage.tar.gz",fd,"storage.tar.gz",{0},counts)
        # The earlier source-review transcript masked daily.regular's
        # internal secret argument. Do not reconstruct a redacted API call.
        # Open only this root-owned 0600 file under the already validated
        # private stage dirfd, with no symlink following and exact metadata.
        mf=os.open("SHA256SUMS",
                   os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
        mstat=os.fstat(mf)
        if (not stat.S_ISREG(mstat.st_mode) or mstat.st_uid!=0
            or mstat.st_nlink!=1 or stat.S_IMODE(mstat.st_mode)!=0o600):
            os.close(mf)
            raise Deny("DAILY_MANIFEST_FILE_UNTRUSTED")
        try:
            if mstat.st_size>64000:raise Deny("DAILY_MANIFEST_OVERSIZE")
            body=os.read(mf,64001)
            if len(body)!=mstat.st_size:raise Deny("DAILY_MANIFEST_DRIFT")
        finally:
            os.close(mf)
        lines=body.decode("ascii").splitlines()
        if any(x.endswith("  storage.tar.gz") for x in lines):
            raise Deny("DAILY_MANIFEST_DUPLICATE_STORAGE_ARCHIVE")
        lines.append(digest+"  storage.tar.gz")
        fresh=("".join(row+"\n" for row in sorted(lines))).encode("ascii")
        builder.new_private_file(fd,"SHA256SUMS.new",fresh)
        os.replace("SHA256SUMS.new","SHA256SUMS",src_dir_fd=fd,dst_dir_fd=fd)
        os.fsync(fd)
        daily.verify_snapshot(fd,0,{0})
    finally:
        os.close(fd)

def verify_health_service_once():
    show=["/usr/bin/systemctl","show","--no-pager","-p","InvocationID",
          "-p","Result","-p","ExecMainStatus",UNIT]
    def read_props():
        p=subprocess.run(show,cwd="/",env=ENV,stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                         timeout=15,check=False)
        if p.returncode!=0 or len(p.stdout)>8192:
            raise Deny("HEALTH_UNIT_METADATA_UNAVAILABLE")
        return dict(row.split("=",1) for row in p.stdout.decode("ascii").splitlines()
                    if "=" in row)
    before=read_props()
    result=subprocess.run(["/usr/bin/systemctl","start",UNIT],
                          cwd="/",env=ENV,stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                          timeout=90,check=False)
    after=read_props()
    if (result.returncode!=0 or after.get("Result")!="success"
        or after.get("ExecMainStatus")!="0" or not after.get("InvocationID")
        or after["InvocationID"]==before.get("InvocationID")):
        raise Deny("NATIVE_HEALTH_OWN_INVOCATION_NOT_PASS")
    return True

def run_once():
    buf,v3,transport,user,release,app,storage,env_source=runtime_sources()
    install_bundle(buf)
    prepare_stage()
    builder=imported("KMJ_OFFSITE_V3_DAILY_SOURCE_BUILDER_REVIEW_20261115.py","kmj_owner_v3_builder")
    tx=imported("KMJ_OFFSITE_V3_TRANSFER_BOUND_TRANSACTION_REVIEW_20261115.py","kmj_owner_v3_transaction")
    with os.fdopen(v3.exclusive_lock(),"r+b"):
        with tempfile.TemporaryDirectory(prefix=".kmj-fresh-x25519-",dir=str(transport.VAULT)) as tmp:
            work=Path(tmp)
            v3.create_fresh(app,storage,user,work)
            stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            fd=os.open(work,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                builder.copy_file(env_source,fd,"app.env",{0,user.pw_uid},
                                  {"bytes":0},private=True)
            finally:
                os.close(fd)
            builder.build_preverified_snapshot(
                STAGE,DAILY,stamp,work/"database.dump",storage.parent,
                CONFIG,work/"app.env",expected_uid=0,storage_owner_uid=user.pw_uid,
            )
            attach_full_v2_storage_archive(builder,tx.daily,stamp,work)
            if v3.LIVE.resolve(strict=True)!=release:
                raise Deny("LIVE_RELEASE_CHANGED_BEFORE_ENCRYPTION")
            cipher=work/"fresh.age"
            v3.encrypt(work,cipher)
            receipt=tx.commit_after_same_invocation_v2_readback(
                transport=transport,
                pinned_live_release_probe=lambda:v3.LIVE.resolve(strict=True),
                expected_release=release,vault=transport.VAULT,
                fresh_cipher=cipher,stage_root=STAGE,daily_root=DAILY,
                stamp=stamp,expected_uid=0,
            )
            if not (receipt["remote_sha_readback_same_invocation"]
                    and receipt["local_cipher_sidecar_verified"]
                    and receipt["local_daily_snapshot_verified"]
                    and receipt["local_complete"]):
                raise Deny("DUAL_LOCAL_COMMIT_NOT_VERIFIED")
    print("FRESH_REMOTE_SFTP_SHA_READBACK=PASS")
    print("FRESH_LOCAL_CIPHER_SIDECAR=PASS")
    print("FRESH_LOCAL_DAILY_PGDMP_STORAGE_CONFIG=PASS")
    print("INDEPENDENT_REMOTE_RESTORE=NOT_VERIFIED")
    # Do not change health source, do not mark pass without systemd.
    health_contract()
    verify_health_service_once()
    print("HEALTH_UNIT_OWN_INVOCATION=SUCCESS_EXIT0")
    print("RESULT=FRESH_DUAL_LOCAL_HEALTH_ONEPASS_PASS")
    return 0

def bound_root_digest(path):
    """Read ONLY a fixed reviewed source using nofollow, tight size and inode check.

    Digest is a file-identity diagnostic, never release approval. This routine
    does not import source code, read secrets, alter files or start services.
    """
    before=os.lstat(path)
    if (not stat.S_ISREG(before.st_mode) or before.st_uid!=0
        or before.st_nlink!=1 or before.st_mode&0o022
        or not 128<=before.st_size<=131072):
        raise Deny("PIN_SOURCE_METADATA_INVALID")
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        actual=os.fstat(fd)
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,
            before.st_ctime_ns)!=(actual.st_dev,actual.st_ino,
                                  actual.st_size,actual.st_mtime_ns,actual.st_ctime_ns):
            raise Deny("PIN_SOURCE_RACED")
        raw=os.read(fd,131073)
        after=os.fstat(fd)
        if (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,
            after.st_ctime_ns)!=(actual.st_dev,actual.st_ino,
                                 actual.st_size,actual.st_mtime_ns,actual.st_ctime_ns):
            raise Deny("PIN_SOURCE_RACED")
        if len(raw)!=actual.st_size:
            raise Deny("PIN_SOURCE_SHORT_READ")
    finally:
        os.close(fd)
    return hashlib.sha256(raw).hexdigest()


def audit_root_pins():
    """Exact-path, metadata-guarded source hash audit; never reads backup data.

    Prints fixed symbolic labels, pin verdict and mismatched SOURCE digest only.
    Source digests identify reviewed code bytes, not credentials or archives.
    """
    sources=[("BUNDLE_%02d" % n, BASE/name, sha)
             for n,(name,sha) in enumerate(PINS.items(),1)]
    sources.extend((
        ("INSTALLED_V3",V3_INSTALLED,V3_INSTALLED_SHA),
        ("INSTALLED_SFTP",V3_PARENT,V3_PARENT_SHA),
        ("HEALTH_SOURCE",HEALTH,HEALTH_SHA),
    ))
    all_match=True
    for label,path,expected in sources:
        try:
            digest=bound_root_digest(path)
        except (OSError,Deny):
            print(label+"_PIN=UNREADABLE_OR_UNTRUSTED")
            all_match=False
            continue
        if digest==expected:
            print(label+"_PIN=PASS")
        else:
            print(label+"_PIN=SHA_MISMATCH")
            print(label+"_OBSERVED_SHA256="+digest)
            all_match=False
    print("PRODUCTION_AND_BACKUP_MUTATION=NONE")
    print("SOURCE_CONTENT_OR_CREDENTIALS_PRINTED=NO")
    print("RESULT="+("ROOT_PIN_AUDIT_PASS" if all_match else "ROOT_PIN_AUDIT_BLOCKED"))
    return 0 if all_match else 4


def selftest():
    pattern="find /var/backups/kmj-elite-daily -mindepth 2 -maxdepth 2 -name '*.tar.gz' -type f -mtime -2 | grep -q ."
    a=parse_exact_find(pattern)
    assert a==(str(DAILY),"2","2","*.tar.gz")
    assert fnmatch.fnmatchcase("storage.tar.gz",a[3])
    for bad in (pattern.replace("-mtime -2","-mtime +2"),
                pattern.replace("-maxdepth 2","-maxdepth 30"),
                pattern+"; touch /root/bad"):
        try:parse_exact_find(bad)
        except Deny:pass
        else:raise AssertionError("BAD_HEALTH_FIND_ADMITTED")
    assert len(PINS)==6 and len(set(PINS.values()))==6
    assert V3_INSTALLED_SHA=="2834ff3361027536bee0b971fae6dddb00677460f15adf3e8d81e7821853016f"
    assert V3_PARENT_SHA=="8f9165714774758a6bef05abff7bf72d655518ab7ed1c3cdd8dc588d3c85c13c"
    assert all(callable(x) for x in (admit_exact_installed_v3,runtime_sources,run_once))
    assert V3_INSTALLED.parent==V3_PARENT.parent
    assert "v3" in V3_INSTALLED.name
    print("KMJ_V3_HEALTH_ONEPASS_20261117_OFFLINE_SELFTEST=PASS")
    print("HOST_OR_SERVICE_MUTATION=NONE")
    return 0

def main():
    os.umask(0o077)
    if len(sys.argv)!=2 or sys.argv[1] not in ("--selftest","--audit-pins","--preflight","--run-once"):
        print("RESULT=BLOCKED_ARGS")
        return 2
    if sys.argv[1]=="--selftest":
        return selftest()
    try:
        root_owner()
        if sys.argv[1]=="--audit-pins":
            return audit_root_pins()
        if sys.argv[1]=="--preflight":
            runtime_sources()
            print("BACKUP_TRANSFER_EXECUTED=NO")
            print("SERVICE_MODIFIED=NO")
            print("RESULT=GUARDED_ONEPASS_PREFLIGHT_PASS")
            return 0
        return run_once()
    except Exception as e:
        reason=str(e)
        if not re.fullmatch(r"[A-Z0-9_]{5,96}",reason):
            reason=type(e).__name__.upper()
        print("BLOCKER="+reason)
        print("NATIVE_HEALTH_EXIT0=NOT_ATTESTED")
        print("LIVE_SERVICE_AND_RELEASE_CONFIG_CHANGED=NO")
        print("RESULT=BLOCKED_FAIL_CLOSED")
        return 3

if __name__=="__main__":
    raise SystemExit(main())
