#!/usr/bin/python3
"""V3 fresh live PostgreSQL+storage -> DNS-only pinned Google X25519 SFTP.

READ-ONLY --inspect; --send-once writes only to new private temp directories
and sends a new distinct age object via previously vetted pinned SFTP with
SHA256 readback. Does not change production DB/app/unit, existing archive or
key. Receiver remains numeric IP; IP rotation is a separate release gate.
"""
from __future__ import annotations
import fcntl,hashlib,importlib.util,os,pwd,re,shutil,socket,stat,subprocess,sys,tempfile,datetime as dt
from pathlib import Path
PARENT="KMJ_OFFSITE_SFTP_DNS_PINNED_V2_20261112.py"
PARENT_SHA="8f9165714774758a6bef05abff7bf72d655518ab7ed1c3cdd8dc588d3c85c13c"
PUBLIC="age1952vsyz25elfzn8slyhuc4k586dhw0er45yy26myhvv3lcp9qeps8mj7f5"
LIVE=Path("/home/kmjprod/current")
OWNER="kmjprod"
LOCK=Path("/run/lock/kmj-offsite-fresh-x25519.lock")
SCHEDULED=Path("/usr/local/libexec/kmj-offsite-fresh-x25519-v3-20261112.py")
DROPIN=Path("/etc/systemd/system/kmj-elite-offsite-backup.service.d/97-kmj-offsite-fresh-x25519-20261112.conf")
MAX_SIZE=8*1024**3
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","HOME":"/root","LANG":"C","LC_ALL":"C"}
class Deny(Exception):pass

def emit(k,v):
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,85}",str(k)) or not re.fullmatch(r"[A-Z0-9_.:-]{1,110}",str(v)):
        raise Deny("OUTPUT_SHAPE")
    print(f"{k}={v}",flush=True)

def run(argv,*,timeout=30,cwd="/",env=None):
    try:
        return subprocess.run(argv,cwd=cwd,env=env or ENV,stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                              timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired):
        raise Deny("TOOL_TIMEOUT_OR_MISSING") from None

def pinned_transport():
    source=Path(__file__).resolve().with_name(PARENT)
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_uid!=0 or a.st_nlink!=1 or stat.S_IMODE(a.st_mode)!=0o600 or not 1024<=a.st_size<=131072:
            raise Deny("TRANSPORT_FILE_UNTRUSTED")
        body=os.read(fd,131073);b=os.fstat(fd)
        if len(body)!=a.st_size or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns):
            raise Deny("TRANSPORT_FILE_RACE")
    finally:os.close(fd)
    if hashlib.sha256(body).hexdigest()!=PARENT_SHA:raise Deny("TRANSPORT_SHA_CHANGED")
    spec=importlib.util.spec_from_file_location("kmj_fresh_exact_sftp_transport",source)
    if not spec or not spec.loader:raise Deny("TRANSPORT_IMPORT")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if hashlib.sha256(source.read_bytes()).hexdigest()!=PARENT_SHA:raise Deny("TRANSPORT_IMPORT_CHANGED")
    return module

def live_app():
    if not LIVE.is_symlink():raise Deny("LIVE_SYMLINK_MISSING")
    path=LIVE.resolve(strict=True)
    if not path.is_relative_to("/home/kmjprod/releases/") or not re.fullmatch(r"platform-[a-f0-9]{12}",path.name):
        raise Deny("RELEASE_PATH_UNEXPECTED")
    s=path.lstat()
    user=pwd.getpwnam(OWNER)
    if not stat.S_ISDIR(s.st_mode) or s.st_uid not in (0,user.pw_uid) or s.st_mode&0o022:
        raise Deny("RELEASE_DIR_UNSAFE")
    app=path/"apps/platform"
    if app.is_symlink() or app.resolve(strict=True)!=app:raise Deny("APP_DIR_SYMLINK")
    for name in ("vendor/autoload.php","bootstrap/app.php",".env"):
        if not (app/name).is_file():raise Deny("LIVE_LARAVEL_MISSING")
    storage=(app/"storage/app").resolve(strict=True)
    if (not storage.is_relative_to("/home/kmjprod/") or not storage.is_dir() or
        storage==Path("/home/kmjprod") or storage.is_symlink()):
        raise Deny("STORAGE_OUTSIDE_APP_ROOT")
    return user,path,app,storage

def check_tools():
    for name in ("php8.4","pg_dump","pg_restore","tar","age","sha256sum","runuser"):
        if not any(os.access(Path(prefix)/name,os.X_OK) for prefix in ("/usr/bin","/usr/sbin","/bin","/sbin")):
            raise Deny("REQUIRED_TOOL_UNAVAILABLE")
    if not re.fullmatch(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}",PUBLIC):
        raise Deny("GOOGLE_X25519_PIN")

# The PHP is executed AS the live nonroot app owner, never root; it uses
# Laravel's effective config (including cached config). No credentials print.
DUMP_PHP=r'''<?php
try {
  $root=$argv[1];$output=$argv[2];
  require $root.'/vendor/autoload.php';
  $app=require $root.'/bootstrap/app.php';
  $app->make(\Illuminate\Contracts\Console\Kernel::class)->bootstrap();
  if ((string)config('app.env')!=='production') throw new \RuntimeException('NOT_PRODUCTION');
  $db=config('database.connections.'.config('database.default'));
  if (!is_array($db) || ($db['driver']??null)!=='pgsql' ||
      !empty($db['url']) || !empty($db['read']) || !empty($db['write'])) throw new \RuntimeException('CONFIG');
  $host=(string)($db['host']??'');$port=(string)($db['port']??'5432');
  $name=$db['database']??null;$user=$db['username']??null;
  if (!in_array($host,['127.0.0.1','localhost','::1','/var/run/postgresql','/run/postgresql'],true) ||
      !preg_match('/^[0-9]{2,5}$/',$port) ||
      !is_string($name) || !preg_match('/^[a-zA-Z0-9_]{1,65}$/',$name) ||
      !is_string($user) || !preg_match('/^[a-zA-Z0-9_]{1,65}$/',$user))
      throw new \RuntimeException('INVALID_PGSQL');
  $cmd=['/usr/bin/pg_dump','--format=custom','--no-owner','--no-acl',
    '--host='.$host,'--port='.$port,'--username='.$user,
    '--dbname='.$name,'--file='.$output];
  $pipes=[];
  $proc=proc_open($cmd,[0=>['file','/dev/null','r'],1=>['file','/dev/null','w'],
    2=>['file','/dev/null','w']],$pipes,$root,
    ['PATH'=>'/usr/bin:/bin','HOME'=>'/home/kmjprod','LANG'=>'C',
     'PGPASSWORD'=>(string)($db['password']??''),'PGCONNECT_TIMEOUT'=>'12',
     'PGOPTIONS'=>'-c statement_timeout=300000']);
  if (!is_resource($proc) || proc_close($proc)!==0 ||
      !is_file($output) || filesize($output)<32) throw new \RuntimeException('DUMP_FAILED');
  echo "DUMP=PASS\n";
} catch (\Throwable $e) { echo "DUMP=BLOCKED\n";exit(3); }
'''.encode("utf8")

def private_file(path,uid=0):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=uid or s.st_nlink!=1 or s.st_mode&0o077:
            raise Deny("PRIVATE_FILE_UNSAFE")
        return s
    finally:os.close(fd)

def copy_app_dump(src,dest,uid):
    read=os.open(src,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        before=os.fstat(read)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid!=uid or
            before.st_mode&0o077 or before.st_nlink!=1 or
            not 32<=before.st_size<=MAX_SIZE):
            raise Deny("APP_DUMP_UNSAFE")
        write=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            size=0
            while True:
                block=os.read(read,1048576)
                if not block:break
                size+=len(block)
                if size>MAX_SIZE:raise Deny("DUMP_SIZE_CAP")
                while block:
                    n=os.write(write,block)
                    if n<1:raise Deny("DUMP_COPY_FAILED")
                    block=block[n:]
            os.fsync(write)
        finally:os.close(write)
        after=os.fstat(read)
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise Deny("DUMP_CHANGED")
        if size!=before.st_size:raise Deny("DUMP_COPY_INCOMPLETE")
        return size
    finally:os.close(read)

def native_pg_restore_candidates():
    """Find approved root-owned native readers, newest first (not pg_wrapper)."""
    directory=Path("/usr/lib/postgresql")
    if not directory.is_dir() or directory.is_symlink():
        raise Deny("PG_RESTORE_NATIVE_DIRECTORY_MISSING")
    result=[]
    for version in directory.iterdir():
        if not re.fullmatch(r"[0-9]{1,2}",version.name):continue
        binary=version/"bin/pg_restore"
        try:
            dirs=(directory.lstat(),version.lstat(),(version/"bin").lstat())
            meta=binary.lstat()
        except OSError:continue
        if any(not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022 for s in dirs):
            continue
        if (binary.is_symlink() or not stat.S_ISREG(meta.st_mode) or
            meta.st_uid!=0 or meta.st_mode&0o022 or not os.access(binary,os.X_OK)):
            continue
        result.append((int(version.name),binary))
    result.sort(key=lambda item:item[0],reverse=True)
    return result

def verify_pg_dump_custom(dump):
    """PGDMP magic + exact native pg_restore --list, never print TOC."""
    private_file(dump,uid=0)
    with dump.open("rb") as file:
        if file.read(5)!=b"PGDMP":raise Deny("FRESH_DUMP_NOT_PGDMP")
    emit("FRESH_DUMP_MAGIC","PGDMP_PASS")
    candidates=native_pg_restore_candidates()
    emit("PG_RESTORE_NATIVE_CANDIDATES",len(candidates))
    if not candidates:raise Deny("PG_RESTORE_NATIVE_MISSING")
    unsupported=0
    for version,binary in candidates:
        check=run([str(binary),"--list",str(dump)],timeout=50)
        if check.returncode==0:
            emit("PG_RESTORE_READER_MAJOR",version)
            emit("PG_RESTORE_TOC","PASS")
            return version
        if b"unsupported version" in check.stderr.lower():unsupported+=1
    emit("PG_RESTORE_UNSUPPORTED_ARCHIVE_REJECTIONS",unsupported)
    raise Deny("FRESH_PGDMP_NO_COMPATIBLE_READER")

def create_fresh(app,storage,user,work):
    with tempfile.TemporaryDirectory(prefix="kmj-pg-dump-",dir="/tmp") as tmp_name:
        tmp=Path(tmp_name)
        os.chown(tmp,0,user.pw_gid);os.chmod(tmp,0o750)
        child=tmp/"work";child.mkdir(mode=0o700)
        os.chown(child,user.pw_uid,user.pw_gid)
        script=tmp/"dump.php"
        script.write_bytes(DUMP_PHP);os.chown(script,0,user.pw_gid);script.chmod(0o640)
        result=run(["/usr/sbin/runuser","-u",OWNER,"--","/usr/bin/php8.4",
                    str(script),str(app),str(child/"database.dump")],timeout=700)
        if result.returncode or result.stdout.strip()!=b"DUMP=PASS":
            raise Deny("FRESH_PGDUMP_FAILED")
        amount=copy_app_dump(child/"database.dump",work/"database.dump",user.pw_uid)
    verify_pg_dump_custom(work/"database.dump")
    emit("FRESH_PGDMP","PASS")
    emit("FRESH_PGDMP_BYTES",amount)
    storage_tar=work/"storage.tar.gz"
    if run(["/usr/bin/tar","-czf",str(storage_tar),"-C",str(storage),"."],timeout=600).returncode:
        raise Deny("STORAGE_ARCHIVE_FAILED")
    if not 1<=private_file(storage_tar).st_size<=MAX_SIZE:
        raise Deny("STORAGE_ARCHIVE_TOO_LARGE")
    if run(["/usr/bin/tar","-tzf",str(storage_tar)],timeout=60).returncode:
        raise Deny("STORAGE_ARCHIVE_CORRUPT")
    emit("RESOLVED_STORAGE_BACKUP","PASS")
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (work/"metadata.txt").write_text(
        "schema=kmj.offsite.fresh.x25519.v1\n"+
        f"created_utc={stamp}\n"+
        "contains=production_pg_dump_and_storage\n"+
        "secrets_env=EXCLUDED\n",encoding="ascii")
    (work/"metadata.txt").chmod(0o600)
    lines=[]
    for name in ("database.dump","storage.tar.gz","metadata.txt"):
        hash=hashlib.sha256()
        with (work/name).open("rb") as fd:
            while part:=fd.read(1048576):hash.update(part)
        lines.append(f"{hash.hexdigest()}  {name}\n")
    (work/"SHA256SUMS").write_text("".join(lines),encoding="ascii")
    (work/"SHA256SUMS").chmod(0o600)
    if run(["/usr/bin/sha256sum","-c","SHA256SUMS"],cwd=str(work),timeout=30).returncode:
        raise Deny("MANIFEST_INTEGRITY")
    for name in ("database.dump","storage.tar.gz","metadata.txt","SHA256SUMS"):
        private_file(work/name)
    emit("SOURCE_MANIFEST","PASS")

def encrypt(work,cipher):
    tar=None;age=None
    try:
        tar=subprocess.Popen(["/usr/bin/tar","-czf","-","-C",str(work),
                              "database.dump","storage.tar.gz","metadata.txt","SHA256SUMS"],
             cwd="/",env=ENV,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
             stderr=subprocess.DEVNULL,start_new_session=True)
        if tar.stdout is None:raise Deny("TAR_PIPE_MISSING")
        age=subprocess.Popen(["/usr/bin/age","-r",PUBLIC,"-o",str(cipher)],
             cwd="/",env=ENV,stdin=tar.stdout,stdout=subprocess.DEVNULL,
             stderr=subprocess.DEVNULL,start_new_session=True)
        tar.stdout.close()
        if age.wait(timeout=900)!=0:raise Deny("AGE_FAILED")
        if tar.wait(timeout=30)!=0:raise Deny("SOURCE_TAR_FAILED")
    except (OSError,subprocess.TimeoutExpired):
        raise Deny("AGE_TAR_TIMEOUT_OR_UNAVAILABLE") from None
    finally:
        for child in (age,tar):
            if child is not None and child.poll() is None:child.kill();child.wait(timeout=10)

def exclusive_lock():
    fd=os.open(LOCK,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    st=os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_nlink!=1 or st.st_mode&0o077:
        os.close(fd);raise Deny("LOCK_UNSAFE")
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        os.close(fd);raise Deny("BACKUP_ALREADY_RUNNING") from None
    return fd

def schedule_unit_preflight(transport):
    """Review the sole exact installed drop-in; no unit or file mutations."""
    if Path(__file__).resolve()!=SCHEDULED:
        raise Deny("SCHEDULED_MODULE_NOT_INSTALLED")
    if transport.prop("LoadState")!="loaded":
        raise Deny("SCHEDULED_UNIT_NOT_LOADED")
    if transport.prop("User") not in ("","root") or transport.prop("Type")!="oneshot":
        raise Deny("SCHEDULED_UNIT_USER_TYPE_DRIFT")
    if transport.prop("DropInPaths")!=str(DROPIN):
        raise Deny("SCHEDULED_DROPIN_UNREVIEWED")
    raw=transport.prop("ExecStart") or ""
    if not re.search(r"(?:^|[ ;])path=/usr/bin/python3(?:[ ;]|$)",raw):
        raise Deny("SCHEDULED_EXECUTABLE_DRIFT")
    marker="argv[]=/usr/bin/python3 -I -B "+str(SCHEDULED)+" --scheduled-run"
    if marker not in raw:
        raise Deny("SCHEDULED_ARGV_DRIFT")
    if transport.prop("ActiveState") not in ("activating","active","inactive","failed"):
        raise Deny("SCHEDULED_UNIT_STATE_DRIFT")
    emit("SCHEDULED_UNIT_IDENTITY","EXACT_PINNED")
    emit("SCHEDULED_UNIT_ACTIVE","EXPECTED")

def inspect(transport,*,scheduled=False):
    check_tools()
    user,release,app,storage=live_app()
    if scheduled:
        schedule_unit_preflight(transport)
    else:
        if transport.prop("LoadState")!="loaded" or transport.prop("Type")!="oneshot":
            raise Deny("MIGRATION_UNIT_LOAD_TYPE")
        if transport.prop("User") not in ("","root") or transport.prop("DropInPaths")!=str(DROPIN):
            raise Deny("MIGRATION_DROPIN_USER")
        argv=transport.prop("ExecStart") or ""
        candidates=(
           "argv[]=/usr/bin/python3 -I -B /usr/local/libexec/kmj-offsite-fresh-x25519-v2-20261112.py --scheduled-run",
           "argv[]=/usr/bin/python3 -I -B "+str(SCHEDULED)+" --scheduled-run")
        if not any(token in argv for token in candidates):
            raise Deny("MIGRATION_START_NOT_V2_OR_V3")
        if transport.prop("ActiveState") not in ("inactive","failed"):
            raise Deny("MIGRATION_UNIT_RUNNING")
    transport.pinned_conf()
    # Current DNS may rotate; server identity remains strictly ED25519 pinned.
    transport.dns_address()
    s=transport.VAULT.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:
        raise Deny("VAULT_UNSAFE")
    for root,label in ((transport.VAULT,"VAULT_SPACE"),(Path("/tmp"),"DUMP_SCRATCH_SPACE")):
        v=os.statvfs(root)
        if v.f_bavail*v.f_frsize < 2*1024**3:
            raise Deny(label+"_BELOW_2GIB")
    emit("MINIMUM_TEMP_DISK_SPACE","PASS_2GIB")
    readers=native_pg_restore_candidates()
    emit("PG_RESTORE_NATIVE_CANDIDATES",len(readers))
    if not readers:raise Deny("PG_RESTORE_NATIVE_MISSING")
    version=run(["/usr/bin/pg_dump","--version"],timeout=15)
    if version.returncode!=0:raise Deny("PG_DUMP_VERSION_UNAVAILABLE")
    match=re.search(rb"PostgreSQL\) ([0-9]{1,2})(?:\.|[ \r\n])",version.stdout)
    if match is None:raise Deny("PG_DUMP_VERSION_UNRECOGNIZED")
    major=int(match.group(1))
    emit("PG_DUMP_CLIENT_MAJOR",major)
    emit("MATCHING_NATIVE_PG_RESTORE","YES" if any(n==major for n,_ in readers) else "NO")
    emit("LIVE_RELEASE","VERIFIED")
    emit("PRODUCTION_PGSQL_CONFIG","REQUIRES_RUNTIME_CHECK")
    emit("APP_USER","NONROOT")
    emit("STORAGE_TARGET","RESOLVED_WITHIN_KMJPROD_HOME")
    emit("X25519_RECIPIENT","PINNED")
    emit("SFTP_CLIENT_IDENTITY","PINNED")
    emit("GOOGLE_ENDPOINT","DNS_ONLY_STRICT_PINNED_HOSTKEY")
    emit("FRESH_DUMP_EXECUTED","NO")
    emit("SYSTEMD_MUTATION","NONE")
    emit("RESULT","INSPECT_PASS")
    return user,release,app,storage

def send(transport,*,scheduled=False):
    user,release,app,storage=inspect(transport,scheduled=scheduled)
    with os.fdopen(exclusive_lock(),"r+b"):
        hostkey=transport.host_key()
        emit("SFTP_HOSTKEY","PIN_MATCH")
        with tempfile.TemporaryDirectory(prefix=".kmj-fresh-x25519-",dir=str(transport.VAULT)) as tmp:
            work=Path(tmp)
            create_fresh(app,storage,user,work)
            if LIVE.resolve(strict=True)!=release:raise Deny("LIVE_RELEASE_CHANGED")
            cipher=work/"fresh.age"
            encrypt(work,cipher)
            sha=transport.digest_cipher(cipher)
            emit("NEW_X25519_CIPHER","PASS")
            emit("CIPHER_BYTES",cipher.stat().st_size)
            emit("CIPHER_SHA256_UPPER",sha.upper())
            transport.transfer(cipher,sha,hostkey)
            if LIVE.resolve(strict=True)!=release:
                raise Deny("LIVE_RELEASE_CHANGED_AFTER_TRANSFER")
            emit("REMOTE_SFTP_SHA_READBACK","PASS")
            emit("REMOTE_DATABASE_RESTORE","NOT_VERIFIED")
            emit("IP_ROTATION_GUARD","DNS_ONLY_PINNED_HOSTKEY_DDNS_PENDING")
            emit("SYSTEMD_MUTATION","NONE")
            emit("PRODUCTION_DB_MUTATION","NONE")
            emit("RESULT","FRESH_PGDUMP_X25519_GOOGLE_TRANSFER_PASS")

def selftest():
    if (b"--format=custom" not in DUMP_PHP or
        b"PGPASSWORD" not in DUMP_PHP or
        b"PG_DUMP=PASS" in DUMP_PHP or
        b"DUMP=PASS" not in DUMP_PHP):
        raise Deny("PHP_ARGV_CONTRACT")
    if not re.fullmatch(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}",PUBLIC):
        raise Deny("RECIPIENT")
    for marker in ("database.dump","storage.tar.gz","metadata.txt","SHA256SUMS"):
        if not re.fullmatch("[a-zA-Z0-9_.]+",marker):raise Deny("TAR_MEMBER")
    emit("OFFLINE_TESTS","4_PASS")
    emit("BACKUP_EXECUTED","NO")
    emit("RESULT","SELFTEST_PASS")

def main():
    os.umask(0o077)
    emit("SCHEMA","KMJ_OFFSITE_FRESH_PGDUMP_X25519_GOOGLE_SFTP_V3")
    if len(sys.argv)!=2 or sys.argv[1] not in ("--selftest","--inspect","--send-once","--installed-check","--scheduled-run") or os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        emit("RESULT","BLOCKED_HOST_OR_ARGS");return 2
    try:
        if sys.argv[1]=="--selftest":selftest();return 0
        transport=pinned_transport()
        if sys.argv[1]=="--inspect":inspect(transport)
        elif sys.argv[1]=="--installed-check":inspect(transport,scheduled=True)
        elif sys.argv[1]=="--scheduled-run":send(transport,scheduled=True)
        else:send(transport)
        return 0
    except Deny as exc:
        code=str(exc)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,80}",code):code="SAFE"
        emit("RESULT","BLOCKED_"+code);return 3
    except Exception:
        emit("RESULT","BLOCKED_SAFE");return 3
if __name__=="__main__":raise SystemExit(main())
