"use client";

import { useEffect, useState } from "react";
import { getPreferences, updatePreferences } from "@/api/preferences.api";
import type { UserPreferenceResponse } from "@/types/backend";
import { Button } from "@/shared/ui/button";

export function ProfileView() {
  const [prefs, setPrefs] = useState<UserPreferenceResponse | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getPreferences()
      .then(setPrefs)
      .catch(() => setPrefs(null));
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      const next = await updatePreferences({
        style_preferences: { theme: "healing" },
        font_preferences: { primary: "Kaiti SC" },
        color_preferences: { primary: "#9b7652" },
        behavior_stats: { last_active_screen: "profile" }
      });
      setPrefs(next);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mx-auto w-full max-w-[760px] rounded-lg border border-line bg-paper/80 p-8">
      <h1 className="text-2xl font-semibold">我的偏好</h1>
      <p className="mt-3 text-muted">已对接 `GET /preferences` 与 `PUT /preferences`。</p>
      <div className="mt-6 grid gap-4 rounded-lg border border-line bg-white/75 p-5 text-sm">
        <div>style_preferences: {JSON.stringify(prefs?.style_preferences ?? {})}</div>
        <div>font_preferences: {JSON.stringify(prefs?.font_preferences ?? {})}</div>
        <div>color_preferences: {JSON.stringify(prefs?.color_preferences ?? {})}</div>
        <div>behavior_stats: {JSON.stringify(prefs?.behavior_stats ?? {})}</div>
      </div>
      <Button className="mt-6" onClick={handleSave} disabled={saving}>
        {saving ? "保存中..." : "更新偏好"}
      </Button>
    </section>
  );
}
