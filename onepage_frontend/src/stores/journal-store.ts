import { create } from "zustand";
import type { JournalResponse, PageResponse } from "@/types/backend";

type JournalState = {
  journals: JournalResponse[];
  localPages: PageResponse[];
  activeJournalId?: string;
  setJournals: (journals: JournalResponse[]) => void;
  upsertJournal: (journal: JournalResponse) => void;
  setActiveJournalId: (journalId?: string) => void;
  addLocalPage: (page: PageResponse) => void;
  upsertLocalPage: (page: PageResponse) => void;
};

function upsertById<T extends { id: string }>(items: T[], nextItem: T) {
  const existingIndex = items.findIndex((item) => item.id === nextItem.id);
  if (existingIndex === -1) {
    return [nextItem, ...items];
  }
  const nextItems = [...items];
  nextItems[existingIndex] = nextItem;
  return nextItems;
}

export const useJournalStore = create<JournalState>((set) => ({
  journals: [],
  localPages: [],
  activeJournalId: undefined,
  setJournals: (journals) =>
    set((state) => ({
      journals,
      activeJournalId: state.activeJournalId ?? journals[0]?.id
    })),
  upsertJournal: (journal) =>
    set((state) => ({
      journals: upsertById(state.journals, journal)
    })),
  setActiveJournalId: (activeJournalId) => set({ activeJournalId }),
  addLocalPage: (page) => set((state) => ({ localPages: [page, ...state.localPages] })),
  upsertLocalPage: (page) =>
    set((state) => ({
      localPages: upsertById(state.localPages, page)
    }))
}));
