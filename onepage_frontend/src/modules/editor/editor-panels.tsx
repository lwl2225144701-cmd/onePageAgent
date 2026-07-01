"use client";

import { useEffect, useMemo, useState } from "react";
import { Download, Flower2, LayoutTemplate, Palette, Type } from "lucide-react";
import { listMaterials, markMaterialUsed } from "@/api/materials.api";
import { getMaterialPreviewUrl } from "@/modules/materials/utils";
import { Button } from "@/shared/ui/button";
import { useEditorStore } from "@/stores/editor-store";
import type { MaterialResponse } from "@/types/backend";

type Panel = "stickers" | "text" | "font" | "export" | "layout";

const exportOptions: Array<{ format: "png" | "jpeg" | "pdf"; label: string }> = [
  { format: "png", label: "PNG 图片" },
  { format: "jpeg", label: "JPEG 图片" },
  { format: "pdf", label: "PDF 文档" },
];

const moodIconOptions = ["😊", "😌", "😮‍💨", "🥹", "🤩", "🥰", "🤔", "😴", "😔", "😢", "😟", "😡"];
const weatherIconOptions = ["☀️", "🌤️", "⛅", "☁️", "🌧️", "⛈️", "❄️", "🌫️", "💨", "🌈"];

export function EditorPanels({
  panel,
  onClose,
  onExport
}: {
  panel?: Panel;
  onClose: () => void;
  onExport: (format: "png" | "jpeg" | "pdf") => void;
}) {
  const { layout, selectedId, updateText, updateTagIcon, updateFont, replaceSticker } = useEditorStore();
  const [stickerOptions, setStickerOptions] = useState<MaterialResponse[]>([]);
  const [draftText, setDraftText] = useState("");
  const selectedIndex = layout.elements.findIndex((element, index) => String(element.props.id ?? `${element.type}-${index}`) === selectedId);
  const selectedElement = selectedIndex >= 0 ? layout.elements[selectedIndex] : undefined;
  const selectedTextElement = selectedElement && ["text", "date_tag", "mood_tag", "weather_tag"].includes(selectedElement.type) ? selectedElement : undefined;
  const selectedIconOptions =
    selectedElement?.type === "mood_tag"
      ? moodIconOptions
      : selectedElement?.type === "weather_tag"
        ? weatherIconOptions
        : [];
  const selectedStickers = layout.elements.filter((element) => element.type === "sticker" && typeof element.props.url === "string" && element.props.url);
  const selectedStickerElement = useMemo(
    () => (selectedElement?.type === "sticker" ? selectedElement : undefined),
    [selectedElement],
  );
  const selectedStickerUrl = typeof selectedStickerElement?.props.url === "string" ? selectedStickerElement.props.url : "";

  useEffect(() => {
    if (panel !== "stickers") return;
    listMaterials({ type: "sticker" })
      .then((response) => setStickerOptions(response.data))
      .catch(() => setStickerOptions([]));
  }, [panel]);

  useEffect(() => {
    setDraftText(String(selectedTextElement?.props.content ?? selectedTextElement?.props.date ?? selectedTextElement?.props.mood ?? selectedTextElement?.props.weather ?? ""));
  }, [selectedTextElement, panel]);

  if (!panel) return null;

  return (
    <div className="max-h-[300px] overflow-auto bg-transparent p-5 [scrollbar-width:none] [-webkit-overflow-scrolling:touch] [&::-webkit-scrollbar]:hidden">
      <div className="mb-4 flex items-center justify-between font-song text-[20px] font-semibold text-[#4f3d2c]">
        <span>{panelTitle(panel)}</span>
        <button className="grid h-8 w-8 place-items-center rounded-full text-[#8a7a68] hover:bg-[#f4eadc]/70" onClick={onClose}>
          ×
        </button>
      </div>
      {panel === "text" && (
        <div>
          {selectedIconOptions.length > 0 && selectedId ? (
            <div className="mb-4 rounded-[16px] border border-[#eadcc9]/48 bg-[#fffdf8] p-3">
              <div className="mb-2 text-sm font-medium text-[#4f3d2c]">切换图标</div>
              <div className="flex flex-wrap gap-2">
                {selectedIconOptions.map((icon) => {
                  const active = String(selectedElement?.props.icon ?? "") === icon;
                  return (
                    <button
                      key={icon}
                      type="button"
                      aria-label={`使用图标 ${icon}`}
                      className={`grid h-10 w-10 place-items-center rounded-full border text-lg transition ${
                        active
                          ? "border-[#c99a66] bg-[#f1dcc5] shadow-[0_4px_10px_rgba(168,126,92,0.14)]"
                          : "border-[#eadcc9]/55 bg-[#fffaf3] hover:bg-[#f4eadc]"
                      }`}
                      onClick={() => updateTagIcon(selectedId, icon)}
                    >
                      {icon}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}
          <textarea
            className="min-h-28 w-full resize-none rounded-[16px] border border-[#eadcc9]/60 bg-[#fffdf8] p-3 leading-7 text-[#4f3d2c] outline-none shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]"
            value={draftText}
            onChange={(event) => setDraftText(event.target.value)}
            onBlur={(event) => selectedTextElement && selectedIndex >= 0 && updateText(selectedIndex, event.target.value)}
          />
          <Button
            className="mt-3 w-full rounded-full bg-gradient-to-b from-[#c8a37e] to-[#a97852] text-white shadow-[0_8px_18px_rgba(139,93,52,0.16)]"
            onClick={() => {
              if (selectedTextElement && selectedIndex >= 0) {
                updateText(selectedIndex, draftText);
              }
              onClose();
            }}
          >
            应用文字
          </Button>
        </div>
      )}
      {panel === "stickers" && (
        <div className="grid gap-3">
          <div className="rounded-[16px] border border-[#eadcc9]/48 bg-[#fffdf8] px-3 py-2 text-sm leading-6 text-[#6f6257]">
            {selectedStickerElement
              ? "当前已选中 AI 贴图，可从素材库中替换。替换后可直接点顶部撤销恢复。"
              : "请先在画布上选中一个 AI 已生成的贴图，然后再替换。"}
          </div>
          {selectedStickerElement ? (
            <div className="rounded-[16px] border border-[#d0ad7f]/58 bg-[#fff7eb] p-3">
              <div className="mb-2 text-xs font-medium text-[#7d6043]">当前替换目标</div>
              <div className="flex items-center gap-3">
                <div className="relative h-16 w-16 overflow-hidden rounded-[12px] border border-white bg-[#fffdf8] shadow-sm">
                  <img src={selectedStickerUrl} alt="当前选中的贴图" className="h-full w-full object-cover" />
                </div>
                <div className="min-w-0 flex-1 text-sm text-[#4f4238]">
                  <div className="truncate">AI 已选贴图</div>
                  <div className="truncate text-xs text-[#6f6257]">{selectedStickerUrl.split("/").pop()}</div>
                </div>
              </div>
            </div>
          ) : null}
          {selectedStickers.length > 0 ? (
            <div className="grid grid-cols-4 gap-3">
              {selectedStickers.map((element, index) => {
                const url = String(element.props.url);
                const elementId = String(element.props.id ?? `sticker-${index}`);
                const active = selectedId === elementId;
                return (
                  <div
                    key={`${url}-${index}`}
                    className={`overflow-hidden rounded-[14px] border p-2 ${
                      active ? "border-[#d0ad7f] bg-[#fff7eb]" : "border-[#eadcc9]/55 bg-[#fffdf8]"
                    }`}
                  >
                    <div className="relative aspect-square overflow-hidden rounded-[10px] bg-[#fffaf0]">
                      <img src={url} alt="AI 选中的贴图" className="h-full w-full object-cover" />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="rounded-[16px] border border-dashed border-[#eadcc9]/70 bg-[#fffdf8] px-4 py-6 text-center text-sm text-[#8a7a68]">
              当前画布还没有 AI 选中的贴图
            </div>
          )}
          <div className="border-t border-[#eadcc9]/48 pt-3">
            <div className="mb-3 text-sm font-medium text-[#4f3d2c]">素材库贴图</div>
            {stickerOptions.length > 0 ? (
              <div className="grid grid-cols-4 gap-3">
                {stickerOptions.map((item) => {
                  const category = String(item.meta_info?.category ?? "");
                  const previewUrl = getMaterialPreviewUrl(item);
                  const isCurrent = item.file_url === selectedStickerUrl;
                  const disabled = !selectedStickerElement || isCurrent;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      disabled={disabled}
                      className={`overflow-hidden rounded-[14px] border p-2 text-left disabled:cursor-not-allowed disabled:opacity-50 ${
                        isCurrent ? "border-[#d0ad7f] bg-[#fff7eb]" : "border-[#eadcc9]/55 bg-[#fffdf8]"
                      }`}
                      onClick={async () => {
                        if (!selectedId || !selectedStickerElement) return;
                        replaceSticker(selectedId, item.file_url);
                        await markMaterialUsed(item.id).catch(() => undefined);
                        onClose();
                      }}
                    >
                      <div className="relative aspect-square overflow-hidden rounded-[10px] bg-[#fffaf0]">
                        <img src={previewUrl} alt={category || "素材贴图"} className="h-full w-full object-cover" />
                      </div>
                      <div className="mt-2 truncate text-xs text-[#6f6257]">{isCurrent ? "当前使用" : category || "贴图"}</div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-[16px] border border-dashed border-[#eadcc9]/70 bg-[#fffdf8] px-4 py-6 text-center text-sm text-[#8a7a68]">
                素材库暂无可替换贴图
              </div>
            )}
          </div>
        </div>
      )}
      {panel === "font" && (
        <div className="grid gap-2">
          <div className="rounded-[16px] border border-[#eadcc9]/48 bg-[#fffdf8] px-3 py-2 text-sm leading-6 text-[#6f6257]">
            {selectedTextElement ? "将字体应用到当前选中的文字。" : "未选中文字，将字体应用到全部文字。"}
          </div>
          {["日系手写体", "清和手写体", "宋体", "思源宋体", "LXGW WenKai"].map((item) => (
            <Button
              key={item}
              variant="soft"
              className="justify-start rounded-full border border-[#eadcc9]/52 bg-[#fffdf8] text-left text-[#5f5146]"
              onClick={() => {
                updateFont(selectedTextElement ? selectedId : undefined, item);
                onClose();
              }}
            >
              {item}
            </Button>
          ))}
        </div>
      )}
      {panel === "export" && (
        <div className="grid gap-2">
          {exportOptions.map((option) => (
            <Button
              key={option.format}
              variant="soft"
              className="inline-flex items-center justify-center gap-2 rounded-full border border-[#eadcc9]/52 bg-[#fffdf8] text-[#5f5146]"
              onClick={() => onExport(option.format)}
            >
              <Download size={16} className="shrink-0" />
              <span>{option.label}</span>
            </Button>
          ))}
          <p className="text-xs leading-6 text-muted">导出当前画布内容，支持未保存页面。</p>
        </div>
      )}
      {panel === "layout" && (
        <div className="grid grid-cols-3 gap-2">
          {["海边", "周末", "日常"].map((item) => (
            <Button key={item} variant="soft" className="rounded-full border border-[#eadcc9]/52 bg-[#fffdf8] text-[#5f5146]">
              {item}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

export function ToolbarButton({ panel, active, onClick }: { panel: Panel; active: boolean; onClick: () => void }) {
  const Icon = panelIcon(panel);
  return (
    <button
      className={`grid h-12 place-items-center rounded-[13px] px-1 text-[11px] leading-none transition ${
        active
          ? "bg-[#ead4b5] text-[#4f3d2c] shadow-[inset_0_1px_0_rgba(255,255,255,0.62)]"
          : "bg-[#fffaf3]/56 text-[#7d6d5d] hover:bg-[#f4eadc]/60"
      }`}
      onClick={onClick}
      title={panelTitle(panel)}
      aria-label={panelTitle(panel)}
    >
      <Icon size={15} />
      <span className="whitespace-nowrap">{panelTitle(panel)}</span>
    </button>
  );
}

function panelTitle(panel: Panel) {
  return ({ layout: "模板", stickers: "贴纸", text: "文字", font: "字体", export: "导出" } as const)[panel];
}

function panelIcon(panel: Panel) {
  return ({ layout: LayoutTemplate, stickers: Flower2, text: Type, font: Palette, export: Download } as const)[panel];
}
