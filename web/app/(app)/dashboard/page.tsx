import { loadBeaconData } from "@/lib/data";
import { DashboardWithToggle } from "./direction-toggle";

export const dynamic = "force-dynamic";

export default function DashboardPage() {
  const data = loadBeaconData();
  return <DashboardWithToggle data={data} />;
}
