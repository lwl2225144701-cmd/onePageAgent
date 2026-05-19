import { create } from "zustand";
import type { LayoutJSON } from "@/types/backend";

type AITaskState = {
  taskId?: string;
  status: "idle" | "pending" | "processing" | "completed" | "failed";
  progress: number;
  stepName: string;
  result?: LayoutJSON;
  setTask: (taskId: string) => void;
  setProgress: (progress: number, stepName?: string, status?: AITaskState["status"]) => void;
  setResult: (result: LayoutJSON) => void;
  reset: () => void;
};

export const useAITaskStore = create<AITaskState>((set) => ({
  status: "idle",
  progress: 0,
  stepName: "准备生成",
  setTask: (taskId) => set({ taskId, status: "pending", progress: 0, stepName: "任务已创建" }),
  setProgress: (progress, stepName, status = "processing") => set({ progress, stepName: stepName ?? "生成中", status }),
  setResult: (result) => set({ result, status: "completed", progress: 100, stepName: "完成" }),
  reset: () => set({ taskId: undefined, status: "idle", progress: 0, stepName: "准备生成", result: undefined })
}));
