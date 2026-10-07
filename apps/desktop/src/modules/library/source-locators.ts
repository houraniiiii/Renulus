import type { Locator } from './types';

function ordinal(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}

export function sourceLocationLabel(locators: Locator[]): string {
  const pages = [...new Set(locators.map(value => value.page).filter(ordinal))];
  if (pages.length) return 'Page ' + pages.join(', ');
  const slides = [...new Set(locators.filter(value => value.format === 'pptx').map(value => value.slide).filter(ordinal))];
  if (slides.length) return 'Slide ' + slides.join(', ');
  const sheets = [...new Set(locators.filter(value => value.format === 'xlsx').flatMap(value =>
    value.sheet_name?.trim() ? [value.sheet_name.trim()] : ordinal(value.sheet) ? [String(value.sheet)] : []))];
  if (sheets.length) return 'Sheet ' + sheets.join(', ');
  if (locators.some(value => value.format === 'docx')) return locators.some(value => value.table_ref) ? 'Document table' : 'Document item';
  if (locators.some(value => value.char_span)) return 'Original text span';
  return 'Original document';
}
