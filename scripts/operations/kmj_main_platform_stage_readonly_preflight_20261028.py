#!/usr/bin/env python3
"""Read-only KMJ Main Platform release preflight; sanitized CodeBridge receipt."""
import datetime
import json
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import subprocess
import tempfile

HOST = "staging.kmjtechno.com"
EXPECTED_SHA = "ad4cfa68291ec6a05e88f30ed0a93b2d15af40fe"
LIVE_LINK = Path("/home/kmjprod/current")
ROOT = Path("/srv/kmj-codebridge-projects/kmj-main-platform")
RECEIPTS = ROOT / "work/qa/operator-receipts"
FILE_NAME = "main-platform-release-preflight-20261028.json"

def limited_run(argv, timeout=8):
    try:
        result = subprocess.run(argv, cwd="/", env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C"}, timeout=timeout, check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        return result.returncode, result.stdout[:1500]
    except (OSError, subprocess.TimeoutExpired):
        return 124, ""

def safe_staging_vhost(conf, canonical):
    """Accept a plain file or only the canonical Ubuntu sites-enabled symlink."""
    try:
        if conf.is_symlink():
            return (conf.resolve(strict=True) == canonical
                    and canonical.is_file() and not canonical.is_symlink())
        return conf.is_file()
    except (OSError, RuntimeError):
        return False

def status():
    checks = {}
    checks["hostname_guard"] = socket.gethostname().split(".")[0] == "KMJ-elite"
    checks["root_guard"] = os.geteuid() == 0
    if not checks["hostname_guard"] or not checks["root_guard"]:
        return checks
    checks["live_pointer_present"] = LIVE_LINK.is_symlink()
    current = LIVE_LINK.resolve().name if LIVE_LINK.is_symlink() else ""
    checks["live_release"] = current if re.fullmatch(r"platform-[a-f0-9]{12}",current) else "UNKNOWN"
    checks["live_release_expected"] = current == "platform-8070dad72c55"
    conf = Path("/etc/nginx/sites-enabled/staging.kmjtechno.com.conf")
    checks["staging_site_config_present"] = safe_staging_vhost(
        conf, Path("/etc/nginx/sites-available/staging.kmjtechno.com.conf"))
    if checks["staging_site_config_present"]:
        try:
            source=conf.read_text(encoding="utf-8")
            checks["staging_hostname_in_config"] = bool(re.search(r"\bserver_name\s+[^;]*\bstaging\.kmjtechno\.com\b",source))
            checks["staging_tls_listen_configured"] = bool(re.search(r"\blisten\s+[^;]*443\b",source))
        except (OSError,UnicodeDecodeError):
            checks["staging_hostname_in_config"] = False
            checks["staging_tls_listen_configured"] = False
    rc,_ = limited_run(["/usr/sbin/nginx","-t"])
    checks["nginx_config_valid"] = rc == 0
    checks["staging_tls_valid"] = False
    try:
        context = ssl.create_default_context()
        with socket.create_connection(("127.0.0.1",443),timeout=4) as stream:
            with context.wrap_socket(stream,server_hostname=HOST) as peer:
                checks["staging_tls_valid"] = bool(peer.getpeercert())
    except (OSError,ssl.SSLError,ValueError):
        pass
    header = tempfile.NamedTemporaryFile(mode="w+b",prefix="kmj-stage-head-",dir="/root",delete=False)
    head_path=Path(header.name)
    header.close()
    try:
        rc,code = limited_run(["/usr/bin/curl","--proto","=https","--fail","--silent","--show-error","--connect-timeout","5","--max-time","12","--resolve",HOST+":443:127.0.0.1","--dump-header",str(head_path),"--output","/dev/null","--write-out","%{http_code}","https://"+HOST+"/"],timeout=17)
        checks["staging_http_200"] = rc == 0 and code.strip() == "200"
        if checks["staging_http_200"]:
            headers=head_path.read_text(encoding="utf-8",errors="replace")[:8192].splitlines()
            values=[line.partition(":")[2].strip().lower() for line in headers if line.lower().startswith("x-kmj-deploy-sha:")]
            checks["staging_exact_sha"] = len(values)==1 and values[0]==EXPECTED_SHA
        else:
            checks["staging_exact_sha"] = False
    finally:
        try: head_path.unlink()
        except OSError: pass
    checks["customer_storage_present"] = (LIVE_LINK / "apps/platform/storage").is_dir()
    return checks

def save(checks):
    for directory in [ROOT, ROOT/"work",ROOT/"work/qa"]:
        if not directory.is_dir() or directory.is_symlink():
            raise RuntimeError("UNSAFE_RECEIPT_PARENT")
    if RECEIPTS.is_symlink():
        raise RuntimeError("UNSAFE_RECEIPT_DIRECTORY")
    RECEIPTS.mkdir(mode=0o755,exist_ok=True)
    if (RECEIPTS.stat().st_mode & 0o022) or not stat.S_ISDIR(RECEIPTS.stat().st_mode):
        raise RuntimeError("INSECURE_RECEIPT_DIRECTORY")
    dest=RECEIPTS/FILE_NAME
    if dest.exists() or dest.is_symlink():
        raise RuntimeError("RECEIPT_ALREADY_EXISTS")
    payload={"schema":"kmj.release.preflight.v1","sampled_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),"expected_staging_sha":EXPECTED_SHA,"checks":checks,"production_mutated":False,"approval_issued":False}
    raw=(json.dumps(payload,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
    if len(raw)>3500:
        raise RuntimeError("RECEIPT_TOO_LARGE")
    fd,path=tempfile.mkstemp(prefix=".kmj-preflight-",dir=RECEIPTS)
    temp=Path(path)
    try:
        with os.fdopen(fd,"wb") as output:
            os.fchmod(output.fileno(),0o644)
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.link(temp,dest)
        fd=os.open(str(RECEIPTS),os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        try:temp.unlink()
        except OSError:pass

if __name__ == "__main__":
    result=status()
    if not result.get("root_guard") or not result.get("hostname_guard"):
        print("KMJ_RELEASE_PREFLIGHT=BLOCKED_WRONG_OPERATOR_OR_HOST")
        raise SystemExit(2)
    try:
        save(result)
    except (OSError,RuntimeError) as error:
        print("KMJ_RELEASE_PREFLIGHT=BLOCKED_RECEIPT_SAFETY")
        raise SystemExit(2) from error
    print("KMJ_RELEASE_PREFLIGHT_RECEIPT=work/qa/operator-receipts/"+FILE_NAME)
    print("KMJ_RELEASE_PREFLIGHT_PRODUCTION_MUTATION=NONE")
    print("KMJ_RELEASE_PREFLIGHT_STAGING_READY="+("YES" if all(result.get(k) for k in ("live_release_expected","staging_site_config_present","staging_hostname_in_config","staging_tls_listen_configured","nginx_config_valid","staging_tls_valid","staging_http_200","staging_exact_sha","customer_storage_present")) else "NO"))
