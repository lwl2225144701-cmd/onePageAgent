type Size = {
  width: number;
  height: number;
};

type Position = {
  x: number;
  y: number;
};

type TransformInput = Position & {
  width: number;
  height: number;
  rotation?: number;
};

type BoundsOptions = {
  safeInset?: number | "auto";
  maxWidth?: number;
  maxHeight?: number;
};

export function getPageSafeInset(page: Size) {
  return clamp(page.width * 0.072, page.width * 0.045, page.width * 0.095);
}

export function clampPositionToPage(position: Position, box: Size, page: Size, options: BoundsOptions = {}): Position {
  const safeInset = options.safeInset === "auto" ? getPageSafeInset(page) : options.safeInset ?? 0;
  const minX = Math.min(safeInset, Math.max(0, page.width - box.width) / 2);
  const minY = Math.min(safeInset, Math.max(0, page.height - box.height) / 2);
  const maxX = Math.max(minX, page.width - box.width - minX);
  const maxY = Math.max(minY, page.height - box.height - minY);

  return {
    x: clamp(position.x, minX, maxX),
    y: clamp(position.y, minY, maxY),
  };
}

export function clampTransformToPage(input: TransformInput, page: Size, minimum: Partial<Size> = {}, options: BoundsOptions = {}): TransformInput {
  const safeInset = options.safeInset === "auto" ? getPageSafeInset(page) : options.safeInset ?? 0;
  const maxWidth = options.maxWidth ?? Math.max(minimum.width ?? 1, page.width - safeInset * 2);
  const maxHeight = options.maxHeight ?? Math.max(minimum.height ?? 1, page.height - safeInset * 2);
  const width = clamp(input.width, minimum.width ?? 1, maxWidth);
  const height = clamp(input.height, minimum.height ?? 1, maxHeight);
  const position = clampPositionToPage({ x: input.x, y: input.y }, { width, height }, page, { safeInset });

  return {
    ...input,
    x: position.x,
    y: position.y,
    width,
    height,
  };
}

export function estimateTextHeight(content: string, width: number, fontSize: number, lineHeight = 1.45) {
  const safeWidth = Math.max(width, 120);
  const charsPerLine = Math.max(1, Math.floor(safeWidth / Math.max(fontSize * 0.9, 1)));
  const explicitLines = content.split("\n");
  const lineCount = explicitLines.reduce((total, line) => total + Math.max(1, Math.ceil(line.length / charsPerLine)), 0);
  return Math.max(fontSize * lineHeight, lineCount * fontSize * lineHeight);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}
