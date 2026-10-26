import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';
export default defineConfig({
    root: fileURLToPath(new URL('.', import.meta.url)),
    publicDir: '../public',
    resolve: {
        alias: {
            // This owner-only fixture never renders the customer fallback.
            // Its generated Laravel route imports are unavailable in this
            // static preview; fail loudly if owner selection regresses.
            '@/layouts/app/app-sidebar-layout': fileURLToPath(
                new URL('./customer-layout-unavailable.tsx', import.meta.url),
            ),
            '@': fileURLToPath(new URL('../resources/js', import.meta.url)),
        },
    },
    plugins: [react(), tailwindcss()],
    build: { outDir: '../.visual-preview', emptyOutDir: true },
    server: { host: '127.0.0.1', port: 4173, strictPort: true },
    preview: { host: '127.0.0.1', port: 4173, strictPort: true },
});
