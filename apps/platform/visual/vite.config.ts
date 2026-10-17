import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';
export default defineConfig({
    root: fileURLToPath(new URL('.', import.meta.url)),
    publicDir: '../public',
    resolve: {
        alias: {
            '@': fileURLToPath(new URL('../resources/js', import.meta.url)),
        },
    },
    plugins: [react(), tailwindcss()],
    build: { outDir: '../.visual-preview', emptyOutDir: true },
    server: { host: '127.0.0.1', port: 4173, strictPort: true },
    preview: { host: '127.0.0.1', port: 4173, strictPort: true },
});
