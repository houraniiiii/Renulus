// Scoped adaptation of Hermes desktop electron-builder whitelist/Windows packaging.
const fs = require('node:fs');
const path = require('node:path');
const bundle = process.env.RENULUS_BACKEND_BUNDLE;
const renderer = process.env.RENULUS_RENDERER_BUNDLE;
const native = process.env.RENULUS_NATIVE_BUNDLE;
const output = process.env.RENULUS_DELIVERY_OUTPUT;
const revision = process.env.RENULUS_DELIVERY_REVISION;
const authorizedRoot = path.resolve('C:/Renulus-native-delivery/desktop-20261005');
const requestedRoot = process.env.RENULUS_DELIVERY_ROOT || authorizedRoot;
if (!/^[Cc]:[\\/]/.test(requestedRoot) || /[\x00-\x1f]/.test(requestedRoot)) throw new Error('DeliveryRoot requires an absolute local C SSD path.');
const deliveryRoot = path.resolve(requestedRoot);
const rootRelative = path.relative(authorizedRoot, deliveryRoot);
if (rootRelative) {
  const parts = rootRelative.split(path.sep);
  if (parts.length !== 2 || parts[0] !== 'deliveries' || !/^[a-z0-9][a-z0-9._-]{0,63}$/.test(parts[1]) || parts[1].endsWith('.') || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$/i.test(parts[1])) throw new Error('DeliveryRoot may only use the exact authorised C root or one named deliveries child; repository, data, profile and credential roots are excluded.');
}
function rejectReparseAncestors(value) {
  for (let cursor = path.resolve(value); ; cursor = path.dirname(cursor)) {
    if (fs.lstatSync(cursor, { throwIfNoEntry: false })?.isSymbolicLink()) throw new Error('A delivery path may not traverse a reparse path.');
    if (cursor === path.dirname(cursor)) break;
  }
}
rejectReparseAncestors(deliveryRoot);
if (fs.existsSync(deliveryRoot) && !fs.statSync(deliveryRoot).isDirectory()) throw new Error('DeliveryRoot must be a directory.');
if (revision && (!output || !/^[0-9a-f]{40}$/.test(revision))) throw new Error('A checkpoint installer identity requires an exact delivery revision and guarded output.');
if (output) {
  const roots = [path.join(__dirname, 'release'), deliveryRoot];
  const confined = path.isAbsolute(output) && roots.some(root => {
    const relative = path.relative(root, output);
    return relative && !relative.startsWith('..') && !path.isAbsolute(relative);
  });
  if (!confined) throw new Error('A delivery output must stay in the desktop release tree or exact authorised C root; E inputs are preserved.');
  const externalRelative = path.relative(roots[1], output);
  if (externalRelative && !externalRelative.startsWith('..') && !path.isAbsolute(externalRelative) && !/^(preparation|payloads|environment|temporary|proofs|source-[0-9a-f]{8}|matching-[0-9a-f]{8}|installed-[0-9a-f]{8})$/.test(externalRelative.split(path.sep)[0])) throw new Error('A delivery output cannot use repository or application-data directories.');
  rejectReparseAncestors(output);
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
  // NSIS uninstalls an earlier registered app with the same ID even for a fresh /D.
  // Keep checkpoint installs independent so their public payloads stay intact.
  appId: revision ? 'org.renulus.desktop.delivery.' + revision : 'org.renulus.desktop.development',
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
