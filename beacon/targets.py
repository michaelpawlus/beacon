"""Career OS — aspirational role track (#43, WS3).

`role_targets` are named roles the user is *not yet qualified for* — the JD is
frozen at capture time (`description_snapshot` + `required_skills`) so the
demand side survives the posting. Each `beacon target fit` run writes a
`role_fit_snapshots` row, turning fit into a time series: "fit 5.2 in June
2026 → 7.4 by mid-2027" is the core deliverable.

Gap analysis is scoped to targets (horizon-weighted, so a 2-year target's
missing skill outranks a 4-year one) and links wins to the gaps they're
closing — evidence accumulating against a gap is the cue to put it on the
resume. `role_dispatches` capture field reports from people actually doing
the target roles, so the JD-demanded skill list can be checked against the
attributes that make real FDEs successful.
"""

import json
import re
import sqlite3
from datetime import date, datetime

from beacon.research.skill_gaps import SKILL_ALIASES, SKILL_CATEGORIES, _normalize_skill

HORIZONS = ("1y", "2y", "3y", "4y")
TARGET_STATUSES = ("active", "achieved", "dropped")

# Nearer horizons weigh heavier in gap prioritization: a skill blocking a
# 1-year target matters more right now than one blocking a 4-year target.
HORIZON_WEIGHTS = {"1y": 4, "2y": 3, "3y": 2, "4y": 1}
DEFAULT_HORIZON_WEIGHT = 1

FIT_WEIGHTS = {
    "skill_overlap": 0.55,
    "evidence_depth": 0.25,
    "story_readiness": 0.10,
    "gap_momentum": 0.10,
}

# Snapshots older than this are stale — the quarterly cadence in
# docs/career-strategy.md. Dashboard + career review nudge past it.
SNAPSHOT_STALE_DAYS = 90


def _canon(name: str) -> str:
    return _normalize_skill(name)


def _parse_json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [parsed]
    except (json.JSONDecodeError, TypeError):
        return [value]


def _canon_skill_list(skills: list) -> list[str]:
    """Canonicalize + dedupe a skill list, preserving order — fit and gap
    comparisons assume required skills speak the same canonical names as the
    profile (e.g. `--skill k8s` must match a profile's `Kubernetes`)."""
    seen: set[str] = set()
    out: list[str] = []
    for s in skills:
        canonical = _canon(str(s))
        if canonical.lower() not in seen:
            seen.add(canonical.lower())
            out.append(canonical)
    return out


def extract_target_skills(description: str, profile_skills: set[str] | None = None) -> list[str]:
    """Pull canonical skill names out of a JD snapshot — deterministic, no LLM.

    Combines the match-jobs keyword extractor with a word-boundary scan of the
    skill-alias vocabulary, so target gaps speak the same canonical names as
    `beacon gaps` / the profile skills table.
    """
    from beacon.research.job_fit import _heuristic_extract

    extracted = _heuristic_extract(description or "", profile_skills or set())
    seen: set[str] = set()
    skills: list[str] = []

    def _add(name: str) -> None:
        canonical = _canon(name)
        if canonical.lower() not in seen:
            seen.add(canonical.lower())
            skills.append(canonical)

    for kw in extracted.get("keywords", []):
        _add(kw)

    text = (description or "").lower()
    for alias, canonical in SKILL_ALIASES.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text):
            _add(canonical)
    return skills


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def add_target(
    conn: sqlite3.Connection,
    title: str,
    company_id: int | None = None,
    source_job_id: int | None = None,
    source_url: str | None = None,
    archetype: str | None = None,
    horizon: str | None = None,
    target_comp_min: int | None = None,
    target_comp_max: int | None = None,
    description_snapshot: str | None = None,
    required_skills: list[str] | None = None,
    why: str | None = None,
) -> int:
    """Insert a role target and return its ID. Raises ValueError on bad horizon."""
    if horizon is not None and horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon {horizon!r}. Valid: {', '.join(HORIZONS)}")

    if required_skills is None and description_snapshot:
        required_skills = extract_target_skills(description_snapshot)
    elif required_skills:
        required_skills = _canon_skill_list(required_skills)

    cur = conn.execute(
        """INSERT INTO role_targets
           (title, company_id, source_job_id, source_url, archetype, horizon,
            target_comp_min, target_comp_max, description_snapshot, required_skills, why)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title,
            company_id,
            source_job_id,
            source_url,
            archetype,
            horizon,
            target_comp_min,
            target_comp_max,
            description_snapshot,
            json.dumps(required_skills) if required_skills else None,
            why,
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_target(conn: sqlite3.Connection, target_id: int) -> dict | None:
    """Get a single target with company name + latest snapshot."""
    row = conn.execute(
        """SELECT t.*, c.name AS company_name
           FROM role_targets t LEFT JOIN companies c ON t.company_id = c.id
           WHERE t.id = ?""",
        (target_id,),
    ).fetchone()
    if not row:
        return None
    target = dict(row)
    snap = conn.execute(
        "SELECT fit_score, computed_at FROM role_fit_snapshots "
        "WHERE role_target_id = ? ORDER BY computed_at DESC, id DESC LIMIT 1",
        (target_id,),
    ).fetchone()
    target["latest_fit"] = snap["fit_score"] if snap else None
    target["last_computed_at"] = snap["computed_at"] if snap else None
    return target


def list_targets(
    conn: sqlite3.Connection,
    horizon: str | None = None,
    status: str | None = "active",
) -> list[dict]:
    """List targets with company names + latest fit. status=None returns all."""
    clauses = []
    params: list = []
    if status:
        clauses.append("t.status = ?")
        params.append(status)
    if horizon:
        clauses.append("t.horizon = ?")
        params.append(horizon)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    rows = conn.execute(
        f"""SELECT t.*, c.name AS company_name,
                   s.fit_score AS latest_fit, s.computed_at AS last_computed_at
            FROM role_targets t
            LEFT JOIN companies c ON t.company_id = c.id
            LEFT JOIN role_fit_snapshots s ON s.id = (
                SELECT id FROM role_fit_snapshots
                WHERE role_target_id = t.id ORDER BY computed_at DESC, id DESC LIMIT 1
            ){where}
            ORDER BY CASE t.horizon WHEN '1y' THEN 1 WHEN '2y' THEN 2 WHEN '3y' THEN 3
                     WHEN '4y' THEN 4 ELSE 5 END, t.id""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def update_target(
    conn: sqlite3.Connection,
    target_id: int,
    status: str | None = None,
    horizon: str | None = None,
    why: str | None = None,
    archetype: str | None = None,
) -> bool:
    """Update mutable fields on a target. Returns True if found."""
    if status is not None and status not in TARGET_STATUSES:
        raise ValueError(f"Unknown status {status!r}. Valid: {', '.join(TARGET_STATUSES)}")
    if horizon is not None and horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon {horizon!r}. Valid: {', '.join(HORIZONS)}")

    fields = {"status": status, "horizon": horizon, "why": why, "archetype": archetype}
    sets = [f"{k} = ?" for k, v in fields.items() if v is not None]
    params = [v for v in fields.values() if v is not None]
    if not sets:
        return False
    params.append(target_id)
    cur = conn.execute(
        f"UPDATE role_targets SET {', '.join(sets)}, updated_at = datetime('now') WHERE id = ?",
        params,
    )
    conn.commit()
    return cur.rowcount > 0


def required_skills_for(target: dict) -> list[str]:
    """Canonical required skills for a target (frozen JSON, falling back to
    extraction). Canonicalized on read too, so rows written before the
    storage-side normalization (or edited by hand) still compare correctly."""
    skills = _parse_json_list(target.get("required_skills"))
    if not skills and target.get("description_snapshot"):
        skills = extract_target_skills(target["description_snapshot"])
    return _canon_skill_list(skills)


# ---------------------------------------------------------------------------
# Fit computation + snapshots
# ---------------------------------------------------------------------------


def _win_evidence_map(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Map canonical skill (lowercase) → wins that used it (via win technologies)."""
    rows = conn.execute("SELECT id, title, win_date, technologies FROM wins").fetchall()
    evidence: dict[str, list[dict]] = {}
    for r in rows:
        for tech in _parse_json_list(r["technologies"]):
            key = _canon(str(tech)).lower()
            evidence.setdefault(key, []).append(
                {"id": r["id"], "title": r["title"], "win_date": r["win_date"]}
            )
    return evidence


def compute_target_fit(
    conn: sqlite3.Connection,
    target: dict,
    profile: dict | None = None,
) -> dict:
    """Score how close the profile + evidence base is to a target. Deterministic.

    Sub-scores:
      * skill_overlap — profile terms vs the frozen required-skills list.
      * evidence_depth — required skills backed by logged wins (the
        "wins connected to closing gaps" signal).
      * story_readiness — polished STAR+R stories for the target archetype.
      * gap_momentum — missing skills already tracked as learning/closed
        in skill_gaps (you're actively moving on them).
    """
    from beacon.research.job_fit import load_profile_snapshot

    snapshot = profile or load_profile_snapshot(conn)
    required = required_skills_for(target)
    profile_terms ={_canon(t).lower() for t in snapshot["all_terms_lc"]} | snapshot["all_terms_lc"]

    matched = [s for s in required if s.lower() in profile_terms]
    missing = [s for s in required if s.lower() not in profile_terms]

    reasons: list[str] = []

    if required:
        skill_score = round(10.0 * len(matched) / len(required), 2)
        sample = ", ".join(matched[:5])
        reasons.append(f"skill_overlap:{len(matched)}/{len(required)}" + (f" ({sample})" if sample else ""))
    else:
        skill_score = 5.0
        reasons.append("skill_overlap:no_required_skills_captured")

    win_evidence = _win_evidence_map(conn)
    evidenced = {s: win_evidence[s.lower()] for s in required if s.lower() in win_evidence}
    if required:
        evidence_score = round(10.0 * len(evidenced) / len(required), 2)
        reasons.append(f"evidence_depth:{len(evidenced)}/{len(required)} skills win-backed")
    else:
        evidence_score = 5.0

    archetype = target.get("archetype")
    if archetype:
        story_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM interview_stories WHERE status = 'polished' "
            "AND archetypes IS NOT NULL "
            "AND EXISTS (SELECT 1 FROM json_each(archetypes) WHERE json_each.value = ?)",
            (archetype,),
        ).fetchone()["cnt"]
    else:
        story_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM interview_stories WHERE status = 'polished'"
        ).fetchone()["cnt"]
    story_score = {0: 2.0, 1: 6.0, 2: 8.0}.get(story_count, 10.0)
    reasons.append(f"story_readiness:{story_count} polished stories")

    if missing:
        moving = conn.execute(
            "SELECT skill_name FROM skill_gaps WHERE status IN ('learning', 'closed')"
        ).fetchall()
        moving_lc = {r["skill_name"].lower() for r in moving}
        in_motion = [s for s in missing if s.lower() in moving_lc]
        momentum_score = round(10.0 * len(in_motion) / len(missing), 2)
        reasons.append(f"gap_momentum:{len(in_motion)}/{len(missing)} gaps in motion")
    else:
        in_motion = []
        momentum_score = 10.0
        reasons.append("gap_momentum:no_open_gaps")

    composite = (
        skill_score * FIT_WEIGHTS["skill_overlap"]
        + evidence_score * FIT_WEIGHTS["evidence_depth"]
        + story_score * FIT_WEIGHTS["story_readiness"]
        + momentum_score * FIT_WEIGHTS["gap_momentum"]
    )

    return {
        "fit_score": round(min(composite, 10.0), 2),
        "sub_scores": {
            "skill_overlap": skill_score,
            "evidence_depth": evidence_score,
            "story_readiness": story_score,
            "gap_momentum": momentum_score,
        },
        "matched": matched,
        "missing": missing,
        "reasons": reasons,
        "evidence": {
            "win_evidence": evidenced,
            "polished_stories": story_count,
            "gaps_in_motion": in_motion,
        },
    }


def snapshot_fit(conn: sqlite3.Connection, target: dict, profile: dict | None = None) -> dict:
    """Compute fit, persist a role_fit_snapshots row, and report the delta."""
    prev = conn.execute(
        "SELECT fit_score, gaps_json FROM role_fit_snapshots "
        "WHERE role_target_id = ? ORDER BY computed_at DESC, id DESC LIMIT 1",
        (target["id"],),
    ).fetchone()

    fit = compute_target_fit(conn, target, profile=profile)
    conn.execute(
        "INSERT INTO role_fit_snapshots (role_target_id, fit_score, gaps_json, evidence_json) "
        "VALUES (?, ?, ?, ?)",
        (target["id"], fit["fit_score"], json.dumps(fit["missing"]), json.dumps(fit["evidence"])),
    )
    conn.commit()

    result = {
        "target_id": target["id"],
        "title": target["title"],
        "company": target.get("company_name"),
        "horizon": target.get("horizon"),
        **fit,
    }
    if prev and prev["fit_score"] is not None:
        result["previous_fit"] = prev["fit_score"]
        result["fit_delta"] = round(fit["fit_score"] - prev["fit_score"], 2)
        prev_gaps = {str(s).lower() for s in _parse_json_list(prev["gaps_json"])}
        cur_gaps = {s.lower() for s in fit["missing"]}
        result["gaps_closed_since_last"] = sorted(prev_gaps - cur_gaps)
        result["gaps_opened_since_last"] = sorted(cur_gaps - prev_gaps)
    return result


def latest_snapshot_age_days(conn: sqlite3.Connection) -> int | None:
    """Days since the newest fit snapshot across all targets. None = never run."""
    row = conn.execute(
        "SELECT MAX(computed_at) AS latest FROM role_fit_snapshots"
    ).fetchone()
    if not row or not row["latest"]:
        return None
    latest = datetime.fromisoformat(row["latest"])
    return (datetime.now() - latest).days


def targets_needing_fit(conn: sqlite3.Connection) -> list[dict]:
    """Active targets with no fit baseline or a snapshot older than the
    quarterly cadence. Checked per target — a fresh snapshot on one target
    must not mask a newly added target that has never been baselined."""
    needing = []
    for t in list_targets(conn, status="active"):
        last = t.get("last_computed_at")
        if last is None:
            needing.append({**t, "snapshot_age_days": None})
            continue
        age = (datetime.now() - datetime.fromisoformat(last)).days
        if age > SNAPSHOT_STALE_DAYS:
            needing.append({**t, "snapshot_age_days": age})
    return needing


# ---------------------------------------------------------------------------
# Target-scoped gap analysis
# ---------------------------------------------------------------------------


def dispatch_attribute_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Canonical attribute (lowercase) → number of dispatches observing it."""
    rows = conn.execute("SELECT attributes FROM role_dispatches").fetchall()
    counts: dict[str, int] = {}
    for r in rows:
        seen_in_row: set[str] = set()
        for attr in _parse_json_list(r["attributes"]):
            key = _canon(str(attr)).lower()
            if key not in seen_in_row:
                seen_in_row.add(key)
                counts[key] = counts.get(key, 0) + 1
    return counts


def analyze_target_gaps(conn: sqlite3.Connection) -> dict:
    """Aggregate missing skills across active targets, horizon-weighted.

    Returns gaps ranked by priority (sum of horizon weights of the demanding
    targets), each annotated with win evidence ("you're already closing this —
    put it on the resume") and field observation counts from dispatches
    (JD-demanded *and* field-validated gaps come first).
    """
    from beacon.research.job_fit import load_profile_snapshot

    targets = list_targets(conn, status="active")
    profile = load_profile_snapshot(conn)
    profile_terms = {_canon(t).lower() for t in profile["all_terms_lc"]} | profile["all_terms_lc"]
    win_evidence = _win_evidence_map(conn)
    field_counts = dispatch_attribute_counts(conn)

    demand: dict[str, dict] = {}
    for t in targets:
        weight = HORIZON_WEIGHTS.get(t.get("horizon"), DEFAULT_HORIZON_WEIGHT)
        for skill in required_skills_for(t):
            if skill.lower() in profile_terms:
                continue
            entry = demand.setdefault(
                skill.lower(),
                {"skill_name": skill, "demand_count": 0, "priority": 0, "example_targets": []},
            )
            entry["demand_count"] += 1
            entry["priority"] += weight
            if len(entry["example_targets"]) < 3:
                entry["example_targets"].append(
                    {"id": t["id"], "title": t["title"], "company": t.get("company_name")}
                )

    gaps = []
    for key, entry in demand.items():
        wins = win_evidence.get(key, [])
        gaps.append({
            "skill_name": entry["skill_name"],
            "category": SKILL_CATEGORIES.get(entry["skill_name"], "other"),
            "demand_count": entry["demand_count"],
            "priority": entry["priority"],
            "example_targets": entry["example_targets"],
            "field_observed": field_counts.get(key, 0),
            "win_evidence_count": len(wins),
            "example_wins": wins[:3],
        })

    gaps.sort(key=lambda g: (-g["priority"], -g["field_observed"], g["skill_name"].lower()))
    return {
        "gaps": gaps,
        "targets_analyzed": len(targets),
        "jd_vs_field": jd_vs_field(conn, targets=targets, field_counts=field_counts),
    }


def sync_target_gaps(conn: sqlite3.Connection, gaps: list[dict]) -> dict:
    """Upsert target gaps into skill_gaps so `gaps list/export` (and the
    stack-quest/code-daily quest feed) are driven by aspirational demand.

    Existing rows keep their status (open/learning/closed). Synced rows are
    provenance-tagged (`"target": true` on each example entry — an inner
    addition, so the gaps-list envelope contract is untouched). Rows that
    already carry job-market demand from `gaps analyze` are *merged*, not
    overwritten: their demand_count and job examples survive, target entries
    are layered in, and priority is raised to the target priority when
    higher. Purely target-owned rows whose demand has vanished — skill
    acquired, or the demanding target dropped — are retired (status closed,
    demand/priority zeroed); mixed rows just shed their stale target entries.
    Auto-retired rows (recognizable by closed + zeroed demand/priority) are
    reopened when target demand returns; a user's manual `closed` is kept.
    """
    inserted = 0
    updated = 0
    reopened = 0
    for gap in gaps:
        target_entries = [{**t, "target": True} for t in gap["example_targets"]]
        existing = conn.execute(
            "SELECT id, demand_count, priority, category, example_jobs, status "
            "FROM skill_gaps WHERE skill_name = ?",
            (gap["skill_name"],),
        ).fetchone()
        if existing:
            job_entries = [
                e for e in _parse_json_list(existing["example_jobs"])
                if not (isinstance(e, dict) and e.get("target"))
            ]
            if job_entries:
                # Job-driven row: keep the market signal (demand_count + job
                # examples), layer target provenance on top, elevate priority.
                conn.execute(
                    """UPDATE skill_gaps
                       SET example_jobs = ?, priority = ?, category = COALESCE(category, ?),
                           updated_at = datetime('now')
                       WHERE id = ?""",
                    (
                        json.dumps(job_entries + target_entries),
                        max(existing["priority"] or 0, gap["priority"]),
                        gap["category"],
                        existing["id"],
                    ),
                )
            else:
                # An auto-retired row carries the closed + zeroed fingerprint
                # the retirement path writes; demand is back, so reopen it.
                # A manually closed row (non-zero demand/priority) stays closed.
                auto_retired = (
                    existing["status"] == "closed"
                    and (existing["demand_count"] or 0) == 0
                    and (existing["priority"] or 0) == 0
                )
                status = "open" if auto_retired else existing["status"]
                if auto_retired:
                    reopened += 1
                conn.execute(
                    """UPDATE skill_gaps
                       SET demand_count = ?, category = ?, example_jobs = ?,
                           priority = ?, status = ?, updated_at = datetime('now')
                       WHERE id = ?""",
                    (gap["demand_count"], gap["category"], json.dumps(target_entries),
                     gap["priority"], status, existing["id"]),
                )
            updated += 1
        else:
            conn.execute(
                """INSERT INTO skill_gaps (skill_name, category, demand_count, example_jobs, priority)
                   VALUES (?, ?, ?, ?, ?)""",
                (gap["skill_name"], gap["category"], gap["demand_count"],
                 json.dumps(target_entries), gap["priority"]),
            )
            inserted += 1

    current = {g["skill_name"].lower() for g in gaps}
    retired = 0
    stale = conn.execute(
        "SELECT id, skill_name, example_jobs FROM skill_gaps WHERE status != 'closed'"
    ).fetchall()
    for row in stale:
        if row["skill_name"].lower() in current:
            continue
        examples = _parse_json_list(row["example_jobs"])
        tagged = [e for e in examples if isinstance(e, dict) and e.get("target")]
        if not tagged:
            continue
        if len(tagged) == len(examples):
            # Purely target-owned and no longer demanded — retire it.
            conn.execute(
                "UPDATE skill_gaps SET status = 'closed', demand_count = 0, priority = 0, "
                "updated_at = datetime('now') WHERE id = ?",
                (row["id"],),
            )
            retired += 1
        else:
            # Mixed row: job demand persists — just drop the stale target entries.
            untagged = [e for e in examples if not (isinstance(e, dict) and e.get("target"))]
            conn.execute(
                "UPDATE skill_gaps SET example_jobs = ?, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(untagged), row["id"]),
            )

    conn.commit()
    return {"inserted": inserted, "updated": updated, "retired": retired, "reopened": reopened}


def jd_vs_field(
    conn: sqlite3.Connection,
    targets: list[dict] | None = None,
    field_counts: dict[str, int] | None = None,
) -> dict:
    """Where JD-demanded skills and field-observed FDE attributes diverge.

    `field_only` is the interesting list: attributes real practitioners say
    matter that no JD asks for — the disconnect between job descriptions and
    the actual shape of successful FDEs.
    """
    if targets is None:
        targets = list_targets(conn, status="active")
    if field_counts is None:
        field_counts = dispatch_attribute_counts(conn)

    jd_skills: dict[str, str] = {}
    for t in targets:
        for skill in required_skills_for(t):
            jd_skills.setdefault(skill.lower(), skill)

    field_names: dict[str, str] = {}
    for r in conn.execute("SELECT attributes FROM role_dispatches").fetchall():
        for attr in _parse_json_list(r["attributes"]):
            canonical = _canon(str(attr))
            field_names.setdefault(canonical.lower(), canonical)

    both = sorted(jd_skills[k] for k in jd_skills.keys() & field_names.keys())
    jd_only = sorted(jd_skills[k] for k in jd_skills.keys() - field_names.keys())
    field_only = sorted(field_names[k] for k in field_names.keys() - jd_skills.keys())
    dispatch_count = conn.execute("SELECT COUNT(*) AS cnt FROM role_dispatches").fetchone()["cnt"]
    return {"both": both, "jd_only": jd_only, "field_only": field_only, "dispatch_count": dispatch_count}


# ---------------------------------------------------------------------------
# Trajectory
# ---------------------------------------------------------------------------


def get_trajectory(conn: sqlite3.Connection, target_id: int) -> dict | None:
    """Fit-over-time series for a target, with per-step deltas."""
    target = get_target(conn, target_id)
    if not target:
        return None

    rows = conn.execute(
        "SELECT * FROM role_fit_snapshots WHERE role_target_id = ? "
        "ORDER BY computed_at ASC, id ASC",
        (target_id,),
    ).fetchall()

    snapshots = []
    deltas = []
    prev = None
    for r in rows:
        snap = {
            "fit_score": r["fit_score"],
            "computed_at": r["computed_at"],
            "gaps": _parse_json_list(r["gaps_json"]),
            "evidence": json.loads(r["evidence_json"]) if r["evidence_json"] else {},
        }
        snapshots.append(snap)
        if prev is not None:
            prev_gaps = {str(s).lower() for s in prev["gaps"]}
            cur_gaps = {str(s).lower() for s in snap["gaps"]}
            deltas.append({
                "from": prev["computed_at"],
                "to": snap["computed_at"],
                "fit_delta": round((snap["fit_score"] or 0) - (prev["fit_score"] or 0), 2),
                "gaps_closed": sorted(prev_gaps - cur_gaps),
                "gaps_opened": sorted(cur_gaps - prev_gaps),
            })
        prev = snap

    return {"target": target, "snapshots": snapshots, "deltas": deltas}


def render_trajectory_markdown(trajectory: dict) -> str:
    """Render a target's fit trajectory as markdown (vault-ready)."""
    t = trajectory["target"]
    snapshots = trajectory["snapshots"]
    company = f" @ {t['company_name']}" if t.get("company_name") else ""
    lines = [f"# Target Trajectory — {t['title']}{company}", ""]
    lines.append(f"**Horizon:** {t.get('horizon') or '—'}  |  **Status:** {t['status']}")
    if t.get("target_comp_min") or t.get("target_comp_max"):
        lo = f"${t['target_comp_min']:,}" if t.get("target_comp_min") else "?"
        hi = f"${t['target_comp_max']:,}" if t.get("target_comp_max") else "?"
        lines.append(f"**Comp band:** {lo}–{hi}")
    if t.get("why"):
        lines.append(f"**Why:** {t['why']}")
    lines.append("")

    if not snapshots:
        lines.append("No fit snapshots yet — run `beacon target fit " + str(t["id"]) + "` to start the time series.")
        return "\n".join(lines) + "\n"

    lines.append("## Fit over time")
    lines.append("")
    lines.append("| Date | Fit | Open gaps |")
    lines.append("|------|-----|-----------|")
    for s in snapshots:
        day = (s["computed_at"] or "")[:10]
        lines.append(f"| {day} | {s['fit_score']:.1f} | {len(s['gaps'])} |")
    lines.append("")

    first, last = snapshots[0], snapshots[-1]
    if len(snapshots) > 1:
        total = round((last["fit_score"] or 0) - (first["fit_score"] or 0), 2)
        arrow = "↑" if total > 0 else ("↓" if total < 0 else "→")
        lines.append(
            f"Overall: **{first['fit_score']:.1f} → {last['fit_score']:.1f}** ({arrow} {total:+.1f} "
            f"since {(first['computed_at'] or '')[:10]})"
        )
        lines.append("")

    if trajectory["deltas"]:
        lines.append("## What moved the number")
        lines.append("")
        for d in trajectory["deltas"]:
            day = (d["to"] or "")[:10]
            lines.append(f"### {day} ({d['fit_delta']:+.1f})")
            if d["gaps_closed"]:
                lines.append(f"- Gaps closed: {', '.join(d['gaps_closed'])}")
            if d["gaps_opened"]:
                lines.append(f"- Gaps opened: {', '.join(d['gaps_opened'])}")
            if not d["gaps_closed"] and not d["gaps_opened"]:
                lines.append("- No gap changes (evidence/story/momentum shift)")
            lines.append("")

    lines.append("## Current gaps")
    lines.append("")
    if last["gaps"]:
        for g in last["gaps"]:
            lines.append(f"- {g}")
    else:
        lines.append("None — required skills fully covered. Time to re-raise the bar?")
    lines.append("")

    evidence = last.get("evidence") or {}
    win_ev = evidence.get("win_evidence") or {}
    if win_ev:
        lines.append("## Win-backed skills (resume-ready)")
        lines.append("")
        for skill, wins in win_ev.items():
            titles = "; ".join(w["title"] for w in wins[:2])
            lines.append(f"- **{skill}** — {titles}")
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Dispatches — field reports from real FDEs
# ---------------------------------------------------------------------------


def add_dispatch(
    conn: sqlite3.Connection,
    title: str,
    url: str | None = None,
    source: str | None = None,
    author: str | None = None,
    author_role: str | None = None,
    role_target_id: int | None = None,
    attributes: list[str] | None = None,
    takeaways: str | None = None,
    quote: str | None = None,
    date_published: str | None = None,
) -> int:
    """Log a dispatch from someone actually doing a target role."""
    cur = conn.execute(
        """INSERT INTO role_dispatches
           (title, url, source, author, author_role, role_target_id,
            attributes, takeaways, quote, date_published)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title,
            url,
            source,
            author,
            author_role,
            role_target_id,
            json.dumps(attributes) if attributes else None,
            takeaways,
            quote,
            date_published,
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_dispatches(conn: sqlite3.Connection, role_target_id: int | None = None, limit: int = 50) -> list[dict]:
    """List dispatches, newest first."""
    clauses = ""
    params: list = []
    if role_target_id is not None:
        clauses = " WHERE role_target_id = ?"
        params.append(role_target_id)
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM role_dispatches{clauses} ORDER BY id DESC LIMIT ?", params
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["attributes"] = _parse_json_list(d.get("attributes"))
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Wins ↔ target gaps (regular check for career review / dashboard)
# ---------------------------------------------------------------------------


def wins_closing_gaps(conn: sqlite3.Connection, since: str | None = None) -> list[dict]:
    """Wins whose technologies hit a target-demanded missing skill.

    The regular check: which logged wins are evidence against the gaps the
    aspirational targets care about — and therefore belong on the resume.
    """
    analysis = analyze_target_gaps(conn)
    gap_names = {g["skill_name"].lower(): g["skill_name"] for g in analysis["gaps"]}
    if not gap_names:
        return []

    clauses = ""
    params: list = []
    if since:
        clauses = " WHERE win_date >= ?"
        params.append(since)
    rows = conn.execute(
        f"SELECT id, title, win_date, technologies FROM wins{clauses} ORDER BY win_date DESC", params
    ).fetchall()

    out = []
    for r in rows:
        hit = sorted({
            gap_names[_canon(str(t)).lower()]
            for t in _parse_json_list(r["technologies"])
            if _canon(str(t)).lower() in gap_names
        })
        if hit:
            out.append({"id": r["id"], "title": r["title"], "win_date": r["win_date"], "gap_skills": hit})
    return out


# ---------------------------------------------------------------------------
# Seeds — first aspirational targets (Palantir-tier + frontier-lab FDE)
# ---------------------------------------------------------------------------

SEED_TARGETS = [
    {
        "title": "Forward Deployed Software Engineer",
        "company": "Palantir",
        "archetype": "solutions_fde",
        "horizon": "2y",
        "target_comp_min": 190_000,
        "target_comp_max": 240_000,
        "why": (
            "Palantir-tier FDE is the canonical next-tier move (~$215k TC median). "
            "One documented enterprise FDE tour is the qualification; this is the "
            "2028–2030 target on the comp line."
        ),
        "description_snapshot": (
            "Forward Deployed Software Engineers work directly with customers to "
            "understand their hardest problems and build software that solves them. "
            "You will deploy and configure the platform on customer infrastructure, "
            "integrate messy enterprise data, model the customer's world in the "
            "ontology, and ship production workflows under real-world constraints. "
            "Requirements: strong programming skills in Python, Java, or TypeScript; "
            "SQL and data integration experience; comfort with AWS, Kubernetes, and "
            "Docker; experience deploying LLMs and AI agents into production "
            "workflows; exceptional customer-facing communication; high tolerance "
            "for ambiguity and travel; ability to own outcomes end-to-end on site."
        ),
        "required_skills": [
            "Python", "Java", "JavaScript", "SQL", "AWS", "Kubernetes", "Docker",
            "Data Integration", "LLMs", "AI Agents", "Customer-facing Delivery",
            "Ontology Modeling", "Ambiguity Tolerance",
        ],
    },
    {
        "title": "Staff Forward Deployed Engineer / Applied AI Lead",
        "company": None,
        "archetype": "solutions_fde",
        "horizon": "3y",
        "target_comp_min": 200_000,
        "target_comp_max": 240_000,
        "why": (
            "The realistic $200–240k next-move rung: staff-level applied-AI/FDE "
            "leadership at a serious enterprise AI shop. Matches the comp line "
            "without requiring a frontier-lab bar."
        ),
        "description_snapshot": (
            "Lead applied AI deployments for enterprise customers end to end. "
            "Scope and deliver LLM and agent systems against real business "
            "workflows, define evaluation harnesses, drive adoption and change "
            "management with executive stakeholders, and mentor delivery engineers. "
            "Requirements: deep experience with LLMs, RAG, and AI agents in "
            "production; Python and SQL fluency; Docker-based deployment; rigorous "
            "evals discipline; demonstrated enablement of customer teams; executive "
            "communication and change management at the VP level."
        ),
        "required_skills": [
            "LLMs", "RAG", "AI Agents", "Python", "SQL", "Docker", "Evals",
            "Prompt Engineering", "Change Management", "Enablement",
            "Executive Communication",
        ],
    },
    {
        "title": "Forward Deployed Engineer",
        "company": "Anthropic",
        "archetype": "solutions_fde",
        "horizon": "4y",
        "target_comp_min": 320_000,
        "target_comp_max": 460_000,
        "why": (
            "Frontier-lab FDE is the stretch tier ($350k+ TC, mostly equity) — the "
            "2031 target. Requires a documented tour of closing the value overhang "
            "at a real enterprise plus frontier-model depth."
        ),
        "description_snapshot": (
            "Forward Deployed Engineers embed with strategic customers to turn "
            "frontier model capability into deployed business value. You will "
            "architect and ship Claude-powered agent systems, design evals that "
            "prove business impact, build with MCP and the agent SDK, and feed "
            "field learnings back into the product. Requirements: expert-level "
            "prompt engineering and LLM systems design; production RAG and agent "
            "architectures; Python; embeddings and vector databases; evals; "
            "enterprise deployment experience; exceptional stakeholder management "
            "with both executives and engineers."
        ),
        "required_skills": [
            "Claude", "LLMs", "AI Agents", "RAG", "Prompt Engineering", "Python",
            "MCP", "Embeddings", "Vector Databases", "Evals",
            "Enterprise Deployment", "Stakeholder Management",
        ],
    },
    {
        "title": "Forward Deployed Engineer",
        "company": "OpenAI",
        "archetype": "solutions_fde",
        "horizon": "4y",
        "target_comp_min": 300_000,
        "target_comp_max": 440_000,
        "why": (
            "Second frontier-lab exemplar so the 4y tier isn't a single data "
            "point; keeps the target-gap analysis honest about what the tier "
            "actually demands."
        ),
        "description_snapshot": (
            "Work hands-on with strategic customers to deploy frontier models "
            "against their highest-value problems. Build production systems on "
            "the API — fine-tuning, RAG, agentic workflows — and own technical "
            "success from prototype through production. Requirements: strong "
            "Python; production LLM systems including fine-tuning, embeddings, "
            "and vector databases; AI agent architectures; solution architecture "
            "for enterprise environments; ability to operate autonomously inside "
            "customer organizations."
        ),
        "required_skills": [
            "Python", "LLMs", "Fine-tuning", "RAG", "AI Agents", "Embeddings",
            "Vector Databases", "Solution Architecture", "Enterprise Deployment",
        ],
    },
]

SEED_DISPATCHES = [
    {
        "title": "Reflections on Palantir",
        "url": "https://nabeelqu.co/reflections-on-palantir",
        "source": "blog",
        "author": "Nabeel S. Qureshi",
        "author_role": "Former FDE @ Palantir",
        "target_company": "Palantir",
        "attributes": [
            "Customer Obsession", "Ownership", "On-site User Empathy",
            "Data Integration", "Pragmatism Over Elegance", "Ambiguity Tolerance",
            "Product Instinct",
        ],
        "takeaways": (
            "Field report: success as a Palantir FDE hinged less on raw engineering "
            "than on customer obsession, end-to-end ownership, and tolerating "
            "ambiguity on site. Unglamorous data integration work is the moat — a "
            "notable disconnect from how JDs weight the role."
        ),
    },
]


def seed_targets(conn: sqlite3.Connection) -> dict:
    """Seed the aspirational role targets (idempotent on title + company)."""
    inserted = []
    skipped = []
    for seed in SEED_TARGETS:
        company_id = None
        if seed["company"]:
            row = conn.execute(
                "SELECT id FROM companies WHERE name = ? OR name LIKE ?",
                (seed["company"], f"{seed['company']}%"),
            ).fetchone()
            if row:
                company_id = row["id"]
            else:
                # Minimal company record so targets at the same title (e.g. two
                # frontier-lab FDE roles) stay distinct and dedupe stays sane.
                cur = conn.execute(
                    "INSERT INTO companies (name, tier) VALUES (?, 4)", (seed["company"],)
                )
                company_id = cur.lastrowid

        existing = conn.execute(
            "SELECT id FROM role_targets WHERE LOWER(title) = LOWER(?) "
            "AND (company_id IS ? OR company_id = ?)",
            (seed["title"], company_id, company_id),
        ).fetchone()
        label = seed["title"] + (f" @ {seed['company']}" if seed["company"] else "")
        if existing:
            skipped.append(label)
            continue

        target_id = add_target(
            conn,
            title=seed["title"],
            company_id=company_id,
            archetype=seed["archetype"],
            horizon=seed["horizon"],
            target_comp_min=seed["target_comp_min"],
            target_comp_max=seed["target_comp_max"],
            description_snapshot=seed["description_snapshot"],
            required_skills=seed["required_skills"],
            why=seed["why"],
        )
        inserted.append({"id": target_id, "title": label})

    dispatches_inserted = 0
    for seed in SEED_DISPATCHES:
        existing = conn.execute(
            "SELECT id FROM role_dispatches WHERE url = ?", (seed["url"],)
        ).fetchone()
        if existing:
            continue
        target_row = None
        if seed.get("target_company"):
            target_row = conn.execute(
                "SELECT t.id FROM role_targets t JOIN companies c ON t.company_id = c.id "
                "WHERE c.name LIKE ? LIMIT 1",
                (f"{seed['target_company']}%",),
            ).fetchone()
        add_dispatch(
            conn,
            title=seed["title"],
            url=seed["url"],
            source=seed["source"],
            author=seed["author"],
            author_role=seed["author_role"],
            role_target_id=target_row["id"] if target_row else None,
            attributes=seed["attributes"],
            takeaways=seed["takeaways"],
        )
        dispatches_inserted += 1

    return {
        "inserted": inserted,
        "skipped": skipped,
        "dispatches_inserted": dispatches_inserted,
        "seeded_at": date.today().isoformat(),
    }
