import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const dockerfile = readFileSync(join(dirname(fileURLToPath(import.meta.url)),
  'Dockerfile.KMJ-P520-RECOVERY-OWNER-20261121'), 'utf8');

test('P520 recovery image has digest-pinned PostgreSQL 18 and AGE+Python', () => {
  assert.match(dockerfile, /^FROM postgres:18\.6-alpine3\.24@sha256:10a5c69a83035ab5239f5620d708520e8b28f5aa1f2b20143e6024532edadfb5$/m);
  assert.match(dockerfile, /RUN apk add --no-cache age python3/);
  for (const name of ['age --version', 'python3 --version','pg_restore --version','initdb --version']) {
    assert.ok(dockerfile.includes(name), name);
  }
});
test('P520 recovery image enforces nonroot and private volume mount', () => {
  assert.match(dockerfile, /chown postgres:postgres \/recovery/);
  assert.match(dockerfile, /chmod 0700 \/recovery/);
  assert.match(dockerfile, /^USER postgres$/m);
  assert.match(dockerfile, /^WORKDIR \/recovery$/m);
  assert.doesNotMatch(dockerfile, /^(ADD|COPY|ENTRYPOINT)\b/m);
});
