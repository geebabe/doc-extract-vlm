'use client';

import { ReactNode } from 'react';

interface SplitViewProps {
  left: ReactNode;
  right: ReactNode;
}

export default function SplitView({ left, right }: SplitViewProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 w-full min-h-[600px]">
      {/* Left: Image */}
      <div className="flex flex-col min-h-[340px] lg:min-h-[600px]">
        {left}
      </div>
      {/* Right: Fields panel */}
      <div className="flex flex-col min-h-[340px] lg:min-h-[600px] overflow-hidden">
        {right}
      </div>
    </div>
  );
}
