"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type Konva from "konva";
import { Layer, Rect, Stage, Text, Transformer } from "react-konva";
import { CanvasAssetNode } from "@/modules/editor/components/canvas-asset-node";
import { CanvasTagNode } from "@/modules/editor/components/canvas-tag-node";
import { CanvasTextNode, resolveFontFamily } from "@/modules/editor/components/canvas-text-node";
import { clampPositionToPage, clampTransformToPage, estimateTextHeight } from "@/modules/editor/layout-bounds";
import { useEditorStore } from "@/stores/editor-store";

const DEFAULT_SCALE = 0.33;
const MIN_SCALE = 0.28;
const MAX_SCALE = 0.39;

export type CanvasExportFormat = "png" | "jpeg";

export type CanvasExportApi = {
  toDataUrl: (format: CanvasExportFormat) => Promise<string | undefined>;
};

function getTagContent(type: string, props: Record<string, unknown>) {
  if (type === "date_tag") {
    return String(props.date ?? props.content ?? "");
  }
  if (type === "mood_tag") {
    const icon = String(props.icon ?? "").trim();
    const mood = String(props.mood ?? props.content ?? "").trim();
    return [icon, mood].filter(Boolean).join(" ");
  }
  if (type === "weather_tag") {
    const icon = String(props.icon ?? "").trim();
    const weather = String(props.weather ?? props.content ?? "").trim();
    return [icon, weather].filter(Boolean).join(" ");
  }
  return String(props.content ?? "");
}

function getTagWidth(content: string, fontSize: number, explicitWidth?: unknown) {
  const width = Number(explicitWidth ?? 0);
  if (width > 0) return width;
  return Math.max(160, Math.min(420, content.length * fontSize * 0.95 + 36));
}

function getAssetBoundsOptions(type: string, role: string, page: { width: number; height: number }) {
  if (role === "background" || role === "frame") {
    return { maxWidth: page.width, maxHeight: page.height };
  }
  if (role === "tape") {
    return { maxWidth: page.width * 0.9, maxHeight: page.height * 0.14 };
  }
  if (type === "image") {
    return { maxWidth: page.width * 0.72, maxHeight: page.height * 0.5 };
  }
  return { maxWidth: page.width * 0.38, maxHeight: page.height * 0.28 };
}

export function JournalCanvas({ onReady }: { onReady?: (api: CanvasExportApi | undefined) => void }) {
  const { layout, selectedId, select, updateElementPosition, updateElementTransform } = useEditorStore();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const stageRef = useRef<Konva.Stage | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const nodeRefs = useRef<Record<string, Konva.Node | null>>({});
  const [viewport, setViewport] = useState({ width: 0, height: 0 });

  const expectedAssetCount = useMemo(
    () => layout.elements.filter((element) => ["image", "sticker", "decoration"].includes(element.type) && typeof element.props.url === "string" && element.props.url).length,
    [layout.elements],
  );

  const toDataUrl = useCallback(async (format: CanvasExportFormat) => {
    const stage = stageRef.current;
    if (!stage) return undefined;
    if (document.fonts?.ready) {
      await document.fonts.ready;
    }
    const deadline = Date.now() + 5000;
    while (stage.find("Image").length < expectedAssetCount && Date.now() < deadline) {
      await new Promise((resolve) => window.setTimeout(resolve, 50));
    }
    if (stage.find("Image").length < expectedAssetCount) {
      return undefined;
    }
    stage.draw();
    return stage.toDataURL({
      mimeType: format === "jpeg" ? "image/jpeg" : "image/png",
      quality: 0.95,
      pixelRatio: 2,
    });
  }, [expectedAssetCount]);

  useEffect(() => {
    onReady?.({ toDataUrl });
    return () => onReady?.(undefined);
  }, [onReady, toDataUrl]);

  useEffect(() => {
    const transformer = transformerRef.current;
    if (!transformer) return;
    const node = selectedId ? nodeRefs.current[selectedId] : null;
    if (node) {
      transformer.nodes([node]);
    } else {
      transformer.nodes([]);
    }
    transformer.getLayer()?.batchDraw();
  }, [selectedId, layout]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const updateViewport = () => {
      const rect = container.getBoundingClientRect();
      setViewport({ width: rect.width, height: rect.height });
    };

    updateViewport();
    const resizeObserver = new ResizeObserver(updateViewport);
    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, []);

  const pageSize = { width: layout.page.width, height: layout.page.height };
  const pageBorderInset = Number(layout.style?.page_border_inset ?? 24);
  const pageBorderWidth = Number(layout.style?.page_border_width ?? 0);
  const taskId =
    typeof (layout as { task_id?: unknown }).task_id === "string"
      ? String((layout as { task_id?: unknown }).task_id)
      : typeof (layout as { meta?: { task_id?: unknown } }).meta?.task_id === "string"
        ? String((layout as { meta?: { task_id?: unknown } }).meta?.task_id)
        : "";
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      console.info("ONEPAGE_LAYOUT_ENGINE_USED", {
        task_id: taskId || undefined,
        layout_engine: (layout as { meta?: { layout_engine?: unknown } }).meta?.layout_engine,
        template_id: (layout as { meta?: { template_id?: unknown } }).meta?.template_id ?? layout.style?.template_id,
        build_commit: (layout as { meta?: { build_commit?: unknown } }).meta?.build_commit,
      });
    }
  }, [layout, taskId]);
  const scale = useMemo(() => {
    if (!viewport.width || !viewport.height) return DEFAULT_SCALE;

    const availableWidth = Math.max(0, viewport.width - 10);
    const availableHeight = Math.max(0, viewport.height - 10);
    const fittedScale = Math.min(availableWidth / layout.page.width, availableHeight / layout.page.height);
    return Math.min(MAX_SCALE, Math.max(MIN_SCALE, fittedScale));
  }, [layout.page.height, layout.page.width, viewport.height, viewport.width]);

  return (
    <div ref={containerRef} className="grid h-full min-h-0 w-full place-items-center overflow-hidden">
      <div className="overflow-hidden rounded-[20px] border border-[#eadcc9]/24 bg-[#fffdf8]/50 p-1 shadow-[0_12px_24px_rgba(111,82,51,0.085)]">
        <Stage ref={stageRef} width={layout.page.width * scale} height={layout.page.height * scale} scaleX={scale} scaleY={scale}>
          <Layer>
            <Rect width={layout.page.width} height={layout.page.height} fill={layout.page.background} cornerRadius={28} />
            {pageBorderWidth > 0 ? (
              <Rect
                x={pageBorderInset}
                y={pageBorderInset}
                width={layout.page.width - pageBorderInset * 2}
                height={layout.page.height - pageBorderInset * 2}
                stroke={String(layout.style?.page_border ?? "#E5D8C7")}
                strokeWidth={pageBorderWidth}
                cornerRadius={24}
                listening={false}
              />
            ) : null}
            {layout.elements
              .slice()
              .sort((a, b) => a.z_index - b.z_index)
              .map((element, index) => {
                const props = element.props;
                const id = String(props.id ?? `${element.type}-${index}`);
                if (element.type === "text") {
                  const fontSize = Number(props.size ?? 48);
                  const width = Number(props.w ?? 700);
                  const lineHeight = Number(props.lineHeight ?? 1.45);
                  const frame = clampTransformToPage(
                    {
                      x: Number(props.x ?? 0),
                      y: Number(props.y ?? 0),
                      width,
                      height: estimateTextHeight(String(props.content ?? ""), width, fontSize, lineHeight),
                    },
                    pageSize,
                    { width: 160, height: fontSize },
                  );
                  return (
                    <CanvasTextNode
                      key={id}
                      registerNode={(node) => {
                        nodeRefs.current[id] = node;
                      }}
                      id={id}
                      x={frame.x}
                      y={frame.y}
                      width={frame.width}
                      height={Number(props.h ?? frame.height)}
                      fontSize={fontSize}
                      lineHeight={lineHeight}
                      maxLines={Number(props.maxLines ?? props.max_lines ?? 0) || undefined}
                      shadow={readShadow(props.shadow)}
                      content={String(props.content ?? "")}
                      color={String(props.color ?? "#332b22")}
                      align={String(props.align ?? "left")}
                      font={String(props.font ?? layout.style?.font ?? "handwriting")}
                      selected={selectedId === id}
                      pageWidth={pageSize.width}
                      pageHeight={pageSize.height}
                      onSelect={() => select(id)}
                      onPositionChange={(x, y) => updateElementPosition(id, x, y)}
                      onTransformChange={(x, y, width, rotation) =>
                        updateElementTransform(id, { x, y, w: width, rotation })
                      }
                    />
                  );
                }
            if (element.type === "date_tag" || element.type === "mood_tag" || element.type === "weather_tag") {
              const content = getTagContent(element.type, props);
              const fontSize = Number(props.size ?? (element.type === "date_tag" ? 28 : 30));
              const width = getTagWidth(content, fontSize, props.w);
              const frame = clampTransformToPage(
                {
                  x: Number(props.x ?? 0),
                  y: Number(props.y ?? 0),
                  width,
                  height: estimateTextHeight(content, width, fontSize),
                },
                pageSize,
                { width: 120, height: fontSize },
              );
              return (
                <CanvasTagNode
                  key={id}
                  registerNode={(node) => {
                    nodeRefs.current[id] = node;
                  }}
                  id={id}
                  text={String(props.text ?? props.date ?? props.mood ?? props.weather ?? props.content ?? "")}
                  icon={String(props.icon ?? "")}
                  x={frame.x}
                  y={frame.y}
                  width={frame.width}
                  height={Number(props.h ?? frame.height)}
                  fontSize={fontSize}
                  fontFamily={resolveFontFamily(String(props.font ?? layout.style?.font ?? "handwriting"))}
                  color={String(props.color ?? "#8B7D6B")}
                  fill={typeof props.fill === "string" ? props.fill : undefined}
                  stroke={typeof props.stroke === "string" ? props.stroke : undefined}
                  strokeWidth={Number(props.strokeWidth ?? 0)}
                  borderRadius={Number(props.borderRadius ?? 0)}
                  paddingX={Number(props.paddingX ?? 0)}
                  paddingY={Number(props.paddingY ?? 0)}
                  iconGap={Number(props.iconGap ?? 0)}
                  opacity={Number(props.opacity ?? 1)}
                  shadow={readShadow(props.shadow)}
                  selected={selectedId === id}
                  pageWidth={pageSize.width}
                  pageHeight={pageSize.height}
                  onSelect={() => select(id)}
                  onPositionChange={(x, y) => updateElementPosition(id, x, y)}
                  onTransformChange={(x, y, nextWidth, rotation) =>
                    updateElementTransform(id, { x, y, w: nextWidth, rotation })
                  }
                />
              );
            }
            if (element.type === "image") {
              const role = String(props.role ?? "");
              const boundsOptions = getAssetBoundsOptions(element.type, role, pageSize);
              const frame = clampTransformToPage(
                {
                  x: Number(props.x ?? 0),
                  y: Number(props.y ?? 0),
                  width: Number(props.w ?? 280),
                  height: Number(props.h ?? 360),
                  rotation: Number(props.rotation ?? 0),
                },
                pageSize,
                { width: 80, height: 80 },
                boundsOptions,
              );
              return (
                <CanvasAssetNode
                  key={id}
                  registerNode={(node) => {
                    nodeRefs.current[id] = node;
                  }}
                  id={id}
                  url={typeof props.url === "string" ? props.url : undefined}
                  elementType={element.type}
                  materialId={typeof props.material_id === "string" ? props.material_id : undefined}
                  taskId={taskId}
                  pageWidth={pageSize.width}
                  pageHeight={pageSize.height}
                  x={frame.x}
                  y={frame.y}
                  width={frame.width}
                  height={frame.height}
                  rotation={frame.rotation ?? 0}
                  opacity={Number(props.opacity ?? 1)}
                  fit={readFit(props.fit)}
                  objectPosition={String(props.objectPosition ?? "center")}
                  visualBBox={readVisualBBox(props.visualBBox)}
                  cornerRadius={Number(props.cornerRadius ?? 18)}
                  mask={typeof props.mask === "string" ? props.mask : null}
                  role={role}
                  mimeType={typeof props.mimeType === "string" ? props.mimeType : undefined}
                  selected={selectedId === id}
                  onSelect={() => select(id)}
                  onPositionChange={(x, y) => updateElementPosition(id, x, y)}
                  onTransformChange={(x, y, width, height, rotation) =>
                    updateElementTransform(
                      id,
                      clampTransformToPage(
                        { x, y, width, height, rotation },
                        pageSize,
                        { width: 80, height: 80 },
                        boundsOptions,
                      ),
                    )
                  }
                />
              );
            }
            if (element.type === "sticker" || element.type === "decoration") {
              if (typeof props.url === "string" && props.url) {
                const role = String(props.role ?? "");
                const boundsOptions = getAssetBoundsOptions(element.type, role, pageSize);
                const frame = clampTransformToPage(
                  {
                    x: Number(props.x ?? 0),
                    y: Number(props.y ?? 0),
                    width: Number(props.w ?? 180),
                    height: Number(props.h ?? 180),
                    rotation: Number(props.rotation ?? 0),
                  },
                  pageSize,
                  { width: 48, height: 48 },
                  boundsOptions,
                );
                return (
                  <CanvasAssetNode
                    key={id}
                    id={id}
                    url={props.url}
                    elementType={element.type}
                    materialId={typeof props.material_id === "string" ? props.material_id : undefined}
                    taskId={taskId}
                    pageWidth={pageSize.width}
                    pageHeight={pageSize.height}
                    x={frame.x}
                    y={frame.y}
                    width={frame.width}
                    height={frame.height}
                    rotation={frame.rotation ?? 0}
                    opacity={Number(props.opacity ?? 1)}
                    fit={readFit(props.fit)}
                    objectPosition={String(props.objectPosition ?? "center")}
                    visualBBox={readVisualBBox(props.visualBBox)}
                    cornerRadius={Number(props.cornerRadius ?? 18)}
                    mask={typeof props.mask === "string" ? props.mask : null}
                    role={role}
                    mimeType={typeof props.mimeType === "string" ? props.mimeType : undefined}
                    selected={selectedId === id}
                    onSelect={() => select(id)}
                    registerNode={(node) => {
                      nodeRefs.current[id] = node;
                    }}
                    onPositionChange={(x, y) => updateElementPosition(id, x, y)}
                    onTransformChange={(x, y, width, height, rotation) =>
                      updateElementTransform(
                        id,
                        clampTransformToPage(
                          { x, y, width, height, rotation },
                          pageSize,
                          { width: 48, height: 48 },
                          boundsOptions,
                        ),
                      )
                    }
                  />
                );
              }
            }
            const fontSize = Number(props.size ?? 72);
            const fallbackWidth = fontSize;
            const fallbackHeight = fontSize;
            return (
              <Text
                key={id}
                x={clampPositionToPage(
                  { x: Number(props.x ?? 0), y: Number(props.y ?? 0) },
                  { width: fallbackWidth, height: fallbackHeight },
                  pageSize,
                ).x}
                y={clampPositionToPage(
                  { x: Number(props.x ?? 0), y: Number(props.y ?? 0) },
                  { width: fallbackWidth, height: fallbackHeight },
                  pageSize,
                ).y}
                text={String(props.content ?? "✿")}
                fontSize={fontSize}
                fill={String(props.color ?? "#c99566")}
                draggable
                dragBoundFunc={(position) => clampPositionToPage(position, { width: fallbackWidth, height: fallbackHeight }, pageSize)}
                onClick={() => select(id)}
                onDragEnd={(event) => {
                  const next = clampPositionToPage({ x: event.target.x(), y: event.target.y() }, { width: fallbackWidth, height: fallbackHeight }, pageSize);
                  updateElementPosition(id, next.x, next.y);
                }}
              />
            );
            })}
            <Transformer
              ref={transformerRef}
              rotateEnabled
              enabledAnchors={["top-left", "top-right", "bottom-left", "bottom-right"]}
              borderStroke="#c99a66"
              anchorStroke="#c99a66"
              anchorFill="#fffaf4"
              anchorSize={8}
            />
          </Layer>
        </Stage>
      </div>
    </div>
  );
}

function readFit(value: unknown): "contain" | "cover" | "fill" | "watermark" {
  return value === "cover" || value === "fill" || value === "watermark" ? value : "contain";
}

function readVisualBBox(value: unknown) {
  if (!value || typeof value !== "object") return undefined;
  const bbox = value as Record<string, unknown>;
  return { x: Number(bbox.x ?? 0), y: Number(bbox.y ?? 0), w: Number(bbox.w ?? 1), h: Number(bbox.h ?? 1) };
}

function readShadow(value: unknown) {
  if (!value || typeof value !== "object") return undefined;
  const shadow = value as Record<string, unknown>;
  return {
    color: typeof shadow.color === "string" ? shadow.color : undefined,
    blur: Number(shadow.blur ?? 0),
    opacity: Number(shadow.opacity ?? 0),
    offset_x: Number(shadow.offset_x ?? 0),
    offset_y: Number(shadow.offset_y ?? 0),
  };
}
