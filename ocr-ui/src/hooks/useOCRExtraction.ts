'use client';

import { useState, useCallback } from 'react';
import { OCRResponse, DocumentType } from '@/types/ocr';
import { extractOCR } from '@/services/apiClient';

interface UseOCRExtractionReturn {
  loading: boolean;
  error: string | null;
  result: OCRResponse | null;
  extract: (file: File, docType: DocumentType) => Promise<void>;
  reset: () => void;
}

export function useOCRExtraction(): UseOCRExtractionReturn {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OCRResponse | null>(null);

  const extract = useCallback(async (file: File, docType: DocumentType) => {
    setLoading(true);
    setError(null);
    try {
      const res = await extractOCR(file, docType);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setLoading(false);
    setError(null);
    setResult(null);
  }, []);

  return { loading, error, result, extract, reset };
}
