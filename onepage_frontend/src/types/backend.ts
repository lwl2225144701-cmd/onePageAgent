export type UnifiedResponse<T> = {
  success: boolean;
  error_code?: string | null;
  message?: string | null;
  data: T | null;
  timestamp: string;
};

export type PaginatedResponse<T> = {
  data: T[];
  pagination: {
    page: number;
    size: number;
    total: number;
    total_pages: number;
  };
};

export type UploadResponse = {
  file_id: string;
  file_url: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  created_at?: string | null;
};

export type TaskResponse = {
  task_id: string;
  status: string;
  progress: number;
  created_at?: string | null;
};

export type TaskDetailResponse = TaskResponse & {
  user_id: string;
  input_json: Record<string, unknown>;
  result_json?: LayoutJSON | null;
  error_message?: string | null;
};

export type LayoutElement = {
  type: string;
  props: Record<string, unknown>;
  z_index: number;
};

export type LayoutJSON = {
  page: {
    width: number;
    height: number;
    background: string;
  };
  elements: LayoutElement[];
  style?: Record<string, unknown>;
};

export type ElementDTO = {
  element_type: string;
  props_json: Record<string, unknown>;
  z_index: number;
};

export type PageResponse = {
  id: string;
  journal_id: string;
  user_id: string;
  title?: string | null;
  content_text?: string | null;
  layout_json?: LayoutJSON | null;
  thumbnail_url?: string | null;
  weather?: Record<string, unknown> | null;
  mood?: string | null;
  page_date?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type JournalResponse = {
  id: string;
  user_id: string;
  name: string;
  cover_url?: string | null;
  page_count: number;
  settings?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type MaterialResponse = {
  id: string;
  material_type: string;
  style_tags?: string[] | null;
  emotion_tags?: string[] | null;
  scene_tags?: string[] | null;
  file_url: string;
  preview_url?: string | null;
  raw_file_url?: string | null;
  mime_type?: string | null;
  meta_info?: Record<string, unknown> | null;
  is_favorite: boolean;
  last_used_at?: string | null;
  created_at?: string | null;
};

export type MaterialGroup = {
  material_type: string;
  items: MaterialResponse[];
};

export type MaterialUploadSessionCreateInput = {
  file_name: string;
  file_size: number;
  mime_type: string;
  material_type: "sticker" | "background" | "decoration";
  category: string;
  tags: string[];
  visibility: "private" | "public";
};

export type MaterialUploadSessionCreateResponse = {
  session_id: string;
  upload_id: string;
  object_key: string;
  chunk_size: number;
  total_parts: number;
  part_urls: string[];
  expires_at: string;
};

export type WeatherIconKey =
  | "sunny"
  | "cloudy"
  | "overcast"
  | "rain"
  | "thunderstorm"
  | "snow"
  | "sleet"
  | "fog"
  | "dust"
  | "wind"
  | "unknown";

export type WeatherResponse = {
  province: string;
  city: string;
  district: string;
  location: string;
  adcode: string;
  weather: string;
  temperature: number | null;
  humidity: number | null;
  wind_direction: string;
  wind_power: string;
  report_time: string;
  icon_key: WeatherIconKey;
  source: "amap" | "unavailable";
  error_type?: string | null;
  message?: string | null;
};

export type EnvironmentContext = {
  date: string;
  time: string;
  weekday: string;
  timezone: string;
  province: string;
  city: string;
  district: string;
  location: string;
  adcode: string;
  weather: string;
  temperature: number | null;
  humidity: number | null;
  icon_key: WeatherIconKey;
  report_time: string;
  source: "amap" | "unavailable";
};

export type UserPreferenceResponse = {
  id: string;
  user_id: string;
  style_preferences?: Record<string, unknown> | null;
  font_preferences?: Record<string, unknown> | null;
  color_preferences?: Record<string, unknown> | null;
  behavior_stats?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
};
