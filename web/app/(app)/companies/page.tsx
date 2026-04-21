import { PlaceholderPage } from "@/components/chrome/placeholder-page";

export default function CompaniesPage() {
  return (
    <PlaceholderPage
      title="Companies"
      breadcrumbs={["Companies"]}
      cliHint="beacon companies --tier 1 --json"
      description="The watchlist of ~94 AI-native companies with scores, signals, and leadership intel. Data source lives in the CLI — this view will render it once wired."
    />
  );
}
