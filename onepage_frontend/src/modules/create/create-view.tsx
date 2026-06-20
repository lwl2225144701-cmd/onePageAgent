"use client";

import Image from "next/image";
import { Camera, CircleHelp, Cloud, CloudFog, CloudLightning, CloudRain, CloudSun, Flower2, MapPin, Mic, Snowflake, Sun, Type, Wind } from "lucide-react";
import { createAiTask } from "@/api/ai-tasks.api";
import { uploadAudio, uploadImage } from "@/api/uploads.api";
import { getWeather } from "@/api/weather.api";
import { useAITaskStore } from "@/stores/ai-task-store";
import { useCreateStore } from "@/stores/create-store";
import { Button } from "@/shared/ui/button";
import type { EnvironmentContext, WeatherIconKey, WeatherResponse } from "@/types/backend";
import { useEffect, useMemo, useState } from "react";

const moods = [
  { label: "开心", emoji: "😊" },
  { label: "平静", emoji: "😌" },
  { label: "放松", emoji: "😮‍💨" },
  { label: "感动", emoji: "🥹" },
  { label: "兴奋", emoji: "🤩" },
  { label: "甜蜜", emoji: "🥰" },
  { label: "发呆", emoji: "🤔" },
  { label: "困倦", emoji: "😴" },
  { label: "低落", emoji: "😔" },
  { label: "难过", emoji: "😢" },
  { label: "焦虑", emoji: "😟" },
  { label: "愤怒", emoji: "😡" },
];

const journalPaperStyle = {
  backgroundImage:
    "linear-gradient(180deg, rgba(255,252,247,0.88), rgba(250,242,231,0.74)), repeating-linear-gradient(180deg, transparent 0, transparent 31px, rgba(183,151,119,0.13) 32px), radial-gradient(rgba(128,91,58,0.08) 0.5px, transparent 0.7px)",
  backgroundSize: "auto, auto, 18px 18px",
} satisfies React.CSSProperties;

function readWeatherText(weather: Record<string, unknown>) {
  const value = String(weather.weather ?? weather.text ?? "").trim();
  return value && value !== "unknown" ? value : "";
}

function readTemperature(weather: Record<string, unknown>) {
  const value = weather.temperature ?? weather.temperature_celsius;
  return typeof value === "number" ? Math.round(value) : null;
}

const weatherIcons: Record<WeatherIconKey, React.ComponentType<{ size?: number; className?: string }>> = {
  sunny: Sun,
  cloudy: CloudSun,
  overcast: Cloud,
  rain: CloudRain,
  thunderstorm: CloudLightning,
  snow: Snowflake,
  sleet: CloudRain,
  fog: CloudFog,
  dust: Wind,
  wind: Wind,
  unknown: CircleHelp,
};

type LookupStatus = "loading" | "ready" | "unavailable";

function localDateContext(date: Date) {
  const pad = (value: number) => String(value).padStart(2, "0");
  const dateText = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  return {
    date: dateText,
    displayDate: dateText.replaceAll("-", "."),
    time: `${pad(date.getHours())}:${pad(date.getMinutes())}`,
    weekday: ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][date.getDay()],
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
  };
}

function buildEnvironmentContext(
  date: ReturnType<typeof localDateContext>,
  weather: Record<string, unknown>,
  weatherReady: boolean,
): EnvironmentContext {
  const source = weatherReady && weather.source === "amap" ? "amap" : "unavailable";
  return {
    date: date.date,
    time: date.time,
    weekday: date.weekday,
    timezone: date.timezone,
    province: String(weather.province ?? ""),
    city: String(weather.city ?? ""),
    district: String(weather.district ?? ""),
    location: String(weather.location ?? ""),
    adcode: String(weather.adcode ?? ""),
    weather: weatherReady ? readWeatherText(weather) || "unknown" : "unknown",
    temperature: weatherReady ? readTemperature(weather) : null,
    humidity: weatherReady && typeof weather.humidity === "number" ? weather.humidity : null,
    icon_key: weatherReady ? (String(weather.icon_key ?? "unknown") as WeatherIconKey) : "unknown",
    report_time: weatherReady ? String(weather.report_time ?? "") : "",
    source,
  };
}

export function CreateView({ onGenerated }: { onGenerated: () => void }) {
  const { text, mood, imageFiles, weather, setText, setMood, setImageFiles, setImageUrls, setWeather } = useCreateStore();
  const setTask = useAITaskStore((state) => state.setTask);
  const dateContext = useMemo(() => localDateContext(new Date()), []);
  const [locationStatus, setLocationStatus] = useState<LookupStatus>("loading");
  const [weatherStatus, setWeatherStatus] = useState<LookupStatus>("loading");
  const weatherText = readWeatherText(weather);
  const temperature = readTemperature(weather);
  const locationText = String(weather.location ?? "").trim();
  const iconKey = String(weather.icon_key ?? "unknown") as WeatherIconKey;
  const WeatherIcon = weatherIcons[iconKey] ?? weatherIcons.unknown;

  useEffect(() => {
    let active = true;
    if (!("geolocation" in navigator)) {
      setLocationStatus("unavailable");
      setWeatherStatus("unavailable");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const currentWeather = await getWeather(position.coords.latitude, position.coords.longitude);
          if (!active) return;
          setWeather(currentWeather);
          setLocationStatus(currentWeather.location ? "ready" : "unavailable");
          setWeatherStatus(currentWeather.source === "amap" && currentWeather.weather !== "unknown" ? "ready" : "unavailable");
        } catch {
          if (!active) return;
          setLocationStatus("unavailable");
          setWeatherStatus("unavailable");
        }
      },
      () => {
        if (!active) return;
        setLocationStatus("unavailable");
        setWeatherStatus("unavailable");
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 },
    );
    return () => {
      active = false;
    };
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
        page_date: dateContext.date,
        environment_context: buildEnvironmentContext(dateContext, weather, weatherStatus === "ready"),
      });
      setTask(task.task_id);
    } catch {
      setTask("mock-task");
    }
  }

  return (
    <section className="grid min-h-[calc(100dvh-112px)] place-items-center max-md:h-[calc(100dvh-120px-env(safe-area-inset-bottom))] max-md:min-h-0 max-md:items-stretch">
      <div className="flex w-full max-w-[390px] flex-col overflow-hidden rounded-[20px] border border-line bg-[#fffaf4]/95 p-5 shadow-journal [scrollbar-width:none] [-webkit-overflow-scrolling:touch] [&::-webkit-scrollbar]:hidden max-md:h-full max-md:min-h-0 max-md:max-w-none max-md:overflow-y-auto max-md:overscroll-contain">
        <header className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-left text-[22px] font-semibold leading-none">{dateContext.displayDate} {dateContext.weekday}</div>
            <div className="flex items-center gap-2 text-sm text-muted">
              {weatherStatus === "ready" ? (
                <>
                  {temperature !== null ? <span>{temperature}°C</span> : null}
                  <span>{weatherText}</span>
                  <WeatherIcon size={16} className="text-[#b7834f]" />
                </>
              ) : (
                <span>{weatherStatus === "loading" ? "天气获取中" : "天气暂不可用"}</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted">
            <MapPin size={14} />
            <span>{locationStatus === "ready" ? locationText : locationStatus === "loading" ? "正在获取定位" : "未获取定位"}</span>
          </div>
        </header>
        <div className="mb-5 mt-6 grid grid-cols-4 gap-3.5 max-md:mb-5 max-md:mt-7">
          <Tool icon={Type} label="文字输入" active />
          <label className="grid place-items-center gap-2 text-center text-xs font-medium text-[#7d7064]">
            <span className="grid h-10 w-[52px] place-items-center rounded-full border border-[#eadcc9]/45 bg-[#fbf5ed]/72 text-[#7d7064] shadow-[0_4px_10px_rgba(111,82,51,0.035)]">
              <Mic size={18} strokeWidth={1.8} />
            </span>
            <span className="whitespace-nowrap">语音输入</span>
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
          <label className="grid place-items-center gap-2 text-center text-xs font-medium text-[#7d7064]">
            <span className="grid h-10 w-[52px] place-items-center rounded-full border border-[#eadcc9]/45 bg-[#fbf5ed]/72 text-[#7d7064] shadow-[0_4px_10px_rgba(111,82,51,0.035)]">
              <Camera size={18} strokeWidth={1.8} />
            </span>
            <span className="whitespace-nowrap">拍照上传</span>
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
        <div className="relative rounded-[18px] border border-[#eadcc9]/58 bg-[#fffaf0]/76 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.76),0_8px_18px_rgba(111,82,51,0.045)]" style={journalPaperStyle}>
          <textarea
            className="min-h-[168px] w-full resize-none bg-transparent text-[15px] leading-8 text-[#4f3d2c] outline-none placeholder:text-[#a99b8e]/82 max-md:min-h-[198px]"
            maxLength={300}
            value={text}
            placeholder={"今天去了海边，\n阳光照在脸颊，海浪很轻很轻，\n和朋友一起散步、拍照，\n度过了一个很治愈的周末~"}
            onChange={(event) => setText(event.target.value)}
          />
          <div className="absolute bottom-3 right-4 text-[11px] text-[#9a8a78]/70">{text.length}/300</div>
        </div>
        {imageFiles.length ? (
          <div className="mt-4 flex gap-2">
            {imageFiles.map((file) => (
              <Image
                key={`${file.name}-${file.lastModified}`}
                className="h-[72px] w-[72px] rounded-lg border-[3px] border-white object-cover shadow"
                src={URL.createObjectURL(file)}
                alt="上传预览"
                width={72}
                height={72}
                unoptimized
              />
            ))}
          </div>
        ) : null}
        <div className="mb-2.5 mt-5 flex items-baseline gap-2">
          <span className="text-sm font-semibold text-[#4f3d2c]">选择心情</span>
          <span className="text-[11px] text-[#9a8a78]/72">今天是什么感觉？</span>
        </div>
        <div className="relative min-w-0 overflow-hidden">
          <div className="flex snap-x gap-2 overflow-x-auto pb-1 [overscroll-behavior-x:contain] [scrollbar-width:none] [-webkit-overflow-scrolling:touch] [&::-webkit-scrollbar]:hidden">
            {moods.map((item) => (
              <button
                key={item.label}
                className={`grid min-h-[66px] w-[54px] shrink-0 snap-start place-items-center rounded-[16px] text-[11px] transition ${mood === item.label ? "text-[#4f3d2c]" : "text-[#8a7a68]"}`}
                onClick={() => setMood(item.label)}
              >
                <span
                  className={`grid h-10 w-10 place-items-center rounded-full text-[22px] leading-none transition ${
                    mood === item.label
                      ? "-rotate-3 border border-[#d8b994]/70 bg-[#f1dcc5] shadow-[0_6px_14px_rgba(168,126,92,0.14),inset_0_1px_0_rgba(255,255,255,0.65)]"
                      : "border border-[#eadcc9]/32 bg-[#fbf5ed]/76 shadow-[inset_0_1px_0_rgba(255,255,255,0.55)]"
                  }`}
                >
                  {item.emoji}
                </span>
                <span>{item.label}</span>
              </button>
            ))}
          </div>
          <div className="pointer-events-none absolute bottom-1 right-0 top-0 w-5 bg-gradient-to-l from-[#fffaf4]/78 to-transparent" />
        </div>
        <Button className="mt-5 min-h-12 w-full rounded-full bg-gradient-to-b from-[#c8a37e] to-[#ab7b55] text-base font-semibold shadow-[0_10px_22px_rgba(139,93,52,0.18)] max-md:min-h-14" onClick={handleGenerate} disabled={!text.trim()}>
          生成我的一页
        </Button>
      </div>
    </section>
  );
}

function Tool({ icon: Icon, label, active }: { icon: React.ComponentType<{ size?: number }>; label: string; active?: boolean }) {
  return (
    <button className={`grid place-items-center gap-2 text-center text-xs font-medium ${active ? "text-[#4f3d2c]" : "text-[#7d7064]"}`}>
      <span
        className={`grid h-10 w-[52px] place-items-center rounded-full border shadow-[0_4px_10px_rgba(111,82,51,0.035)] ${
          active ? "border-[#d9bfa2]/70 bg-[#efe2d2] text-[#5d4530]" : "border-[#eadcc9]/45 bg-[#fbf5ed]/72 text-[#7d7064]"
        }`}
      >
        <Icon size={18} />
      </span>
      <span className="whitespace-nowrap">{label}</span>
    </button>
  );
}
