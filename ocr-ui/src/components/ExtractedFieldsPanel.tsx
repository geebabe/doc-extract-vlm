'use client';

import { BBoxField, OCRResponse } from '@/types/ocr';
import FieldRow from './FieldRow';

interface ExtractedFieldsPanelProps {
  result: OCRResponse;
  activeFieldKey: string | null;
  onFieldHover: (key: string | null) => void;
  processingTime?: number;
  cacheHit?: boolean;
  onDownload?: () => void;
}

export default function ExtractedFieldsPanel({
  result,
  activeFieldKey,
  onFieldHover,
  processingTime,
  cacheHit,
  onDownload,
}: ExtractedFieldsPanelProps) {
  const fields = result.data ?? {};
  const entries = Object.entries(fields) as [string, BBoxField][];
  const fieldsWithValue = entries.filter(([, f]) => f.value !== null && f.value !== '').length;
  const fieldsWithBbox = entries.filter(([, f]) => f.bounding_box !== null).length;

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-bold text-white tracking-tight">Extracted Fields</h2>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="text-[11px] text-white/40">
              {fieldsWithValue}/{entries.length} fields
            </span>
            <span className="text-white/15">·</span>
            <span className="text-[11px] text-indigo-400/70">
              {fieldsWithBbox} with bbox
            </span>
            {processingTime != null && (
              <>
                <span className="text-white/15">·</span>
                <span className="text-[11px] text-white/35">{processingTime}ms</span>
              </>
            )}
            {cacheHit && (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                cached
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Success badge */}
          {result.success && (
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-1 rounded-full">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
              Done
            </span>
          )}

          {/* Download JSON */}
          {onDownload && (
            <button
              id="download-json-btn"
              onClick={onDownload}
              title="Download as JSON"
              className="flex items-center gap-1.5 text-[11px] font-medium text-indigo-300 hover:text-white bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 hover:border-indigo-500/40 px-2.5 py-1 rounded-full transition-all duration-150"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              JSON
            </button>
          )}
        </div>
      </div>

      {/* Hover hint */}
      <p className="text-[10px] text-white/25 italic -mt-1">
        Hover a field to highlight its region on the image →
      </p>

      {/* Divider */}
      <div className="h-px bg-white/8" />

      {/* Fields list */}
      <div className="flex flex-col gap-1.5 overflow-y-auto flex-1 pr-0.5">
        {entries.length === 0 ? (
          <div className="text-sm text-white/30 text-center py-10">No fields returned by the API.</div>
        ) : (
          entries.map(([key, field]) => (
            <FieldRow
              key={key}
              fieldKey={key}
              field={field}
              isActive={activeFieldKey === key}
              onMouseEnter={onFieldHover}
              onMouseLeave={() => onFieldHover(null)}
            />
          ))
        )}
      </div>
    </div>
  );
}
