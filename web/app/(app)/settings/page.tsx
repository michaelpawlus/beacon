import { PlaceholderPage } from "@/components/chrome/placeholder-page";

export default function SettingsPage() {
  return (
    <PlaceholderPage
      title="Settings"
      breadcrumbs={["Settings"]}
      cliHint="beacon config show --json"
      description="Scoring thresholds, CLI peer mode, notification channels, and keyboard shortcut overrides."
    />
  );
}
