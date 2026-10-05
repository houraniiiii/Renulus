// Scoped adaptation of Hermes desktop electron-builder whitelist/Windows packaging.
const fs = require('node:fs');
const path = require('node:path');
const bundle = process.env.RENULUS_BACKEND_BUNDLE;
const renderer = process.env.RENULUS_RENDERER_BUNDLE;
const native = process.env.RENULUS_NATIVE_BUNDLE;
const output = process.env.RENULUS_DELIVERY_OUTPUT;
if (output) {
  const roots = [path.join(__dirname, 'release'), path.resolve('E:/Renulus-native-delivery/desktop-20261005')];
  const confined = path.isAbsolute(output) && roots.some(root => {
    const relative = path.relative(root, output);
    return relative && !relative.startsWith('..') && !path.isAbsolute(relative);
  });
  if (!confined) throw new Error('A delivery output must stay in the desktop release tree or exact authorised E root.');
  let cursor = path.resolve(output);
  while (cursor !== path.dirname(cursor)) {
    if (fs.existsSync(cursor) && fs.lstatSync(cursor).isSymbolicLink()) throw new Error('A delivery output may not traverse a reparse path.');
    cursor = path.dirname(cursor);
  }
}
if (renderer && (!path.isAbsolute(renderer) || !fs.existsSync(path.join(renderer, 'index.html')) || !fs.existsSync(path.join(renderer, 'renderer-provenance.json')))) throw new Error('An integrated renderer requires its built index and committed source provenance.');
if (native && (!path.isAbsolute(native) || !fs.existsSync(path.join(native, 'main.cjs')) || !fs.existsSync(path.join(native, 'native-provenance.json')))) throw new Error('An integrated native entry requires its compiled main and source/adoption provenance.');
if (!bundle || !path.isAbsolute(bundle) || !fs.existsSync(path.join(bundle, 'bundle.json'))) {
  throw new Error('Packaging requires an explicit RENULUS_BACKEND_BUNDLE containing the verified embedded runtime and helpers.');
}
const contract = JSON.parse(fs.readFileSync(path.join(bundle, 'bundle.json'), 'utf8'));
if (contract.version !== 1 || contract.format !== 'embedded-cpython-windows-v1' || contract.python.executable !== 'python/python.exe' || !fs.existsSync(path.join(bundle, 'python', 'python.exe')) || !fs.existsSync(path.join(bundle, 'inventory.json'))) throw new Error('The backend bundle is incomplete.');
if (native) {
  const provenance = JSON.parse(fs.readFileSync(path.join(native, 'native-provenance.json'), 'utf8'));
  const ui = renderer && JSON.parse(fs.readFileSync(path.join(renderer, 'renderer-provenance.json'), 'utf8'));
  if (provenance.kind !== 'committed-integrated-native' || provenance.electron_version !== require('./package.json').devDependencies.electron || provenance.source_revision !== contract.source_revision || !ui || ui.source_revision !== contract.source_revision) throw new Error('Integrated backend, renderer and native entry must use one committed source revision and the patched Electron pin.');
}
module.exports = {
  electronVersion: require('./package.json').devDependencies.electron,
  electronDist: path.join(__dirname, 'node_modules', 'electron', 'dist'),
  appId: 'org.renulus.desktop.development',
  productName: 'Renulus Development',
  artifactName: 'Renulus-Development-${version}-windows-x64-setup.${ext}',
  asar: true,
  nativeModules: { npmRebuild: false, nodeGypRebuild: false },
  toolsets: { nsis: '1.2.1', sevenZip: '1.0.0' },
  directories: { output: output || 'release' },
  files: [renderer ? { from: renderer, to: 'dist', filter: ['**/*'] } : 'dist/**', native ? { from: native, to: 'dist-electron', filter: ['**/*'] } : 'dist-electron/**', 'licenses/**', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'package.json'],
  extraResources: [{ from: bundle, to: 'backend' }, { from: path.join(__dirname, 'licenses'), to: 'licenses' }, { from: path.join(__dirname, 'THIRD_PARTY_NOTICES.md'), to: 'THIRD_PARTY_NOTICES.md' }],
  publish: null,
  forceCodeSigning: false,
  win: { executableName: 'Renulus Development', icon: 'public/renulus.ico', target: ['nsis'], sign: false },
  nsis: { oneClick: false, perMachine: false, allowElevation: false, allowToChangeInstallationDirectory: true, deleteAppDataOnUninstall: false, runAfterFinish: false, createDesktopShortcut: false, createStartMenuShortcut: false },
};
