#!/usr/bin/env bash
# KMJ Elite: web speed tune (compression, HTTP/2, immutable asset caching, optional brotli).
# Owner runs as root on KMJ-elite. Reversible: full /etc/nginx backup + automatic rollback if `nginx -t` fails.
# Touches ONLY: /etc/nginx/conf.d/kmj-speed.conf (+ kmj-brotli.conf) and the `listen 443 ssl;` line of the
# kmjtechno.com / www.kmjtechno.com server blocks. No secrets, no app/DB/release change.
set -Eeuo pipefail
[ "$(id -u)" = 0 ] || { echo "KMJ_SPEED=BLOCKED_NOT_ROOT"; exit 2; }
[ "$(hostname)" = "KMJ-elite" ] || { echo "KMJ_SPEED=BLOCKED_WRONG_HOST"; exit 2; }

TS=$(date -u +%Y%m%dT%H%M%SZ)
BK=/root/nginx-speed-backup-$TS
mkdir -p "$BK" && cp -a /etc/nginx "$BK/nginx"
echo "backup: $BK"

rollback() {
  echo "ROLLBACK: restoring /etc/nginx from $BK"
  rm -f /etc/nginx/conf.d/kmj-speed.conf /etc/nginx/conf.d/kmj-brotli.conf
  rsync -a --delete "$BK/nginx/" /etc/nginx/
  nginx -t && systemctl reload nginx || true
}

nginx -T 2>/dev/null | grep -qE 'include /etc/nginx/conf\.d/\*\.conf' \
  || { echo "KMJ_SPEED=BLOCKED_CONF_D_NOT_INCLUDED"; exit 3; }
nginx -t 2>&1 | grep -q "successful" || { echo "KMJ_SPEED=BLOCKED_NGINX_ALREADY_INVALID"; exit 3; }

# 1) http-level: compress css/js/svg/json/fonts, long immutable cache for hashed build assets, file-descriptor cache
cat > /etc/nginx/conf.d/kmj-speed.conf <<'CONF'
# Managed by KMJ_NGINX_SPEED_TUNE.sh (remove this file + reload nginx to undo)
gzip_vary on;
gzip_proxied any;
gzip_comp_level 5;
gzip_min_length 512;
gzip_types text/plain text/css text/xml text/javascript application/javascript application/json
           application/xml application/xml+rss application/manifest+json image/svg+xml font/ttf font/otf;

map $uri $kmj_asset_cache {
    default "";
    ~^/build/assets/ "public, max-age=31536000, immutable";
    ~^/assets/(brand|products)/ "public, max-age=2592000";
}
add_header Cache-Control $kmj_asset_cache;

open_file_cache max=2000 inactive=60s;
open_file_cache_valid 60s;
open_file_cache_min_uses 2;
open_file_cache_errors on;
CONF

# 2) HTTP/2 on the kmjtechno.com / www server blocks only (nginx 1.24: listen parameter)
python3 - <<'PY'
import glob, os, re
changed = 0
for path in sorted(set(os.path.realpath(p) for p in glob.glob('/etc/nginx/sites-enabled/*'))):
    s = open(path).read()
    out, i = [], 0
    while True:
        m = re.search(r'(?m)^\s*server\s*\{', s[i:])
        if not m:
            out.append(s[i:]); break
        start = i + m.start()
        out.append(s[i:start])
        depth, j = 0, i + m.end() - 1
        while True:
            c = s[j]
            depth += (c == '{') - (c == '}')
            j += 1
            if depth == 0: break
        block = s[start:j]
        if re.search(r'(?m)^\s*server_name\s+(www\.)?kmjtechno\.com\s*;', block) and 'listen 443 ssl;' in block and 'http2' not in block:
            block = block.replace('listen 443 ssl;', 'listen 443 ssl http2;', 1); changed += 1
        out.append(block); i = j
    new = ''.join(out)
    if new != s:
        open(path, 'w').write(new)
print(f"http2 blocks changed: {changed}")
PY

if ! nginx -t 2>&1 | grep -q successful; then nginx -t || true; rollback; echo "KMJ_SPEED=ROLLED_BACK_NGINX_TEST_FAILED"; exit 4; fi
systemctl reload nginx
echo "step1 OK: compression + cache + http2 applied"

# 3) optional brotli (Ubuntu package); skipped silently if not available. Failure never undoes step 1.
if apt-cache policy libnginx-mod-http-brotli-filter 2>/dev/null | grep -q 'Candidate: [0-9]'; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y libnginx-mod-http-brotli-filter libnginx-mod-http-brotli-static >/dev/null 2>&1 || true
  cat > /etc/nginx/conf.d/kmj-brotli.conf <<'CONF'
brotli on;
brotli_comp_level 5;
brotli_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml image/svg+xml;
CONF
  if nginx -t 2>&1 | grep -q successful; then systemctl reload nginx; echo "step3 OK: brotli on"
  else rm -f /etc/nginx/conf.d/kmj-brotli.conf; nginx -t >/dev/null 2>&1 && systemctl reload nginx || true; echo "step3 SKIPPED: brotli not usable (gzip stays on)"; fi
else
  echo "step3 SKIPPED: brotli package not available (gzip stays on)"
fi

# 4) local verification (no secrets)
CSS=$(ls /home/kmjprod/current/apps/platform/public/build/assets/*.css 2>/dev/null | head -1 || true)
echo "--- verify ---"
curl -skI --http2 --resolve kmjtechno.com:443:127.0.0.1 https://kmjtechno.com/robots.txt | sed -n '1p'
if [ -n "$CSS" ]; then
  curl -skI --http2 -H 'Accept-Encoding: br, gzip' --resolve kmjtechno.com:443:127.0.0.1 "https://kmjtechno.com/build/assets/$(basename "$CSS")" | grep -iE '^(HTTP|content-encoding|cache-control)'
fi
echo "KMJ_SPEED=DONE backup=$BK"
echo "undo: rm -f /etc/nginx/conf.d/kmj-speed.conf /etc/nginx/conf.d/kmj-brotli.conf; rsync -a --delete $BK/nginx/ /etc/nginx/; nginx -t && systemctl reload nginx"
