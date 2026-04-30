import { loadContentData } from "@/lib/data";
import { ContentView } from "./view";

export const dynamic = "force-dynamic";

export default function ContentPage() {
  const data = loadContentData();
  return <ContentView data={data} />;
}
