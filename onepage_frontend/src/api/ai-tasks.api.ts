import { apiClient, createEventSource, unwrap } from "@/api/client";
import type { TaskDetailResponse, TaskResponse } from "@/types/backend";

export type CreateTaskInput = {
  text: string;
  image_urls: string[];
  audio_url?: string;
  mood: string;
  weather?: Record<string, unknown>;
  page_date: string;
};

export function createAiTask(input: CreateTaskInput) {
  return unwrap<TaskResponse>(apiClient.post("/ai/tasks", { input_json: input }));
}

export function getAiTask(taskId: string) {
  return unwrap<TaskDetailResponse>(apiClient.get(`/ai/tasks/${taskId}`));
}

export function subscribeAiTask(taskId: string) {
  return createEventSource(`/ai/tasks/${taskId}/events`);
}
