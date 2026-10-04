/** Capture Chromium's internal viewer, including open shadow-root controls. */
export async function capturePdfFrames(page) {
  const frames = [];
  for (const frame of page.frames().filter(frame => frame !== page.mainFrame())) {
    try {
      frames.push({ url: frame.url(), ...await frame.evaluate(() => {
        const inputs = [], embeds = [], viewers = [], text = [];
        function scan(root) {
          for (const element of root.querySelectorAll('*')) {
            if (element.tagName === 'INPUT') inputs.push({ id: element.id, type: element.type, value: element.value });
            if (element.tagName === 'EMBED') embeds.push({ type: element.type, src: element.src });
            if (element.tagName.toLowerCase() === 'pdf-viewer') viewers.push(element.tagName);
            if (element.shadowRoot) { text.push(element.shadowRoot.textContent.slice(0, 1500)); scan(element.shadowRoot); }
          }
        }
        scan(document);
        return { readyState: document.readyState, body: document.body?.innerText.slice(0, 700), shadowText: text.join(' ').slice(0, 3000), embeds, viewers, inputs };
      }) });
    } catch (error) { frames.push({ url: frame.url(), error: error.message }); }
  }
  return frames;
}

export function classifyPdfFrames(frames, page = 2) {
  const errorFrames = frames.filter(frame => /^(chrome-error:|chromewebdata:)/i.test(frame.url) || /chromewebdata|ERR_BLOCKED|blocked|refused/i.test(frame.body ?? ''));
  const viewerDetected = frames.some(frame => frame.viewers?.length || frame.embeds?.some(embed => /application/(pdf|x-google-chrome-pdf)/i.test(embed.type)));
  const citationPageSelected = frames.some(frame => frame.inputs?.some(input => /page/i.test(input.id) && input.value === String(page)));
  return { blocked: errorFrames.length > 0, errorFrameUrls: errorFrames.map(frame => frame.url), viewerDetected, citationPageSelected };
}
