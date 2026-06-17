import { DocumentType, OCRResponse } from '@/types/ocr';

const API_BASE_URL = process.env.NEXT_PUBLIC_OCR_API_URL ?? 'http://localhost:8000';

const ENDPOINT_MAP: Record<DocumentType, string> = {
  id_card: '/extract/id_card/file',
  invoice: '/extract/invoice/file',
  others: '/extract/others/file',
};

export async function extractOCR(
  file: File,
  docType: DocumentType
): Promise<OCRResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const endpoint = ENDPOINT_MAP[docType];
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => response.statusText);
    throw new Error(`API error ${response.status}: ${errorText}`);
  }

  const json = await response.json();
  return json as OCRResponse;
}
