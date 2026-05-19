"use client";

import { Download, Flower2, Type } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { useEditorStore } from "@/stores/editor-store";

type Panel = "stickers" | "text" | "font" | "export" | "layout";

export function EditorPanels({
  panel,
  onClose,
  onExport
}: {
  panel?: Panel;
  onClose: () => void;
  onExport: (format: "png" | "pdf") => void;
}) {
  const { layout, selectedId, updateText } = useEditorStore();
  if (!panel) return null;

  const selectedIndex = layout.elements.findIndex((element, index) => String(element.props.id ?? `${element.type}-${index}`) === selectedId);
  const selectedElement = selectedIndex >= 0 ? layout.elements[selectedIndex] : undefined;

  return (
    <aside className="absolute bottom-[86px] left-3 right-3 max-h-[300px] overflow-auto rounded-2xl border border-line bg-white/95 p-5 shadow-journal">
      <div className="mb-4 flex items-center justify-between font-semibold">
        <span>{panelTitle(panel)}</span>
        <button className="grid h-8 w-8 place-items-center rounded-full hover:bg-[#f4eadc]" onClick={onClose}>
          ×
        </button>
      </div>
      {panel === "text" && (
        <div>
          <textarea
            className="min-h-28 w-full resize-none rounded-lg border border-line p-3 leading-7 outline-none"
            defaultValue={String(selectedElement?.props.content ?? "")}
            onBlur={(event) => selectedIndex >= 0 && updateText(selectedIndex, event.target.value)}
          />
          <Button className="mt-3 w-full" onClick={onClose}>
            应用文字
          </Button>
        </div>
      )}
      {panel === "stickers" && (
        <div className="grid grid-cols-5 gap-2">
          {["✿", "❀", "❁", "✦", "☕", "camera", "memo", "paper", "bear", "sea"].map((item) => (
            <Button key={item} variant="soft" className="rounded-lg px-2">
              {item}
            </Button>
          ))}
        </div>
      )}
      {panel === "font" && (
        <div className="grid gap-2">
          {["日系手写体", "清和手写体", "宋体", "思源宋体", "LXGW WenKai"].map((item) => (
            <Button key={item} variant="soft" className="justify-start rounded-lg text-left">
              {item}
            </Button>
          ))}
        </div>
      )}
      {panel === "export" && (
        <div className="grid gap-2">
          <Button variant="soft" className="rounded-lg" onClick={() => onExport("png")}>
            <Download size={16} /> PNG 图片
          </Button>
          <Button variant="soft" className="rounded-lg" onClick={() => onExport("pdf")}>
            PDF 文档
          </Button>
          <p className="text-xs leading-6 text-muted">导出优先调用后端 `POST /export`，失败时走本地降级。</p>
        </div>
      )}
      {panel === "layout" && (
        <div className="grid grid-cols-3 gap-2">
          {["海边", "周末", "日常"].map((item) => (
            <Button key={item} variant="soft" className="rounded-lg">
              {item}
            </Button>
          ))}
        </div>
      )}
    </aside>
  );
}

export function ToolbarButton({ panel, active, onClick }: { panel: Panel; active: boolean; onClick: () => void }) {
  const Icon = panel === "text" || panel === "font" ? Type : panel === "stickers" ? Flower2 : Download;
  return (
    <button className={`grid min-h-12 place-items-center rounded-lg ${active ? "bg-[#eadcc9]" : "bg-[#f4eadc]"}`} onClick={onClick}>
      <Icon size={16} />
      {panelTitle(panel)}
    </button>
  );
}

function panelTitle(panel: Panel) {
  return ({ layout: "模板", stickers: "贴纸", text: "文字", font: "字体", export: "导出" } as const)[panel];
}
