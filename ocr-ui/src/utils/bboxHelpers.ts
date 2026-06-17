/**
 * Converts normalized bbox coords [0, 1000] → pixel coordinates
 * relative to the rendered image dimensions.
 */
export function bboxToPixels(
  bbox: [number, number, number, number],
  imageWidth: number,
  imageHeight: number
): { x: number; y: number; width: number; height: number } {
  const [xmin, ymin, xmax, ymax] = bbox;
  return {
    x: (xmin / 1000) * imageWidth,
    y: (ymin / 1000) * imageHeight,
    width: ((xmax - xmin) / 1000) * imageWidth,
    height: ((ymax - ymin) / 1000) * imageHeight,
  };
}

/**
 * Formats a snake_case field key into a human-readable label.
 * e.g. "date_of_birth" → "Date of Birth"
 */
export function formatFieldLabel(key: string): string {
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Checks if a bounding box is valid (non-null and has positive area).
 */
export function isValidBbox(
  bbox: [number, number, number, number] | null
): bbox is [number, number, number, number] {
  if (!bbox) return false;
  const [xmin, ymin, xmax, ymax] = bbox;
  return xmax > xmin && ymax > ymin;
}
