"use client";

import { useEffect, useMemo, useState } from "react";
import { Archive, BookOpen, Download, FileText, Heart, Palette, PenLine, Shield, Sparkles, UserRound } from "lucide-react";
import { getPreferences, updatePreferences } from "@/api/preferences.api";
import type { UserPreferenceResponse } from "@/types/backend";

type Entry = {
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
};

const quickEntries: Entry[] = [
  { label: "我的收藏", icon: Heart },
  { label: "最近创作", icon: PenLine },
  { label: "草稿箱", icon: FileText },
  { label: "导出记录", icon: Download },
];

const settingEntries: Entry[] = [
  { label: "手账本设置", icon: BookOpen },
  { label: "素材偏好", icon: Palette },
  { label: "导出设置", icon: Archive },
  { label: "隐私设置", icon: Shield },
  { label: "关于有一页", icon: Sparkles },
];

const fallbackPalette = ["#FAF6F0", "#C4A882", "#B7BEA3"];

export function ProfileView() {
  const [prefs, setPrefs] = useState<UserPreferenceResponse | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getPreferences()
      .then(setPrefs)
      .catch(() => setPrefs(null));
  }, []);

  const preferenceView = useMemo(() => toPreferenceView(prefs), [prefs]);

  async function handleSave() {
    setSaving(true);
    try {
      const next = await updatePreferences({
        style_preferences: { theme: "healing", layout_style: "minimal" },
        font_preferences: { font: "handwriting", size: "medium" },
        color_preferences: { palette: fallbackPalette },
        behavior_stats: { last_active_screen: "profile" },
      });
      setPrefs(next);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="grid min-h-[calc(100dvh-112px)] place-items-center max-md:h-[calc(100dvh-120px-env(safe-area-inset-bottom))] max-md:min-h-0 max-md:items-stretch">
      <div className="profile-page relative flex min-h-[690px] w-full max-w-[760px] flex-col overflow-hidden rounded-[20px] border border-line bg-[#fffaf4] shadow-journal max-md:h-full max-md:min-h-0 max-md:max-w-none">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_56%_8%,rgba(255,255,255,0.92),transparent_32%),linear-gradient(180deg,rgba(255,250,244,0.96),rgba(246,235,221,0.82))]" />
        <div className="pointer-events-none absolute inset-0 opacity-30 [background-image:radial-gradient(rgba(118,83,52,0.13)_0.55px,transparent_0.7px),radial-gradient(rgba(255,255,255,0.62)_0.55px,transparent_0.8px)] [background-position:0_0,8px_7px] [background-size:18px_18px,22px_22px] [mix-blend-mode:multiply]" />

        <div className="relative z-10 min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-5 pt-6 [scrollbar-width:none] [-webkit-overflow-scrolling:touch] [&::-webkit-scrollbar]:hidden max-md:px-4 max-md:pb-6">
          <header className="relative mb-5">
            <h1 className="font-song text-[34px] font-semibold leading-none tracking-[0.03em] text-[#4F3D2C]">我的</h1>
            <p className="mt-3 text-[13px] leading-6 text-[#7d6d5d]">把手账、素材和偏好都收进自己的小抽屉。</p>
            <div className="pointer-events-none absolute right-5 top-0 h-14 w-14 text-[#b7895e]/52" aria-hidden>
              <span className="absolute left-5 top-6 h-9 w-px -rotate-12 bg-current" />
              <span className="absolute left-8 top-1 h-11 w-px rotate-12 bg-current" />
              <span className="absolute left-2 top-1 text-base">✿</span>
              <span className="absolute right-1 top-5 text-base">✿</span>
            </div>
          </header>

          <section className="rounded-[18px] border border-[#eadcc9]/55 bg-[#fffaf3]/62 p-4 shadow-[0_10px_24px_rgba(111,82,51,0.06),inset_0_1px_0_rgba(255,255,255,0.72)]">
            <div className="flex items-center gap-4">
              <div className="grid h-[68px] w-[68px] shrink-0 place-items-center rounded-full border border-[#eadcc9] bg-[linear-gradient(180deg,#f7dec0,#d9a86c)] text-white shadow-[0_8px_18px_rgba(111,82,51,0.16)]">
                <UserRound size={32} strokeWidth={1.8} />
              </div>
              <div className="min-w-0">
                <h2 className="font-song text-[24px] font-semibold leading-none text-[#4f3d2c]">今天也要加油鸭</h2>
                <p className="mt-2 text-xs text-[#9a8a78]">ID: onepage2024</p>
                <p className="mt-2 text-[13px] leading-5 text-[#6f6257]">记录生活，发现每一页的美好</p>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-3 rounded-[16px] bg-[#fffdf8]/56 py-3 text-center">
              <Stat value="56" label="手账页" />
              <Stat value="3" label="手账本" />
              <Stat value="128" label="收藏素材" />
            </div>
          </section>

          <section className="mt-3 rounded-[18px] border border-[#eadcc9]/42 bg-[#fffaf3]/42 p-4 shadow-[0_6px_18px_rgba(111,82,51,0.035),inset_0_1px_0_rgba(255,255,255,0.52)]">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-song text-[22px] font-semibold leading-none text-[#4f3d2c]">我的偏好</h2>
              <button
                className="rounded-full border border-[#d8c7b2] bg-[#fffdf8]/68 px-3 py-1.5 text-xs text-[#6f6257] shadow-[0_5px_12px_rgba(111,82,51,0.05)]"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? "保存中..." : "编辑偏好"}
              </button>
            </div>
            <div className="mt-4 grid gap-3 text-sm">
              <PreferenceRow label="风格偏好" values={preferenceView.styles} />
              <PreferenceRow label="字体偏好" values={preferenceView.fonts} />
              <div className="flex items-center justify-between gap-4">
                <span className="shrink-0 text-[#8a7a68]">常用配色</span>
                <div className="flex min-w-0 flex-wrap justify-end gap-2">
                  {preferenceView.palette.map((color) => (
                    <span key={color} className="h-5 w-5 rounded-full border border-white/80 shadow-[0_2px_6px_rgba(111,82,51,0.12)]" style={{ backgroundColor: color }} />
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section className="mt-3 grid grid-cols-2 gap-3">
            {quickEntries.map((entry) => (
              <EntryCard key={entry.label} entry={entry} />
            ))}
          </section>

          <section className="mt-3 rounded-[18px] border border-[#eadcc9]/36 bg-[#fffaf3]/34 p-2 shadow-[0_5px_16px_rgba(111,82,51,0.028)]">
            {settingEntries.map((entry) => (
              <SettingRow key={entry.label} entry={entry} />
            ))}
          </section>
        </div>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="font-song text-[24px] font-semibold leading-none text-[#4f3d2c]">{value}</div>
      <div className="mt-2 text-xs text-[#8a7a68]">{label}</div>
    </div>
  );
}

function PreferenceRow({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="shrink-0 text-[#8a7a68]">{label}</span>
      <div className="flex min-w-0 flex-wrap justify-end gap-1.5">
        {values.map((value) => (
          <span key={value} className="rounded-full border border-[#eadcc9]/70 bg-[#fffdf8]/54 px-2.5 py-1 text-xs text-[#6f6257]">
            {value}
          </span>
        ))}
      </div>
    </div>
  );
}

function EntryCard({ entry }: { entry: Entry }) {
  const Icon = entry.icon;
  return (
    <button className="flex min-h-16 items-center gap-3 rounded-[16px] border border-[#eadcc9]/45 bg-[#fffaf3]/46 px-3 text-left text-[#5f5146] shadow-[0_6px_16px_rgba(111,82,51,0.035)]">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[#ead4b5]/68 text-[#7d6043]">
        <Icon size={18} />
      </span>
      <span className="text-sm font-medium">{entry.label}</span>
    </button>
  );
}

function SettingRow({ entry }: { entry: Entry }) {
  const Icon = entry.icon;
  return (
    <button className="flex min-h-11 w-full items-center justify-between rounded-[14px] px-2.5 text-left text-sm text-[#5f5146] hover:bg-[#fffdf8]/50">
      <span className="flex items-center gap-3">
        <Icon size={17} className="text-[#8a7a68]" />
        {entry.label}
      </span>
      <span className="text-[#c5ad93]">›</span>
    </button>
  );
}

function toPreferenceView(prefs: UserPreferenceResponse | null) {
  const style = prefs?.style_preferences ?? {};
  const font = prefs?.font_preferences ?? {};
  const color = prefs?.color_preferences ?? {};
  const palette = Array.isArray(color.palette) ? color.palette.map(String) : fallbackPalette;

  return {
    styles: [styleLabel(style.theme), layoutLabel(style.layout_style)].filter(Boolean),
    fonts: [fontLabel(font.font ?? font.primary), sizeLabel(font.size)].filter(Boolean),
    palette: palette.length ? palette.slice(0, 3) : fallbackPalette,
  };
}

function styleLabel(value: unknown) {
  const map: Record<string, string> = {
    healing: "治愈风",
    minimal: "极简风",
    vintage: "复古风",
    cute: "可爱风",
  };
  return map[String(value ?? "healing")] ?? "治愈风";
}

function layoutLabel(value: unknown) {
  const map: Record<string, string> = {
    minimal: "极简排版",
    collage: "拼贴排版",
    free: "自由排版",
  };
  return map[String(value ?? "minimal")] ?? "极简排版";
}

function fontLabel(value: unknown) {
  const text = String(value ?? "handwriting");
  if (text.includes("Kaiti") || text === "handwriting") return "手写体";
  if (text.includes("Song") || text === "serif") return "宋体";
  return "自然字体";
}

function sizeLabel(value: unknown) {
  const map: Record<string, string> = {
    small: "小号",
    medium: "中号",
    large: "大号",
  };
  return map[String(value ?? "medium")] ?? "中号";
}
