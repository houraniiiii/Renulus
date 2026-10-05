import type { Capabilities } from './types';

const textExtensions = new Set(['txt', 'md']);
const imageExtensions = new Set(['png', 'jpg', 'jpeg', 'tif', 'tiff']);
const officeExtensions = new Set(['docx', 'pptx', 'xlsx']);
const officeMedia: Record<string, string> = {
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
};

export function canImportFile(filename: string, capabilities: Capabilities | null): boolean {
  const extension = filename.split('.').at(-1)?.toLowerCase() ?? '';
  if (textExtensions.has(extension)) return capabilities?.text_import === true;
  if (officeExtensions.has(extension)) return capabilities?.office_import === true;
  if (extension === 'pdf' || imageExtensions.has(extension)) return capabilities?.pdf_image_import === true;
  return false;
}

export function officeOriginalExtension(mediaType: string): string | null {
  return officeMedia[mediaType.split(';')[0].trim().toLowerCase()] ?? null;
}
