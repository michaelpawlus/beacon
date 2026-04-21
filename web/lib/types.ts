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
