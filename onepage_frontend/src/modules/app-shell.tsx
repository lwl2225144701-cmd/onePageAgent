"use client";

import { useState } from "react";
import { Flower2, Home, Library, Plus, UserRound } from "lucide-react";
import { LoadingView } from "@/modules/ai/loading-view";
import { CreateView } from "@/modules/create/create-view";
import { EditorView } from "@/modules/editor/editor-view";
import { LibraryView } from "@/modules/journal/library-view";
import { MaterialsView } from "@/modules/materials/materials-view";
import { ProfileView } from "@/modules/profile/profile-view";
import { Button } from "@/shared/ui/button";
import type { PageResponse } from "@/types/backend";

export type Screen = "home" | "create" | "loading" | "editor" | "library" | "materials" | "profile";

const navItems: Array<{ id: Screen; label: string; icon: React.ComponentType<{ size?: number; className?: string }>; central?: boolean }> = [
  { id: "home", label: "首页", icon: Home },
  { id: "library", label: "手账本", icon: Library },
  { id: "create", label: "创作", icon: Plus, central: true },
  { id: "materials", label: "素材库", icon: Flower2 },
  { id: "profile", label: "我的", icon: UserRound }
];

export function AppShell({ initialScreen = "home" }: { initialScreen?: Screen }) {
  const [screen, setScreen] = useState<Screen>(initialScreen);
  const [editingPage, setEditingPage] = useState<PageResponse | undefined>();
  const immersiveEditor = screen === "editor";

  function handleNavigate(nextScreen: Screen) {
    if (nextScreen === "create") {
      setEditingPage(undefined);
    }
    setScreen(nextScreen);
  }

  return (
    <div className="grid min-h-screen grid-cols-[220px_1fr] bg-warm-surface text-ink max-md:grid-cols-1">
      <aside className="sticky top-0 z-20 h-screen border-r border-line/80 bg-paper/85 px-5 py-10 backdrop-blur max-md:hidden">
        <div className="mb-14 max-md:hidden">
          <div className="font-song text-[32px] leading-tight">
            有一页
            <br />
            <span className="text-2xl italic">onepage</span>
          </div>
          <p className="mt-5 leading-8 text-muted">记录生活，发现每一页的美好。</p>
        </div>
        <nav className="grid gap-2">
          {navItems.map((item) => {
            const active = screen === item.id || (item.id === "create" && (screen === "loading" || screen === "editor"));
            return (
              <NavButton
                key={item.id}
                item={item}
                active={active}
                mode="side"
                onClick={() => handleNavigate(item.id)}
              />
            );
          })}
        </nav>
      </aside>

      <main
        className={`min-w-0 ${
          immersiveEditor
            ? "p-0"
            : "p-9 max-md:p-4 max-md:pb-[calc(104px+env(safe-area-inset-bottom))]"
        }`}
      >
        {screen === "home" && <StartView onNavigate={handleNavigate} />}
        {screen === "create" && (
          <CreateView
            onGenerated={() => {
              setEditingPage(undefined);
              setScreen("loading");
            }}
          />
        )}
        {screen === "loading" && (
          <LoadingView
            onDone={() => {
              setEditingPage(undefined);
              setScreen("editor");
            }}
            onCancel={() => setScreen("create")}
          />
        )}
        {screen === "editor" && (
          <EditorView
            initialPage={editingPage}
            onBack={() => setScreen(editingPage ? "library" : "create")}
            onSaved={() => {
              setEditingPage(undefined);
              setScreen("library");
            }}
          />
        )}
        {screen === "library" && (
          <LibraryView
            onCreate={() => {
              setEditingPage(undefined);
              setScreen("create");
            }}
            onOpenPage={(page) => {
              setEditingPage(page);
              setScreen("editor");
            }}
          />
        )}
        {screen === "materials" && <MaterialsView />}
        {screen === "profile" && <ProfileView />}
      </main>
      {!immersiveEditor && (
        <nav className="fixed bottom-[calc(12px+env(safe-area-inset-bottom))] left-6 right-6 z-30 hidden h-[72px] grid-cols-5 rounded-[28px] border border-white/70 bg-[#fffaf2]/94 px-3 shadow-[0_12px_30px_rgba(94,61,32,0.18)] backdrop-blur-md max-md:grid">
          {navItems.map((item) => {
            const active = screen === item.id || (item.id === "create" && screen === "loading");
            return (
              <NavButton
                key={item.id}
                item={item}
                active={active}
                mode="tab"
                onClick={() => handleNavigate(item.id)}
              />
            );
          })}
        </nav>
      )}
    </div>
  );
}

function NavButton({
  item,
  active,
  mode,
  onClick,
}: {
  item: (typeof navItems)[number];
  active: boolean;
  mode: "side" | "tab";
  onClick: () => void;
}) {
  const Icon = item.icon;

  if (item.central) {
    return (
      <button
        className={`grid place-items-center ${mode === "side" ? "min-h-11 rounded-lg px-4" : "min-h-[72px]"}`}
        onClick={onClick}
        aria-label={item.label}
        title={item.label}
      >
        <span
          className={`grid place-items-center rounded-full shadow-[0_8px_18px_rgba(76,66,52,0.22)] ${
            mode === "side" ? "h-10 w-10" : "-mt-7 h-14 w-14 border border-[#f1d7b4]"
          } ${mode === "tab" ? "bg-[linear-gradient(180deg,#eec894,#d59a60)] text-white shadow-[0_10px_22px_rgba(165,104,52,0.34)]" : active ? "bg-[#5b5446] text-paper" : "bg-[#efe6da] text-ink"}`}
        >
          <Icon size={mode === "side" ? 20 : 22} />
        </span>
      </button>
    );
  }

  return (
    <button
      className={
        mode === "side"
          ? `flex min-h-11 items-center gap-2 whitespace-nowrap rounded-lg px-4 text-left transition ${active ? "bg-[#f0e5d7]" : "hover:bg-[#f8efe4]"}`
          : `relative grid min-h-[72px] place-items-center text-center text-[11px] leading-none transition ${active ? "text-ink" : "text-[#7f7164]"}`
      }
      onClick={onClick}
    >
      <Icon size={mode === "side" ? 16 : 18} className="shrink-0" />
      <span className="whitespace-nowrap">{item.label}</span>
    </button>
  );
}

function StartView({ onNavigate }: { onNavigate: (screen: Screen) => void }) {
  return (
    <section className="grid min-h-[calc(100dvh-112px)] place-items-center max-md:h-[calc(100dvh-120px-env(safe-area-inset-bottom))] max-md:min-h-0 max-md:items-stretch">
      <div className="relative flex min-h-[690px] w-full max-w-[360px] flex-col overflow-hidden rounded-[20px] border border-line bg-[#fffaf4] px-7 pb-7 pt-14 shadow-journal [scrollbar-width:none] [-webkit-overflow-scrolling:touch] [&::-webkit-scrollbar]:hidden max-md:h-full max-md:min-h-0 max-md:max-w-none max-md:overflow-y-auto max-md:px-6 max-md:pb-6 max-md:pt-12">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,rgba(255,255,255,0.95),transparent_38%),linear-gradient(180deg,rgba(255,250,244,0.92),rgba(244,224,202,0.72))]" />
        <div className="relative z-10 text-center">
          <div className="font-song text-[42px] leading-none tracking-[0.18em] max-md:text-[46px]">有一页</div>
          <div className="mx-auto mt-3 w-fit -rotate-6 font-song text-[32px] italic leading-none text-[#b68a60] max-md:text-[36px]">onepage</div>
          <p className="mt-9 text-[15px] font-semibold tracking-[0.12em] max-md:mt-11">AI 智能排版手账</p>
          <p className="mt-3 text-sm tracking-[0.12em] text-muted">让记录，更鲜活温度</p>
        </div>
        <div className="relative z-10 mt-auto h-[260px] max-md:h-[clamp(220px,30dvh,310px)] max-md:min-h-0">
          <div className="absolute bottom-0 left-[-28px] right-[-28px] h-[118px] bg-gradient-to-b from-[#d9b894] to-[#c79a6c]" />
          <div className="absolute bottom-[64px] left-[-4px] h-12 w-24 -rotate-6 rounded-sm border border-[#e4d2bf] bg-[#fff8ef] shadow-[0_10px_0_rgba(216,190,166,0.45)]" />
          <div className="absolute bottom-[82px] left-4 h-12 w-24 -rotate-3 rounded-sm border border-[#e4d2bf] bg-[#fbf1e4]" />
          <div className="absolute bottom-[8px] left-[58px] h-[82px] w-[180px] -rotate-3 rounded-[50%] border border-[#d7c2ad] bg-[#fffaf3]" />
          <div className="absolute bottom-[50px] left-[86px] h-[94px] w-[142px] rotate-3 rounded-sm border border-[#dfcdbb] bg-[#fffdf8]" />
          <div className="absolute bottom-[74px] left-[164px] h-[2px] w-[78px] rotate-[-17deg] rounded-full bg-[#6e6256]" />
          <div className="absolute bottom-[58px] left-[192px] h-[8px] w-[44px] rotate-[-17deg] rounded-full bg-[#8d7f70]" />
          <div className="absolute bottom-[46px] right-[28px] h-[132px] w-[44px] rounded-b-2xl rounded-t-full border border-[#cdbba8] bg-white/45" />
          <div className="absolute bottom-[168px] right-[42px] h-[60px] w-[2px] rotate-[-22deg] bg-[#b98a58]" />
          <div className="absolute bottom-[178px] right-[18px] h-[72px] w-[2px] rotate-[24deg] bg-[#b98a58]" />
          <div className="absolute bottom-[212px] right-[14px] text-[#b98a58]">✣</div>
          <div className="absolute bottom-[196px] right-[58px] text-[#b98a58]">✢</div>
        </div>
        <div className="relative z-10 mt-7 grid gap-3 max-md:mt-6">
          <Button className="min-h-11 w-full rounded-full text-[15px] font-semibold" onClick={() => onNavigate("create")}>
            开始记录
          </Button>
          <Button variant="ghost" className="min-h-10 w-full rounded-full bg-white/88 text-sm shadow-sm" onClick={() => onNavigate("library")}>
            导入手账本
          </Button>
        </div>
      </div>
    </section>
  );
}
