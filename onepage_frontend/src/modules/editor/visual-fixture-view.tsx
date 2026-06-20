"use client";

import { useEffect, useState } from "react";

import type { CanvasExportApi } from "@/modules/editor/journal-canvas";
import { JournalCanvas } from "@/modules/editor/journal-canvas";
import { getVisualFixture, type VisualFixtureId } from "@/modules/editor/visual-fixtures";
import { useEditorStore } from "@/stores/editor-store";

declare global {
  interface Window {
    __onepageVisualExport?: () => Promise<string | undefined>;
  }
}

export function VisualFixtureView({ fixtureId }: { fixtureId: VisualFixtureId }) {
  const setLayout = useEditorStore((state) => state.setLayout);
  const select = useEditorStore((state) => state.select);
  const [ready, setReady] = useState(false);
  const [canvasApi, setCanvasApi] = useState<CanvasExportApi>();

  useEffect(() => {
    setLayout(getVisualFixture(fixtureId), { markSaved: true });
    select(undefined);
    setReady(true);
  }, [fixtureId, select, setLayout]);

  useEffect(() => {
    window.__onepageVisualExport = canvasApi ? () => canvasApi.toDataUrl("png") : undefined;
    return () => {
      delete window.__onepageVisualExport;
    };
  }, [canvasApi]);

  return (
    <main className="grid h-[100dvh] w-full place-items-center overflow-hidden bg-[#fbf5ec]" data-visual-ready={ready && canvasApi ? "true" : "false"}>
      <div className="h-[820px] w-[380px]" data-visual-canvas>
        <JournalCanvas onReady={setCanvasApi} />
      </div>
    </main>
  );
}
