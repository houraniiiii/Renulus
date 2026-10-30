// MIT OpenCode; retained provenance in PROVENANCE.json.
function destinationOrigin(input) {
  if (!URL.canParse(input)) return;
  const url = new URL(input);
  return /^https?:$/.test(url.protocol) && !url.username && !url.password ? url.origin : void 0;
}
function localFileURL(input) {
  if (!URL.canParse(input)) return;
  const url = new URL(input);
  return url.protocol === "file:" && !url.hostname ? url.href : void 0;
}
function canonicalPath(input) {
  const value = decodeURIComponent(input).replaceAll("\\", "/").replace(/^\/([A-Za-z]:\/)/, "$1");
  return process.platform === "win32" ? value.toLowerCase() : value;
}
function fileURLWithin(input, roots) {
  const href = localFileURL(input);
  if (!href || roots.length === 0) return false;
  const path = canonicalPath(new URL(href).pathname);
  return roots.some((root) => {
    const prefix = canonicalPath(root).replace(/\/+$/, "");
    return path === prefix || path.startsWith(`${prefix}/`);
  });
}
function allowedDestination(input, policy) {
  return !!destinationOrigin(input) || fileURLWithin(input, policy?.fileRoots ?? []);
}
function normalizeURL(input, policy) {
  const url = withScheme(input);
  const reason = refusal(url, policy);
  if (reason === "browser.address.credentials")
    throw new Error("URLs with a user name or password are not supported. Remove them from the URL.");
  if (reason)
    throw new Error(
      policy?.fileRoots?.length ? "Only HTTP, HTTPS, about:blank, and file URLs inside the workspace are supported." : "Only HTTP, HTTPS, and about:blank URLs are supported."
    );
  return url;
}
function refusal(input, policy) {
  const url = withScheme(input);
  if (url === "about:blank" || allowedDestination(url, policy)) return;
  if (URL.canParse(url) && /^https?:$/.test(new URL(url).protocol)) return "browser.address.credentials";
  return policy?.fileRoots?.length ? "browser.address.workspace" : "browser.address.web";
}
function withScheme(input) {
  const value = input.trim();
  if (!value || /^about:blank$/i.test(value)) return "about:blank";
  if (/^[a-z][a-z\d+.-]*:\/\//i.test(value)) return value;
  const local = /^(?:(?:[a-z\d-]+\.)*localhost|127(?:\.\d{1,3}){3}|\[::1\])(?::\d+)?(?:[/?#]|$)/i.test(value);
  return `${local ? "http" : "https"}://${value}`;
}
export {
  allowedDestination,
  destinationOrigin,
  fileURLWithin,
  localFileURL,
  normalizeURL,
  refusal
};
