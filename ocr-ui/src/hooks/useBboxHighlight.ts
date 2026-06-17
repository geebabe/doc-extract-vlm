'use client';

import { useState, useCallback } from 'react';

interface UseBboxHighlightReturn {
  activeFieldKey: string | null;
  setActiveFieldKey: (key: string | null) => void;
  clearHighlight: () => void;
}

export function useBboxHighlight(): UseBboxHighlightReturn {
  const [activeFieldKey, setActiveFieldKey] = useState<string | null>(null);

  const clearHighlight = useCallback(() => {
    setActiveFieldKey(null);
  }, []);

  return { activeFieldKey, setActiveFieldKey, clearHighlight };
}
