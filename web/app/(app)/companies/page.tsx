import { Suspense } from "react";
import { loadCompaniesData } from "@/lib/data";
import { CompaniesView } from "./view";

export const dynamic = "force-dynamic";

export default function CompaniesPage() {
  const data = loadCompaniesData();
  return (
    <Suspense fallback={null}>
      <CompaniesView data={data} />
    </Suspense>
  );
}
