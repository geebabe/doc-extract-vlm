'use client';

import { useRef, useState, useCallback } from 'react';

interface ImageUploaderProps {
  onFileSelected: (file: File, previewUrl: string, isPdf: boolean) => void;
  disabled?: boolean;
}

const MAX_SIZE_MB = 10;
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/bmp', 'application/pdf'];

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ImageUploader({ onFileSelected, disabled = false }: ImageUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleFile = useCallback((file: File) => {
    setError(null);

    if (!ALLOWED_TYPES.includes(file.type)) {
      setError('Unsupported format. Please upload JPEG, PNG, WEBP, GIF, BMP, or PDF.');
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File is too large. Maximum size is ${MAX_SIZE_MB} MB.`);
      return;
    }

    const isPdf = file.type === 'application/pdf';
    const previewUrl = URL.createObjectURL(file);
    setSelectedFile(file);
    onFileSelected(file, previewUrl, isPdf);
  }, [onFileSelected]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    // reset input so same file can be re-selected
    e.target.value = '';
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div className="flex flex-col gap-2">
      <div
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        role="button"
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => e.key === 'Enter' && !disabled && inputRef.current?.click()}
        aria-label="Upload document"
        className={`
          relative flex flex-col items-center justify-center gap-3 p-8 rounded-2xl border-2 border-dashed
          transition-all duration-200 select-none outline-none
          ${dragging
            ? 'border-indigo-400 bg-indigo-500/10 scale-[1.01] shadow-lg shadow-indigo-500/10'
            : 'border-white/20 bg-white/5 hover:border-indigo-400/60 hover:bg-white/8'
          }
          ${disabled ? 'opacity-50 cursor-not-allowed pointer-events-none' : 'cursor-pointer'}
        `}
      >
        <input
          ref={inputRef}
          id="file-upload-input"
          type="file"
          accept="image/*,application/pdf"
          className="hidden"
          onChange={handleInputChange}
          disabled={disabled}
        />

        {/* Icon */}
        <div className={`w-14 h-14 rounded-2xl flex items-center justify-center transition-colors duration-200 ${dragging ? 'bg-indigo-500/30' : 'bg-indigo-500/15'}`}>
          <svg className="w-7 h-7 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
        </div>

        <div className="text-center">
          <p className="text-sm font-semibold text-white/80">
            {dragging ? 'Drop it here!' : 'Drag & drop or click to upload'}
          </p>
          <p className="text-xs text-white/35 mt-1">JPEG · PNG · WEBP · PDF &nbsp;·&nbsp; Max {MAX_SIZE_MB} MB</p>
        </div>

        {/* Selected file info badge */}
        {selectedFile && !error && (
          <div className="flex items-center gap-2 bg-white/8 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white/60">
            <svg className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            <span className="truncate max-w-[180px]">{selectedFile.name}</span>
            <span className="text-white/30 flex-shrink-0">{formatSize(selectedFile.size)}</span>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/8 border border-red-500/15 px-3 py-2 rounded-xl">
          <svg className="w-3.5 h-3.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          {error}
        </div>
      )}
    </div>
  );
}
