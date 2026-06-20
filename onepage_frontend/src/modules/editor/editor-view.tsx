"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { ArrowLeft, Redo2, RefreshCw, Save, Trash2, Undo2 } from "lucide-react";
import { createJournal, listJournals } from "@/api/journals.api";
import { createPage, deletePage, getPage, updatePage } from "@/api/pages.api";
import type { CanvasExportApi } from "@/modules/editor/journal-canvas";
import { downloadImageDataUrl, downloadPdfFromJpegDataUrl } from "@/modules/editor/export-utils";
import { EditorPanels, ToolbarButton } from "@/modules/editor/editor-panels";
import { useCreateStore } from "@/stores/create-store";
import { useEditorStore } from "@/stores/editor-store";
import { useJournalStore } from "@/stores/journal-store";
import { toast } from "@/shared/toast";
import type { PageResponse } from "@/types/backend";

type Panel = "stickers" | "text" | "font" | "export" | "layout";
const DEFAULT_JOURNAL_NAME = "2024 手账本";

const JournalCanvas = dynamic(() => import("@/modules/editor/journal-canvas").then((mod) => mod.JournalCanvas), {
  ssr: false
});

export function EditorView({ initialPage, onBack, onSaved }: { initialPage?: PageResponse; onBack: () => void; onSaved: () => void }) {
  const [panel, setPanel] = useState<Panel | undefined>();
  const [savedPageId, setSavedPageId] = useState<string | undefined>();
  const [canvasApi, setCanvasApi] = useState<CanvasExportApi | undefined>();
  const { text, mood, weather, setText, setMood, setWeather } = useCreateStore();
  const layout = useEditorStore((state) => state.layout);
  const setLayout = useEditorStore((state) => state.setLayout);
  const canUndo = useEditorStore((state) => state.canUndo);
  const canRedo = useEditorStore((state) => state.canRedo);
  const isDirty = useEditorStore((state) => state.isDirty);
  const undo = useEditorStore((state) => state.undo);
  const redo = useEditorStore((state) => state.redo);
  const journals = useJournalStore((state) => state.journals);
  const activeJournalId = useJournalStore((state) => state.activeJournalId);
  const setJournals = useJournalStore((state) => state.setJournals);
  const upsertJournal = useJournalStore((state) => state.upsertJournal);
  const setActiveJournalId = useJournalStore((state) => state.setActiveJournalId);
  const upsertLocalPage = useJournalStore((state) => state.upsertLocalPage);

  useEffect(() => {
    if (!initialPage) return;
    setSavedPageId(initialPage.id);
    setText(initialPage.content_text ?? "");
    setMood(initialPage.mood ?? "平静");
    setWeather(initialPage.weather ?? { weather: "晴", temperature: 26 });
    if (initialPage.journal_id) {
      setActiveJournalId(initialPage.journal_id);
    }
    if (initialPage.layout_json) {
      setLayout(initialPage.layout_json, { markSaved: true });
    }
    upsertLocalPage(initialPage);
  }, [initialPage, setActiveJournalId, setLayout, setMood, setText, setWeather, upsertLocalPage]);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!isDirty) return;
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  function handleBack() {
    if (isDirty && !window.confirm("当前有未保存修改，确定离开吗？")) {
      return;
    }
    onBack();
  }

  async function resolveJournalId() {
    if (activeJournalId) return activeJournalId;

    const localJournal = journals.find((journal) => journal.name === DEFAULT_JOURNAL_NAME) ?? journals[0];
    if (localJournal) {
      setActiveJournalId(localJournal.id);
      return localJournal.id;
    }

    const result = await listJournals(1, 20).catch(() => ({ data: [] as typeof journals }));
    if (result.data.length > 0) {
      setJournals(result.data);
      const remoteJournal = result.data.find((journal) => journal.name === DEFAULT_JOURNAL_NAME) ?? result.data[0];
      if (remoteJournal) {
        setActiveJournalId(remoteJournal.id);
        return remoteJournal.id;
      }
    }

    const createdJournal = await createJournal(DEFAULT_JOURNAL_NAME, { style: "healing" });
    upsertJournal(createdJournal);
    setActiveJournalId(createdJournal.id);
    return createdJournal.id;
  }

  async function savePage() {
    const pageDate = getTodayDate();
    const pageTitle = buildPageTitle(text, mood);
    try {
      const journalId = await resolveJournalId();
      const payload = {
        journal_id: journalId,
        title: pageTitle,
        content_text: text,
        layout_json: layout,
        mood,
        weather,
        page_date: pageDate
      };
      const page = savedPageId ? await updatePage(savedPageId, payload) : await createPage(payload);
      if (page.layout_json) {
        setLayout(page.layout_json, { markSaved: true });
      }
      upsertLocalPage(page);
      setSavedPageId(page.id);
      const refreshed = await listJournals(1, 20).catch(() => undefined);
      if (refreshed) {
        setJournals(refreshed.data);
      }
    } catch {
      const fallbackPageId = savedPageId ?? `${Date.now()}`;
      upsertLocalPage({
        id: fallbackPageId,
        journal_id: activeJournalId ?? "local",
        user_id: "local",
        title: pageTitle,
        content_text: text,
        layout_json: layout,
        mood,
        weather,
        page_date: pageDate
      });
      setSavedPageId(savedPageId ?? fallbackPageId);
    }
    onSaved();
  }

  async function handleExport(format: "png" | "jpeg" | "pdf") {
    if (!canvasApi) {
      toast("画布尚未准备好");
      return;
    }
    try {
      const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
      if (format === "pdf") {
        const jpegDataUrl = await canvasApi.toDataUrl("jpeg");
        if (!jpegDataUrl) throw new Error("export failed");
        downloadPdfFromJpegDataUrl(jpegDataUrl, `onepage-${timestamp}.pdf`, layout.page.width, layout.page.height);
      } else {
        const dataUrl = await canvasApi.toDataUrl(format);
        if (!dataUrl) throw new Error("export failed");
        downloadImageDataUrl(dataUrl, `onepage-${timestamp}.${format === "jpeg" ? "jpg" : "png"}`);
      }
      toast("导出已生成");
    } catch (error) {
      toast("导出失败，请确认素材图片可正常加载");
    }
  }

  async function refreshPage() {
    if (!savedPageId) return;
    const page = await getPage(savedPageId).catch(() => undefined);
    if (!page) return;
    if (page.layout_json) {
      setLayout(page.layout_json, { markSaved: true });
    }
    upsertLocalPage(page);
  }

  async function removePage() {
    if (!savedPageId) return;
    await deletePage(savedPageId).catch(() => undefined);
    setSavedPageId(undefined);
  }

  return (
    <section className="grid h-[100dvh] min-h-0 place-items-center max-md:items-stretch">
      <div className="relative flex h-full min-h-0 w-full max-w-[460px] flex-col overflow-hidden rounded-[20px] border border-[#eadcc9]/62 bg-[#fffaf4]/95 p-2.5 shadow-journal [scrollbar-width:none] [-webkit-overflow-scrolling:touch] [&::-webkit-scrollbar]:hidden max-md:max-w-none max-md:rounded-none max-md:border-0 max-sm:p-2">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_52%_6%,rgba(255,255,255,0.9),transparent_34%),linear-gradient(180deg,rgba(255,250,244,0.95),rgba(246,235,221,0.78))]" />
        <div className="pointer-events-none absolute inset-0 opacity-22 [background-image:radial-gradient(rgba(118,83,52,0.12)_0.55px,transparent_0.7px)] [background-size:18px_18px]" />

        <header className="relative z-40 flex items-center gap-1.5 rounded-[16px] border border-[#eadcc9]/34 bg-[#fffdf8]/38 px-2 py-1 shadow-[0_4px_12px_rgba(111,82,51,0.025)]">
          <button className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-[#5f4b38] hover:bg-[#f4eadc]/60" onClick={handleBack} title="返回">
            <ArrowLeft size={17} />
          </button>
          <div className="min-w-0 shrink">
            <div className="whitespace-nowrap font-song text-[17px] font-semibold leading-none text-[#4f3d2c]">编辑这一页</div>
            <div className={`mt-0.5 whitespace-nowrap text-[10px] ${isDirty ? "text-[#a66d4f]/82" : "text-[#8a7a68]/78"}`}>{isDirty ? "有新的小改动" : "已保存"}</div>
          </div>
          <div className="flex-1" />
          <button
            className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-[#eadcc9]/38 bg-[#fffaf3]/42 text-[#6f6257] hover:bg-[#f4eadc]/60 disabled:opacity-40"
            title="撤销"
            onClick={undo}
            disabled={!canUndo}
          >
            <Undo2 size={16} />
          </button>
          <button
            className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-[#eadcc9]/38 bg-[#fffaf3]/42 text-[#6f6257] hover:bg-[#f4eadc]/60 disabled:opacity-40"
            title="重做"
            onClick={redo}
            disabled={!canRedo}
          >
            <Redo2 size={16} />
          </button>
          <button
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-[#e7caa4] bg-gradient-to-b from-[#c8a37e] to-[#a97852] text-white shadow-[0_6px_14px_rgba(139,93,52,0.16)]"
            onClick={savePage}
            title="保存"
            aria-label="保存"
          >
            <Save size={16} />
          </button>
          <button
            className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-[#eadcc9]/38 bg-[#fffaf3]/42 text-[#6f6257] hover:bg-[#f4eadc]/60 disabled:opacity-40"
            onClick={refreshPage}
            disabled={!savedPageId}
            title="刷新"
            aria-label="刷新"
          >
            <RefreshCw size={15} />
          </button>
          <button
            className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-[#eadcc9]/38 bg-[#fffaf3]/42 text-[#6f6257] hover:bg-[#f4eadc]/60 disabled:opacity-40"
            onClick={removePage}
            disabled={!savedPageId}
            title="删除"
            aria-label="删除"
          >
            <Trash2 size={15} />
          </button>
        </header>
        <div className="relative z-10 min-h-0 flex-1 px-0.5 pb-[calc(68px+env(safe-area-inset-bottom))] pt-1">
          <JournalCanvas onReady={setCanvasApi} />
        </div>
        <div
          className={`absolute bottom-[calc(8px+env(safe-area-inset-bottom))] left-2 right-2 z-30 overflow-hidden border text-xs ${
            panel
              ? "rounded-[22px] border-[#eadcc9]/70 bg-[#fffaf3] shadow-[0_18px_38px_rgba(111,82,51,0.15),inset_0_1px_0_rgba(255,255,255,0.84)]"
              : "rounded-[16px] border-[#eadcc9]/36 bg-[#fffdf8]/42 shadow-[0_5px_14px_rgba(111,82,51,0.028)]"
          }`}
          style={{ maxHeight: panel ? "min(390px, calc(100% - 96px))" : undefined }}
        >
          <EditorPanels panel={panel} onClose={() => setPanel(undefined)} onExport={handleExport} />
          <div
            className={`grid grid-cols-5 gap-1.5 p-1.5 ${
              panel ? "bg-transparent shadow-[inset_0_1px_0_rgba(234,220,201,0.14)]" : ""
            }`}
          >
            {(["layout", "stickers", "text", "font", "export"] as Panel[]).map((item) => (
              <ToolbarButton key={item} panel={item} active={panel === item} onClick={() => setPanel(panel === item ? undefined : item)} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function getTodayDate() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function buildPageTitle(text: string, mood: string) {
  const firstLine = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean);
  if (!firstLine) return `${mood || "今日"}手账`;
  return firstLine.length > 18 ? `${firstLine.slice(0, 18)}...` : firstLine;
}
