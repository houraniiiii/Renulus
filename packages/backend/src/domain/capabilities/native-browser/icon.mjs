// MIT OpenCode; retained provenance in PROVENANCE.json.
import { nativeImage } from "electron";
const MAX_ICON_URL = 24576;
function loadIcon(candidates, network) {
  return candidates.filter((url) => /^(?:https?:|data:image\/)/i.test(url)).slice(0, 3).reduce(
    (found, url) => found.then(async (icon) => {
      if (icon) return icon;
      const fetched = /^data:/i.test(url) ? inline(url) : await network?.icon(url).catch(() => void 0);
      return fetched ? encode(fetched) : void 0;
    }),
    Promise.resolve(void 0)
  );
}
function inline(url) {
  const match = /^data:(image\/[\w.+-]+)(;base64)?,(.*)$/is.exec(url);
  if (!match) return;
  const body = match[3] ?? "";
  return { mime: (match[1] ?? "").toLowerCase(), data: match[2] ? Buffer.from(body, "base64") : unescape(body) };
}
function unescape(text) {
  return Buffer.concat(
    text.split(/(%[\da-f]{2})/i).map((part) => /^%[\da-f]{2}$/i.test(part) ? Buffer.from([parseInt(part.slice(1), 16)]) : Buffer.from(part))
  );
}
function encode(fetched) {
  if (fetched.mime === "image/svg+xml") {
    if (!/<svg[\s>]/i.test(fetched.data.toString("utf8"))) return;
    const url2 = `data:image/svg+xml;base64,${fetched.data.toString("base64")}`;
    return url2.length <= MAX_ICON_URL ? url2 : void 0;
  }
  const image = nativeImage.createFromBuffer(fetched.data);
  if (image.isEmpty()) return;
  const size = image.getSize();
  const fitted = Math.max(size.width, size.height) <= 32 ? image : image.resize(size.width >= size.height ? { width: 32, quality: "best" } : { height: 32, quality: "best" });
  const url = fitted.toDataURL();
  return url.length <= MAX_ICON_URL ? url : void 0;
}
export {
  loadIcon
};
