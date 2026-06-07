"use client";

import type Konva from "konva";
import { Text } from "react-konva";

import { clampPositionToPage, clampTransformToPage, estimateTextHeight } from "@/modules/editor/layout-bounds";

type CanvasTextNodeProps = {
  id: string;
  x: number;
  y: number;
  width: number;
  fontSize: number;
  content: string;
  color: string;
  align: string;
  font?: string;
  selected: boolean;
  pageWidth: number;
  pageHeight: number;
  onSelect: () => void;
  onPositionChange: (x: number, y: number) => void;
  onTransformChange: (x: number, y: number, width: number, rotation: number) => void;
  registerNode?: (node: Konva.Node | null) => void;
};

export function CanvasTextNode({
  id,
  x,
  y,
  width,
  fontSize,
  content,
  color,
  align,
  font,
  selected,
  pageWidth,
  pageHeight,
  onSelect,
  onPositionChange,
  onTransformChange,
  registerNode,
}: CanvasTextNodeProps) {
  const textHeight = estimateTextHeight(content, width, fontSize);
  const pageSize = { width: pageWidth, height: pageHeight };
  const fontFamily = resolveFontFamily(font);

  return (
    <Text
      key={id}
      ref={registerNode}
      x={x}
      y={y}
      width={width}
      text={content}
      fontFamily={fontFamily}
      fontSize={fontSize}
      fill={color}
      align={align as never}
      lineHeight={1.45}
      shadowColor="#fffaf2"
      shadowBlur={10}
      shadowOpacity={0.95}
      shadowOffsetX={0}
      shadowOffsetY={0}
      draggable
      dragBoundFunc={(position) => clampPositionToPage(position, { width, height: textHeight }, pageSize)}
      onClick={onSelect}
      onDragEnd={(event) => {
        const next = clampPositionToPage({ x: event.target.x(), y: event.target.y() }, { width, height: textHeight }, pageSize);
        onPositionChange(next.x, next.y);
      }}
      onTransformEnd={(event) => {
        const node = event.target as Konva.Text;
        const scaleX = node.scaleX();
        const nextWidth = Math.max(120, node.width() * scaleX);
        const nextHeight = estimateTextHeight(content, nextWidth, fontSize);
        node.scaleX(1);
        node.scaleY(1);
        const next = clampTransformToPage(
          { x: node.x(), y: node.y(), width: nextWidth, height: nextHeight, rotation: node.rotation() },
          pageSize,
          { width: 120, height: fontSize * 1.45 },
        );
        onTransformChange(next.x, next.y, next.width, next.rotation ?? 0);
      }}
      stroke={selected ? "#c99a66" : undefined}
      strokeWidth={selected ? 2 : 0}
    />
  );
}

function resolveFontFamily(font?: string) {
  const key = String(font ?? "").trim();
  const map: Record<string, string> = {
    handwriting: "Kaiti SC, LXGW WenKai, serif",
    brush: "Kaiti SC, Songti SC, serif",
    serif: "Songti SC, SimSun, serif",
    "sans-serif": "PingFang SC, system-ui, sans-serif",
    "日系手写体": "Kaiti SC, LXGW WenKai, serif",
    "清和手写体": "Kaiti SC, LXGW WenKai, serif",
    "宋体": "Songti SC, SimSun, serif",
    "思源宋体": "Source Han Serif SC, Songti SC, serif",
    "LXGW WenKai": "LXGW WenKai, Kaiti SC, serif",
  };
  return map[key] ?? (key || map.handwriting);
}
