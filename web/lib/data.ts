import "server-only";
import path from "node:path";
import fs from "node:fs";
import Database from "better-sqlite3";
import { MOCK_DATA } from "./mock-data";
import type {
  BeaconData,
  FollowUp,
  Interview,
  JobMatch,
  NewsItem,
  PipelineEntry,
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
