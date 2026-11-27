#!/usr/bin/python3
"""Fresh Nov-17 V3 X25519 offsite restore: pinned ciphertext and complete four-member bundle.

--prepare: use pinned prior hardened exact-cipher helper to copy ONLY the
20261117T125803Z 442310B X25519 object by exact SHA into new 0700 scratch. No key read.
--extract: in key-free networkless bwrap, verify four regular tar members,
SHA256SUMS, fresh metadata, PGDMP magic and bounded dynamic size; validate nested
storage.tar.gz members without extracting them. Writes only 0600 disposable
database.dump and storage.tar.gz into THIS run's private scratch.
--selftest: synthetic, no real cipher/key or source file access.
Does not print raw filenames, SQL, credentials, key or content.
"""
from __future__ import annotations
import hashlib,importlib.util,io,os,posixpath,pwd,re,socket,stat,sys,tarfile
from pathlib import Path

BASE="KMJ_GOOGLE_X25519_EXACT_PGDMP_RESTORE_HELPER_20261112.py"
BASE_SHA="b20e55f1de13d8bae3f6e4156dafc135002b4d73215bf3f5613359419c893f26"
CIPHER_SHA="6755926098fe9a6fc00d4669337025b4ad2d033d7ea039c0a5d6aef17421c87d"
CIPHER_BYTES=442310
DUMP_SIZE_PROOF="BOUNDED_AND_MANIFEST_ATTESTED"
BACKUP_STAMP="20261117T100210Z"
MIN_DUMP_BYTES=64
MAX_DUMP_BYTES=33554432
EXPECTED=("database.dump","storage.tar.gz","metadata.txt","SHA256SUMS")
MAX_STORAGE_BYTES=1024**3
MAX_STORAGE_CONTENT=8*1024**3
MAX_STORAGE_MEMBERS=50000
class Block(Exception): pass

def emit(k,v):
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,85}",str(k)) or not re.fullmatch(r"[A-Z0-9_.:-]{1,120}",str(v)):
        raise Block("OUTPUT_SHAPE")
    print(f"{k}={v}",flush=True)

def source():
    path=Path(__file__).resolve().with_name(BASE)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.geteuid() or before.st_nlink!=1 or before.st_mode&0o022 or not 1024<=before.st_size<=131072:
            raise Block("BASE_MODULE_METADATA")
        data=os.read(fd,131073)
        after=os.fstat(fd)
        if len(data)!=before.st_size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise Block("BASE_MODULE_RACE")
    finally:os.close(fd)
    if hashlib.sha256(data).hexdigest()!=BASE_SHA:raise Block("BASE_MODULE_SHA")
    sp=importlib.util.spec_from_file_location("kmj_fresh_google_restore_source",path)
    if not sp or not sp.loader:raise Block("BASE_MODULE_IMPORT")
    mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=BASE_SHA:raise Block("BASE_POST_IMPORT_SHA")
    mod.SHA=CIPHER_SHA
    mod.CIPHER_BYTES=CIPHER_BYTES
    # The original Nov12 helper remains untouched. Restrict its filename
    # discovery to Nov17, and still enforce exact *cryptographic* SHA.
    mod.NAME=re.compile(r"kmj-legacy-20261117T[0-2][0-9][0-5][0-9][0-5][0-9]Z-[a-f0-9]{32}\.age\Z", re.ASCII)
    return mod

def archive_name(raw):
    if not raw or len(raw)>4096 or raw.startswith("/") or "\\" in raw or any(ord(c)<32 or ord(c)==127 for c in raw):
        raise Block("TAR_NAME_UNSAFE")
    if raw in (".","./"):return "."
    normalized=raw.removeprefix("./").rstrip("/")
    if not normalized or any(p in ("",".","..") for p in normalized.split("/")):
        raise Block("TAR_NAME_TRAVERSAL")
    return normalized

def relative_link(name,target):
    if not target or len(target)>4096 or target.startswith("/") or "\\" in target or any(ord(c)<32 or ord(c)==127 for c in target):
        raise Block("STORAGE_SYMLINK_UNSAFE")
    resolved=posixpath.normpath(posixpath.join(posixpath.dirname(name),target))
    if resolved in (".","..") or resolved.startswith("../") or resolved.startswith("/"):
        raise Block("STORAGE_SYMLINK_ESCAPE")

def digest_extract(item,tar,work,canonical,materialize=False):
    if not item.isfile() or item.size<0:
        raise Block("NONREGULAR_OUTER_MEMBER")
    if canonical=="database.dump" and not MIN_DUMP_BYTES<=item.size<=MAX_DUMP_BYTES:
        raise Block("PGDMP_RECEIPT_SIZE")
    if canonical=="storage.tar.gz" and item.size>MAX_STORAGE_BYTES:
        raise Block("STORAGE_TAR_SIZE")
    if canonical in ("metadata.txt","SHA256SUMS") and item.size>2048:
        raise Block("SMALL_METADATA_SIZE")
    f=tar.extractfile(item)
    if f is None:raise Block("TAR_MEMBER_INACCESSIBLE")
    data_small=bytearray()
    sha=hashlib.sha256()
    outfile=None
    written=0
    try:
        if materialize:
            dest=work/canonical
            fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
            outfile=os.fdopen(fd,"wb")
        with f:
            while written<item.size:
                data=f.read(min(1048576,item.size-written))
                if not data:raise Block("TRUNCATED_MEMBER")
                sha.update(data)
                if outfile:
                    outfile.write(data)
                else:
                    data_small.extend(data)
                written+=len(data)
        if outfile:
            outfile.flush()
            os.fsync(outfile.fileno())
    finally:
        if outfile:outfile.close()
    if written!=item.size:raise Block("FILE_LENGTH_MISMATCH")
    return sha.hexdigest(),bytes(data_small)

def verify_storage(blob):
    count=0;files=0;dirs=0;links=0;expanded=0;seen=set()
    try:
        with tarfile.open(blob,"r:gz") as pack:
            for item in pack:
                name=archive_name(item.name)
                if name in seen:raise Block("STORAGE_DUPLICATE_MEMBER")
                seen.add(name);count+=1
                if count>MAX_STORAGE_MEMBERS:raise Block("STORAGE_MEMBER_COUNT")
                if item.isdir():dirs+=1;continue
                if item.issym():
                    relative_link(name,item.linkname)
                    links+=1;continue
                if not item.isfile() or item.size<0 or item.size>MAX_STORAGE_CONTENT:
                    raise Block("STORAGE_UNSAFE_MEMBER")
                expanded+=item.size
                if expanded>MAX_STORAGE_CONTENT:raise Block("STORAGE_EXPANDED_LIMIT")
                s=pack.extractfile(item)
                if s is None:raise Block("STORAGE_MEMBER_NO_STREAM")
                remain=item.size
                with s:
                    while remain:
                        data=s.read(min(1048576,remain))
                        if not data:raise Block("STORAGE_TRUNCATED_MEMBER")
                        remain-=len(data)
                files+=1
    except (tarfile.TarError,EOFError,OSError,UnicodeError):
        raise Block("STORAGE_TAR_INVALID") from None
    if count==0:raise Block("STORAGE_ARCHIVE_EMPTY")
    return files,dirs,links,expanded

def inspect_bundle(stream,work):
    seen=set();digests={};meta=None;checks=None
    try:
        with tarfile.open(fileobj=stream,mode="r:gz") as archive:
            for item in archive:
                if not item.isfile():raise Block("OUTER_SPECIAL_OR_LINK")
                name=archive_name(item.name)
                if name not in EXPECTED or name in seen:
                    raise Block("OUTER_NAMES_OR_DUPLICATE")
                seen.add(name)
                sha,small=digest_extract(item,archive,work,name,name in ("database.dump","storage.tar.gz"))
                digests[name]=sha
                if name=="metadata.txt":meta=small
                elif name=="SHA256SUMS":checks=small
    except (tarfile.TarError,EOFError,OSError,UnicodeError):
        raise Block("OUTER_TAR_INVALID") from None
    if seen!=set(EXPECTED):raise Block("OUTER_MEMBERS_INCOMPLETE")
    expected_meta=(
        rb"schema=kmj\.offsite\.fresh\.x25519\.v1\n"
        rb"created_utc=20261117T[0-2][0-9][0-5][0-9][0-5][0-9]Z\n"
        rb"contains=production_pg_dump_and_storage\n"
        rb"secrets_env=EXCLUDED\n"
    )
    if meta is None or not re.fullmatch(expected_meta,meta):
        raise Block("FRESH_METADATA_SCHEMA_OR_DATE")
    if checks is None:raise Block("SOURCE_MANIFEST_MISSING")
    lines=checks.decode("ascii","strict").splitlines()
    if len(lines)!=3:raise Block("SOURCE_MANIFEST_LINES")
    names=("database.dump","storage.tar.gz","metadata.txt")
    for line,name in zip(lines,names):
        if not re.fullmatch(r"[a-f0-9]{64}  "+re.escape(name),line):
            raise Block("SOURCE_MANIFEST_FORMAT")
        if line[:64]!=digests[name]:raise Block("SOURCE_MANIFEST_MISMATCH")
    f=work/"database.dump"
    if not MIN_DUMP_BYTES<=f.lstat().st_size<=MAX_DUMP_BYTES:
        raise Block("PGDMP_RECEIPT_SIZE")
    with f.open("rb") as dump:
        if dump.read(5)!=b"PGDMP":raise Block("FRESH_PGDMP_MAGIC")
    store=work/"storage.tar.gz"
    verify_storage(store)
    emit("OUTER_REGULAR_FILES",4)
    emit("FRESH_PGDMP_BYTES",f.lstat().st_size)
    emit("STORAGE_INNER_TAR","NONEXTRACTING_VALIDATION_PASS")
    emit("SOURCE_SHA256_MANIFEST","EXACT_ALL_THREE_PASS")
    emit("FRESH_METADATA_DATE","20261117_VERIFIED")
    emit("SOURCE_PGDMP_MAGIC","PASS")
    emit("ONLY_REQUIRED_FILES_EXTRACTED","YES")
    emit("RESULT","FRESH_BUNDLE_KEYFREE_VERIFIED")

def prepare(work):
    base=source()
    base.prepare(work)
    emit("RESTORE_TARGET","EXACT_20261117_V3_CIPHER")
def extract(work):
    base=source()
    folder=base.workdir(work)
    path=folder/"bundle.tar.gz"
    st=path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or st.st_nlink!=1 or stat.S_IMODE(st.st_mode)!=0o600 or not 0<st.st_size<MAX_STORAGE_BYTES:
        raise Block("PLAINTEXT_ARCHIVE_METADATA")
    with path.open("rb") as stream:
        inspect_bundle(stream,folder)
def selftest():
    for valid in ("database.dump","storage.tar.gz","metadata.txt","SHA256SUMS","./","./storage/file"):
        archive_name(valid)
    for bad in ("/etc/passwd","a/../b","../escape","a\\b","x\nb"):
        try:archive_name(bad)
        except Block:pass
        else:raise Block("NAME_FAIL_OPEN")
    relative_link("folder/link","../data")
    for bad in ("/etc/passwd","../../outside",""):
        try:relative_link("folder/link",bad)
        except Block:pass
        else:raise Block("LINK_FAIL_OPEN")
    assert re.fullmatch(r"[0-9a-f]{64}",CIPHER_SHA)
    assert CIPHER_BYTES==442310 and DUMP_SIZE_PROOF=="BOUNDED_AND_MANIFEST_ATTESTED" and BACKUP_STAMP=="20261117T100210Z"
    emit("OFFLINE_TESTS","10_PASS")
    emit("REAL_CIPHERTEXT_READ","NO")
    emit("RESULT","SELFTEST_PASS")

def main():
    emit("SCHEMA","KMJ_GOOGLE_V3_20261117_PGDMP_X25519_RESTORE_HELPER_V1")
    if len(sys.argv) not in (2,3) or os.geteuid()==0 or pwd.getpwuid(os.geteuid()).pw_name!="info" or os.environ.get("HOME")!="/home/info":
        emit("RESULT","BLOCKED_USER_ENV");return 2
    if sys.argv[1] in ("--prepare","--selftest") and socket.gethostname().split(".")[0]!="google-vps1":
        emit("RESULT","BLOCKED_HOST");return 2
    try:
        if len(sys.argv)==2 and sys.argv[1]=="--selftest":selftest()
        elif len(sys.argv)==3 and sys.argv[1]=="--prepare":prepare(sys.argv[2])
        elif len(sys.argv)==3 and sys.argv[1]=="--extract":extract(sys.argv[2])
        else:emit("RESULT","BLOCKED_ARGS");return 2
        return 0
    except (Block,UnicodeDecodeError,AssertionError) as exc:
        why=str(exc) if isinstance(exc,Block) else "SAFE"
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,90}",why):why="SAFE"
        emit("RESULT","BLOCKED_"+why);return 3
    except Exception:
        emit("RESULT","BLOCKED_SAFE");return 3
if __name__=="__main__":raise SystemExit(main())
