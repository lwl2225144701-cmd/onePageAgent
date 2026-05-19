"use client";

import { useState } from "react";
import { BookOpen, Flower2, Home, Library, UserRound } from "lucide-react";
import { CreateView } from "@/modules/create/create-view";
import { EditorView } from "@/modules/editor/editor-view";
import { LibraryView } from "@/modules/journal/library-view";
import { LoadingView } from "@/modules/ai/loading-view";
import { MaterialsView } from "@/modules/materials/materials-view";
import { ProfileView } from "@/modules/profile/profile-view";
import { Button } from "@/shared/ui/button";

type Screen = "home" | "create" | "loading" | "editor" | "library" | "materials" | "profile";

const navItems: Array<{ id: Screen; label: string; icon: React.ComponentType<{ size?: number }> }> = [
  { id: "home", label: "首页", icon: Home },
  { id: "create", label: "创作", icon: BookOpen },
  { id: "library", label: "手账本", icon: Library },
  { id: "materials", label: "素材库", icon: Flower2 },
  { id: "profile", label: "我的", icon: UserRound }
];

export default function HomePage() {
  const [screen, setScreen] = useState<Screen>("home");

  return (
    <div className="grid min-h-screen grid-cols-[220px_1fr] bg-warm-surface text-ink max-md:grid-cols-1">
      <aside className="sticky top-0 h-screen border-r border-line/80 bg-paper/85 px-5 py-10 backdrop-blur max-md:static max-md:h-auto max-md:py-4">
        <div className="mb-14 max-md:hidden">
          <div className="font-song text-[32px] leading-tight">
            有一页
            <br />
            <span className="text-2xl italic">onepage</span>
          </div>
          <p className="mt-5 leading-8 text-muted">记录生活，发现每一页的美好。</p>
        </div>
        <nav className="grid gap-2 max-md:grid-cols-5">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`flex min-h-11 items-center gap-2 rounded-lg px-4 text-left transition max-md:justify-center max-md:px-2 max-md:text-xs ${
                  screen === item.id ? "bg-[#f0e5d7]" : "hover:bg-[#f8efe4]"
                }`}
                onClick={() => setScreen(item.id)}
              >
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="min-w-0 p-9 max-md:p-4">
        {screen === "home" && <StartView onNavigate={setScreen} />}
        {screen === "create" && <CreateView onGenerated={() => setScreen("loading")} />}
        {screen === "loading" && <LoadingView onDone={() => setScreen("editor")} onCancel={() => setScreen("create")} />}
        {screen === "editor" && <EditorView onBack={() => setScreen("create")} onSaved={() => setScreen("library")} />}
        {screen === "library" && <LibraryView onCreate={() => setScreen("create")} />}
        {screen === "materials" && <MaterialsView />}
        {screen === "profile" && <ProfileView />}
      </main>
    </div>
  );
}

function StartView({ onNavigate }: { onNavigate: (screen: Screen) => void }) {
  return (
    <section className="grid min-h-[calc(100vh-72px)] place-items-center">
      <div className="grid min-h-[620px] w-full max-w-[980px] grid-cols-[minmax(280px,380px)_1fr] items-end gap-12 rounded-lg border border-line bg-paper/75 p-14 shadow-journal max-lg:grid-cols-1 max-lg:p-8">
        <div className="self-center text-center">
          <div className="font-song text-[42px] leading-tight">
            有一页
            <br />
            <span className="text-2xl italic">onepage</span>
          </div>
          <p className="mt-7 font-semibold">AI 智能排版手账</p>
          <p className="mt-4 text-muted">让记录、照片和心情自动生成温柔的一页。</p>
          <Button className="mt-10 w-full" onClick={() => onNavigate("create")}>
            开始记录
          </Button>
          <Button variant="ghost" className="mt-3 w-full" onClick={() => onNavigate("library")}>
            导入手账本
          </Button>
        </div>
        <div className="relative h-[360px] border-b-[20px] border-[#d6b389] max-lg:h-[220px]">
          <div className="absolute bottom-5 left-16 h-[90px] w-[270px] -rotate-6 border border-line bg-paper shadow-[18px_18px_0_#f1e3d1,34px_35px_0_#ead8c1]" />
          <div className="absolute bottom-3 right-32 h-36 w-14 rounded-t-full rounded-b-lg bg-gradient-to-b from-[#fbf8f2] to-[#e8dbc9]" />
          <div className="absolute bottom-3 left-2 h-12 w-20 rounded-b-full border-2 border-[#e6d5c2] bg-[#fff8ef]" />
        </div>
      </div>
    </section>
  );
}

function EmptyView({ title, text }: { title: string; text: string }) {
  return (
    <section className="grid min-h-[calc(100vh-72px)] place-items-center text-center">
      <div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="mt-3 text-muted">{text}</p>
      </div>
    </section>
  );
}
