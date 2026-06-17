'use client';

import { useState, useCallback, useEffect } from 'react';
import ImageUploader from '@/components/ImageUploader';
import DocumentTypeSelector from '@/components/DocumentTypeSelector';
import ImageCanvas from '@/components/ImageCanvas';
import ExtractedFieldsPanel from '@/components/ExtractedFieldsPanel';
import SplitView from '@/components/SplitView';
import dynamic from 'next/dynamic';

const PdfPreview = dynamic(() => import('@/components/PdfPreview'), { ssr: false });
import { SkeletonPanel, SkeletonImage } from '@/components/SkeletonLoader';
import { useOCRExtraction } from '@/hooks/useOCRExtraction';
import { useBboxHighlight } from '@/hooks/useBboxHighlight';
import { DocumentType, BBoxField } from '@/types/ocr';

// ─── Download helper ────────────────────────────────────────────────────────
function downloadJSON(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Main Page ──────────────────────────────────────────────────────────────
export default function ExtractPage() {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isPdf, setIsPdf] = useState(false);
  const [docType, setDocType] = useState<DocumentType>('others');

  const { loading, error, result, extract, reset } = useOCRExtraction();
  const { activeFieldKey, setActiveFieldKey, clearHighlight } = useBboxHighlight();

  // Revoke object URL whenever previewUrl changes to avoid memory leaks
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleFileSelected = useCallback((file: File, url: string, pdf: boolean) => {
    setUploadedFile(file);
    setPreviewUrl(url);
    setIsPdf(pdf);
    reset();
    clearHighlight();
  }, [reset, clearHighlight]);

  const handleExtract = async () => {
    if (!uploadedFile) return;
    clearHighlight();
    await extract(uploadedFile, docType);
  };

  const handleClear = useCallback(() => {
    setUploadedFile(null);
    setPreviewUrl(null);
    setIsPdf(false);
    reset();
    clearHighlight();
  }, [reset, clearHighlight]);

  const handleDownload = useCallback(() => {
    if (!result) return;
    const safeName = uploadedFile?.name.replace(/\.[^.]+$/, '') ?? 'extraction';
    downloadJSON(result, `${safeName}_${docType}.json`);
  }, [result, uploadedFile, docType]);

  const hasResult = result?.success && result.data;
  const fields = (result?.data ?? {}) as Record<string, BBoxField>;
  const showSplitView = (hasResult || loading) && uploadedFile;

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950 text-white">
      {/* Ambient glows */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden>
        <div className="absolute -top-60 -left-60 w-[500px] h-[500px] bg-indigo-600/15 rounded-full blur-3xl" />
        <div className="absolute -bottom-60 -right-40 w-[400px] h-[400px] bg-violet-600/12 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-indigo-900/10 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-4 py-10 sm:px-6 lg:px-8 flex flex-col gap-8">

        {/* ── Hero Header ── */}
        <div className="text-center">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold tracking-wide mb-5">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
            Powered by VLM + PaddleOCR
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight bg-gradient-to-br from-white via-indigo-100 to-violet-300 bg-clip-text text-transparent leading-tight pb-1">
            Document Extractor
          </h1>
          <p className="mt-3 text-base text-white/45 max-w-lg mx-auto leading-relaxed">
            Upload a Vietnamese ID card, invoice, or any document to extract structured data with interactive bounding box visualization.
          </p>
        </div>

        {/* ── Upload Panel (hidden while showing results) ── */}
        {!showSplitView && (
          <div className="max-w-lg mx-auto w-full bg-white/[0.04] backdrop-blur-md border border-white/10 rounded-2xl p-6 shadow-2xl shadow-black/40 flex flex-col gap-5
            animate-in fade-in slide-in-from-bottom-4 duration-300">

            <ImageUploader onFileSelected={handleFileSelected} disabled={loading} />

            <DocumentTypeSelector value={docType} onChange={setDocType} disabled={loading} />

            {/* Extract button */}
            <button
              id="extract-btn"
              onClick={handleExtract}
              disabled={!uploadedFile || loading}
              className={`
                w-full py-3.5 rounded-xl font-bold text-sm tracking-wide
                transition-all duration-200 flex items-center justify-center gap-2.5
                ${uploadedFile && !loading
                  ? 'bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:scale-[1.01] active:scale-[0.99]'
                  : 'bg-white/8 text-white/25 cursor-not-allowed'
                }
              `}
            >
              {loading ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                  Extracting…
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  Extract Data
                </>
              )}
            </button>

            {/* API Error */}
            {error && (
              <div className="flex items-start gap-3 p-3.5 rounded-xl bg-red-500/8 border border-red-500/20 text-sm text-red-300 animate-in fade-in duration-200">
                <svg className="w-4 h-4 mt-0.5 flex-shrink-0 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                <div className="flex-1">
                  <p className="font-semibold text-red-300 mb-0.5">Extraction failed</p>
                  <p className="text-red-400/80 text-xs leading-relaxed">{error}</p>
                </div>
                <button
                  id="retry-btn"
                  onClick={handleExtract}
                  className="flex-shrink-0 text-xs font-semibold text-red-300 hover:text-white border border-red-500/30 hover:border-red-400/50 px-2.5 py-1 rounded-lg transition-all"
                >
                  Retry
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Split View Results ── */}
        {showSplitView && (
          <div className="bg-white/[0.04] backdrop-blur-md border border-white/10 rounded-2xl p-5 shadow-2xl shadow-black/40 animate-in fade-in slide-in-from-bottom-3 duration-300">

            {/* Result bar */}
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                {/* Doc type pill */}
                <span className="text-xs font-semibold text-white/50 uppercase tracking-widest">
                  {docType === 'id_card' ? '🪪 ID Card' : docType === 'invoice' ? '🧾 Invoice' : '📄 General'}
                </span>
                {uploadedFile && (
                  <span className="text-xs text-white/25 truncate max-w-[160px]">{uploadedFile.name}</span>
                )}
              </div>
              <button
                id="clear-results-btn"
                onClick={handleClear}
                className="flex items-center gap-1.5 text-xs text-white/35 hover:text-red-400 transition-colors px-3 py-1.5 rounded-lg hover:bg-red-500/8 border border-transparent hover:border-red-500/15"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                Clear & retry
              </button>
            </div>

            <SplitView
              left={
                <div className="flex flex-col gap-2 h-full">
                  <p className="text-[10px] font-bold text-white/30 uppercase tracking-widest">Document</p>
                  <div className="flex-1 relative min-h-[300px]">
                    {loading ? (
                      <SkeletonImage />
                    ) : isPdf && previewUrl ? (
                      <PdfPreview url={previewUrl} filename={uploadedFile?.name ?? 'document.pdf'} />
                    ) : previewUrl ? (
                      <ImageCanvas
                        imageUrl={previewUrl}
                        fields={fields}
                        activeFieldKey={activeFieldKey}
                        loading={false}
                      />
                    ) : null}
                  </div>
                </div>
              }
              right={
                <div className="h-full bg-white/[0.03] rounded-xl border border-white/8 p-4 min-h-[300px]">
                  {loading ? (
                    <SkeletonPanel />
                  ) : hasResult ? (
                    <ExtractedFieldsPanel
                      result={result!}
                      activeFieldKey={activeFieldKey}
                      onFieldHover={setActiveFieldKey}
                      processingTime={result?.metadata?.processing_time_ms}
                      cacheHit={result?.metadata?.cache_hit}
                      onDownload={handleDownload}
                    />
                  ) : error ? (
                    <div className="flex flex-col items-center justify-center h-full gap-4 py-8">
                      <div className="w-12 h-12 rounded-full bg-red-500/15 flex items-center justify-center">
                        <svg className="w-6 h-6 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-semibold text-red-300 mb-1">Extraction Failed</p>
                        <p className="text-xs text-red-400/70 max-w-[220px]">{error}</p>
                      </div>
                      <button
                        onClick={handleExtract}
                        className="text-xs font-semibold text-white bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 px-4 py-2 rounded-xl transition-all"
                      >
                        Retry Extraction
                      </button>
                    </div>
                  ) : null}
                </div>
              }
            />
          </div>
        )}

        {/* ── Footer ── */}
        <p className="text-center text-[11px] text-white/15 pb-2">
          OCR API · FastAPI + PaddleOCR + VLM · Vietnamese document extraction
        </p>
      </div>
    </main>
  );
}
