// MIT OpenCode; retained provenance in PROVENANCE.json.
import { Browser } from "@opencode/plugin-browser/rpc";
import { mkdir, readFile, stat, writeFile, rm } from "node:fs/promises";
import { mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
function createBrowserFiles(source) {
  const directory = path.join(tmpdir(), `opencode-browser-client-${crypto.randomUUID()}`);
  const files = /* @__PURE__ */ new Map();
  const ready = mkdir(directory, { recursive: true, mode: 448 });
  return {
    directory,
    ready,
    list: () => Array.from(files.values()).map(({ path: _path, resources: _resources, ...file }) => file),
    add(name, mime, resources = source()) {
      const id = Browser.FileID.make(`file_${crypto.randomUUID()}`);
      const target = path.join(directory, id);
      mkdirSync(target, { recursive: true, mode: 448 });
      const file = {
        id,
        name: name.slice(0, 2048),
        mime,
        bytes: 0,
        state: "pending",
        // A page receives this basename as the uploaded File.name, so spaces and non-ASCII stay;
        // only characters no supported filesystem accepts are replaced. Each file has its own
        // directory, so names never collide.
        path: path.join(
          target,
          name.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_").replace(/[. ]+$/, "").slice(-120) || "file"
        ),
        resources: [...new Set(resources)].sort()
      };
      files.set(id, file);
      return file;
    },
    async save(name, mime, data, resources = source()) {
      if (data.byteLength > Browser.MAX_FILE_BYTES)
        throw new Error(
          "Capture exceeds the 5 MiB transfer limit. Reduce screenshot maxWidth/quality or trace duration; for a heap snapshot, use a smaller page/test case. Do not retry an identical capture."
        );
      await ready;
      const file = this.add(name, mime, resources);
      await writeFile(file.path, data, { mode: 384 }).catch((error) => {
        file.state = "failed";
        throw new Error(
          "Cannot write the capture on the desktop. Ask the user to check desktop temporary-directory access and free space before retrying.",
          { cause: error }
        );
      });
      file.bytes = data.byteLength;
      file.state = "completed";
      return file.id;
    },
    get(id) {
      const file = files.get(id);
      if (!file)
        throw new Error(
          "File ID is not retained in this tab. Call browser.files.list({tabID}) and use an exact returned fileID from the same tab, not a server path or request ID."
        );
      if (file.state === "pending")
        throw new Error(
          "File is still being downloaded or captured. Check browser.files.list({tabID}) again and wait for state completed; do not start a duplicate download."
        );
      if (file.state === "failed")
        throw new Error(
          "The download or capture failed, so this file cannot be read. Inspect browser.console and browser.network.list for the cause before deciding to start it again."
        );
      return file;
    },
    async transfer(id, authorized) {
      const file = this.get(id);
      if (authorized && file.resources.some((url) => !authorized.includes(url)))
        throw new Error(
          "Capture source changed before export. Inspect the tab and request the file again to check its source permissions; no bytes were exported."
        );
      if ((await stat(file.path).catch((error) => {
        throw unavailableFile(error);
      })).size > Browser.MAX_FILE_BYTES)
        throw new Error(
          "File exceeds the 5 MiB transfer limit. Choose a smaller completed file; repeating browser.files.get for this file will not help."
        );
      const data = await readFile(file.path).catch((error) => {
        throw unavailableFile(error);
      });
      return { id, name: file.name, mime: file.mime, data: new Uint8Array(data) };
    },
    dispose: () => ready.then(() => rm(directory, { recursive: true, force: true }))
  };
}
function unavailableFile(error) {
  return new Error(
    "The retained file cannot be read on the desktop. Its temporary copy may have been removed. Use an already exported server-local path if available, or deliberately create a new capture.",
    { cause: error }
  );
}
export {
  createBrowserFiles
};
