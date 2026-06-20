"use client";

import { useEffect, useState } from "react";
import type Konva from "konva";
import { Group, Image as KonvaImage, Rect } from "react-konva";

import { clampPositionToPage, clampTransformToPage } from "@/modules/editor/layout-bounds";

type CanvasAssetNodeProps = {
  id: string;
  url?: string;
  pageWidth: number;
  pageHeight: number;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  opacity?: number;
  fit?: "contain" | "cover" | "fill" | "watermark";
  objectPosition?: string;
  visualBBox?: { x?: number; y?: number; w?: number; h?: number };
  cornerRadius?: number;
  mask?: string | null;
  role?: string;
  mimeType?: string;
  elementType?: string;
  materialId?: string;
  taskId?: string;
  selected: boolean;
  onSelect: () => void;
  onPositionChange: (x: number, y: number) => void;
  onTransformChange: (x: number, y: number, width: number, height: number, rotation: number) => void;
  registerNode?: (node: Konva.Node | null) => void;
};

export function CanvasAssetNode({
  id,
  url,
  pageWidth,
  pageHeight,
  x,
  y,
  width,
  height,
  rotation,
  opacity = 1,
  fit = "contain",
  objectPosition = "center",
  visualBBox,
  cornerRadius = 18,
  mask,
  role,
  mimeType,
  elementType = "image",
  materialId,
  taskId,
  selected,
  onSelect,
  onPositionChange,
  onTransformChange,
  registerNode,
}: CanvasAssetNodeProps) {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    setImage(null);
    setImageError(false);
    if (!url) {
      return;
    }
    let active = true;
    const next = new window.Image();
    next.crossOrigin = "anonymous";
    next.onload = () => {
      if (!active) return;
      setImage(next);
    };
    next.onerror = () => {
      if (!active) return;
      setImage(null);
      setImageError(true);
      if (process.env.NODE_ENV !== "production") {
        console.warn("MATERIAL_IMAGE_LOAD_FAILED", {
          material_id: materialId ?? id,
          element_type: elementType,
          url,
          task_id: taskId || undefined,
        });
      }
    };
    next.src = url;
    return () => {
      active = false;
      setImage(null);
    };
  }, [elementType, id, materialId, taskId, url]);

  const commonProps = {
    ref: registerNode,
    x,
    y,
    width,
    height,
    rotation,
    opacity,
    draggable: true,
    dragBoundFunc: (position: { x: number; y: number }) =>
      clampPositionToPage(position, { width, height }, { width: pageWidth, height: pageHeight }),
    onClick: onSelect,
    onDragEnd: (event: Konva.KonvaEventObject<DragEvent>) => {
      const next = clampPositionToPage(
        { x: event.target.x(), y: event.target.y() },
        { width, height },
        { width: pageWidth, height: pageHeight },
      );
      onPositionChange(next.x, next.y);
    },
    onTransformEnd: (event: Konva.KonvaEventObject<Event>) => {
      const node = event.target as Konva.Node;
      const scaleX = node.scaleX();
      const scaleY = node.scaleY();
      const nextWidth = Math.max(48, width * scaleX);
      const nextHeight = Math.max(48, height * scaleY);
      node.scaleX(1);
      node.scaleY(1);
      const next = clampTransformToPage(
        { x: node.x(), y: node.y(), width: nextWidth, height: nextHeight, rotation: node.rotation() },
        { width: pageWidth, height: pageHeight },
        { width: 48, height: 48 },
      );
      onTransformChange(next.x, next.y, next.width, next.height, next.rotation ?? 0);
    },
  } as const;

  if (!image || imageError) {
    return null;
  }

  const svgAsset = isSvgAsset(url, mimeType);
  const placement = calculateAssetPlacement({
    naturalWidth: image.naturalWidth,
    naturalHeight: image.naturalHeight,
    width,
    height,
    fit,
    objectPosition,
    visualBBox: svgAsset ? undefined : visualBBox,
  });

  const cropProps = svgAsset
    ? {}
    : {
        cropX: placement.cropX,
        cropY: placement.cropY,
        cropWidth: placement.cropWidth,
        cropHeight: placement.cropHeight,
      };

  const clipProps = mask === "circle"
    ? {
        clipFunc: (context: Konva.Context) => {
          context.beginPath();
          context.ellipse(width / 2, height / 2, width / 2, height / 2, 0, 0, Math.PI * 2);
          context.closePath();
        },
      }
    : { clipX: 0, clipY: 0, clipWidth: width, clipHeight: height };

  return (
    <Group
      key={id}
      {...commonProps}
      {...clipProps}
    >
      {selected ? (
        <Rect
          x={0}
          y={0}
          width={width}
          height={height}
          stroke="#c99a66"
          strokeWidth={8}
          cornerRadius={cornerRadius}
        />
      ) : null}
      <KonvaImage
        image={image}
        x={placement.x}
        y={placement.y}
        width={placement.width}
        height={placement.height}
        {...cropProps}
        cornerRadius={mask === "none" ? 0 : cornerRadius}
        name={role}
      />
    </Group>
  );
}

type PlacementInput = {
  naturalWidth: number;
  naturalHeight: number;
  width: number;
  height: number;
  fit: "contain" | "cover" | "fill" | "watermark";
  objectPosition: string;
  visualBBox?: { x?: number; y?: number; w?: number; h?: number };
};

export function calculateAssetPlacement(input: PlacementInput) {
  const sourceWidth = Math.max(1, input.naturalWidth);
  const sourceHeight = Math.max(1, input.naturalHeight);
  const bbox = normalizeVisualBBox(input.visualBBox);
  let cropX = bbox.x * sourceWidth;
  let cropY = bbox.y * sourceHeight;
  let cropWidth = bbox.w * sourceWidth;
  let cropHeight = bbox.h * sourceHeight;
  const boxRatio = input.width / Math.max(1, input.height);
  const sourceRatio = cropWidth / Math.max(1, cropHeight);

  if (input.fit === "cover") {
    if (sourceRatio > boxRatio) {
      const nextWidth = cropHeight * boxRatio;
      cropX += positionFactor(input.objectPosition, "x") * (cropWidth - nextWidth);
      cropWidth = nextWidth;
    } else {
      const nextHeight = cropWidth / boxRatio;
      cropY += positionFactor(input.objectPosition, "y") * (cropHeight - nextHeight);
      cropHeight = nextHeight;
    }
    return { x: 0, y: 0, width: input.width, height: input.height, cropX, cropY, cropWidth, cropHeight };
  }

  if (input.fit === "fill") {
    return { x: 0, y: 0, width: input.width, height: input.height, cropX, cropY, cropWidth, cropHeight };
  }

  const scale = Math.min(input.width / cropWidth, input.height / cropHeight);
  const drawWidth = cropWidth * scale;
  const drawHeight = cropHeight * scale;
  const x = positionFactor(input.objectPosition, "x") * (input.width - drawWidth);
  const y = positionFactor(input.objectPosition, "y") * (input.height - drawHeight);
  return { x, y, width: drawWidth, height: drawHeight, cropX, cropY, cropWidth, cropHeight };
}

function normalizeVisualBBox(value?: { x?: number; y?: number; w?: number; h?: number }) {
  const x = Number(value?.x ?? 0);
  const y = Number(value?.y ?? 0);
  const w = Number(value?.w ?? 1);
  const h = Number(value?.h ?? 1);
  if (![x, y, w, h].every(Number.isFinite) || x < 0 || y < 0 || w <= 0 || h <= 0 || x + w > 1.0001 || y + h > 1.0001) {
    return { x: 0, y: 0, w: 1, h: 1 };
  }
  return { x, y, w, h };
}

function positionFactor(value: string, axis: "x" | "y") {
  const normalized = String(value || "center").toLowerCase();
  if (axis === "x") {
    if (normalized.includes("left")) return 0;
    if (normalized.includes("right")) return 1;
  } else {
    if (normalized.includes("top")) return 0;
    if (normalized.includes("bottom")) return 1;
  }
  return 0.5;
}

function isSvgAsset(url?: string, mimeType?: string) {
  return String(mimeType || "").toLowerCase().includes("svg") || /\.svg(?:$|\?)/i.test(String(url || ""));
}
