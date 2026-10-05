/** Original Renulus test image: white 16×16 PNG with a teal 8×8 square, MIT.
 * 100 bytes; SHA-256 004300443c19b2ac42179cb4a9859445ea610cbfa5d52512e9aa5edf0bbef76d.
 * This constant never reads an upload, a case, the clipboard or a local file.
 */
export const IMAGE_CHECK_PNG = 'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAK0lEQVR42mP8//8/AymAiYFEQHsNLMgcxspGrIr+t9cPZj8MBw2MwyAtAQAnCgkb/OW0XAAAAABJRU5ErkJggg==';

export function imageCapabilityRequest(runId: string, model: string) {
  return {
    run_id: runId, model, purpose: 'capability-image-check',
    scope: { kind: 'temporary-case' },
    system: 'Check image input acceptance only. Reply with one short word. This is an original synthetic connection test, not clinical material.',
    messages: [{ role: 'user', content: [
      { type: 'text', text: 'This is the Renulus connection test image. Reply accepted.' },
      { type: 'image', media_type: 'image/png', data: IMAGE_CHECK_PNG, detail: 'low' },
    ] }],
  };
}
