import { createServer } from 'vite';
import { fileURLToPath } from 'node:url';

// Fixed loopback-only, synthetic-data preview. Never starts Laravel or uses credentials.
const server = await createServer({
    configFile: fileURLToPath(
        new URL('../visual/vite.config.ts', import.meta.url),
    ),
});
try {
    await server.listen();
    await import('./browser-preview-verify.mjs');
} finally {
    await server.close();
}
