import { loadSettingsData } from "@/lib/data";
import { SettingsView } from "./view";

export const dynamic = "force-dynamic";

export default function SettingsPage() {
  const data = loadSettingsData();
  return <SettingsView data={data} />;
}
