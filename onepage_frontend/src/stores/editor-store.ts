import { create } from "zustand";

import { fallbackLayout } from "@/modules/editor/fallback-layout";
import type { LayoutElement, LayoutJSON } from "@/types/backend";

type TransformPatch = {
  x: number;
  y: number;
  w?: number;
  h?: number;
  rotation?: number;
};

type HistoryState = {
  past: LayoutJSON[];
  future: LayoutJSON[];
};

type CommitOptions = {
  kind: "content" | "replace" | "geometry" | "load";
};

type SetLayoutOptions = {
  markSaved?: boolean;
};

type EditorState = {
  layout: LayoutJSON;
  savedLayout: LayoutJSON;
  selectedId?: string;
  past: LayoutJSON[];
  future: LayoutJSON[];
  canUndo: boolean;
  canRedo: boolean;
  isDirty: boolean;
  lastCommitAt: number;
  lastCommitKind?: CommitOptions["kind"];
  setLayout: (layout: LayoutJSON, options?: SetLayoutOptions) => void;
  select: (selectedId?: string) => void;
  undo: () => void;
  redo: () => void;
  updateText: (elementIndex: number, content: string) => void;
  updateFont: (selectedId: string | undefined, font: string) => void;
  replaceSticker: (selectedId: string, url: string) => void;
  updateElementPosition: (selectedId: string, x: number, y: number) => void;
  updateElementTransform: (selectedId: string, patch: TransformPatch) => void;
};

function getElementId(element: LayoutElement, index: number) {
  return String(element.props.id ?? `${element.type}-${index}`);
}

function withUpdatedElements(layout: LayoutJSON, updater: (element: LayoutElement, index: number) => LayoutElement): LayoutJSON {
  return {
    ...layout,
    elements: layout.elements.map(updater),
  };
}

function withSelectedElement(layout: LayoutJSON, selectedId: string, updater: (element: LayoutElement) => LayoutElement): LayoutJSON {
  return withUpdatedElements(layout, (element, index) => {
    if (getElementId(element, index) !== selectedId) {
      return element;
    }
    return updater(element);
  });
}

function cloneLayout(layout: LayoutJSON): LayoutJSON {
  return {
    ...layout,
    page: { ...layout.page },
    style: layout.style ? { ...layout.style } : undefined,
    elements: layout.elements.map((element) => ({
      ...element,
      props: { ...element.props },
    })),
  };
}

function layoutsEqual(left: LayoutJSON, right: LayoutJSON) {
  return JSON.stringify(left) === JSON.stringify(right);
}

export const useEditorStore = create<EditorState>((set, get) => {
  const MERGE_WINDOW_MS = 600;

  const commitLayout = (nextLayout: LayoutJSON, options: CommitOptions = { kind: "content" }) => {
    const { layout, savedLayout } = get();
    const previous = cloneLayout(layout);
    const next = cloneLayout(nextLayout);
    if (layoutsEqual(previous, next)) {
      return;
    }
    set((state) => ({
      layout: next,
      isDirty: !layoutsEqual(next, savedLayout),
      canUndo: true,
      canRedo: false,
      past:
        options.kind === "geometry" &&
        state.lastCommitKind === "geometry" &&
        Date.now() - state.lastCommitAt <= MERGE_WINDOW_MS &&
        state.past.length > 0
          ? state.past
          : [...state.past, previous],
      future: [],
      lastCommitAt: Date.now(),
      lastCommitKind: options.kind,
    }));
  };

  const replaceHistory = (layout: LayoutJSON): HistoryState & Pick<EditorState, "layout" | "canUndo" | "canRedo"> => ({
    layout: cloneLayout(layout),
    past: [],
    future: [],
    canUndo: false,
    canRedo: false,
  });

  return {
    layout: cloneLayout(fallbackLayout),
    savedLayout: cloneLayout(fallbackLayout),
    selectedId: "title",
    past: [],
    future: [],
    canUndo: false,
    canRedo: false,
    isDirty: false,
    lastCommitAt: 0,
    lastCommitKind: "load",
    setLayout: (layout, options = {}) =>
      set((state) => {
        const nextLayout = cloneLayout(layout);
        const nextSavedLayout = options.markSaved ? cloneLayout(layout) : state.savedLayout;
        return {
          ...replaceHistory(nextLayout),
          savedLayout: nextSavedLayout,
          isDirty: !layoutsEqual(nextLayout, nextSavedLayout),
          lastCommitAt: 0,
          lastCommitKind: "load",
        };
      }),
    select: (selectedId) => set({ selectedId }),
    undo: () =>
      set((state) => {
        if (state.past.length === 0) {
          return state;
        }
        const previous = state.past[state.past.length - 1];
        return {
          layout: cloneLayout(previous),
          past: state.past.slice(0, -1),
          future: [cloneLayout(state.layout), ...state.future],
          canUndo: state.past.length > 1,
          canRedo: true,
          isDirty: !layoutsEqual(previous, state.savedLayout),
          lastCommitAt: Date.now(),
          lastCommitKind: "load",
        };
      }),
    redo: () =>
      set((state) => {
        if (state.future.length === 0) {
          return state;
        }
        const next = state.future[0];
        return {
          layout: cloneLayout(next),
          past: [...state.past, cloneLayout(state.layout)],
          future: state.future.slice(1),
          canUndo: true,
          canRedo: state.future.length > 1,
          isDirty: !layoutsEqual(next, state.savedLayout),
          lastCommitAt: Date.now(),
          lastCommitKind: "load",
        };
      }),
    updateText: (elementIndex, content) => {
      const nextLayout = withUpdatedElements(get().layout, (element, index) => {
        if (index !== elementIndex) return element;
        const nextProps: Record<string, unknown> = { ...element.props, content };
        if (element.type === "date_tag") nextProps.date = content;
        if (element.type === "mood_tag") nextProps.mood = content;
        if (element.type === "weather_tag") nextProps.weather = content;
        return { ...element, props: nextProps };
      });
      commitLayout(nextLayout, { kind: "content" });
    },
    updateFont: (selectedId, font) => {
      const textTypes = new Set(["text", "date_tag", "mood_tag", "weather_tag"]);
      const nextLayout = selectedId
        ? withSelectedElement(get().layout, selectedId, (element) =>
            textTypes.has(element.type) ? { ...element, props: { ...element.props, font } } : element,
          )
        : withUpdatedElements(get().layout, (element) =>
            textTypes.has(element.type) ? { ...element, props: { ...element.props, font } } : element,
          );
      commitLayout(nextLayout, { kind: "content" });
    },
    replaceSticker: (selectedId, url) => {
      const nextLayout = withSelectedElement(get().layout, selectedId, (element) =>
        element.type === "sticker"
          ? {
              ...element,
              props: {
                ...element.props,
                url,
              },
            }
          : element,
      );
      commitLayout(nextLayout, { kind: "replace" });
    },
    updateElementPosition: (selectedId, x, y) => {
      const nextLayout = withSelectedElement(get().layout, selectedId, (element) => ({
        ...element,
        props: {
          ...element.props,
          x,
          y,
        },
      }));
      commitLayout(nextLayout, { kind: "geometry" });
    },
    updateElementTransform: (selectedId, patch) => {
      const nextLayout = withSelectedElement(get().layout, selectedId, (element) => ({
        ...element,
        props: {
          ...element.props,
          ...patch,
        },
      }));
      commitLayout(nextLayout, { kind: "geometry" });
    },
  };
});
