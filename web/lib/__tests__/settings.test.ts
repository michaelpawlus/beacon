import { afterEach, describe, expect, it, vi } from "vitest";
import path from "node:path";
import fs from "node:fs";
import os from "node:os";
import Database from "better-sqlite3";

function makeFixtureDb(opts: { withToml?: string } = {}): { dbPath: string; cleanup: () => void } {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "beacon-web-settings-"));
  const dbPath = path.join(dir, "beacon.db");
  if (opts.withToml !== undefined) {
    fs.writeFileSync(path.join(dir, "beacon.toml"), opts.withToml);
  }
  const db = new Database(dbPath);
  db.exec(`
    CREATE TABLE automation_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_type TEXT NOT NULL,
      started_at TEXT NOT NULL,
      completed_at TEXT,
      jobs_found INTEGER,
      new_relevant_jobs INTEGER,
      errors TEXT,
      duration_seconds REAL
    );
  `);
  db.prepare(
    `INSERT INTO automation_log (run_type, started_at, completed_at, jobs_found, errors, duration_seconds)
       VALUES (?, ?, ?, ?, ?, ?)`,
  ).run("full", new Date().toISOString(), new Date().toISOString(), 12, null, 41.2);
  db.close();
  return {
    dbPath,
    cleanup: () => fs.rmSync(dir, { recursive: true, force: true }),
  };
}

describe("toSettings via loadSettingsData", () => {
  const cleanups: Array<() => void> = [];
  afterEach(() => {
    while (cleanups.length) cleanups.pop()!();
    vi.resetModules();
    delete process.env.BEACON_DB;
    delete process.env.BEACON_CONFIG;
  });

  it("hydrates notifications from fixture TOML and marks scoring code-defined", async () => {
    const toml = [
      "[notifications]",
      'email = "me@example.com"',
      'cadence = "daily"',
      "desktop = true",
      "min_relevance_alert = 8.0",
      "",
      "[smtp]",
      'host = "smtp.example.com"',
      "port = 587",
      'user = "me"',
      'password = ""',
      "",
    ].join("\n");

    const fx = makeFixtureDb({ withToml: toml });
    cleanups.push(fx.cleanup);
    process.env.BEACON_DB = fx.dbPath;

    const { loadSettingsData } = await import("../data");
    const data = loadSettingsData();

    expect(data.isMockData).toBe(false);
    const desktop = data.notifications.find((n) => n.channel.startsWith("Desktop"))!;
    expect(desktop.enabled).toBe(true);
    expect(desktop.detail).toContain("≥ 8");

    const email = data.notifications.find((n) => n.channel === "Email digest")!;
    expect(email.enabled).toBe(true);
    expect(email.detail).toContain("smtp.example.com");
    expect(email.detail).toContain("me@example.com");

    expect(data.scoring.length).toBeGreaterThan(0);
    expect(data.scoring.every((s) => s.isCodeDefined === true)).toBe(true);

    expect(data.automation.lastRunType).toBe("full");
    expect(data.automation.lastRunOk).toBe(true);
  });

  it("renders defaults when TOML is missing, still flips isMockData=false", async () => {
    const fx = makeFixtureDb();
    cleanups.push(fx.cleanup);
    process.env.BEACON_DB = fx.dbPath;

    const { loadSettingsData } = await import("../data");
    const data = loadSettingsData();

    expect(data.isMockData).toBe(false);
    const email = data.notifications.find((n) => n.channel === "Email digest")!;
    expect(email.enabled).toBe(false);
    expect(email.detail).toMatch(/SMTP not configured/);
  });
});
