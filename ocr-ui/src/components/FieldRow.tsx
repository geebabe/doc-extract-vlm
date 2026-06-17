'use client';

import { BBoxField } from '@/types/ocr';
import { formatFieldLabel, isValidBbox } from '@/utils/bboxHelpers';

interface FieldRowProps {
  fieldKey: string;
  field: BBoxField;
  isActive: boolean;
  onMouseEnter: (key: string) => void;
  onMouseLeave: () => void;
}

export default function FieldRow({ fieldKey, field, isActive, onMouseEnter, onMouseLeave }: FieldRowProps) {
  const hasBbox = isValidBbox(field.bounding_box);
  const displayValue = field.value !== null && field.value !== undefined && field.value !== ''
    ? String(field.value)
    : '—';

  return (
    <div
      onMouseEnter={() => hasBbox && onMouseEnter(fieldKey)}
      onMouseLeave={onMouseLeave}
      className={`
        group flex items-start justify-between gap-4 px-4 py-3 rounded-xl border
        transition-all duration-150 cursor-default
        ${isActive
          ? 'bg-amber-500/10 border-amber-500/40 shadow-md shadow-amber-500/5'
          : hasBbox
            ? 'bg-white/5 border-white/10 hover:bg-white/8 hover:border-indigo-500/30'
            : 'bg-white/3 border-white/5 opacity-60'
        }
      `}
    >
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className={`text-xs font-semibold uppercase tracking-wider transition-colors duration-150 ${isActive ? 'text-amber-400' : 'text-white/40'}`}>
          {formatFieldLabel(fieldKey)}
        </span>
        <span className={`text-sm font-medium break-words transition-colors duration-150 ${isActive ? 'text-white' : 'text-white/80'}`}>
          {displayValue}
        </span>
      </div>

      <div className="flex-shrink-0 flex items-center gap-1.5 pt-0.5">
        {isActive && (
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
        )}
        {!hasBbox && (
          <span className="text-[10px] text-white/25 italic">no bbox</span>
        )}
        {hasBbox && !isActive && (
          <svg className="w-3.5 h-3.5 text-indigo-400/40 group-hover:text-indigo-400/70 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z" />
          </svg>
        )}
      </div>
    </div>
  );
}
