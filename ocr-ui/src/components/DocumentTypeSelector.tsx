'use client';

import { DocumentType } from '@/types/ocr';

const DOC_TYPE_OPTIONS: { value: DocumentType; label: string; icon: string; description: string }[] = [
  { value: 'id_card', label: 'ID Card', icon: '🪪', description: 'Vietnamese ID / CCCD' },
  { value: 'invoice', label: 'Invoice', icon: '🧾', description: 'VAT invoices & receipts' },
  { value: 'others', label: 'General Document', icon: '📄', description: 'Any other document' },
];

interface DocumentTypeSelectorProps {
  value: DocumentType;
  onChange: (value: DocumentType) => void;
  disabled?: boolean;
}

export default function DocumentTypeSelector({ value, onChange, disabled = false }: DocumentTypeSelectorProps) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-semibold uppercase tracking-widest text-white/40">
        Document Type
      </label>
      <div className="grid grid-cols-3 gap-2">
        {DOC_TYPE_OPTIONS.map((opt) => {
          const isActive = value === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => !disabled && onChange(opt.value)}
              disabled={disabled}
              className={`
                flex flex-col items-center gap-1.5 px-3 py-3 rounded-xl border text-center
                transition-all duration-200 text-sm font-medium
                ${isActive
                  ? 'border-indigo-500 bg-indigo-500/20 text-white shadow-lg shadow-indigo-500/10'
                  : 'border-white/10 bg-white/5 text-white/60 hover:border-white/30 hover:bg-white/10 hover:text-white'
                }
                ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
              `}
            >
              <span className="text-xl">{opt.icon}</span>
              <span className="leading-tight">{opt.label}</span>
              <span className="text-[10px] text-white/40 leading-tight">{opt.description}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
