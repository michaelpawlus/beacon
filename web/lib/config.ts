import "server-only";
import fs from "node:fs";
import path from "node:path";

export type BeaconTomlConfig = {
  notifications: {
    email: string;
    cadence: string;
    desktop: boolean;
    minRelevanceAlert: number;
  };
  smtp: {
    host: string;
    port: number;
    user: string;
    password: string;
  };
  scanning: {
    cadence: string;
  };
  logging: {
    level: string;
    file: string;
  };
  scoring: {
    homeLocation: string;
  };
};

export type ConfigLoadResult = {
  config: BeaconTomlConfig | null;
  path: string;
  exists: boolean;
};

function parseValue(raw: string): string | number | boolean {
  const v = raw.trim();
  if (v.length === 0) return "";
  if (v === "true") return true;
  if (v === "false") return false;
  if (v.startsWith('"') && v.endsWith('"')) {
    return v.slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, "\\");
  }
  if (v.startsWith("'") && v.endsWith("'")) {
    return v.slice(1, -1);
  }
  const asNum = Number(v);
  if (!Number.isNaN(asNum)) return asNum;
  return v;
}

export function parseBeaconToml(text: string): Record<string, Record<string, string | number | boolean>> {
  const sections: Record<string, Record<string, string | number | boolean>> = {};
  let current: Record<string, string | number | boolean> | null = null;

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const sectionMatch = line.match(/^\[([^\]]+)\]$/);
    if (sectionMatch) {
      const name = sectionMatch[1].trim();
      if (!sections[name]) sections[name] = {};
      current = sections[name];
      continue;
    }
    const eq = line.indexOf("=");
    if (eq === -1 || !current) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1);
    current[key] = parseValue(value);
  }
  return sections;
}

function asString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function asNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" ? v : fallback;
}

function asBool(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function toConfig(sections: Record<string, Record<string, string | number | boolean>>): BeaconTomlConfig {
  const n = sections["notifications"] ?? {};
  const s = sections["smtp"] ?? {};
  const sc = sections["scanning"] ?? {};
  const l = sections["logging"] ?? {};
  const sg = sections["scoring"] ?? {};
  return {
    notifications: {
      email: asString(n["email"]),
      cadence: asString(n["cadence"], "daily"),
      desktop: asBool(n["desktop"], true),
      minRelevanceAlert: asNumber(n["min_relevance_alert"], 7),
    },
    smtp: {
      host: asString(s["host"]),
      port: asNumber(s["port"], 587),
      user: asString(s["user"]),
      password: asString(s["password"]),
    },
    scanning: { cadence: asString(sc["cadence"], "daily") },
    logging: {
      level: asString(l["level"], "INFO"),
      file: asString(l["file"], "data/beacon.log"),
    },
    scoring: { homeLocation: asString(sg["home_location"]) },
  };
}

export function resolveConfigPath(dbPath: string): string {
  if (process.env.BEACON_CONFIG) return process.env.BEACON_CONFIG;
  return path.join(path.dirname(dbPath), "beacon.toml");
}

export function loadBeaconConfig(dbPath: string): ConfigLoadResult {
  const configPath = resolveConfigPath(dbPath);
  if (!fs.existsSync(configPath)) {
    return { config: null, path: configPath, exists: false };
  }
  try {
    const text = fs.readFileSync(configPath, "utf8");
    return { config: toConfig(parseBeaconToml(text)), path: configPath, exists: true };
  } catch {
    return { config: null, path: configPath, exists: false };
  }
}
