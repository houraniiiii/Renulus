/** Two-page original test material. Never substitute an acquired document. */
export function syntheticPdf() {
  const stream = page => ['0.95 0.98 0.97 rg 0 0 380 480 re f', '0.1 0.4 0.35 rg BT /F1 24 Tf 38 425 Td (RENULUS - PAGE ' + page + ') Tj ET', 'BT /F1 15 Tf 38 390 Td (Synthetic PDF viewer fixture) Tj ET', 'BT /F1 120 Tf 150 180 Td (' + (page === 'ONE' ? '1' : '2') + ') Tj ET', 'BT /F1 13 Tf 38 45 Td (Not clinical or patient material) Tj ET'].join('\n') + '\n';
  const one = stream('ONE'), two = stream('TWO');
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>', '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 380 480] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>', '<< /Length ' + Buffer.byteLength(one) + ' >>\nstream\n' + one + 'endstream', '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 380 480] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>', '<< /Length ' + Buffer.byteLength(two) + ' >>\nstream\n' + two + 'endstream', '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'];
  let body = '%PDF-1.4\n'; const offsets = [0];
  for (let i = 0; i < objects.length; i++) { offsets.push(Buffer.byteLength(body)); body += (i + 1) + ' 0 obj\n' + objects[i] + '\nendobj\n'; }
  const xref = Buffer.byteLength(body);
  body += 'xref\n0 ' + offsets.length + '\n0000000000 65535 f \n' + offsets.slice(1).map(offset => String(offset).padStart(10, '0') + ' 00000 n \n').join('');
  return Buffer.from(body + 'trailer\n<< /Size ' + offsets.length + ' /Root 1 0 R >>\nstartxref\n' + xref + '\n%%EOF\n');
}
