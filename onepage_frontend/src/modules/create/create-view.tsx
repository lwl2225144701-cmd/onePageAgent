"use client";

import { Camera, Flower2, Mic, Type } from "lucide-react";
import { createAiTask } from "@/api/ai-tasks.api";
import { uploadAudio, uploadImage } from "@/api/uploads.api";
import { getWeather } from "@/api/weather.api";
import { useAITaskStore } from "@/stores/ai-task-store";
import { useCreateStore } from "@/stores/create-store";
import { Button } from "@/shared/ui/button";
import { useEffect } from "react";

const moods = ["开心", "平静", "放松", "感动", "兴奋"];

export function CreateView({ onGenerated }: { onGenerated: () => void }) {
  const { text, mood, imageFiles, weather, setText, setMood, setImageFiles, setImageUrls, setWeather } = useCreateStore();
  const setTask = useAITaskStore((state) => state.setTask);

  useEffect(() => {
    if (!("geolocation" in navigator)) return;
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const currentWeather = await getWeather(position.coords.latitude, position.coords.longitude);
          setWeather(currentWeather);
        } catch {
          // keep local fallback weather
        }
      },
      () => undefined,
      { timeout: 2000 }
    );
  }, [setWeather]);

  async function handleGenerate() {
    onGenerated();
    try {
      const uploaded = await Promise.all(imageFiles.map((file) => uploadImage(file)));
      const imageUrls = uploaded.map((item) => item.file_url);
      setImageUrls(imageUrls);
      const task = await createAiTask({
        text,
        mood,
        image_urls: imageUrls,
        weather,
        page_date: "2024-06-01"
      });
      setTask(task.task_id);
    } catch {
      setTask("mock-task");
    }
  }

  return (
    <section className="grid min-h-[calc(100vh-72px)] place-items-center">
      <div className="min-h-[720px] w-full max-w-[390px] rounded-[18px] border border-line bg-paper/95 p-6 shadow-journal">
        <header className="flex items-center justify-between">
          <strong>2024.06.01 周六</strong>
          <span className="text-sm text-muted">26°C 晴 ☀</span>
        </header>
        <div className="my-7 grid grid-cols-4 gap-2">
          <Tool icon={Type} label="文字输入" active />
          <label className="grid min-h-14 place-items-center rounded-lg border border-line bg-[#f4eadc] px-2 text-center text-xs">
            <Mic size={18} />
            语音输入
            <input
              className="hidden"
              type="file"
              accept="audio/*"
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                try {
                  await uploadAudio(file);
                } catch {
                  // keep fallback flow when backend unavailable
                }
              }}
            />
          </label>
          <label className="grid min-h-14 place-items-center rounded-lg border border-line bg-[#f4eadc] px-2 text-center text-xs">
            <Camera size={18} />
            拍照上传
            <input
              className="hidden"
              type="file"
              accept="image/*"
              multiple
              onChange={(event) => setImageFiles(Array.from(event.target.files ?? []).slice(0, 4))}
            />
          </label>
          <Tool icon={Flower2} label="选择素材" />
        </div>
        <label className="mb-2 block font-semibold">今天去了海边，阳光很温柔，海风微咸。</label>
        <textarea
          className="min-h-40 w-full resize-none rounded-lg border border-line bg-white/75 p-4 leading-8 outline-none"
          maxLength={300}
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
        <div className="-mt-7 pr-3 text-right text-xs text-muted">{text.length}/300</div>
        <div className="my-6 flex min-h-20 gap-2">
          {imageFiles.map((file) => (
            <img
              key={`${file.name}-${file.lastModified}`}
              className="h-[72px] w-[72px] rounded-lg border-[3px] border-white object-cover shadow"
              src={URL.createObjectURL(file)}
              alt="上传预览"
            />
          ))}
        </div>
        <div className="grid grid-cols-5 gap-2">
          {moods.map((item) => (
            <button
              key={item}
              className={`grid min-h-16 place-items-center rounded-lg text-sm ${mood === item ? "bg-[#f1e4d3] text-ink" : "text-muted"}`}
              onClick={() => setMood(item)}
            >
              <span>♡</span>
              {item}
            </button>
          ))}
        </div>
        <Button className="mt-8 w-full" onClick={handleGenerate} disabled={!text.trim()}>
          生成手账
        </Button>
        <p className="mt-2 text-center text-xs text-muted">天气接口：{String(weather.weather ?? "晴")} · AI 任务将携带 weather 字段</p>
      </div>
    </section>
  );
}

function Tool({ icon: Icon, label, active }: { icon: React.ComponentType<{ size?: number }>; label: string; active?: boolean }) {
  return (
    <button className={`grid min-h-14 place-items-center rounded-lg border border-line px-2 text-xs ${active ? "bg-[#e6d7c3]" : "bg-[#f4eadc]"}`}>
      <Icon size={18} />
      {label}
    </button>
  );
}
