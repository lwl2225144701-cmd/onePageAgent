"use client";

import { useEffect } from "react";
import { getAiTask, subscribeAiTask } from "@/api/ai-tasks.api";
import { useAITaskStore } from "@/stores/ai-task-store";
import { useCreateStore } from "@/stores/create-store";
import { useEditorStore } from "@/stores/editor-store";
import { Button } from "@/shared/ui/button";
import { fallbackLayout } from "@/modules/editor/fallback-layout";

const stages = [
  { limit: 22, label: "内容理解", text: "正在理解今天的记录", note: "把你写下的片段轻轻整理好" },
  { limit: 44, label: "风格匹配", text: "正在匹配心情和风格", note: "为这一页挑选合适的语气和色调" },
  { limit: 66, label: "素材挑选", text: "正在挑选合适的素材", note: "寻找贴纸、纸张和小装饰" },
  { limit: 88, label: "版式整理", text: "正在整理这一页的版式", note: "把文字、照片和心情放进版式里" },
  { limit: 101, label: "细节润色", text: "正在做最后润色", note: "调整留白、层级和细节温度" },
];

const flowSteps = ["内容理解", "素材匹配", "排版生成"];

export function LoadingView({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const { taskId, progress, stepName, setProgress, setResult } = useAITaskStore();
  const { text, mood } = useCreateStore();
  const setLayout = useEditorStore((state) => state.setLayout);
  const stage = stages.find((item) => progress < item.limit) ?? stages[stages.length - 1];
  const previewTitle = buildPreviewTitle(text, mood);
  const flowStep = getFlowStep(progress);
  const statusText = toGentleStatus(stepName) || stage.text;

  useEffect(() => {
    if (!taskId) return;
    if (taskId === "mock-task") {
      const timer = window.setInterval(() => {
        setProgress(Math.min(progress + 18, 100), "本地生成演示", progress + 18 >= 100 ? "completed" : "processing");
      }, 260);
      return () => window.clearInterval(timer);
    }

    const source = subscribeAiTask(taskId);
    source.onmessage = (event) => {
      const data = JSON.parse(event.data) as { progress: number; step_name: string; status: string };
      setProgress(data.progress, data.step_name, data.status as never);
    };
    source.onerror = () => source.close();
    return () => source.close();
  }, [taskId, progress, setProgress]);

  useEffect(() => {
    if (progress < 100) return;
    async function finish() {
      if (taskId && taskId !== "mock-task") {
        const detail = await getAiTask(taskId);
        if (detail.result_json) {
          setResult(detail.result_json);
          setLayout(detail.result_json);
        }
      } else {
        setResult(fallbackLayout);
        setLayout(fallbackLayout);
      }
      window.setTimeout(onDone, 260);
    }
    finish().catch(() => {
      setResult(fallbackLayout);
      setLayout(fallbackLayout);
      onDone();
    });
  }, [progress, taskId, onDone, setLayout, setResult]);

  return (
    <section className="grid min-h-[calc(100dvh-112px)] place-items-center max-md:h-[calc(100dvh-120px-env(safe-area-inset-bottom))] max-md:min-h-0 max-md:items-stretch">
      <div className="relative flex min-h-[720px] w-full max-w-[390px] flex-col overflow-hidden rounded-[20px] border border-[#eadcc9]/70 bg-[#fffaf4]/95 p-5 text-center shadow-journal [scrollbar-width:none] [-webkit-overflow-scrolling:touch] [&::-webkit-scrollbar]:hidden max-md:h-full max-md:min-h-0 max-md:max-w-none max-md:overflow-y-auto">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_52%_8%,rgba(255,255,255,0.9),transparent_34%),linear-gradient(180deg,rgba(255,250,244,0.96),rgba(246,235,221,0.82))]" />
        <div className="pointer-events-none absolute inset-0 opacity-25 [background-image:radial-gradient(rgba(118,83,52,0.12)_0.55px,transparent_0.7px)] [background-size:18px_18px]" />

        <div className="relative z-10">
          <div className="onepage-ai-orb relative mx-auto mb-2.5 grid h-11 w-11 place-items-center rounded-full border border-[#eadcc9]/70 bg-[#fffdf8]/70 text-[#b7895e] shadow-[0_8px_18px_rgba(111,82,51,0.08)]">
            <span className="onepage-ai-star">✦</span>
          </div>
          <h1 className="font-song text-[24px] font-semibold leading-none text-[#4f3d2c]">AI 正在为你整理这一页</h1>
          <p className="mt-3 text-sm leading-6 text-[#7d6d5d]">{statusText}</p>
        </div>

        <div className="relative z-10 mx-auto mb-3 mt-4 h-[402px] w-[286px] overflow-hidden rounded-[24px] border border-[#eadcc9]/70 bg-[#fffaf0] p-3.5 shadow-[0_18px_34px_rgba(111,82,51,0.12),inset_0_1px_0_rgba(255,255,255,0.86)]">
          <div className="pointer-events-none absolute inset-0 opacity-35 [background-image:radial-gradient(rgba(128,91,58,0.09)_0.5px,transparent_0.7px),repeating-linear-gradient(180deg,transparent_0,transparent_31px,rgba(183,151,119,0.11)_32px)] [background-size:18px_18px,auto]" />
          <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(110deg,transparent_0%,rgba(255,255,255,0.3)_48%,transparent_72%)] opacity-70 animate-pulse" />
          <div className="relative h-full overflow-hidden rounded-[20px] bg-[#fffdf8]/62 px-5 py-5 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.62)]">
            <div className="absolute left-0 top-0 h-full w-3 bg-[#ead4b5]/22" />
            <div className="absolute left-6 top-4 h-5 w-14 -rotate-6 rounded-sm bg-[#edd9bd]/64 shadow-[0_3px_8px_rgba(111,82,51,0.04)]" />
            <div className="absolute right-7 top-6 h-4 w-11 rotate-6 rounded-sm bg-[#e9cdb0]/42" />
            <div className="pt-4">
              <div className="max-w-[190px] font-song text-[23px] font-semibold leading-snug text-[#4f3d2c]">{previewTitle}</div>
              <div className="mt-1 flex items-center gap-2 text-[10px] tracking-[0.14em] text-[#b0a191]">
                <span>onepage draft</span>
                <span className="h-px w-9 bg-[#d8c7b2]/55" />
              </div>
            </div>

            <div className="relative mt-3 h-[174px]">
              <div className="absolute left-1 top-4 h-[118px] w-[170px] rotate-[-2deg] rounded-[18px] bg-[#ead4b5]/24" />
              <div className="onepage-breathe-item onepage-breathe-main absolute left-2 top-2 h-[146px] w-[118px] rounded-sm border-[7px] border-white bg-[linear-gradient(160deg,#efe1cc,#c7d4c0)] shadow-[0_10px_18px_rgba(111,82,51,0.13)]">
                <div className="m-2 h-2 w-14 rounded-full bg-white/42" />
                <div className="mx-auto mt-11 h-9 w-9 rounded-full bg-white/28" />
                <div className="absolute bottom-2 left-3 h-1.5 w-12 rounded-full bg-white/34" />
              </div>
              <div className="onepage-breathe-item onepage-breathe-side absolute right-3 top-[56px] h-[104px] w-[84px] rounded-sm border-[6px] border-white bg-[linear-gradient(155deg,#f4d6c5,#d7b58d)] shadow-[0_8px_16px_rgba(111,82,51,0.12)]">
                <div className="m-2 h-2 w-9 rounded-full bg-white/38" />
                <div className="mx-auto mt-7 h-6 w-11 rounded-full bg-white/28" />
              </div>
              <div className="onepage-mood-tag absolute right-1 top-[30px] rotate-6 rounded-full bg-[#ead4b5]/82 px-2.5 py-1 text-[11px] text-[#7d6043] shadow-[0_4px_10px_rgba(111,82,51,0.08)]">
                {mood || "平静"}
              </div>
              <div className="absolute left-[118px] top-[134px] -rotate-3 rounded-full bg-[#b7bea3]/34 px-2.5 py-1 text-[10px] text-[#6f715e]">今日心情</div>
              <div className="onepage-breathe-item onepage-breathe-top absolute left-[142px] top-0 text-sm text-[#c99566]/70">✿</div>
            </div>

            <div className="mt-1.5 grid gap-2.5 pl-1 pr-2">
              <div className="mb-0.5 flex items-center gap-2 text-[10px] text-[#a59482]">
                <span className="h-px w-6 bg-[#d8c7b2]/52" />
                <span>正在生成正文</span>
              </div>
              <span className="onepage-writing-line h-2.5 rounded-full bg-[#d8c7b2]/50" />
              <span className="onepage-writing-line h-2.5 w-11/12 rounded-full bg-[#d8c7b2]/42" />
              <span className="onepage-writing-line h-2.5 w-9/12 rounded-full bg-[#d8c7b2]/36" />
            </div>
            <div className="absolute bottom-6 left-8 h-4 w-14 -rotate-6 rounded-sm bg-[#edd9bd]/34" />
            <div className="onepage-breathe-item onepage-breathe-bottom absolute bottom-7 right-7 text-lg text-[#c99566]/76">✿</div>
            <div className="onepage-soft-spark-delayed absolute bottom-14 right-16 text-sm text-[#b7bea3]/80">✧</div>
          </div>
        </div>

        <div className="relative z-10 mt-0">
          <div className="rounded-[18px] border border-[#eadcc9]/52 bg-[#fffdf8]/54 p-3 shadow-[0_8px_18px_rgba(111,82,51,0.045)]">
            <div className="mb-2 flex items-start justify-between gap-3 text-left">
              <div>
                <div className="text-sm font-semibold text-[#5f4b38]">{stage.label}</div>
                <div className="mt-1 text-xs leading-5 text-[#8a7a68]">{stage.note}</div>
              </div>
              <strong className="shrink-0 font-song text-[22px] font-semibold leading-none text-[#5f4b38]">{Math.round(progress)}%</strong>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[#eadbca]/72 shadow-[inset_0_1px_2px_rgba(111,82,51,0.08)]">
              <div className="onepage-progress-fill h-full rounded-full bg-[linear-gradient(90deg,#c8a37e,#b7bea3,#c8a37e)] transition-all" style={{ width: `${progress}%` }} />
            </div>
            <div className="mt-3 grid grid-cols-3 gap-1.5">
              {flowSteps.map((item, index) => (
                <div
                  key={item}
                  className={`rounded-full px-2 py-1 text-[10px] ${
                    index === flowStep
                      ? "bg-[#ead4b5] text-[#5f4b38] shadow-[inset_0_1px_0_rgba(255,255,255,0.62)]"
                      : "bg-[#fffaf3]/58 text-[#a39482]"
                  }`}
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
          <p className="mt-2 text-xs leading-5 text-[#9a8a78]">{statusText}</p>
          <Button
            variant="ghost"
            className="mt-2.5 min-h-10 w-full rounded-full border border-[#eadcc9]/38 bg-[#fffdf8]/34 text-sm text-[#9a8a78] shadow-none"
            onClick={onCancel}
          >
            取消生成
          </Button>
        </div>
        <style>{`
          @keyframes onepageAiBreath {
            0%, 100% { opacity: 0.68; transform: scale(0.94) rotate(-5deg); }
            50% { opacity: 1; transform: scale(1.13) rotate(5deg); }
          }
          @keyframes onepageOrbBreath {
            0%, 100% {
              transform: scale(1);
              box-shadow: 0 8px 18px rgba(111,82,51,0.08), 0 0 0 0 rgba(201,154,102,0.06);
              border-color: rgba(234,220,201,0.7);
            }
            50% {
              transform: scale(1.055);
              box-shadow: 0 10px 24px rgba(111,82,51,0.11), 0 0 0 7px rgba(201,154,102,0.08);
              border-color: rgba(220,188,147,0.82);
            }
          }
          @keyframes onepageOrbHalo {
            0%, 100% { opacity: 0.24; transform: scale(0.88); }
            50% { opacity: 0.54; transform: scale(1.16); }
          }
          @keyframes onepageStaggerBreath {
            0%, 24%, 100% {
              opacity: var(--idle-opacity, 0.72);
              transform: translate3d(0, 0, 0) rotate(var(--rot, 0deg)) scale(1);
              filter: brightness(1);
              box-shadow: var(--idle-shadow, none);
            }
            10% {
              opacity: var(--peak-opacity, 1);
              transform: translate3d(0, var(--lift, -2px), 0) rotate(var(--peak-rot, var(--rot, 0deg))) scale(var(--peak-scale, 1.035));
              filter: brightness(1.13) saturate(1.035) contrast(1.015);
              box-shadow: var(--peak-shadow, var(--idle-shadow, none));
            }
          }
          @keyframes onepageMoodFloat {
            0%, 100% { opacity: 0.82; transform: translateY(0) rotate(6deg); }
            50% { opacity: 1; transform: translateY(-2px) rotate(5deg); }
          }
          @keyframes onepageSoftTwinkle {
            0%, 100% { opacity: 0.42; transform: scale(0.94); }
            48% { opacity: 0.92; transform: scale(1.05); }
          }
          @keyframes onepageWritingGlow {
            0%, 100% { opacity: 0.52; filter: brightness(1); }
            50% { opacity: 0.82; filter: brightness(1.08); }
          }
          @keyframes onepageProgressFlow {
            0% { background-position: 0% 50%; }
            100% { background-position: 160% 50%; }
          }
          .onepage-ai-star {
            display: inline-block;
            position: relative;
            z-index: 1;
            animation: onepageAiBreath 3.6s ease-in-out infinite;
            transform-origin: center;
          }
          .onepage-ai-orb {
            animation: onepageOrbBreath 3.6s ease-in-out infinite;
            transform-origin: center;
          }
          .onepage-ai-orb::before {
            content: "";
            position: absolute;
            inset: -7px;
            border-radius: 9999px;
            background: radial-gradient(circle, rgba(232,196,148,0.22), rgba(232,196,148,0.08) 48%, transparent 72%);
            animation: onepageOrbHalo 3.6s ease-in-out infinite;
            pointer-events: none;
          }
          .onepage-breathe-item {
            animation: onepageStaggerBreath 12s ease-in-out infinite;
            animation-fill-mode: both;
            opacity: var(--idle-opacity, 0.72);
            transform: rotate(var(--rot, 0deg));
            transform-origin: center;
            will-change: transform, opacity, filter;
          }
          .onepage-breathe-main {
            --rot: -3deg;
            --peak-rot: -2.6deg;
            --lift: -5px;
            --idle-opacity: 0.88;
            --peak-opacity: 1;
            --peak-scale: 1.075;
            --idle-shadow: 0 10px 18px rgba(111,82,51,0.13);
            --peak-shadow: 0 18px 32px rgba(111,82,51,0.24), 0 0 0 7px rgba(255,250,244,0.72), 0 0 22px rgba(218,178,126,0.22);
            animation-delay: 0s;
          }
          .onepage-breathe-side {
            --rot: 6deg;
            --peak-rot: 6.7deg;
            --lift: -5px;
            --idle-opacity: 0.84;
            --peak-opacity: 1;
            --peak-scale: 1.085;
            --idle-shadow: 0 8px 16px rgba(111,82,51,0.12);
            --peak-shadow: 0 16px 28px rgba(111,82,51,0.22), 0 0 0 6px rgba(255,250,244,0.68), 0 0 18px rgba(218,178,126,0.2);
            animation-delay: 3s;
          }
          .onepage-breathe-top {
            --rot: 0deg;
            --peak-rot: -4deg;
            --lift: -3px;
            --idle-opacity: 0.42;
            --peak-opacity: 1;
            --peak-scale: 1.34;
            --idle-shadow: 0 0 0 rgba(201,154,102,0);
            --peak-shadow: 0 6px 18px rgba(201,154,102,0.28), 0 0 16px rgba(232,196,148,0.32);
            animation-delay: 6s;
          }
          .onepage-breathe-bottom {
            --rot: 0deg;
            --peak-rot: 3deg;
            --lift: -3px;
            --idle-opacity: 0.48;
            --peak-opacity: 1;
            --peak-scale: 1.3;
            --idle-shadow: 0 0 0 rgba(201,154,102,0);
            --peak-shadow: 0 6px 18px rgba(201,154,102,0.26), 0 0 15px rgba(232,196,148,0.3);
            animation-delay: 9s;
          }
          .onepage-mood-tag {
            animation: onepageMoodFloat 5.4s ease-in-out infinite;
          }
          .onepage-soft-spark {
            animation: onepageSoftTwinkle 4.8s ease-in-out infinite;
          }
          .onepage-soft-spark-delayed {
            animation: onepageSoftTwinkle 5.6s ease-in-out 1.1s infinite;
          }
          .onepage-writing-line {
            position: relative;
            overflow: hidden;
            animation: onepageWritingGlow 3.4s ease-in-out infinite;
          }
          .onepage-writing-line::after {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.32), transparent);
            transform: translateX(-100%);
            animation: onepageProgressFlow 4.2s ease-in-out infinite;
          }
          .onepage-progress-fill {
            background-size: 180% 100%;
            animation: onepageProgressFlow 5.8s ease-in-out infinite;
          }
        `}</style>
      </div>
    </section>
  );
}

function buildPreviewTitle(text: string, mood: string) {
  const content = text.trim();
  if (/小龙虾|龙虾/.test(content)) return "热乎乎的快乐";
  if (/海|海边|沙滩|浪/.test(content)) return "海风里的小确幸";
  if (/咖啡|奶茶|甜品|蛋糕/.test(content)) return "甜甜的片刻";
  if (/朋友|家人|约会|聚会/.test(content)) return "和你们在一起";
  if (/工作|忙|加班|学习/.test(content)) return "认真生活的一天";
  if (/雨|下雨|阴天/.test(content)) return "雨天也有温柔";
  if (mood) return `${mood}的一页`;
  return "今天的一页";
}

function toGentleStatus(stepName: string) {
  if (!stepName || stepName === "本地生成演示") return "";
  if (/task|任务|created|processing|backend|mock/i.test(stepName)) return "";
  return stepName;
}

function getFlowStep(progress: number) {
  if (progress < 34) return 0;
  if (progress < 72) return 1;
  return 2;
}
