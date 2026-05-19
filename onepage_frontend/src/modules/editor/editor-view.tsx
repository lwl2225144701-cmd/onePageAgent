"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { ArrowLeft, Redo2, Save, Undo2 } from "lucide-react";
import { createExport } from "@/api/export.api";
import { createJournal } from "@/api/journals.api";
import { createPage, deletePage, getPage } from "@/api/pages.api";
import { EditorPanels, ToolbarButton } from "@/modules/editor/editor-panels";
import { useCreateStore } from "@/stores/create-store";
import { useEditorStore } from "@/stores/editor-store";
import { useJournalStore } from "@/stores/journal-store";
import { Button } from "@/shared/ui/button";

type Panel = "stickers" | "text" | "font" | "export" | "layout";

const JournalCanvas = dynamic(() => import("@/modules/editor/journal-canvas").then((mod) => mod.JournalCanvas), {
  ssr: false
});

export function EditorView({ onBack, onSaved }: { onBack: () => void; onSaved: () => void }) {
  const [panel, setPanel] = useState<Panel | undefined>();
  const [savedPageId, setSavedPageId] = useState<string | undefined>();
  const { text, mood, weather } = useCreateStore();
  const layout = useEditorStore((state) => state.layout);
  const addLocalPage = useJournalStore((state) => state.addLocalPage);

  async function savePage() {
    try {
      const journal = await createJournal("2024 手账本", { style: "healing" });
      const page = await createPage({
        journal_id: journal.id,
        title: "海边的治愈时光",
        content_text: text,
        layout_json: layout,
        mood,
        weather,
        page_date: "2024-06-01"
      });
      addLocalPage(page);
      setSavedPageId(page.id);
    } catch {
      addLocalPage({
        id: `${Date.now()}`,
        journal_id: "local",
        user_id: "local",
        title: "海边的治愈时光",
        content_text: text,
        layout_json: layout,
        mood,
        weather,
        page_date: "2024-06-01"
      });
      setSavedPageId(undefined);
    }
    onSaved();
  }

  async function handleExport(format: "png" | "pdf") {
    if (!savedPageId) return;
    try {
      await createExport(savedPageId, format);
    } catch {
      // keep local fallback export behavior
    }
  }

  async function refreshPage() {
    if (!savedPageId) return;
    await getPage(savedPageId).catch(() => undefined);
  }

  async function removePage() {
    if (!savedPageId) return;
    await deletePage(savedPageId).catch(() => undefined);
    setSavedPageId(undefined);
  }

  return (
    <section className="grid min-h-[calc(100vh-72px)] place-items-center">
      <div className="relative min-h-[760px] w-full max-w-[460px] rounded-[18px] border border-line bg-paper/95 p-3 shadow-journal">
        <header className="flex items-center gap-2">
          <button className="grid h-9 w-9 place-items-center rounded-full hover:bg-[#f4eadc]" onClick={onBack} title="返回">
            <ArrowLeft size={18} />
          </button>
          <div className="flex-1" />
          <button className="grid h-9 w-9 place-items-center rounded-full hover:bg-[#f4eadc]" title="撤销">
            <Undo2 size={18} />
          </button>
          <button className="grid h-9 w-9 place-items-center rounded-full hover:bg-[#f4eadc]" title="重做">
            <Redo2 size={18} />
          </button>
          <Button className="min-h-9 px-4" onClick={savePage}>
            <Save size={16} /> 保存
          </Button>
          <Button variant="ghost" className="min-h-9 px-4" onClick={refreshPage} disabled={!savedPageId}>
            刷新页
          </Button>
          <Button variant="ghost" className="min-h-9 px-4" onClick={removePage} disabled={!savedPageId}>
            删页
          </Button>
        </header>
        <div className="grid place-items-center py-3">
          <div className="overflow-hidden rounded-lg border border-line bg-white shadow-inner">
            <JournalCanvas />
          </div>
        </div>
        <div className="grid grid-cols-5 gap-2 border-t border-line pt-3 text-sm">
          {(["layout", "stickers", "text", "font", "export"] as Panel[]).map((item) => (
            <ToolbarButton key={item} panel={item} active={panel === item} onClick={() => setPanel(panel === item ? undefined : item)} />
          ))}
        </div>
        <EditorPanels panel={panel} onClose={() => setPanel(undefined)} onExport={handleExport} />
      </div>
    </section>
  );
}
