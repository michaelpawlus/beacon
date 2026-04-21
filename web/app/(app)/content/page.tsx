import { PlaceholderPage } from "@/components/chrome/placeholder-page";

export default function ContentPage() {
  return (
    <PlaceholderPage
      title="Content"
      breadcrumbs={["Content"]}
      cliHint="beacon presence drafts --json"
      description="Resume variants, cover letter templates, LinkedIn/portfolio sync status, story bank, and staleness alerts. Renders from the content_drafts + content_calendar tables."
    />
  );
}
