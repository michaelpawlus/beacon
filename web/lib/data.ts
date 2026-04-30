import "server-only";
import path from "node:path";
import fs from "node:fs";
import Database from "better-sqlite3";
import { MOCK_COMPANIES, MOCK_CONTENT, MOCK_DATA, MOCK_SETTINGS } from "./mock-data";
import type {
  BeaconData,
  CompaniesData,
  Company,
  CompanyScoreBreakdown,
  CompanySignal,
  CompanyTool,
  ContentAlert,
  ContentCalendarItem,
  ContentData,
  ContentDraft,
  FollowUp,
  Interview,
  JobMatch,
  LeadershipSignal,
  NewsItem,
  PipelineEntry,
  ResumeFreshness,
  SettingsAutomationStatus,
  SettingsData,
  Stats,
  SyncEvent,
} from "./types";

const DB_PATH = process.env.BEACON_DB ?? path.join(process.cwd(), "..", "data", "beacon.db");

let _db: Database.Database | null = null;

function openDb(): Database.Database | null {
  if (_db) return _db;
  if (!fs.existsSync(DB_PATH)) return null;
  try {
    _db = new Database(DB_PATH, { readonly: true, fileMustExist: true });
    _db.pragma("journal_mode = WAL");
    return _db;
  } catch {
    return null;
  }
}

function parseJson<T>(raw: unknown, fallback: T): T {
  if (typeof raw !== "string" || !raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function relativeAge(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diffMs = Date.now() - then;
  const mins = Math.max(0, Math.round(diffMs / 60000));
  if (mins < 60) return `${mins}m`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.round(hrs / 24);
  return `${days}d`;
}

function daysSince(iso: string | null | undefined): number {
  if (!iso) return 0;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 0;
  return Math.max(0, Math.round((Date.now() - then) / 86_400_000));
}

function toJobMatches(db: Database.Database): JobMatch[] {
  const rows = db
    .prepare(
      `SELECT j.id, j.title, j.location, j.date_posted, j.date_first_seen,
              j.relevance_score, j.highlights, j.match_reasons,
              c.name as company, c.remote_policy
         FROM job_listings j
         JOIN companies c ON c.id = j.company_id
        WHERE j.status = 'active'
     ORDER BY j.relevance_score DESC, j.date_first_seen DESC
        LIMIT 12`,
    )
    .all() as Array<{
      id: number;
      title: string;
      location: string | null;
      date_posted: string | null;
      date_first_seen: string | null;
      relevance_score: number | null;
      highlights: string | null;
      match_reasons: string | null;
      company: string;
      remote_policy: string | null;
    }>;

  return rows.map((r) => {
    const highlights = parseJson<{ salary?: string; ai_tools?: string[]; experience?: string }>(
      r.highlights,
      {},
    );
    const reasons = parseJson<string[]>(r.match_reasons, []);
    const stack = (highlights.ai_tools && highlights.ai_tools.length ? highlights.ai_tools : reasons).slice(0, 4);
    const score = Math.max(0, Math.min(100, Math.round(((r.relevance_score ?? 0) / 10) * 100)));
    const loc = [r.location, r.remote_policy].filter(Boolean).join(" · ") || "—";
    return {
      id: `j${r.id}`,
      title: r.title,
      company: r.company,
      score,
      comp: highlights.salary || "—",
      loc,
      seniority: highlights.experience || "—",
      stack,
      posted: relativeAge(r.date_first_seen || r.date_posted),
      referral: false,
    } satisfies JobMatch;
  });
}

function toPipeline(db: Database.Database): PipelineEntry[] {
  const rows = db
    .prepare(
      `SELECT a.id, a.status, a.applied_date, a.updated_at,
              j.title, c.name as company
         FROM applications a
         JOIN job_listings j ON j.id = a.job_id
         JOIN companies c ON c.id = j.company_id
        WHERE a.status NOT IN ('withdrawn')
     ORDER BY a.updated_at DESC
        LIMIT 40`,
    )
    .all() as Array<{
      id: number;
      status: string;
      applied_date: string | null;
      updated_at: string | null;
      title: string;
      company: string;
    }>;

  const stageMap: Record<string, PipelineEntry["stage"]> = {
    draft: "Saved",
    applied: "Applied",
    phone_screen: "Screen",
    interview: "Onsite",
    offer: "Offer",
    rejected: "Closed",
    ghosted: "Applied",
  };

  return rows.map((r) => {
    const since = daysSince(r.applied_date || r.updated_at);
    return {
      id: `a${r.id}`,
      company: r.company,
      role: r.title,
      stage: stageMap[r.status] ?? "Saved",
      since,
      owner: "me",
      next: r.status === "ghosted" ? "Ghosted · needs follow-up" : "—",
      ghost: r.status === "ghosted" || (r.status === "applied" && since >= 10),
    } satisfies PipelineEntry;
  });
}

function toStats(db: Database.Database): Stats {
  const totals = db
    .prepare(
      `SELECT
         SUM(CASE WHEN status = 'applied'      THEN 1 ELSE 0 END) as applied,
         SUM(CASE WHEN status IN ('phone_screen','interview','offer') THEN 1 ELSE 0 END) as responses,
         SUM(CASE WHEN status IN ('phone_screen','interview') THEN 1 ELSE 0 END) as interviews,
         SUM(CASE WHEN status = 'offer' THEN 1 ELSE 0 END) as offers,
         COUNT(*) as total
       FROM applications`,
    )
    .get() as {
      applied: number | null;
      responses: number | null;
      interviews: number | null;
      offers: number | null;
      total: number | null;
    } | undefined;
  if (!totals) return MOCK_DATA.stats;
  const applied = totals.applied ?? 0;
  const responses = totals.responses ?? 0;
  return {
    applied,
    responses,
    interviews: totals.interviews ?? 0,
    offers: totals.offers ?? 0,
    responseRate: applied > 0 ? responses / applied : 0,
  };
}

function toSync(db: Database.Database): SyncEvent[] {
  const rows = db
    .prepare(
      `SELECT run_type, started_at, completed_at, jobs_found, new_relevant_jobs,
              errors, duration_seconds
         FROM automation_log
     ORDER BY started_at DESC
        LIMIT 6`,
    )
    .all() as Array<{
      run_type: string;
      started_at: string;
      completed_at: string | null;
      jobs_found: number | null;
      new_relevant_jobs: number | null;
      errors: string | null;
      duration_seconds: number | null;
    }>;

  return rows.map((r) => {
    const ts = new Date(r.started_at);
    const tt = Number.isNaN(ts.getTime())
      ? "—"
      : `${String(ts.getHours()).padStart(2, "0")}:${String(ts.getMinutes()).padStart(2, "0")}`;
    return {
      t: tt,
      cmd: `beacon ${r.run_type}`,
      msg: r.errors
        ? r.errors.split("\n")[0].slice(0, 80)
        : `${r.jobs_found ?? 0} scanned · ${r.new_relevant_jobs ?? 0} new`,
      ok: !r.errors,
    } satisfies SyncEvent;
  });
}

function tableExists(db: Database.Database, name: string): boolean {
  try {
    const row = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name = ?")
      .get(name) as { name?: string } | undefined;
    return !!row?.name;
  } catch {
    return false;
  }
}

function toCompanies(db: Database.Database): Company[] {
  const rows = db
    .prepare(
      `SELECT c.id, c.name, c.domain, c.tier, c.ai_first_score AS score,
              c.remote_policy, c.hq_location, c.industry, c.description,
              c.careers_url, c.careers_platform, c.last_researched_at,
              (SELECT COUNT(*) FROM job_listings j
                WHERE j.company_id = c.id AND j.status = 'active') AS open_jobs
         FROM companies c
     ORDER BY c.tier ASC, c.ai_first_score DESC, c.name ASC`,
    )
    .all() as Array<{
      id: number;
      name: string;
      domain: string | null;
      tier: number | null;
      score: number | null;
      remote_policy: string | null;
      hq_location: string | null;
      industry: string | null;
      description: string | null;
      careers_url: string | null;
      careers_platform: string | null;
      last_researched_at: string | null;
      open_jobs: number | null;
    }>;

  const toolStmt = db.prepare(
    `SELECT tool_name AS name, adoption_level AS adoption, evidence_url AS evidenceUrl
       FROM tools_adopted WHERE company_id = ? ORDER BY tool_name`,
  );
  const signalStmt = db.prepare(
    `SELECT id, signal_type AS type, title, excerpt,
            source_url AS sourceUrl, source_name AS sourceName,
            signal_strength AS strength, date_observed AS dateObserved
       FROM ai_signals WHERE company_id = ?
   ORDER BY COALESCE(date_observed, created_at) DESC LIMIT 12`,
  );
  const leadershipStmt = db.prepare(
    `SELECT id, leader_name AS leader, leader_title AS title,
            signal_type AS signalType, content,
            source_url AS sourceUrl, date_observed AS dateObserved,
            impact_level AS impactLevel
       FROM leadership_signals WHERE company_id = ?
   ORDER BY COALESCE(date_observed, created_at) DESC LIMIT 8`,
  );
  const breakdownStmt = db.prepare(
    `SELECT leadership_score AS leadership, tool_adoption_score AS toolAdoption,
            culture_score AS culture, evidence_depth_score AS evidenceDepth,
            recency_score AS recency, composite_score AS composite,
            last_computed_at AS lastComputedAt
       FROM score_breakdown WHERE company_id = ?`,
  );

  return rows.map((r) => {
    const tools = toolStmt.all(r.id) as CompanyTool[];
    const signals = signalStmt.all(r.id) as CompanySignal[];
    const leadership = leadershipStmt.all(r.id) as LeadershipSignal[];
    const breakdown = breakdownStmt.get(r.id) as CompanyScoreBreakdown | undefined;
    return {
      id: r.id,
      name: r.name,
      domain: r.domain,
      tier: r.tier ?? 4,
      score: typeof r.score === "number" ? r.score : 0,
      remotePolicy: r.remote_policy,
      hqLocation: r.hq_location,
      industry: r.industry,
      description: r.description,
      careersUrl: r.careers_url,
      careersPlatform: r.careers_platform,
      lastResearchedAt: r.last_researched_at,
      lastResearchedAge: relativeAge(r.last_researched_at),
      toolsList: tools,
      openJobs: r.open_jobs ?? 0,
      signals,
      leadership,
      breakdown: breakdown ?? null,
    } satisfies Company;
  });
}

function toContent(db: Database.Database): ContentData {
  const draftRows = db
    .prepare(
      `SELECT id, content_type, platform, title, status,
              published_url, published_at, updated_at, body
         FROM content_drafts
     ORDER BY datetime(updated_at) DESC LIMIT 30`,
    )
    .all() as Array<{
      id: number;
      content_type: string;
      platform: string;
      title: string;
      status: string;
      published_url: string | null;
      published_at: string | null;
      updated_at: string | null;
      body: string | null;
    }>;

  const drafts: ContentDraft[] = draftRows.map((r) => ({
    id: r.id,
    contentType: r.content_type,
    platform: r.platform,
    title: r.title,
    status: r.status,
    publishedUrl: r.published_url,
    publishedAt: r.published_at,
    updatedAt: r.updated_at,
    daysSinceUpdate: daysSince(r.updated_at),
    preview: (r.body ?? "").slice(0, 160).replace(/\s+/g, " ").trim(),
  }));

  const calendarRows = db
    .prepare(
      `SELECT id, title, platform, content_type, topic, target_date, status, draft_id
         FROM content_calendar
     ORDER BY CASE WHEN target_date IS NULL THEN 1 ELSE 0 END, target_date ASC LIMIT 20`,
    )
    .all() as Array<{
      id: number;
      title: string;
      platform: string;
      content_type: string;
      topic: string | null;
      target_date: string | null;
      status: string;
      draft_id: number | null;
    }>;

  const calendar: ContentCalendarItem[] = calendarRows.map((r) => ({
    id: r.id,
    title: r.title,
    platform: r.platform,
    contentType: r.content_type,
    topic: r.topic,
    targetDate: r.target_date,
    status: r.status,
    draftId: r.draft_id,
  }));

  let resumes: ResumeFreshness[] = [];
  if (tableExists(db, "resume_variants")) {
    const variantRows = db
      .prepare(
        `SELECT variant_label, COUNT(*) as cnt, MAX(created_at) as last_created
           FROM resume_variants
       GROUP BY variant_label
       ORDER BY last_created DESC`,
      )
      .all() as Array<{ variant_label: string; cnt: number; last_created: string | null }>;
    resumes = variantRows.map((r) => ({
      variantLabel: r.variant_label,
      count: r.cnt,
      lastCreated: r.last_created,
      daysSince: daysSince(r.last_created),
    }));
  }

  const alerts: ContentAlert[] = [];
  for (const d of drafts) {
    if (d.status !== "draft") continue;
    if (d.daysSinceUpdate >= 21) {
      alerts.push({
        kind: "stale_draft",
        title: d.title,
        detail: `${d.daysSinceUpdate} days since last edit · ${d.platform}`,
        cli: `beacon presence draft ${d.id}`,
        tone: "bad",
      });
    } else if (d.daysSinceUpdate >= 10) {
      alerts.push({
        kind: "stale_draft",
        title: d.title,
        detail: `${d.daysSinceUpdate} days since last edit · ${d.platform}`,
        cli: `beacon presence draft ${d.id}`,
        tone: "warn",
      });
    }
  }
  for (const v of resumes) {
    if (v.daysSince >= 30) {
      alerts.push({
        kind: "stale_resume",
        title: `${v.variantLabel} variant is ${v.daysSince} days old`,
        detail: `${v.count} variants generated · last on ${v.lastCreated?.slice(0, 10) ?? "—"}`,
        cli: `beacon profile resume <job_id>`,
        tone: "bad",
      });
    }
  }
  for (const c of calendar) {
    if (c.status === "outlined" || c.status === "idea") {
      if (c.draftId == null && c.targetDate) {
        const target = new Date(c.targetDate).getTime();
        const today = Date.now();
        const daysOut = Math.round((target - today) / 86_400_000);
        if (daysOut <= 7 && daysOut >= -1) {
          alerts.push({
            kind: "ghost_calendar",
            title: `${c.title} · target ${c.targetDate}`,
            detail: `${c.status} but no draft created yet.`,
            cli:
              c.contentType === "blog_post"
                ? `beacon presence blog-outline --topic '${c.topic ?? c.title}'`
                : `beacon presence linkedin-post --topic '${c.topic ?? c.title}'`,
            tone: daysOut <= 2 ? "bad" : "warn",
          });
        }
      }
    }
  }

  return { drafts, calendar, resumes, alerts };
}

function toSettings(db: Database.Database, dbPath: string): SettingsData {
  const automationRows = db
    .prepare(
      `SELECT run_type, started_at, completed_at, errors, duration_seconds
         FROM automation_log
     ORDER BY started_at DESC LIMIT 60`,
    )
    .all() as Array<{
      run_type: string;
      started_at: string;
      completed_at: string | null;
      errors: string | null;
      duration_seconds: number | null;
    }>;

  const totalRuns = automationRows.length;
  const failedRuns = automationRows.filter((r) => !!r.errors).length;
  const last = automationRows[0];
  const automation: SettingsAutomationStatus = last
    ? {
        lastRun: last.started_at,
        lastRunAge: relativeAge(last.started_at),
        lastRunType: last.run_type,
        lastRunOk: !last.errors,
        totalRuns,
        failedRuns,
        lastDuration: last.duration_seconds,
      }
    : {
        lastRun: null,
        lastRunAge: "—",
        lastRunType: null,
        lastRunOk: true,
        totalRuns: 0,
        failedRuns: 0,
        lastDuration: null,
      };

  return {
    ...MOCK_SETTINGS,
    automation,
    dbPath,
    isMockData: false,
  };
}

export function loadCompaniesData(): CompaniesData {
  const db = openDb();
  if (!db) return MOCK_COMPANIES;
  try {
    const companies = toCompanies(db);
    if (!companies.length) return MOCK_COMPANIES;
    const toolSet = new Set<string>();
    for (const c of companies) for (const t of c.toolsList) toolSet.add(t.name);
    return { companies, totalTools: Array.from(toolSet).sort() };
  } catch {
    return MOCK_COMPANIES;
  }
}

export function loadContentData(): ContentData {
  const db = openDb();
  if (!db) return MOCK_CONTENT;
  try {
    const data = toContent(db);
    if (!data.drafts.length && !data.calendar.length && !data.resumes.length) {
      return MOCK_CONTENT;
    }
    return data;
  } catch {
    return MOCK_CONTENT;
  }
}

export function loadSettingsData(): SettingsData {
  const db = openDb();
  if (!db) return MOCK_SETTINGS;
  try {
    return toSettings(db, DB_PATH);
  } catch {
    return MOCK_SETTINGS;
  }
}

export function loadBeaconData(): BeaconData {
  const db = openDb();
  if (!db) return MOCK_DATA;

  try {
    const newMatches = toJobMatches(db);
    const pipeline = toPipeline(db);
    const stats = toStats(db);
    const sync = toSync(db);

    const interviews: Interview[] = MOCK_DATA.interviews;
    const news: NewsItem[] = MOCK_DATA.news;
    const follow: FollowUp[] = pipeline
      .filter((p) => p.ghost)
      .slice(0, 4)
      .map((p) => ({
        who: p.company,
        role: p.role,
        days: p.since,
        tone: p.since >= 10 ? "bad" : p.since >= 5 ? "warn" : "default",
        action: `Follow up · ${p.since}d since apply`,
      }));

    return {
      newMatches: newMatches.length ? newMatches : MOCK_DATA.newMatches,
      pipeline: pipeline.length ? pipeline : MOCK_DATA.pipeline,
      interviews,
      news,
      sync: sync.length ? sync : MOCK_DATA.sync,
      stats,
      follow: follow.length ? follow : MOCK_DATA.follow,
    };
  } catch {
    return MOCK_DATA;
  }
}
