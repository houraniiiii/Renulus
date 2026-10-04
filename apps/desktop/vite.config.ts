import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

function loopbackPort(value: string | undefined, fallback: number): number {
  const port = value === undefined ? fallback : Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid Renulus loopback port.');
  return port;
}

export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    host: '127.0.0.1',
    port: loopbackPort(process.env.RENULUS_DESKTOP_PORT, 5190),
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:' + loopbackPort(process.env.RENULUS_BACKEND_PORT, 8765),
        changeOrigin: true,
        headers: process.env.RENULUS_SESSION_TOKEN
          ? { 'x-renulus-token': process.env.RENULUS_SESSION_TOKEN }
          : {},
        configure(proxy) {
          proxy.on('proxyRes', response => { response.headers['cache-control'] = 'no-store'; });
        },
      },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
});
