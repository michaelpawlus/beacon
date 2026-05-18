export type JobMatch = {
  id: string;
  title: string;
  company: string;
  score: number;
  comp: string;
  loc: string;
  seniority: string;
  stack: string[];
  posted: string;
  referral: boolean;
};

export type PipelineEntry = {
  id: string;
  company: string;
  role: string;
  stage: "Saved" | "Applied" | "Screen" | "Onsite" | "Offer" | "Closed";
  since: number;
  owner: string;
  next: string;
  ghost: boolean;
};

export type Interview = {
  company: string;
  role: string;
  when: string;
  kind: string;
  who: string;
  prep: number;
};

export type NewsItem = {
  company: string;
  text: string;
  when: string;
  kind: "funding" | "hire" | "product" | string;
};

export type SyncEvent = {
  t: string;
  cmd: string;
  msg: string;
  ok: boolean;
};

export type FollowUp = {
  who: string;
  role: string;
  days: number;
  tone: "default" | "warn" | "bad";
  action: string;
};

export type Stats = {
  applied: number;
  responses: number;
  interviews: number;
  offers: number;
  responseRate: number;
};

export type BeaconData = {
  newMatches: JobMatch[];
  pipeline: PipelineEntry[];
  interviews: Interview[];
  news: NewsItem[];
  sync: SyncEvent[];
  stats: Stats;
  follow: FollowUp[];
};

export type CompanySignal = {
  id: number;
  type: string;
  title: string;
  excerpt: string | null;
  sourceUrl: string | null;
  sourceName: string | null;
  strength: number | null;
  dateObserved: string | null;
};

export type LeadershipSignal = {
  id: number;
  leader: string;
  title: string | null;
  signalType: string | null;
  content: string;
  sourceUrl: string | null;
  dateObserved: string | null;
  impactLevel: string | null;
};

export type CompanyTool = {
  name: string;
  adoption: string | null;
  evidenceUrl: string | null;
};

export type CompanyScoreBreakdown = {
  leadership: number;
  toolAdoption: number;
  culture: number;
  evidenceDepth: number;
  recency: number;
  composite: number;
  lastComputedAt: string | null;
};

export type Company = {
  id: number;
  name: string;
  domain: string | null;
  tier: number;
  score: number;
  remotePolicy: string | null;
  hqLocation: string | null;
  industry: string | null;
  description: string | null;
  careersUrl: string | null;
  careersPlatform: string | null;
  lastResearchedAt: string | null;
  lastResearchedAge: string;
  toolsList: CompanyTool[];
  openJobs: number;
  signals: CompanySignal[];
  leadership: LeadershipSignal[];
  breakdown: CompanyScoreBreakdown | null;
};

export type DiscoveryCandidate = {
  id: number;
  name: string;
  domain: string | null;
  careersUrl: string | null;
  hqLocation: string | null;
  industry: string | null;
  source: string;
  sourceRef: string;
  score: number;
  signalsCount: number;
  createdAt: string | null;
};

export type DiscoverySource = {
  name: string;
  pending: number;
  lastRun: string | null;
  lastRunAge: string;
};

export type DiscoveryData = {
  pendingCount: number;
  sources: DiscoverySource[];
  candidates: DiscoveryCandidate[];
};

export type CompaniesData = {
  companies: Company[];
  totalTools: string[];
  discovery: DiscoveryData;
};

export type ContentDraft = {
  id: number;
  contentType: string;
  platform: string;
  title: string;
  status: "draft" | "published" | "archived" | string;
  publishedUrl: string | null;
  publishedAt: string | null;
  updatedAt: string | null;
  daysSinceUpdate: number;
  preview: string;
};

export type ContentCalendarItem = {
  id: number;
  title: string;
  platform: string;
  contentType: string;
  topic: string | null;
  targetDate: string | null;
  status: "idea" | "outlined" | "drafted" | "published" | string;
  draftId: number | null;
};

export type ResumeFreshness = {
  variantLabel: string;
  count: number;
  lastCreated: string | null;
  daysSince: number;
};

export type ContentAlert = {
  kind: "stale_draft" | "stale_resume" | "missing_calendar" | "ghost_calendar";
  title: string;
  detail: string;
  cli: string;
  tone: "default" | "warn" | "bad";
};

export type PresentationItem = {
  id: number;
  title: string;
  eventName: string | null;
  venue: string | null;
  eventUrl: string | null;
  date: string | null;
  status: "planned" | "accepted" | "delivered" | "cancelled" | string;
  durationMinutes: number | null;
  audience: string | null;
};

export type ContentData = {
  drafts: ContentDraft[];
  calendar: ContentCalendarItem[];
  resumes: ResumeFreshness[];
  alerts: ContentAlert[];
  presentations: PresentationItem[];
};

export type SettingsScoringWeight = {
  key: string;
  label: string;
  value: number;
  isCodeDefined?: boolean;
};

export type SettingsAutomationStatus = {
  lastRun: string | null;
  lastRunAge: string;
  lastRunType: string | null;
  lastRunOk: boolean;
  totalRuns: number;
  failedRuns: number;
  lastDuration: number | null;
};

export type SettingsNotificationChannel = {
  channel: string;
  enabled: boolean;
  detail: string;
};

export type SettingsShortcut = {
  combo: string;
  label: string;
};

export type SettingsData = {
  scoring: SettingsScoringWeight[];
  automation: SettingsAutomationStatus;
  notifications: SettingsNotificationChannel[];
  shortcuts: SettingsShortcut[];
  configPath: string;
  dbPath: string;
  isMockData: boolean;
};
