import { apiClient, unwrap } from "@/api/client";
import type { WeatherResponse } from "@/types/backend";

export function getWeather(lat: number, lng: number) {
  return unwrap<WeatherResponse>(apiClient.get("/weather", { params: { lat, lng } }));
}
