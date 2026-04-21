import { loadBeaconData } from "@/lib/data";
import { ApplicationsView } from "./view";

export const dynamic = "force-dynamic";

export default function ApplicationsPage() {
  const data = loadBeaconData();
  return <ApplicationsView data={data} />;
}
