export type DocumentType = 'id_card' | 'invoice' | 'others';

export interface BBoxField {
  value: string | number | null;
  bounding_box: [number, number, number, number] | null; // [xmin, ymin, xmax, ymax] in [0, 1000]
}

export interface OCRResponse {
  success: boolean;
  data: Record<string, BBoxField> | null;
  error?: string;
  metadata?: {
    cache_hit?: boolean;
    processing_time_ms?: number;
    model_version?: string;
  };
}

export interface ExtractedField {
  key: string;
  label: string;
  field: BBoxField;
}
