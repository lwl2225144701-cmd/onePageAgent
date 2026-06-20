import { notFound } from "next/navigation";

import { VisualFixtureView } from "@/modules/editor/visual-fixture-view";
import { visualFixtureIds, type VisualFixtureId } from "@/modules/editor/visual-fixtures";

export default async function VisualTestPage({ params }: { params: Promise<{ template: string }> }) {
  if (process.env.NODE_ENV === "production" && process.env.ENABLE_VISUAL_FIXTURES !== "true") {
    notFound();
  }
  const { template } = await params;
  if (!visualFixtureIds.includes(template as VisualFixtureId)) {
    notFound();
  }
  return <VisualFixtureView fixtureId={template as VisualFixtureId} />;
}
