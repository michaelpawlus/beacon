import type { SettingsScoringWeight } from "./types";

// Mirrors beacon/research/scoring.py:WEIGHTS. These are code-defined constants,
// not config — surfaced in the UI with an "isCodeDefined" tag so users know
// editing beacon.toml will not change them.
export const SCORING_WEIGHTS: SettingsScoringWeight[] = [
  { key: "leadership",     label: "Leadership signals",     value: 0.30, isCodeDefined: true },
  { key: "tool_adoption",  label: "Tool adoption",          value: 0.25, isCodeDefined: true },
  { key: "culture",        label: "Culture / hiring lang.", value: 0.25, isCodeDefined: true },
  { key: "evidence_depth", label: "Evidence depth",         value: 0.10, isCodeDefined: true },
  { key: "recency",        label: "Recency",                value: 0.10, isCodeDefined: true },
];
