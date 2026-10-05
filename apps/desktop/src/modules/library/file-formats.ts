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

export function fileImportProblem(file: File, capabilities: Capabilities | null): string | undefined {
  if (file.size > 64 * 1024 * 1024) return 'This file exceeds 64 MiB. Choose a smaller document.';
  if (file.size === 0) return 'This file is empty. Choose a file with study material.';
  const extension = file.name.split('.').at(-1)?.toLowerCase() ?? '';
  if (!textExtensions.has(extension) && !imageExtensions.has(extension) && !officeExtensions.has(extension) && extension !== 'pdf') {
    return 'Choose a PDF, PNG, JPEG, TIFF, text, DOCX, PPTX or XLSX file.';
  }
  if (!capabilities) return 'Check document processing availability before importing this file.';
  if (!canImportFile(file.name, capabilities)) return 'Processing this file format is unavailable. Check Connections, then refresh processing availability.';
  return undefined;
}

/** HTTP headers accept byte strings. JSON escapes preserve non-Latin source metadata. */
export function importOptionsHeader(options: unknown): string {
  return JSON.stringify(options).replace(/[\u007f-\uffff]/g, character => '\\u' + character.charCodeAt(0).toString(16).padStart(4, '0'));
}

export function officeOriginalExtension(mediaType: string): string | null {
  return officeMedia[mediaType.split(';')[0].trim().toLowerCase()] ?? null;
}
