'use client';

import { useRef, useEffect, useState } from 'react';
import { BBoxField } from '@/types/ocr';
import { bboxToPixels, isValidBbox, formatFieldLabel } from '@/utils/bboxHelpers';

interface ImageCanvasProps {
  imageUrl: string;
  fields: Record<string, BBoxField>;
  activeFieldKey: string | null;
  loading?: boolean;
}

export default function ImageCanvas({ imageUrl, fields, activeFieldKey, loading = false }: ImageCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [imgSize, setImgSize] = useState({ width: 0, height: 0, offsetX: 0, offsetY: 0 });

  const updateSize = () => {
    const img = imgRef.current;
    const container = containerRef.current;
    if (!img || !container) return;
    // Get the rendered image size (object-contain may add letterboxing)
    const containerRect = container.getBoundingClientRect();
    const naturalRatio = img.naturalWidth / img.naturalHeight;
    const containerRatio = containerRect.width / containerRect.height;
    let renderedW: number, renderedH: number;
    if (naturalRatio > containerRatio) {
      renderedW = containerRect.width;
      renderedH = containerRect.width / naturalRatio;
    } else {
      renderedH = containerRect.height;
      renderedW = containerRect.height * naturalRatio;
    }
    const offsetX = (containerRect.width - renderedW) / 2;
    const offsetY = (containerRect.height - renderedH) / 2;
    setImgSize({ width: renderedW, height: renderedH, offsetX, offsetY });
  };

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;
    if (img.complete && img.naturalWidth) updateSize();
    img.addEventListener('load', updateSize);
    const ro = new ResizeObserver(updateSize);
    if (containerRef.current) ro.observe(containerRef.current);
    return () => {
      img.removeEventListener('load', updateSize);
      ro.disconnect();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageUrl]);

  const entries = Object.entries(fields);
  const activeBbox = activeFieldKey ? fields[activeFieldKey]?.bounding_box : null;

  return (
    <div ref={containerRef} className="relative w-full h-full rounded-xl overflow-hidden bg-black/40 min-h-[300px]">
      {/* Image */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        ref={imgRef}
        src={imageUrl}
        alt="Uploaded document"
        className="w-full h-full object-contain"
        onLoad={updateSize}
      />

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-20 rounded-xl">
          <div className="flex flex-col items-center gap-3">
            <svg className="w-8 h-8 text-indigo-400 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            <span className="text-xs text-white/60 font-medium">Analyzing document…</span>
          </div>
        </div>
      )}

      {/* SVG overlay */}
      {imgSize.width > 0 && !loading && (
        <svg
          className="absolute pointer-events-none"
          style={{ left: imgSize.offsetX, top: imgSize.offsetY, width: imgSize.width, height: imgSize.height }}
          viewBox={`0 0 ${imgSize.width} ${imgSize.height}`}
        >
          {/* All bboxes — subtle */}
          {entries.map(([key, field]) => {
            if (!isValidBbox(field.bounding_box)) return null;
            const { x, y, width, height } = bboxToPixels(field.bounding_box, imgSize.width, imgSize.height);
            const isActive = key === activeFieldKey;
            return (
              <g key={key}>
                <rect
                  x={x} y={y} width={width} height={height}
                  fill={isActive ? 'rgba(251,191,36,0.12)' : 'transparent'}
                  stroke={isActive ? '#fbbf24' : 'rgba(99,102,241,0.45)'}
                  strokeWidth={isActive ? 2 : 1}
                  rx={3}
                />
                {/* Label tooltip for active bbox */}
                {isActive && (
                  <>
                    <rect
                      x={x} y={Math.max(0, y - 22)}
                      width={Math.min(formatFieldLabel(key).length * 7 + 12, imgSize.width - x)}
                      height={18}
                      rx={4}
                      fill="#fbbf24"
                    />
                    <text
                      x={x + 6}
                      y={Math.max(0, y - 22) + 12}
                      fontSize="10"
                      fontWeight="600"
                      fill="#1c1917"
                      fontFamily="system-ui, sans-serif"
                    >
                      {formatFieldLabel(key)}
                    </text>
                  </>
                )}
              </g>
            );
          })}

          {/* Animated marching ants for active bbox */}
          {activeBbox && isValidBbox(activeBbox) && (() => {
            const { x, y, width, height } = bboxToPixels(activeBbox, imgSize.width, imgSize.height);
            return (
              <rect
                x={x - 3} y={y - 3} width={width + 6} height={height + 6}
                fill="none" stroke="#fbbf24" strokeWidth={1.5}
                strokeDasharray="6 3" rx={5} opacity={0.6}
              >
                <animate attributeName="stroke-dashoffset" from="0" to="18" dur="0.7s" repeatCount="indefinite" />
              </rect>
            );
          })()}
        </svg>
      )}
    </div>
  );
}
