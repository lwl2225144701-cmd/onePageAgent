"use client";

import { useEffect } from "react";
import { getAiTask, subscribeAiTask } from "@/api/ai-tasks.api";
import { useAITaskStore } from "@/stores/ai-task-store";
import { useEditorStore } from "@/stores/editor-store";
import { Button } from "@/shared/ui/button";
import { fallbackLayout } from "@/modules/editor/fallback-layout";

export function LoadingView({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const { taskId, progress, stepName, setProgress, setResult } = useAITaskStore();
  const setLayout = useEditorStore((state) => state.setLayout);

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
    <section className="grid min-h-[calc(100vh-72px)] place-items-center">
      <div className="min-h-[720px] w-full max-w-[390px] rounded-[18px] border border-line bg-paper/95 p-6 text-center shadow-journal">
        <h1 className="mt-3 text-lg font-semibold">AI 正在为你生成手账...</h1>
        <p className="mt-2 text-muted">{stepName}</p>
        <div className="relative mx-auto my-8 h-[400px] w-[272px] overflow-hidden rounded-lg border border-line bg-paper">
          <div className="absolute left-[100px] top-8 font-song text-[22px] leading-tight">海边的<br />治愈时光</div>
          <div className="absolute left-11 top-32 h-[120px] w-[88px] border-[6px] border-white bg-sky shadow" />
          <div className="absolute left-36 top-28 h-[120px] w-[88px] rotate-12 border-[6px] border-white bg-[#82aec8] shadow" />
          <div className="absolute bottom-14 left-10 right-10 h-16 opacity-60 [background:repeating-linear-gradient(180deg,#8a715b_0_1px,transparent_1px_14px)]" />
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-[#eadbca]">
          <div className="h-full bg-olive transition-all" style={{ width: `${progress}%` }} />
        </div>
        <div className="mt-2 flex justify-between text-sm text-muted">
          <span>正在匹配风格、素材和排版...</span>
          <strong>{progress}%</strong>
        </div>
        <Button variant="ghost" className="mt-6 w-full" onClick={onCancel}>
          取消生成
        </Button>
      </div>
    </section>
  );
}
