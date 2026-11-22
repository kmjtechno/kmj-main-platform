#!/usr/bin/python3
"""KMJ P0 read-only Certbot link metadata classifier.

Diagnoses the precise predicate CERTBOT_LINK_METADATA_UNTRUSTED in the
reviewed V3 daily publisher. NEVER opens symlink targets, reads private keys
or certificate bytes, follows symlinks, prints host names/lineage names/link
texts, changes permissions/owners, or writes backups/service files.
Only reports aggregate entry counts, owner UID classes, and bounded link
target SHAPE categories; not a release / restore / health PASS.
"""
from __future__ import annotations
import collections
import os
from pathlib import Path
import re
import socket
import stat
import sys

FDS=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC
ROOT=Path("/etc/letsencrypt")
CERTBOT_FILES=("cert.pem","chain.pem","fullchain.pem","privkey.pem")
MAX_LINEAGES=16
MAX_ENTRIES=256

class Deny(Exception): pass

def link_verdict(s,expected_uid):
    """The exact three predicates from publisher line 108-111, no I/O."""
    if not stat.S_ISLNK(s.st_mode):return "NOT_SYMLINK"
    if s.st_uid!=expected_uid:return "NONEXPECTED_OWNER"
    if s.st_nlink!=1:return "LINK_COUNT_NOT_ONE"
    return "METADATA_PASS"

def target_shape(target,lineage,name):
    """Lexical-only classification; never resolve/read the target."""
    if not isinstance(target,str) or len(target)>255 or "\x00" in target:
        return "TARGET_INVALID"
    if target.startswith("/"):
        return "TARGET_ABSOLUTE"
    pattern=(r"\.\./\.\./archive/"+re.escape(lineage)+r"/"+
             re.escape(name.removesuffix(".pem"))+r"[1-9][0-9]{0,4}\.pem")
    if re.fullmatch(pattern,target,flags=re.ASCII):
        return "STANDARD_SAME_LINEAGE"
    return "TARGET_OTHER_RELATIVE"

def scan(root=ROOT,expected_uid=0):
    if not Path(root).is_absolute() or ".." in Path(root).parts:
        raise Deny("ROOT_PATH_INVALID")
    fd=os.open(root,FDS)
    counters=collections.Counter()
    by_uid=collections.Counter()
    try:
        rootst=os.fstat(fd)
        if not stat.S_ISDIR(rootst.st_mode) or rootst.st_uid!=expected_uid or rootst.st_mode&0o022:
            raise Deny("ROOT_DIRECTORY_METADATA_UNTRUSTED")
        live=os.open("live",FDS,dir_fd=fd)
        try:
            live_st=os.fstat(live)
            if (not stat.S_ISDIR(live_st.st_mode)
                    or live_st.st_uid!=expected_uid or live_st.st_mode&0o022):
                raise Deny("LIVE_DIRECTORY_METADATA_UNTRUSTED")
            lineages=sorted(os.listdir(live))
            if len(lineages)>MAX_LINEAGES:
                raise Deny("LINEAGE_LIMIT")
            for lineage in lineages:
                if lineage=="README":
                    s=os.stat(lineage,dir_fd=live,follow_symlinks=False)
                    if not stat.S_ISREG(s.st_mode) or s.st_uid!=expected_uid:
                        raise Deny("LIVE_README_UNEXPECTED")
                    continue
                if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}",lineage) is None:
                    raise Deny("LINEAGE_NAME_INVALID")
                meta=os.stat(lineage,dir_fd=live,follow_symlinks=False)
                if not stat.S_ISDIR(meta.st_mode) or meta.st_uid!=expected_uid or meta.st_mode&0o022:
                    raise Deny("LINEAGE_DIRECTORY_METADATA_UNTRUSTED")
                child=os.open(lineage,FDS,dir_fd=live)
                try:
                    after=os.fstat(child)
                    if (meta.st_dev,meta.st_ino)!=(after.st_dev,after.st_ino):
                        raise Deny("LINEAGE_DIRECTORY_CHANGED")
                    if len(os.listdir(child))>MAX_ENTRIES:
                        raise Deny("LINEAGE_ENTRY_LIMIT")
                    counters["LINEAGES"]+=1
                    for name in CERTBOT_FILES:
                        try:
                            st=os.stat(name,dir_fd=child,follow_symlinks=False)
                        except FileNotFoundError:
                            counters["MISSING_EXPECTED_ENTRY"]+=1
                            continue
                        counters["EXPECTED_ENTRIES"]+=1
                        verdict=link_verdict(st,expected_uid)
                        counters["VERDICT_"+verdict]+=1
                        by_uid[st.st_uid]+=1
                        if stat.S_ISLNK(st.st_mode):
                            # readlink only reads textual metadata; never opens target.
                            text=os.readlink(name,dir_fd=child)
                            counters["SHAPE_"+target_shape(text,lineage,name)]+=1
                        if st.st_nlink!=1:
                            counters["LINK_COUNT_NOT_ONE_TOTAL"]+=1
                finally:os.close(child)
        finally:os.close(live)
    finally:os.close(fd)
    return counters,by_uid

def main():
    if sys.argv[1:]==["--selftest"]:
        s=type("S",(),{"st_mode":stat.S_IFLNK|0o777,
                       "st_uid":1234,"st_nlink":1})
        assert link_verdict(s,1234)=="METADATA_PASS"
        assert link_verdict(s,0)=="NONEXPECTED_OWNER"
        assert target_shape("../../archive/host.tld/privkey12.pem","host.tld","privkey.pem")=="STANDARD_SAME_LINEAGE"
        assert target_shape("/etc/passwd","host.tld","cert.pem")=="TARGET_ABSOLUTE"
        print("KMJ_CERTBOT_META_CLASSIFIER_SELFTEST=PASS")
        print("HOST_MUTATION=NONE")
        return 0
    if sys.argv[1:]!=["--inspect"] or os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        print("RESULT=BLOCKED_ARGS_OR_HOST");return 2
    try:
        counts,uids=scan()
        for k,v in sorted(counts.items()):
            print("CERTBOT_"+k+"="+str(v))
        for uid,count in sorted(uids.items()):
            if uid<0 or uid>2**32:
                raise Deny("UID_UNEXPECTED")
            print("CERTBOT_LINK_OWNER_UID_"+str(uid)+"="+str(count))
        print("LINK_TARGETS_FOLLOWED=NO")
        print("FILE_CONTENTS_OR_TARGETS_PRINTED=NO")
        print("BACKUP_SERVICE_OR_HOST_MUTATION=NONE")
        print("RESULT=READ_ONLY_CERTBOT_METADATA_DIAG_PASS")
        return 0
    except (OSError,Deny,UnicodeError) as e:
        msg=str(e)
        if not re.fullmatch(r"[A-Z][A-Z_]{4,79}",msg):
            msg="SOURCE_METADATA_UNVERIFIED"
        print("BLOCKER="+msg)
        print("HOST_MUTATION=NONE")
        print("RESULT=BLOCKED_READ_ONLY")
        return 3

if __name__=="__main__":
    raise SystemExit(main())
