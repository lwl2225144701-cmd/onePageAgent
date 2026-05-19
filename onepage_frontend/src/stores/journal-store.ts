import { create } from "zustand";
import type { JournalResponse, PageResponse } from "@/types/backend";

type JournalState = {
  journals: JournalResponse[];
  localPages: PageResponse[];
  setJournals: (journals: JournalResponse[]) => void;
  addLocalPage: (page: PageResponse) => void;
};

export const useJournalStore = create<JournalState>((set) => ({
  journals: [],
  localPages: [],
  setJournals: (journals) => set({ journals }),
  addLocalPage: (page) => set((state) => ({ localPages: [page, ...state.localPages] }))
}));
