// Check the complete desktop with the same installed packages as the owned preview.
import { mkdir, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { dependencies, desktopRoot } from './preview.config.mjs';

const directory = resolve(desktopRoot, 'src/modules/memory/.validation-cache');
const configFile = resolve(directory, 'tsconfig.json');
await mkdir(directory, { recursive: true });
const dependencyPath = path => resolve(dependencies, path).replaceAll('\\', '/');
await writeFile(configFile, JSON.stringify({
  extends: resolve(desktopRoot, 'tsconfig.json').replaceAll('\\', '/'),
  compilerOptions: {
    paths: {
      react: [dependencyPath('@types/react')], 'react/*': [dependencyPath('@types/react/*')],
      'react-dom/*': [dependencyPath('@types/react-dom/*')],
      vite: [dependencyPath('vite/dist/node/index.d.ts')],
      '@vitejs/plugin-react': [dependencyPath('@vitejs/plugin-react/dist/index.d.ts')],
      chai: [dependencyPath('@types/chai/index.d.ts')], '*': [dependencyPath('*')],
    },
    typeRoots: [dependencyPath('@types')], types: ['node'],
  },
  files: [dependencyPath('vite/client.d.ts')],
}, null, 2));
try {
  const result = spawnSync(process.execPath, [dependencyPath('typescript/lib/tsc.js'), '--noEmit', '-p', configFile], { cwd: desktopRoot, stdio: 'inherit' });
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
  if (result.status === 0) process.stdout.write('Desktop typecheck passed.\n');
} finally { await rm(configFile, { force: true }); }
