export type DownloadFormat = "png" | "jpeg" | "pdf";

export function downloadImageDataUrl(dataUrl: string, filename: string) {
  const link = document.createElement("a");
  link.href = dataUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export function downloadPdfFromJpegDataUrl(dataUrl: string, filename: string, pageWidth: number, pageHeight: number) {
  const imageBinary = dataUrlToBinary(dataUrl);
  const pagePtWidth = 405;
  const pagePtHeight = Math.round(pagePtWidth * (pageHeight / Math.max(1, pageWidth)));
  const content = `q\n${pagePtWidth} 0 0 ${pagePtHeight} 0 0 cm\n/Im0 Do\nQ`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pagePtWidth} ${pagePtHeight}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`,
    `<< /Type /XObject /Subtype /Image /Width ${pageWidth} /Height ${pageHeight} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${imageBinary.length} >>\nstream\n${imageBinary}\nendstream`,
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
  ];
  const pdfBinary = buildPdf(objects);
  const bytes = new Uint8Array(pdfBinary.length);
  for (let index = 0; index < pdfBinary.length; index += 1) {
    bytes[index] = pdfBinary.charCodeAt(index) & 0xff;
  }
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  downloadImageDataUrl(url, filename);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function dataUrlToBinary(dataUrl: string) {
  const base64 = dataUrl.split(",", 2)[1] ?? "";
  return window.atob(base64);
}

function buildPdf(objects: string[]) {
  let result = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(result.length);
    result += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xrefOffset = result.length;
  result += `xref\n0 ${objects.length + 1}\n`;
  result += "0000000000 65535 f \n";
  offsets.slice(1).forEach((offset) => {
    result += `${String(offset).padStart(10, "0")} 00000 n \n`;
  });
  result += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;
  return result;
}
