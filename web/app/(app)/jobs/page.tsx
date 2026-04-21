import { loadBeaconData } from "@/lib/data";
import { JobsView } from "./view";

export const dynamic = "force-dynamic";

export default function JobsPage() {
  const data = loadBeaconData();
  return <JobsView data={data} />;
}
