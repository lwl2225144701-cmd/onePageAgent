"use client";

import type Konva from "konva";
import { Group, Rect, Text } from "react-konva";

import { clampPositionToPage, clampTransformToPage } from "@/modules/editor/layout-bounds";

type ShadowSpec = {
  color?: string;
  blur?: number;
  opacity?: number;
  offset_x?: number;
  offset_y?: number;
};

type CanvasTagNodeProps = {
  id: string;
  text: string;
  icon?: string;
  x: number;
  y: number;
  width: number;
  height: number;
  fontSize: number;
  fontFamily: string;
  color: string;
  fill?: string;
  stroke?: string;
  strokeWidth?: number;
  borderRadius?: number;
  paddingX?: number;
  paddingY?: number;
  iconGap?: number;
  opacity?: number;
  shadow?: ShadowSpec;
  selected: boolean;
  pageWidth: number;
  pageHeight: number;
  onSelect: () => void;
  onPositionChange: (x: number, y: number) => void;
  onTransformChange: (x: number, y: number, width: number, rotation: number) => void;
  registerNode?: (node: Konva.Node | null) => void;
};

export function CanvasTagNode({
  id,
  text,
  icon = "",
  x,
  y,
  width,
  height,
  fontSize,
  fontFamily,
  color,
  fill,
  stroke,
  strokeWidth = 0,
  borderRadius = 0,
  paddingX = 0,
  paddingY = 0,
  iconGap = 0,
  opacity = 1,
  shadow,
  selected,
  pageWidth,
  pageHeight,
  onSelect,
  onPositionChange,
  onTransformChange,
  registerNode,
}: CanvasTagNodeProps) {
  const pageSize = { width: pageWidth, height: pageHeight };
  const iconWidth = icon ? fontSize : 0;
  const textX = paddingX + iconWidth + (icon ? iconGap : 0);
  const contentHeight = Math.max(fontSize * 1.25, height - paddingY * 2);
  return (
    <Group
      id={id}
      ref={registerNode}
      x={x}
      y={y}
      width={width}
      height={height}
      opacity={opacity}
      draggable
      dragBoundFunc={(position) => clampPositionToPage(position, { width, height }, pageSize)}
      onClick={onSelect}
      onTap={onSelect}
      onDragEnd={(event) => {
        const next = clampPositionToPage({ x: event.target.x(), y: event.target.y() }, { width, height }, pageSize);
        onPositionChange(next.x, next.y);
      }}
      onTransformEnd={(event) => {
        const node = event.target as Konva.Group;
        const nextWidth = Math.max(100, width * node.scaleX());
        node.scaleX(1);
        node.scaleY(1);
        const next = clampTransformToPage(
          { x: node.x(), y: node.y(), width: nextWidth, height, rotation: node.rotation() },
          pageSize,
          { width: 100, height },
        );
        onTransformChange(next.x, next.y, next.width, next.rotation ?? 0);
      }}
    >
      {fill || stroke ? (
        <Rect
          width={width}
          height={height}
          fill={fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          cornerRadius={borderRadius}
          shadowColor={shadow?.color}
          shadowBlur={shadow?.blur ?? 0}
          shadowOpacity={shadow?.opacity ?? 0}
          shadowOffsetX={shadow?.offset_x ?? 0}
          shadowOffsetY={shadow?.offset_y ?? 0}
        />
      ) : null}
      {icon ? (
        <Text
          x={paddingX}
          y={paddingY}
          width={iconWidth}
          height={contentHeight}
          text={icon}
          fontSize={fontSize}
          verticalAlign="middle"
          listening={false}
        />
      ) : null}
      <Text
        x={textX}
        y={paddingY}
        width={Math.max(1, width - textX - paddingX)}
        height={contentHeight}
        text={text}
        fontFamily={fontFamily}
        fontSize={fontSize}
        fill={color}
        verticalAlign="middle"
        listening={false}
      />
      {selected ? (
        <Rect width={width} height={height} stroke="#c99a66" strokeWidth={2} cornerRadius={borderRadius || 8} listening={false} />
      ) : null}
    </Group>
  );
}
