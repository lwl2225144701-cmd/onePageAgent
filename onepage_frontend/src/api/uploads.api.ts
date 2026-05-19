import { apiClient, unwrap } from "@/api/client";
import type { UploadResponse } from "@/types/backend";

export function uploadImage(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return unwrap<UploadResponse>(apiClient.post("/uploads/image", formData));
}

export function uploadAudio(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return unwrap<UploadResponse>(apiClient.post("/uploads/audio", formData));
}
