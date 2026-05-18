import { afterEach, describe, expect, it, vi } from "vitest";
import path from "node:path";
import fs from "node:fs";
import os from "node:os";
import Database from "better-sqlite3";

function makeFixtureDb(): { dbPath: string; cleanup: () => void } {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "beacon-web-"));
  const dbPath = path.join(dir, "beacon.db");
  const db = new Database(dbPath);
  db.exec(`
    CREATE TABLE discovery_candidates (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source TEXT NOT NULL,
      source_ref TEXT NOT NULL,
      name TEXT NOT NULL,
      domain TEXT,
      careers_url TEXT,
      hq_location TEXT,
      industry TEXT,
      signals_json TEXT,
      raw_json TEXT,
      discovery_score REAL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'pending',
      reject_reason TEXT,
      promoted_to_company_id INTEGER,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      UNIQUE(source, source_ref)
    );
  `);
  db.prepare(
    `INSERT INTO discovery_candidates (source, source_ref, name, domain, discovery_score, status, signals_json)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
  ).run("yaml", "low", "LowCo", "low.com", 1.5, "pending", "[]");
  db.prepare(
    `INSERT INTO discovery_candidates (source, source_ref, name, domain, discovery_score, status, signals_json)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
  ).run("yaml", "mid", "MidCo", "mid.com", 4.2, "pending", '[{"type":"x"},{"type":"y"}]');
  db.prepare(
    `INSERT INTO discovery_candidates (source, source_ref, name, domain, discovery_score, status, signals_json)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
  ).run("crunchbase", "high", "HighCo", "high.com", 7.8, "pending", "[]");
  db.prepare(
    `INSERT INTO discovery_candidates (source, source_ref, name, domain, discovery_score, status, signals_json)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
  ).run("yaml", "promoted", "AlreadyIn", "in.com", 9.9, "promoted", "[]");
  db.close();
  return {
    dbPath,
    cleanup: () => fs.rmSync(dir, { recursive: true, force: true }),
  };
}

describe("toDiscovery via loadCompaniesData", () => {
  const created: Array<() => void> = [];
  afterEach(() => {
    while (created.length) created.pop()!();
    vi.resetModules();
    delete process.env.BEACON_DB;
  });

  it("returns pending-only rows sorted by discovery_score DESC", async () => {
    const fx = makeFixtureDb();
    created.push(fx.cleanup);
    process.env.BEACON_DB = fx.dbPath;

    const { loadCompaniesData } = await import("../data");
    const data = loadCompaniesData();

    expect(data.discovery.pendingCount).toBe(3);
    expect(data.discovery.candidates.map((c) => c.name)).toEqual(["HighCo", "MidCo", "LowCo"]);
    expect(data.discovery.candidates.find((c) => c.name === "AlreadyIn")).toBeUndefined();

    const midCo = data.discovery.candidates.find((c) => c.name === "MidCo")!;
    expect(midCo.signalsCount).toBe(2);

    const sources = data.discovery.sources.map((s) => s.name).sort();
    expect(sources).toEqual(["crunchbase", "yaml"]);
    const yaml = data.discovery.sources.find((s) => s.name === "yaml")!;
    expect(yaml.pending).toBe(2);
  });
});
