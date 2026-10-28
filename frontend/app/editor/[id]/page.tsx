import { EditorClient } from "@/components/editor/editor-client";
import { DEMO_MODE, demoProjectIds } from "@/lib/demo-config";

// Static demo builds pre-render one HTML file per sample project; the desktop
// build keeps rendering editor routes on demand from the Python backend.
export function generateStaticParams() {
  return DEMO_MODE ? demoProjectIds.map((id) => ({ id })) : [];
}

export default function EditorPage() {
  return <EditorClient />;
}
