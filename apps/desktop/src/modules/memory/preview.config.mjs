// Owned verification config for a worktree using the integrator's installed packages.
// It does not alter the shared production config or lockfiles.
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const desktopRoot = fileURLToPath(new URL('../../../', import.meta.url));
const localDependencies = resolve(desktopRoot, 'node_modules');
export const dependencies = resolve(process.env.RENULUS_DEPENDENCY_ROOT ??
  (existsSync(resolve(localDependencies, 'react/package.json')) ? localDependencies :
    resolve(desktopRoot, '../../../Renulus-wt-integration/apps/desktop/node_modules')));
const reactPlugin = resolve(dependencies, '@vitejs/plugin-react/dist/index.js');
if (!existsSync(reactPlugin)) throw new Error('Set RENULUS_DEPENDENCY_ROOT to the installed desktop node_modules directory.');
const { default: react } = await import(pathToFileURL(reactPlugin).href);
function port(value, fallback) {
  const selected = value === undefined ? fallback : Number(value);
  if (!Number.isInteger(selected) || selected < 1 || selected > 65535) throw new Error('Invalid local verification port.');
  return selected;
}
export default {
  root: desktopRoot,
  cacheDir: resolve(desktopRoot, 'src/modules/memory/.validation-cache'),
  plugins: [react()],
  resolve: { alias: ['react', 'react-dom', 'lucide-react', '@testing-library/react', 'vitest', '@fontsource-variable/source-sans-3']
    .map(name => ({ find: name, replacement: resolve(dependencies, name).replaceAll('\\', '/') })) },
  test: { environment: 'node', include: ['src/modules/memory/**/*.test.{ts,tsx}'], restoreMocks: true, clearMocks: true },
  server: {
    host: '127.0.0.1', port: port(process.env.RENULUS_DESKTOP_PORT, 5209), strictPort: true,
    fs: { allow: [desktopRoot, dependencies] },
    proxy: { '/api': { target: 'http://127.0.0.1:' + port(process.env.RENULUS_BACKEND_PORT, 8899), changeOrigin: true,
      headers: process.env.RENULUS_SESSION_TOKEN ? { 'x-renulus-token': process.env.RENULUS_SESSION_TOKEN } : {} } },
  },
  build: { outDir: resolve(desktopRoot, 'src/modules/memory/.validation-dist'), emptyOutDir: true },
};
