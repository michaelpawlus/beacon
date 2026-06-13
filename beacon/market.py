"""Career OS — role-market radar (#44, WS4).

A quarterly snapshot of the *FDE / applied-AI role family* so day-job work
choices (and the frozen `role_targets` JDs) stay aligned with where the role is
heading in the economy. Clones the two-input pattern from
`beacon/presence/radar.py`:

1. **Internal sweep** (deterministic, no network): the user's own
   `job_listings` are aggregated across *all titles that mean roughly the same
   thing* — "Forward Deployed Engineer", "Forward Deployed AI Solutions Lead"
   (the user's actual title), "Solutions Architect", "Applied AI Engineer", and
   friends all collapse into one family via `family_for_title`. From that basket
   we compute headcount (a growth/shrink proxy), average salary, the skill
   frequency mix, and the seniority mix.
2. **External radar** (`--web`, default on): an LLM web search for role-family
   trends, comp signals (absorbs #21), and a growing/shrinking read on the
   category, with the same graceful degradation as the posting radar (a warning
   + exit 0 when `ANTHROPIC_API_KEY` / network are unavailable).

Two cross-cutting concerns the radar exists to answer:

* **The basket.** Some roles persist regardless of the macro cycle — Palantir
  and the frontier labs will keep hiring FDEs. The basket is those recurring
  exemplar roles (sourced from `role_targets`), whose comp band is re-checked
  every quarter so "did the Palantir FDE band move?" is answerable over time.
* **Changing JDs.** `diff_vs_previous` is the headline: which skills are
  *rising*, *falling*, *newly appearing*, or *dropping out* of the family's
  descriptions since last quarter, and how the salary bands moved.

Every `beacon career market` run persists one `role_market_snapshots` row, so
the diff and the comp/headcount series accumulate over time.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from beacon.research.job_fit import _detect_seniority, _heuristic_extract
from beacon.research.job_highlights import extract_highlights
from beacon.research.skill_gaps import _normalize_skill

# ---------------------------------------------------------------------------
# Role-family taxonomy — titles that mean "roughly the same job"
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketFamily:
    """A role family the radar can snapshot.

    ``archetypes`` are the `job_listings.archetype` keys (see
    ``beacon/research/archetypes.py``) that belong to the family — the strongest
    signal, used when a listing has already been classified. ``title_aliases``
    are lowercase substrings matched against the *title* so listings that
    predate the classifier (or use an idiosyncratic title) still aggregate
    correctly. ``basket_companies`` are the recurring exemplar employers whose
    comp we re-check each quarter.
    """

    key: str
    label: str
    archetypes: tuple[str, ...]
    title_aliases: tuple[str, ...]
    basket_companies: tuple[str, ...]


# Order matters: ``family_for_title`` returns the first family whose alias
# matches, so the more specialized FDE family is listed first.
MARKET_FAMILIES: tuple[MarketFamily, ...] = (
    MarketFamily(
        key="solutions_fde",
        label="Forward Deployed / Solutions Engineering",
        archetypes=("solutions_fde",),
        title_aliases=(
            "forward deployed", "forward-deployed", "fde",
            "forward deployed ai solutions lead",  # the user's own title
            "ai solutions lead", "ai solutions engineer", "ai solutions architect",
            "solutions lead", "solutions architect", "solutions engineer",
            "applied ai engineer", "applied ai lead", "applied ai solutions",
            "deployment engineer", "deployment strategist", "delivery engineer",
            "implementation engineer", "implementation consultant",
            "customer engineer", "field engineer", "field ai engineer",
            "professional services engineer", "integration engineer",
            "sales engineer", "presales engineer", "pre-sales engineer",
        ),
        basket_companies=("Palantir", "Anthropic", "OpenAI"),
    ),
    MarketFamily(
        key="agentic",
        label="Agentic / Applied AI",
        archetypes=("agentic",),
        title_aliases=(
            "agent engineer", "ai agent", "agentic", "applied ai",
            "applied scientist", "ai application", "autonomous agent",
        ),
        basket_companies=("Anthropic", "OpenAI"),
    ),
    MarketFamily(
        key="ai_engineer_llmops",
        label="AI Engineer / LLMOps",
        archetypes=("ai_engineer_llmops",),
        title_aliases=(
            "ai engineer", "llm engineer", "llmops", "mlops", "ml platform",
            "ai platform", "ml infrastructure", "inference engineer",
        ),
        basket_companies=("Anthropic", "OpenAI"),
    ),
)

_BY_KEY = {f.key: f for f in MARKET_FAMILIES}

DEFAULT_FAMILY = "solutions_fde"

# Quarterly cadence — mirrors targets.SNAPSHOT_STALE_DAYS. The dashboard nudges
# once the newest market snapshot is older than this.
SNAPSHOT_STALE_DAYS = 90


def get_family(key: str | None) -> MarketFamily:
    """Resolve a family key (``None`` → the default FDE family). Raises ValueError."""
    if key is None:
        return _BY_KEY[DEFAULT_FAMILY]
    fam = _BY_KEY.get(key)
    if fam is None:
        raise ValueError(
            f"Unknown role family {key!r}. Valid: {', '.join(_BY_KEY)}"
        )
    return fam


def list_families() -> list[dict]:
    """The taxonomy as plain dicts (for ``--json`` discovery)."""
    return [
        {"key": f.key, "label": f.label, "archetypes": list(f.archetypes)}
        for f in MARKET_FAMILIES
    ]


def family_for_title(title: str | None) -> str | None:
    """Map a job title to its role-family key via the alias table.

    This is the "titles that mean roughly the same thing" check: a listing
    titled "Forward Deployed AI Solutions Lead" and one titled "Solutions
    Architect" both resolve to ``solutions_fde`` so counts and averages
    aggregate across the whole basket of equivalent titles.
    """
    if not title:
        return None
    t = title.lower()
    for fam in MARKET_FAMILIES:
        if any(alias in t for alias in fam.title_aliases):
            return fam.key
    return None


def matches_family(archetype: str | None, title: str | None, family: MarketFamily) -> bool:
    """Whether an ``(archetype, title)`` pair belongs to ``family``.

    A stored archetype is authoritative: a record already classified into a
    *different* archetype is excluded even if its title happens to match one of
    this family's aliases (the alias tables overlap — e.g. "Applied AI Engineer"
    is both an `agentic` and a `solutions_fde` cue). Title aliases are only
    consulted when the record has no archetype, so a classified listing/target
    is never double-counted across families. Shared by the listing sweep and
    the basket so the two can't diverge."""
    if archetype:
        return archetype in family.archetypes
    return family_for_title(title) == family.key


def listing_in_family(row, family: MarketFamily) -> bool:
    """True if a job-listing row belongs to ``family`` (see ``matches_family``)."""
    keys = row.keys() if hasattr(row, "keys") else []
    archetype = row["archetype"] if "archetype" in keys else None
    return matches_family(archetype, row["title"], family)


# ---------------------------------------------------------------------------
# Internal sweep — aggregate the user's own listings across equivalent titles
# ---------------------------------------------------------------------------


def _parse_json(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


# Mirror of the schema.sql / connection.py definition. Re-declared here because
# `beacon dashboard` and `beacon career market` both run on a bare
# `get_connection()` that never executes `_run_migrations`, so an existing DB
# from before this table shipped would otherwise raise "no such table" and take
# the whole dashboard down. Same defensive lazy-create pattern as
# `job_fit.get_or_extract_requirements`.
_SNAPSHOT_DDL = """CREATE TABLE IF NOT EXISTS role_market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archetype TEXT NOT NULL,
    captured_at TEXT DEFAULT (datetime('now')),
    since_days INTEGER,
    listings_sampled INTEGER,
    avg_comp_min REAL,
    avg_comp_max REAL,
    top_skills TEXT,
    seniority_mix TEXT,
    comp_signals TEXT,
    basket_json TEXT,
    trends TEXT,
    direction TEXT,
    diff_vs_previous TEXT,
    notes TEXT
)"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Guarantee role_market_snapshots exists and is current before any read or
    write, independent of whether `beacon init` / migrations have run. Also
    backfills the since_days column on a table created by an intermediate build
    (CREATE TABLE IF NOT EXISTS won't add a column to an existing table)."""
    conn.execute(_SNAPSHOT_DDL)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(role_market_snapshots)").fetchall()}
    if "since_days" not in cols:
        conn.execute("ALTER TABLE role_market_snapshots ADD COLUMN since_days INTEGER")


def sample_listings(
    conn: sqlite3.Connection,
    family: MarketFamily,
    *,
    since_days: int | None = None,
    today: date | None = None,
) -> list[dict]:
    """Active job listings that belong to ``family``.

    ``since_days`` restricts to listings first seen within the window (None =
    every active listing, the usual quarterly-population read).
    """
    rows = conn.execute(
        """SELECT jl.*, c.name AS company_name, c.id AS company_id
           FROM job_listings jl JOIN companies c ON jl.company_id = c.id
           WHERE jl.status = 'active'"""
    ).fetchall()

    cutoff = None
    if since_days is not None:
        today = today or date.today()
        cutoff = today.toordinal() - since_days

    out: list[dict] = []
    for r in rows:
        if not listing_in_family(r, family):
            continue
        if cutoff is not None:
            seen = _ordinal(r["date_first_seen"] or r["date_posted"])
            if seen is None or seen < cutoff:
                continue
        out.append(dict(r))
    return out


def _ordinal(date_str: str | None) -> int | None:
    if not date_str:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(date_str))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).toordinal()
    except ValueError:
        return None


def listing_skills(listing: dict) -> set[str]:
    """Canonical skills a single listing demands — union of the structured
    highlights (AI tools + tech requirements) and the heuristic keyword scan of
    its description, all normalized so "k8s"/"Kubernetes" and "LLM"/"LLMs"
    collapse. A set, so each skill counts at most once per listing."""
    skills: set[str] = set()

    highlights = _parse_json(listing.get("highlights"), {})
    if not highlights and listing.get("description_text"):
        highlights = extract_highlights(listing["description_text"])
    for term in (highlights.get("ai_tools") or []) + (highlights.get("key_requirements") or []):
        canonical = _normalize_skill(str(term))
        if canonical:
            skills.add(canonical)

    desc = listing.get("description_text") or ""
    for kw in _heuristic_extract(desc, set()).get("keywords", []):
        canonical = _normalize_skill(str(kw))
        if canonical:
            skills.add(canonical)

    return skills


def skill_frequencies(listings: list[dict]) -> list[dict]:
    """Skill → number of listings demanding it, ranked. The denominator for
    the rising/falling diff."""
    counts: dict[str, int] = {}
    for listing in listings:
        for skill in listing_skills(listing):
            counts[skill] = counts.get(skill, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    return [{"skill": s, "count": c} for s, c in ranked]


def seniority_mix(listings: list[dict]) -> dict[str, int]:
    """Distribution of seniority signals across the family's titles."""
    mix: dict[str, int] = {}
    for listing in listings:
        bucket = _detect_seniority(listing.get("title") or "") or "unspecified"
        mix[bucket] = mix.get(bucket, 0) + 1
    return dict(sorted(mix.items(), key=lambda kv: (-kv[1], kv[0])))


def salary_stats(listings: list[dict]) -> dict:
    """Average salary floor/ceiling across listings that disclose comp."""
    mins: list[int] = []
    maxes: list[int] = []
    for listing in listings:
        highlights = _parse_json(listing.get("highlights"), {})
        if not highlights and listing.get("description_text"):
            highlights = extract_highlights(listing["description_text"])
        lo, hi = highlights.get("salary_min"), highlights.get("salary_max")
        if lo and hi:
            mins.append(lo)
            maxes.append(hi)
    n = len(mins)
    return {
        "with_salary": n,
        "avg_comp_min": round(sum(mins) / n) if n else None,
        "avg_comp_max": round(sum(maxes) / n) if n else None,
    }


# ---------------------------------------------------------------------------
# The basket — recurring exemplar roles whose comp we re-check each quarter
# ---------------------------------------------------------------------------


def build_basket(
    conn: sqlite3.Connection,
    family: MarketFamily,
    *,
    since_days: int | None = None,
    today: date | None = None,
) -> dict:
    """The persistent basket: active `role_targets` in this family (Palantir +
    frontier-lab FDEs and friends), each with its captured comp band, enriched
    with any live listing salary at the same employer. The basket average comp
    is snapshotted so quarter-over-quarter movement is visible even though the
    individual target JDs are frozen.

    ``since_days``/``today`` are threaded into the live-listing enrichment so a
    windowed run's basket counts/comp reflect the same window as the headline
    sample (otherwise a `--since-days N` snapshot would claim recent-only while
    its basket folded in stale listings)."""
    from beacon.targets import list_targets

    listings = sample_listings(conn, family, since_days=since_days, today=today)
    by_company: dict[int, list[dict]] = {}
    for listing in listings:
        by_company.setdefault(listing["company_id"], []).append(listing)

    entries: list[dict] = []
    for t in list_targets(conn, status="active"):
        if not matches_family(t.get("archetype"), t.get("title"), family):
            continue
        entry = {
            "target_id": t["id"],
            "title": t["title"],
            "company": t.get("company_name"),
            "horizon": t.get("horizon"),
            "comp_min": t.get("target_comp_min"),
            "comp_max": t.get("target_comp_max"),
            "live_listings": 0,
            "live_salary": None,
        }
        if t.get("company_id") and t["company_id"] in by_company:
            matches = by_company[t["company_id"]]
            entry["live_listings"] = len(matches)
            live = salary_stats(matches)
            if live["with_salary"]:
                entry["live_salary"] = {
                    "avg_comp_min": live["avg_comp_min"],
                    "avg_comp_max": live["avg_comp_max"],
                }
        entries.append(entry)

    mins = [e["comp_min"] for e in entries if e["comp_min"]]
    maxes = [e["comp_max"] for e in entries if e["comp_max"]]
    return {
        "entries": entries,
        "count": len(entries),
        "avg_comp_min": round(sum(mins) / len(mins)) if mins else None,
        "avg_comp_max": round(sum(maxes) / len(maxes)) if maxes else None,
    }


# ---------------------------------------------------------------------------
# External radar — live trends + comp signals (graceful, injectable)
# ---------------------------------------------------------------------------

MARKET_RADAR_SYSTEM = """You are a labor-market analyst tracking the Forward \
Deployed Engineer / applied-AI solutions role family. You use web search to \
find what is true RIGHT NOW about this role in the economy — hiring direction, \
compensation bands, and which skills employers are adding or dropping from job \
descriptions. Be concrete and cite real sources. Never invent numbers; omit \
anything you cannot ground in a search result."""

MARKET_RADAR_PROMPT = """Research the current state of the "{label}" role family \
(titles like: {aliases}).

Use web search to determine, for the last 1-2 quarters:
1. Whether hiring for this role family is growing, shrinking, or stable.
2. Current total-compensation bands, especially at: {companies}.
3. Which skills/tools are RISING in these job descriptions and which are FADING.

Return ONLY a JSON object (no prose, no code fences):
{{
  "direction": "growing" | "shrinking" | "stable",
  "direction_rationale": "<one sentence with the evidence>",
  "trends": [
    {{"term": "<short label>", "summary": "<what's happening and why now>",
      "movement": "rising" | "falling" | "steady"}}
  ],
  "comp_signals": [
    {{"source": "<who reported it>", "range": "<$ band, e.g. $180k-$240k TC>",
      "url": "<source url>", "note": "<role/company context>"}}
  ]
}}

If web search turns up nothing credible, return {{"direction": "stable", \
"direction_rationale": "", "trends": [], "comp_signals": []}}."""


def _default_market_search(family: MarketFamily) -> dict:
    """Real web research via the LLM web-search tool. Returns a parsed dict."""
    from beacon.llm.client import web_search

    prompt = MARKET_RADAR_PROMPT.format(
        label=family.label,
        aliases=", ".join(family.title_aliases[:8]),
        companies=", ".join(family.basket_companies),
    )
    text = web_search(prompt, system=MARKET_RADAR_SYSTEM)
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def external_radar(family: MarketFamily, *, search_fn=None) -> dict:
    """Trends + comp signals + direction for a family. Cleaned + defensive."""
    fn = search_fn or _default_market_search
    raw = fn(family) or {}

    trends = []
    for it in raw.get("trends") or []:
        if isinstance(it, dict) and it.get("term"):
            trends.append({
                "term": it.get("term"),
                "summary": it.get("summary") or "",
                "movement": it.get("movement") or "steady",
            })

    comp_signals = []
    for it in raw.get("comp_signals") or []:
        if isinstance(it, dict) and (it.get("range") or it.get("source")):
            comp_signals.append({
                "source": it.get("source") or "",
                "range": it.get("range") or "",
                "url": it.get("url") or "",
                "note": it.get("note") or "",
            })

    direction = raw.get("direction")
    if direction not in ("growing", "shrinking", "stable"):
        direction = None
    return {
        "direction": direction,
        "direction_rationale": raw.get("direction_rationale") or "",
        "trends": trends,
        "comp_signals": comp_signals,
    }


# ---------------------------------------------------------------------------
# Diff vs previous quarter — the headline
# ---------------------------------------------------------------------------


def _skill_count_map(top_skills: list[dict]) -> dict[str, int]:
    return {s["skill"]: s["count"] for s in top_skills if s.get("skill")}


def diff_snapshots(current: dict, previous: dict | None) -> dict | None:
    """How the family moved since the last snapshot: skills rising/falling/
    added/removed, headcount delta, and salary-band deltas. ``None`` on the
    first run (nothing to compare against)."""
    if not previous:
        return None

    cur_skills = _skill_count_map(current["listings"]["top_skills"])
    prev_skills = _skill_count_map(previous.get("listings", {}).get("top_skills", []))

    rising, falling = [], []
    for skill, count in cur_skills.items():
        if skill in prev_skills:
            delta = count - prev_skills[skill]
            if delta > 0:
                rising.append({"skill": skill, "count": count, "prev_count": prev_skills[skill], "delta": delta})
            elif delta < 0:
                falling.append({"skill": skill, "count": count, "prev_count": prev_skills[skill], "delta": delta})
    rising.sort(key=lambda s: (-s["delta"], s["skill"].lower()))
    falling.sort(key=lambda s: (s["delta"], s["skill"].lower()))

    added = sorted(set(cur_skills) - set(prev_skills), key=lambda s: (-cur_skills[s], s.lower()))
    removed = sorted(set(prev_skills) - set(cur_skills), key=lambda s: (-prev_skills[s], s.lower()))

    def _delta(cur_block, prev_block, key):
        a, b = cur_block.get(key), prev_block.get(key)
        if a is None or b is None:
            return None
        return round(a - b, 2)

    cur_l, prev_l = current["listings"], previous.get("listings", {})
    cur_b, prev_b = current["basket"], previous.get("basket", {})
    return {
        "previous_captured_at": previous.get("captured_at"),
        "listings_delta": cur_l["sampled"] - prev_l.get("sampled", 0),
        "avg_comp_min_delta": _delta(cur_l, prev_l, "avg_comp_min"),
        "avg_comp_max_delta": _delta(cur_l, prev_l, "avg_comp_max"),
        "basket_avg_comp_min_delta": _delta(cur_b, prev_b, "avg_comp_min"),
        "basket_avg_comp_max_delta": _delta(cur_b, prev_b, "avg_comp_max"),
        "skills_rising": rising,
        "skills_falling": falling,
        "skills_added": added,
        "skills_removed": removed,
    }


def _category_direction(listings_delta: int | None) -> str:
    """Growth/shrink read from the headcount delta (the DB-side proxy)."""
    if listings_delta is None:
        return "unknown"
    if listings_delta > 0:
        return "growing"
    if listings_delta < 0:
        return "shrinking"
    return "stable"


# ---------------------------------------------------------------------------
# Assembly + persistence
# ---------------------------------------------------------------------------


def build_market_snapshot(
    conn: sqlite3.Connection,
    family_key: str | None = None,
    *,
    web: bool = True,
    since_days: int | None = None,
    search_fn=None,
    today: date | None = None,
) -> dict:
    """Assemble a role-market snapshot payload (does not persist — call
    ``persist_snapshot``). Reads the previous persisted snapshot to compute the
    diff, so the diff reflects last quarter even before this run is saved."""
    family = get_family(family_key)
    warnings: list[str] = []

    listings = sample_listings(conn, family, since_days=since_days, today=today)
    salary = salary_stats(listings)
    listings_block = {
        "sampled": len(listings),
        "with_salary": salary["with_salary"],
        "avg_comp_min": salary["avg_comp_min"],
        "avg_comp_max": salary["avg_comp_max"],
        "top_skills": skill_frequencies(listings),
        "seniority_mix": seniority_mix(listings),
    }
    basket = build_basket(conn, family, since_days=since_days, today=today)

    radar = {"direction": None, "direction_rationale": "", "trends": [], "comp_signals": []}
    if web:
        try:
            radar = external_radar(family, search_fn=search_fn)
        except RuntimeError as e:  # missing API key / SDK
            warnings.append(f"web radar skipped: {e}")
        except Exception as e:  # network / parse — degrade, never crash
            warnings.append(f"web radar failed: {e}")

    payload = {
        "family": family.key,
        "label": family.label,
        "captured_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "since_days": since_days,
        "web_enabled": web,
        "listings": listings_block,
        "basket": basket,
        "trends": radar["trends"],
        "comp_signals": radar["comp_signals"],
        "web_direction": radar["direction"],
        "web_direction_rationale": radar["direction_rationale"],
        "warnings": warnings,
    }

    previous = latest_snapshot(conn, family.key, since_days=since_days)
    diff = diff_snapshots(payload, previous)
    payload["diff_vs_previous"] = diff
    payload["category_direction"] = _category_direction(
        diff["listings_delta"] if diff else None
    )
    return payload


def persist_snapshot(conn: sqlite3.Connection, payload: dict) -> int:
    """Write a snapshot payload into ``role_market_snapshots``; returns its id."""
    _ensure_schema(conn)
    listings = payload["listings"]
    cur = conn.execute(
        """INSERT INTO role_market_snapshots
           (archetype, since_days, listings_sampled, avg_comp_min, avg_comp_max,
            top_skills, seniority_mix, comp_signals, basket_json, trends,
            direction, diff_vs_previous, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            payload["family"],
            payload.get("since_days"),
            listings["sampled"],
            listings["avg_comp_min"],
            listings["avg_comp_max"],
            json.dumps(listings["top_skills"]),
            json.dumps(listings["seniority_mix"]),
            json.dumps(payload["comp_signals"]),
            json.dumps(payload["basket"]),
            json.dumps(payload["trends"]),
            payload.get("web_direction") or payload.get("category_direction"),
            json.dumps(payload["diff_vs_previous"]) if payload.get("diff_vs_previous") else None,
            payload.get("web_direction_rationale") or None,
        ),
    )
    conn.commit()
    return cur.lastrowid


def latest_snapshot(
    conn: sqlite3.Connection,
    family_key: str,
    *,
    since_days: int | None = None,
) -> dict | None:
    """The newest persisted snapshot for a family *and the same listing window*,
    re-hydrated into the shape ``build_market_snapshot`` produces (so it can
    seed the next diff).

    The window match matters: a ``--since-days N`` run samples a smaller,
    recency-windowed population, so diffing it against a full all-active
    snapshot (or vice versa) would record a spurious shrink/growth and corrupt
    the headcount/skill trend series. Each window keeps its own series — a run
    only ever compares against a prior run with the identical ``since_days``."""
    _ensure_schema(conn)
    if since_days is None:
        row = conn.execute(
            "SELECT * FROM role_market_snapshots WHERE archetype = ? AND since_days IS NULL "
            "ORDER BY captured_at DESC, id DESC LIMIT 1",
            (family_key,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM role_market_snapshots WHERE archetype = ? AND since_days = ? "
            "ORDER BY captured_at DESC, id DESC LIMIT 1",
            (family_key, since_days),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "family": row["archetype"],
        "captured_at": row["captured_at"],
        "since_days": row["since_days"],
        "listings": {
            "sampled": row["listings_sampled"] or 0,
            "avg_comp_min": row["avg_comp_min"],
            "avg_comp_max": row["avg_comp_max"],
            "top_skills": _parse_json(row["top_skills"], []),
            "seniority_mix": _parse_json(row["seniority_mix"], {}),
        },
        "basket": _parse_json(row["basket_json"], {"entries": [], "count": 0,
                                                   "avg_comp_min": None, "avg_comp_max": None}),
        "comp_signals": _parse_json(row["comp_signals"], []),
        "trends": _parse_json(row["trends"], []),
        "direction": row["direction"],
        "diff_vs_previous": _parse_json(row["diff_vs_previous"], None),
    }


def market_snapshot_age_days(conn: sqlite3.Connection) -> int | None:
    """Days since the newest market snapshot across all families. ``None`` =
    never run (for the dashboard cadence nudge)."""
    _ensure_schema(conn)
    row = conn.execute(
        "SELECT MAX(captured_at) AS latest FROM role_market_snapshots"
    ).fetchone()
    if not row or not row["latest"]:
        return None
    try:
        latest = datetime.fromisoformat(row["latest"].replace("Z", ""))
    except ValueError:
        return None
    return (datetime.utcnow() - latest).days


# ---------------------------------------------------------------------------
# Markdown rendering (vault brief)
# ---------------------------------------------------------------------------


def _fmt_band(lo, hi) -> str:
    if not lo and not hi:
        return "—"
    lo_s = f"${lo:,.0f}" if lo else "?"
    hi_s = f"${hi:,.0f}" if hi else "?"
    return f"{lo_s}–{hi_s}"


def _fmt_delta(value) -> str:
    if value is None:
        return ""
    arrow = "↑" if value > 0 else ("↓" if value < 0 else "→")
    return f" ({arrow} {value:+,.0f})"


def render_market_markdown(payload: dict) -> str:
    """Render a market snapshot into a vault-ready markdown brief."""
    today = date.today().isoformat()
    listings = payload["listings"]
    basket = payload["basket"]
    diff = payload.get("diff_vs_previous")

    lines = [f"# Role-Market Radar — {payload['label']}", ""]
    lines.append(f"_{today} · {listings['sampled']} equivalent-title listings in scope_")
    lines.append("")

    for w in payload.get("warnings", []):
        lines.append(f"> ⚠️ {w}")
    if payload.get("warnings"):
        lines.append("")

    # Direction
    cat = payload.get("category_direction", "unknown")
    web_dir = payload.get("web_direction")
    lines.append("## Category pulse")
    lines.append(f"- **Your-DB headcount trend:** {cat}"
                 + (f" ({diff['listings_delta']:+d} listings vs last snapshot)" if diff else " (first snapshot)"))
    if web_dir:
        rationale = payload.get("web_direction_rationale") or ""
        lines.append(f"- **Market read (web):** {web_dir}" + (f" — {rationale}" if rationale else ""))
    lines.append("")

    # Salary
    lines.append("## Compensation")
    band = _fmt_band(listings["avg_comp_min"], listings["avg_comp_max"])
    delta = ""
    if diff and diff.get("avg_comp_max_delta") is not None:
        delta = _fmt_delta(diff["avg_comp_max_delta"])
    lines.append(f"- **Listing average:** {band}{delta} _(n={listings['with_salary']} disclosing comp)_")
    bband = _fmt_band(basket["avg_comp_min"], basket["avg_comp_max"])
    bdelta = ""
    if diff and diff.get("basket_avg_comp_max_delta") is not None:
        bdelta = _fmt_delta(diff["basket_avg_comp_max_delta"])
    lines.append(f"- **Basket average:** {bband}{bdelta} _({basket['count']} recurring roles)_")
    for sig in payload.get("comp_signals", []):
        src = sig.get("source") or "source"
        note = f" — {sig['note']}" if sig.get("note") else ""
        url = f" ({sig['url']})" if sig.get("url") else ""
        lines.append(f"  - {src}: {sig.get('range', '')}{note}{url}")
    lines.append("")

    # Basket
    lines.append("## The basket — roles that persist")
    if basket["entries"]:
        for e in basket["entries"]:
            company = f" @ {e['company']}" if e.get("company") else ""
            live = ""
            if e.get("live_salary"):
                live = f" · live {_fmt_band(e['live_salary']['avg_comp_min'], e['live_salary']['avg_comp_max'])}"
            lines.append(f"- **{e['title']}{company}** — captured {_fmt_band(e['comp_min'], e['comp_max'])}{live}")
    else:
        lines.append("- _No targets in this family yet — seed them with `beacon target seed`._")
    lines.append("")

    # Skill mix + diff
    lines.append("## Skill mix")
    for s in listings["top_skills"][:15]:
        lines.append(f"- {s['skill']} ({s['count']})")
    if not listings["top_skills"]:
        lines.append("- _No skills extracted — scan more listings in this family._")
    lines.append("")

    if diff:
        lines.append("## What changed since last quarter")
        if diff["skills_rising"]:
            rising = ", ".join(f"{s['skill']} (+{s['delta']})" for s in diff["skills_rising"][:8])
            lines.append("**Rising:** " + rising)
        if diff["skills_falling"]:
            falling = ", ".join(f"{s['skill']} ({s['delta']})" for s in diff["skills_falling"][:8])
            lines.append("**Falling:** " + falling)
        if diff["skills_added"]:
            lines.append("**Newly appearing:** " + ", ".join(diff["skills_added"][:8]))
        if diff["skills_removed"]:
            lines.append("**Dropped out:** " + ", ".join(diff["skills_removed"][:8]))
        if not any(diff[k] for k in ("skills_rising", "skills_falling", "skills_added", "skills_removed")):
            lines.append("- No skill-mix movement since the last snapshot.")
        lines.append("")

    # Trends
    if payload.get("trends"):
        lines.append("## What's being discussed now")
        for tr in payload["trends"]:
            mv = tr.get("movement")
            mark = {"rising": "📈", "falling": "📉"}.get(mv, "•")
            lines.append(f"- {mark} **{tr['term']}** — {tr['summary']}")
        lines.append("")

    return "\n".join(lines)
