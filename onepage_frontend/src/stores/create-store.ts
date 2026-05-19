import { create } from "zustand";

type CreateState = {
  text: string;
  mood: string;
  imageFiles: File[];
  imageUrls: string[];
  weather: Record<string, unknown>;
  setText: (text: string) => void;
  setMood: (mood: string) => void;
  setImageFiles: (files: File[]) => void;
  setImageUrls: (urls: string[]) => void;
  setWeather: (weather: Record<string, unknown>) => void;
};

export const useCreateStore = create<CreateState>((set) => ({
  text: "今天去了海边，阳光很温柔，海风微咸。和朋友一起散步、拍照，度过了一个轻松的周末。",
  mood: "开心",
  imageFiles: [],
  imageUrls: [],
  weather: { weather: "晴", temperature: 26 },
  setText: (text) => set({ text }),
  setMood: (mood) => set({ mood }),
  setImageFiles: (imageFiles) => set({ imageFiles }),
  setImageUrls: (imageUrls) => set({ imageUrls }),
  setWeather: (weather) => set({ weather })
}));
