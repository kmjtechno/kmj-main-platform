#!/usr/bin/python3
import json, os, pathlib, re, subprocess, tempfile, time, urllib.request, urllib.error
from urllib.parse import urlparse

SERVICE="kmj-codebridge-kmj-main-platform.service"
CONFIG=pathlib.Path("/etc/kmj-codebridge-main-platform/agent.json")
OUT=pathlib.Path("/var/lib/kmj-codebridge-status-export/status.json")
EXPECTED_DEVICE="main-platform-kmjtechnonetgmailcom"
EXPECTED_PROJECT="kmj-main-platform"
EXPECTED_REPOSITORY="kmjtechno/kmj-main-platform"
ALLOWED_GATEWAYS={"https://kmjtechno.com","https://kmj-codebridge-gateway.onrender.com","http://127.0.0.1:8787"}

def run(*args):
    return subprocess.run(args,text=True,capture_output=True,timeout=15,check=False)

def fail(code):
    value={"schema_version":1,"repository":EXPECTED_REPOSITORY,"device":EXPECTED_DEVICE,
           "project":EXPECTED_PROJECT,"branch":"main","connection":"error","version":"unknown",
           "writable":False,"authorized":False,"effective_permissions":[],
           "gates":[],"gate_readiness":{"fast":"blocked","platform":"blocked","full":"blocked"},
           "checkout_sha":"0"*40,"observed_utc_epoch":time.time(),
           "source":"main-vps-restricted-exporter"}
    write(value)
    raise SystemExit(2)

def write(value):
    OUT.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
    fd,tmp=tempfile.mkstemp(prefix=".status-",dir=OUT.parent)
    try:
        with os.fdopen(fd,"w") as f:
            json.dump(value,f,sort_keys=True); f.write("\n"); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp,0o644); os.replace(tmp,OUT)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

if CONFIG.is_symlink() or not CONFIG.is_file():
    fail("CONFIG_UNSAFE")
try:
    cfg=json.loads(CONFIG.read_text())
except Exception:
    fail("CONFIG_INVALID")
if cfg.get("id") != EXPECTED_DEVICE:
    fail("DEVICE_ID_MISMATCH")
projects=cfg.get("projects")
if not isinstance(projects,list):
    fail("PROJECTS_INVALID")
matches=[x for x in projects if isinstance(x,dict) and x.get("id")==EXPECTED_PROJECT]
if len(matches)!=1 or any(isinstance(x,dict) and x.get("id")=="project1" for x in projects):
    fail("PROJECT_ID_MISMATCH")
project=matches[0]
root=pathlib.Path(project.get("root",""))
if str(root)!="/srv/kmj-codebridge-projects/kmj-main-platform" or not root.is_dir():
    fail("PROJECT_ROOT_MISMATCH")
gates=sorted((project.get("gates") or {}).keys())
if gates != ["fast","full","platform"] or project.get("writable") is not True:
    fail("PROJECT_CAPABILITY_MISMATCH")
service=run("systemctl","is-active",SERVICE)
if service.stdout.strip()!="active":
    fail("SERVICE_INACTIVE")
branch=run("git","-c",f"safe.directory={root}","-C",str(root),"rev-parse","--abbrev-ref","HEAD")
sha=run("git","-c",f"safe.directory={root}","-C",str(root),"rev-parse","HEAD")
if branch.returncode or branch.stdout.strip()!="main":
    fail("CHECKOUT_BRANCH_MISMATCH")
checkout=sha.stdout.strip()
if sha.returncode or not re.fullmatch(r"[0-9a-f]{40}",checkout):
    fail("CHECKOUT_SHA_INVALID")
gateway=cfg.get("gateway")
try:
    parsed=urlparse(gateway)
    origin=f"{parsed.scheme}://{parsed.netloc}"
except Exception:
    fail("GATEWAY_INVALID")
if origin not in ALLOWED_GATEWAYS or parsed.path not in {"","/"} or parsed.query or parsed.fragment:
    fail("GATEWAY_INVALID")
token=cfg.get("token")
if not isinstance(token,str) or len(token)<32:
    fail("CREDENTIAL_INVALID")
request=urllib.request.Request(
    origin+"/agent/health",data=b"{}",method="POST",
    headers={"Authorization":"Bearer "+token,"Content-Type":"application/json","User-Agent":"kmj-status-export/1"},
)
try:
    with urllib.request.urlopen(request,timeout=12) as response:
        health=response.status
except urllib.error.HTTPError as exc:
    health=exc.code
except Exception:
    health=0
if health != 200:
    fail("GATEWAY_HEALTH_FAILED")
show=run("systemctl","show",SERVICE,"-p","ExecStart","--value")
match=re.search(r"/opt/kmj-codebridge-releases/([0-9a-f]+)/src/cli\.js",show.stdout)
version="unknown"
if match:
    package=pathlib.Path("/opt/kmj-codebridge-releases")/match.group(1)/"package.json"
    try:
        version=str(json.loads(package.read_text()).get("version") or "unknown")
    except Exception:
        pass
readiness={}
for gate in gates:
    required=(project["gates"].get(gate) or {}).get("requiredFiles") or []
    if not required:
        readiness[gate]="not_configured"
    else:
        readiness[gate]="blocked" if not all((root/path).is_file() for path in required) else "not_configured"
readiness_file=OUT.parent/"gate-readiness.json"
try:
    observed=json.loads(readiness_file.read_text())
    if (isinstance(observed,dict) and set(observed)==set(gates)
            and all(v in {"satisfied","blocked","not_configured"} for v in observed.values())):
        readiness=observed
except Exception:
    pass
value={"schema_version":1,"repository":EXPECTED_REPOSITORY,"device":EXPECTED_DEVICE,
       "project":EXPECTED_PROJECT,"branch":"main","connection":"connected","version":version,
       "writable":True,"authorized":True,"effective_permissions":["read","write","execute"],
       "gates":gates,"gate_readiness":readiness,"checkout_sha":checkout,
       "observed_utc_epoch":time.time(),"source":"main-vps-restricted-exporter"}
write(value)
