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

  const naturalRatio = image.naturalWidth > 0 && image.naturalHeight > 0 ? image.naturalWidth / image.naturalHeight : width / Math.max(1, height);
  const boxRatio = width / Math.max(1, height);
  const drawWidth = boxRatio > naturalRatio ? height * naturalRatio : width;
  const drawHeight = boxRatio > naturalRatio ? height : width / naturalRatio;
  const offsetX = (width - drawWidth) / 2;
  const offsetY = (height - drawHeight) / 2;

  return (
    <Group
      key={id}
      {...commonProps}
    >
      {selected ? (
        <Rect
          x={0}
          y={0}
          width={width}
          height={height}
          stroke="#c99a66"
          strokeWidth={8}
          cornerRadius={18}
        />
      ) : null}
      <KonvaImage
        image={image}
        x={offsetX}
        y={offsetY}
        width={drawWidth}
        height={drawHeight}
        cornerRadius={18}
      />
    </Group>
  );
}
