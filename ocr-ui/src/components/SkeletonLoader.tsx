'use client';

export function SkeletonField() {
  return (
    <div className="flex items-start justify-between gap-4 px-4 py-3 rounded-xl border border-white/5 bg-white/3 animate-pulse">
      <div className="flex flex-col gap-2 flex-1">
        <div className="h-2.5 w-20 rounded-full bg-white/10" />
        <div className="h-3.5 w-40 rounded-full bg-white/8" />
      </div>
      <div className="w-3.5 h-3.5 rounded-full bg-white/10 mt-1 flex-shrink-0" />
    </div>
  );
}

export function SkeletonPanel() {
  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Header skeleton */}
      <div className="flex items-center justify-between animate-pulse">
        <div className="flex flex-col gap-1.5">
          <div className="h-4 w-32 rounded-full bg-white/10" />
          <div className="h-2.5 w-48 rounded-full bg-white/6" />
        </div>
        <div className="h-6 w-16 rounded-full bg-white/8" />
      </div>
      <div className="h-2 w-56 rounded-full bg-white/5 animate-pulse" />
      {/* Field skeletons */}
      <div className="flex flex-col gap-2">
        {Array.from({ length: 7 }).map((_, i) => (
          <SkeletonField key={i} />
        ))}
      </div>
    </div>
  );
}

export function SkeletonImage() {
  return (
    <div className="w-full h-full min-h-[300px] rounded-xl bg-white/5 border border-white/8 animate-pulse flex items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-white/20">
        <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <span className="text-xs animate-pulse">Processing…</span>
      </div>
    </div>
  );
}
