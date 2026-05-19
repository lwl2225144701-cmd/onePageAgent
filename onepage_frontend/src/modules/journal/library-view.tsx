"use client";

import { useEffect } from "react";
import { deleteJournal, getJournal, listJournals } from "@/api/journals.api";
import { useJournalStore } from "@/stores/journal-store";
import { Button } from "@/shared/ui/button";

export function LibraryView({ onCreate }: { onCreate: () => void }) {
  const { journals, localPages, setJournals } = useJournalStore();

  useEffect(() => {
    listJournals()
      .then((result) => setJournals(result.data))
      .catch(() => setJournals([]));
  }, [setJournals]);

  const pageCount = journals[0]?.page_count ?? localPages.length;
  const firstJournalId = journals[0]?.id;

  async function refreshJournalDetail() {
    if (!firstJournalId) return;
    await getJournal(firstJournalId).catch(() => undefined);
  }

  async function removeFirstJournal() {
    if (!firstJournalId) return;
    await deleteJournal(firstJournalId).catch(() => undefined);
    const result = await listJournals().catch(() => ({ data: [] as typeof journals }));
    setJournals(result.data);
  }

  return (
    <section className="mx-auto w-full max-w-[940px]">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">我的手账本</h1>
        <div className="flex items-center gap-2">
          <Button variant="ghost" className="min-h-10 px-5" onClick={refreshJournalDetail} disabled={!firstJournalId}>
            刷新本
          </Button>
          <Button variant="ghost" className="min-h-10 px-5" onClick={removeFirstJournal} disabled={!firstJournalId}>
            删本
          </Button>
          <Button className="min-h-10 px-5" onClick={onCreate}>
            新建
          </Button>
        </div>
      </header>
      <div className="grid grid-cols-4 gap-6 rounded-lg bg-gradient-to-b from-[#b98759] to-[#8b613f] p-7 max-md:grid-cols-2">
        <Book title="2024" subtitle={`${pageCount || 1} 页`} active />
        <Book title="2023" subtitle="月拾光" />
        <Book title="2022" subtitle="旧时光" />
        <button className="min-h-[190px] rounded border-2 border-dashed border-paper/80 bg-white/10 text-paper" onClick={onCreate}>
          ＋<br />新建手账本
        </button>
      </div>
      <div className="mt-7 rounded-lg border border-line bg-paper/75 p-7">
        <h2 className="text-xl font-semibold">2024 手账本</h2>
        <div className="mt-5 grid grid-cols-6 gap-4 max-md:grid-cols-2">
          {Array.from({ length: 12 }, (_, index) => (
            <div key={index} className="min-h-28 rounded-lg border border-line bg-paper p-4 text-center">
              <strong>{index + 1} 月</strong>
              <p className="mt-4">{index === 5 ? Math.max(1, pageCount) : index % 3} 天记录</p>
              <span>✿</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Book({ title, subtitle, active }: { title: string; subtitle: string; active?: boolean }) {
  return (
    <div className={`grid min-h-[190px] place-items-center rounded-r-xl rounded-l p-5 text-center shadow ${active ? "bg-[#e8d3bb]" : "bg-[#cdb38f]"}`}>
      <div>
        <strong>{title}</strong>
        <p className="mt-12">{subtitle}</p>
      </div>
    </div>
  );
}
