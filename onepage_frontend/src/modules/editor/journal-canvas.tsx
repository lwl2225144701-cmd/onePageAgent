"use client";

import { Layer, Rect, Stage, Text } from "react-konva";
import { useEditorStore } from "@/stores/editor-store";

const scale = 0.28;

export function JournalCanvas() {
  const { layout, selectedId, select } = useEditorStore();

  return (
    <Stage width={layout.page.width * scale} height={layout.page.height * scale} scaleX={scale} scaleY={scale}>
      <Layer>
        <Rect width={layout.page.width} height={layout.page.height} fill={layout.page.background} cornerRadius={28} />
        {layout.elements
          .slice()
          .sort((a, b) => a.z_index - b.z_index)
          .map((element, index) => {
            const props = element.props;
            const id = String(props.id ?? `${element.type}-${index}`);
            if (element.type === "text") {
              return (
                <Text
                  key={id}
                  x={Number(props.x ?? 0)}
                  y={Number(props.y ?? 0)}
                  width={Number(props.w ?? 700)}
                  text={String(props.content ?? "")}
                  fontFamily="Kaiti SC"
                  fontSize={Number(props.size ?? 48)}
                  fill={String(props.color ?? "#332b22")}
                  align={String(props.align ?? "left") as never}
                  lineHeight={1.45}
                  draggable
                  onClick={() => select(id)}
                  stroke={selectedId === id ? "#75bfe4" : undefined}
                  strokeWidth={selectedId === id ? 2 : 0}
                />
              );
            }
            if (element.type === "image") {
              return (
                <Rect
                  key={id}
                  x={Number(props.x ?? 0)}
                  y={Number(props.y ?? 0)}
                  width={Number(props.w ?? 280)}
                  height={Number(props.h ?? 360)}
                  fill="#ffffff"
                  stroke={selectedId === id ? "#75bfe4" : "#eadbca"}
                  strokeWidth={selectedId === id ? 8 : 0}
                  shadowBlur={18}
                  rotation={Number(props.rotation ?? 0)}
                  draggable
                  onClick={() => select(id)}
                />
              );
            }
            return (
              <Text
                key={id}
                x={Number(props.x ?? 0)}
                y={Number(props.y ?? 0)}
                text={String(props.content ?? "✿")}
                fontSize={Number(props.size ?? 72)}
                fill={String(props.color ?? "#c99566")}
                draggable
                onClick={() => select(id)}
              />
            );
          })}
      </Layer>
    </Stage>
  );
}
