#!/usr/bin/env python3
"""Owner-root READ-ONLY staging vhost authority and target readiness audit.

Does not emit Nginx config, certificates, URLs besides fixed canonical
host, secrets, source paths, raw errors, or credentials.
No filesystem/service/network mutations or release activation.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

SHA="a9796a25a2801cd303a69f5ad468aa9a704e5fff"
STAGE_OLD="b2e69decab3acd861e94e11992cd8a4cff4f2b94"
PROD_OLD="platform-574e443a2c75"
VHOST=Path("/etc/nginx/sites-enabled/staging.kmjtechno.com.conf")
TARGET=Path("/etc/nginx/sites-available/staging.kmjtechno.com.conf")
MIRROR=Path("/var/lib/kmj-main-platform-stage-serving")/SHA
CODE=MIRROR/"code"
PUBLIC=MIRROR/"public"
POOL=Path("/etc/php/8.4/fpm/pool.d/kmjstage-a979.conf")
SOCKET=Path("/run/php/kmjstage-a979-php84-fpm.sock")
STAGE=Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD=Path("/home/kmjprod/current")
FLAGS=os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC

def emit(k,v):
    print(k+"="+v,flush=True)

def trusted_chain(path):
    if not path.is_absolute():
        return False
    cur=Path("/")
    for part in path.parts[1:-1]:
        cur/=part
        try: st=os.lstat(cur)
        except OSError: return False
        if not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:
            return False
    return True

def read_vhost():
    try:
        if not trusted_chain(VHOST) or not trusted_chain(TARGET): return None,"UNTRUSTED_PARENT"
        lst=os.lstat(VHOST)
        if stat.S_ISLNK(lst.st_mode):
            if VHOST.resolve(strict=True)!=TARGET: return None,"SYMLINK_OUT_OF_SCOPE"
            actual=TARGET
        elif stat.S_ISREG(lst.st_mode):
            actual=VHOST
        else:
            return None,"INVALID_TYPE"
        fd=os.open(actual,FLAGS)
        try:
            st=os.fstat(fd)
            if (not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_nlink!=1
                or st.st_mode&0o022 or st.st_size<1 or st.st_size>262144):
                return None,"UNTRUSTED_FILE"
            contents=os.read(fd,262145)
            check=os.fstat(fd)
            if len(contents)!=st.st_size or (
                st.st_dev,st.st_ino,st.st_mtime_ns,st.st_ctime_ns)!=(
                check.st_dev,check.st_ino,check.st_mtime_ns,check.st_ctime_ns):
                return None,"FILE_CHANGED"
            return contents,"ROOT_TRUSTED"
        finally: os.close(fd)
    except (OSError,ValueError):
        return None,"UNVERIFIED"

def patterns(data):
    if data is None:
        return {}
    # Nginx directives/comments classification only. Never reprint original.
    stripped=re.sub(r"(?m)#.*$","",data.decode("utf-8","replace"))
    tokens={
        "host": bool(re.search(r"\bserver_name\s+staging\.kmjtechno\.com\s*;",stripped)),
        "placeholder": bool(re.search(r"\breturn\s+503\s*;",stripped)),
        "has_https": bool(re.search(r"\blisten\s+(?:\[::\]:)?443\b",stripped)),
        "has_cert": bool(re.search(r"\bssl_certificate\s+\S+\s*;",stripped)),
        "has_key": bool(re.search(r"\bssl_certificate_key\s+\S+\s*;",stripped)),
        "fastcgi_old": "/run/php/kmjstage-php84-fpm.sock" in stripped,
        "fastcgi_new": str(SOCKET) in stripped,
        "root_old": "/home/kmjstage" in stripped,
        "root_new": str(PUBLIC) in stripped,
        "includes": bool(re.search(r"\binclude\s+",stripped)),
    }
    return tokens

def pointer(path,expected):
    try:
        return stat.S_ISLNK(os.lstat(path).st_mode) and os.readlink(path) in expected
    except OSError: return False

def verify_live_pointers():
    return pointer(STAGE,{"/home/kmjstage/releases/"+STAGE_OLD+"/apps/platform",
                         "../releases/"+STAGE_OLD+"/apps/platform"}) and pointer(
        PROD,{"/home/kmjprod/releases/"+PROD_OLD,"releases/"+PROD_OLD})

def service_check(binary,args,timeout=10):
    try:
        p=subprocess.run([binary,*args],capture_output=True,timeout=timeout,check=False,
                         env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C"})
        return p.returncode==0
    except (OSError,subprocess.TimeoutExpired):
        return False

def main():
    if len(sys.argv)!=1 or os.geteuid()!=0 or socket.gethostname().split(".")[0].lower()!="kmj-elite":
        emit("KMJ_STAGE_VHOST_ROUTE_PREFLIGHT","BLOCKED_HOST_ROOT_ARGS")
        return 2
    emit("KMJ_STAGE_VHOST_ROUTE_PREFLIGHT","READ_ONLY_V1")
    emit("LIVE_POINTERS","EXPECTED" if verify_live_pointers() else "DRIFT")
    data,state=read_vhost()
    emit("STAGING_VHOST_SOURCE_TRUST",state)
    emit("STAGING_VHOST_SHA256",hashlib.sha256(data).hexdigest() if data is not None else "NOT_ATTESTED")
    v=patterns(data)
    for k in ("host","placeholder","has_https","has_cert","has_key","fastcgi_old",
              "fastcgi_new","root_old","root_new","includes"):
        emit("STAGING_VHOST_"+k.upper(),"PRESENT" if v.get(k) else "NOT_SEEN_OR_UNVERIFIED")
    emit("NGINX_CONFIG_SYNTAX","PASS" if service_check("/usr/sbin/nginx",["-t"]) else "UNVERIFIED")
    emit("PHP_FPM_CONFIG_SYNTAX","PASS" if service_check("/usr/sbin/php-fpm8.4",["-t"]) else "UNVERIFIED")
    emit("CANDIDATE_SOCKET","PRESENT" if socket_path(SOCKET) else "NOT_ACTIVE")
    emit("CANDIDATE_STATIC","ROOT_MIRROR_PRESENT" if candidate_public() else "UNVERIFIED")
    emit("NGINX_CHANGE","NONE")
    emit("PHP_FPM_CHANGE","NONE")
    emit("PRODUCTION_CHANGE","NONE")
    emit("STAGING_ROUTE_APPROVAL","NOT_ISSUED")
    emit("KMJ_STAGE_VHOST_ROUTE_PREFLIGHT","READ_ONLY_COMPLETE")
    return 0

def socket_path(path):
    try: return stat.S_ISSOCK(os.lstat(path).st_mode)
    except OSError: return False

def candidate_public():
    try:
        st=os.lstat(PUBLIC)
        a=os.lstat(PUBLIC/"build/manifest.json")
        return (stat.S_ISDIR(st.st_mode) and st.st_uid==0 and
                stat.S_IMODE(st.st_mode)==0o550 and
                stat.S_ISREG(a.st_mode) and a.st_uid==0 and
                stat.S_IMODE(a.st_mode)==0o440)
    except OSError: return False

if __name__=="__main__":
    try: raise SystemExit(main())
    except (OSError,ValueError):
        emit("KMJ_STAGE_VHOST_ROUTE_PREFLIGHT","BLOCKED_UNEXPECTED_METADATA")
        raise SystemExit(2)
