// Scoped adaptation of Hermes desktop electron-builder whitelist/Windows packaging.
const fs = require('node:fs');
const path = require('node:path');
const bundle = process.env.RENULUS_BACKEND_BUNDLE;
if (!bundle || !path.isAbsolute(bundle) || !fs.existsSync(path.join(bundle, 'renulus-backend.exe'))) {
  throw new Error('Packaging requires an explicit RENULUS_BACKEND_BUNDLE containing the verified renulus-backend.exe and helpers.');
}
module.exports = {
  appId: 'org.renulus.desktop.development',
  productName: 'Renulus Development',
  asar: true,
  directories: { output: 'release' },
  files: ['dist/**', 'dist-electron/**', 'licenses/**', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'package.json'],
  extraResources: [{ from: bundle, to: 'backend' }],
  publish: null,
  win: { executableName: 'Renulus Development', icon: 'public/renulus.ico', target: ['nsis'] },
  nsis: { oneClick: false, perMachine: false, allowToChangeInstallationDirectory: true, deleteAppDataOnUninstall: false },
};
