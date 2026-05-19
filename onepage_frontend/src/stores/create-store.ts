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
  text: "",
  mood: "平静",
  imageFiles: [],
  imageUrls: [],
  weather: { weather: "晴", temperature: 26 },
  setText: (text) => set({ text }),
  setMood: (mood) => set({ mood }),
  setImageFiles: (imageFiles) => set({ imageFiles }),
  setImageUrls: (imageUrls) => set({ imageUrls }),
  setWeather: (weather) => set({ weather })
}));
