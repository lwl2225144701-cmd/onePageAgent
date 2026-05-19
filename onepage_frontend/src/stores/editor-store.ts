import { create } from "zustand";
import type { LayoutJSON } from "@/types/backend";
import { fallbackLayout } from "@/modules/editor/fallback-layout";

type EditorState = {
  layout: LayoutJSON;
  selectedId?: string;
  setLayout: (layout: LayoutJSON) => void;
  select: (selectedId?: string) => void;
  updateText: (elementIndex: number, content: string) => void;
};

export const useEditorStore = create<EditorState>((set) => ({
  layout: fallbackLayout,
  selectedId: "title",
  setLayout: (layout) => set({ layout }),
  select: (selectedId) => set({ selectedId }),
  updateText: (elementIndex, content) =>
    set((state) => ({
      layout: {
        ...state.layout,
        elements: state.layout.elements.map((element, index) =>
          index === elementIndex ? { ...element, props: { ...element.props, content } } : element
        )
      }
    }))
}));
