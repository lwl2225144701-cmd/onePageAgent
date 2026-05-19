import { apiClient, unwrap } from "@/api/client";
import type { UserPreferenceResponse } from "@/types/backend";

export type UpdatePreferencePayload = {
  style_preferences?: Record<string, unknown>;
  font_preferences?: Record<string, unknown>;
  color_preferences?: Record<string, unknown>;
  behavior_stats?: Record<string, unknown>;
};

export function getPreferences() {
  return unwrap<UserPreferenceResponse>(apiClient.get("/preferences"));
}

export function updatePreferences(payload: UpdatePreferencePayload) {
  return unwrap<UserPreferenceResponse>(apiClient.put("/preferences", payload));
}
