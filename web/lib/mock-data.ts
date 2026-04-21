import type { BeaconData } from "./types";

export const MOCK_DATA: BeaconData = {
  newMatches: [
    { id: "j1", title: "Staff Product Engineer", company: "Anthropic",  score: 94, comp: "$260–320k", loc: "SF · Hybrid",    seniority: "Staff",  stack: ["Python", "TypeScript", "Inference"], posted: "2h", referral: true  },
    { id: "j2", title: "Founding Design Eng",    company: "Browser Co", score: 91, comp: "$220–280k", loc: "Remote · US",    seniority: "Senior", stack: ["Swift", "React", "WebKit"],         posted: "4h", referral: false },
    { id: "j3", title: "ML Platform Engineer",   company: "Harvey",     score: 88, comp: "$240–300k", loc: "NYC · Onsite",   seniority: "Senior", stack: ["Ray", "Kubernetes", "Python"],       posted: "6h", referral: true  },
    { id: "j4", title: "Product Engineer",       company: "Cursor",     score: 86, comp: "$200–260k", loc: "SF · Hybrid",    seniority: "Senior", stack: ["TypeScript", "Rust", "LSP"],         posted: "9h", referral: false },
    { id: "j5", title: "Applied AI Engineer",    company: "Perplexity", score: 82, comp: "$230–290k", loc: "SF · Hybrid",    seniority: "Senior", stack: ["Python", "RAG", "Evals"],            posted: "14h",referral: false },
    { id: "j6", title: "Design Engineer",        company: "Linear",     score: 79, comp: "$210–270k", loc: "Remote · Global",seniority: "Senior", stack: ["React", "TypeScript", "GraphQL"],    posted: "1d", referral: true  },
  ],
  pipeline: [
    { id: "a1", company: "Vercel",    role: "Staff FE",       stage: "Screen",  since: 3,  owner: "me", next: "Recruiter call Thu", ghost: false },
    { id: "a2", company: "Ramp",      role: "Sr Product Eng", stage: "Onsite",  since: 1,  owner: "me", next: "Onsite loop Apr 28", ghost: false },
    { id: "a3", company: "Notion AI", role: "Applied AI",     stage: "Applied", since: 11, owner: "me", next: "Follow up today",   ghost: true  },
    { id: "a4", company: "Replit",    role: "Design Eng",     stage: "Applied", since: 6,  owner: "me", next: "Awaiting",           ghost: false },
  ],
  interviews: [
    { company: "Vercel", role: "Staff FE",       when: "Thu · 2:00p",  kind: "Recruiter",  who: "L. Park", prep: 60 },
    { company: "Ramp",   role: "Sr Product Eng", when: "Mon · 10:00a", kind: "Onsite",     who: "4 loops", prep: 30 },
    { company: "Harvey", role: "ML Platform",    when: "Apr 29",       kind: "Hiring Mgr", who: "S. Chen", prep: 10 },
  ],
  news: [
    { company: "Anthropic", text: "Released Claude 4.5 Haiku · AI model", when: "3h", kind: "product" },
    { company: "Cursor",    text: "Raised $900M Series C at $9.5B",        when: "1d", kind: "funding" },
    { company: "Harvey",    text: "Hired Jane Doe as VP Eng",               when: "2d", kind: "hire"    },
    { company: "Replit",    text: "Launched Agent v3 · new autonomy tier",  when: "3d", kind: "product" },
  ],
  sync: [
    { t: "14:02", cmd: "beacon pull --watchlist",   msg: "94 companies scanned · 12 new matches", ok: true  },
    { t: "14:02", cmd: "beacon enrich anthropic",   msg: "Funding + headcount refreshed",         ok: true  },
    { t: "13:58", cmd: "beacon rank",                msg: "6 jobs moved above threshold (85+)",    ok: true  },
    { t: "09:14", cmd: "beacon pull linkedin",       msg: "rate-limited · retrying in 20m",        ok: false },
    { t: "08:00", cmd: "beacon resume check",        msg: "stale 11d · tailored variant for Ramp", ok: true  },
  ],
  stats: { applied: 14, responses: 6, interviews: 3, offers: 0, responseRate: 0.43 },
  follow: [
    { who: "Notion AI",      role: "Applied AI", days: 11, tone: "bad",    action: "Follow up · 11d since apply" },
    { who: "Linear · B. Ho", role: "Warm intro", days: 6,  tone: "warn",   action: "Reply to intro email" },
    { who: "Harvey",         role: "Take-home sent", days: 2, tone: "default", action: "Submit by Fri" },
  ],
};
