import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
test('landing retains all locked sections in reference order', () => {
 const s=readFileSync(new URL('../apps/platform/resources/js/pages/welcome.tsx', import.meta.url),'utf8');
 const labels=['Our Flagship Products','What We Build','A Complete and Connected Ecosystem','Industries We Serve','Our Roadmap'];
 let previous=-1;
 for(const label of labels){const index=s.indexOf(label);assert.ok(index>previous,`missing or out of order: ${label}`);previous=index;}
});
