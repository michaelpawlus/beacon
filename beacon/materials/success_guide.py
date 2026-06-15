"""FDE success guide — a living, regenerable playbook (beacon career guide, #45).

WS5 of the beacon v2 career-OS pivot (see ``docs/career-strategy.md``). The
"evolving guide to be successful in the new FDE job": a vault-resident document
grounded in actual data, not a static essay. It answers two questions on every
run — *what am I already strong at* and *where do I need to spend more time* —
by joining four data sources the rest of beacon already maintains:

* ``wins`` (shipped) — this quarter's delivery-vs-diffusion mix.
* ``role_targets`` / ``beacon target gaps`` (#43) — the aspirational skill gaps.
* ``role_market_snapshots`` (#44) — where the FDE role family is heading.
* ``media_log`` — the high-signal reading/sharing queue.

Deterministic assembly, mirroring ``interview_brief.py``: no mandatory LLM call,
and every section degrades gracefully when its source table is empty so the
guide is useful from week one and richer every quarter.

Core thesis baked in: the overhang between model capability and realized
business value (diffusion, adoption, enablement, deployment, alignment) is where
FDE roles create outsized value.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import date, datetime

from beacon.career import category_mix, current_role, list_wins, resolve_since
from beacon.db.profile import get_skills
from beacon.market import (
    SNAPSHOT_STALE_DAYS,
    get_family,
    latest_snapshot_any_window,
)
from beacon.research.skill_gaps import _normalize_skill
from beacon.targets import analyze_target_gaps

# The static framing that opens every guide. Kept here (not in the DB) because
# it's the unchanging thesis, not data — the rest of the guide is the evidence
# for or against living it out.
THESIS = (
    "The gap between what models *can* do and what businesses *actually* "
    "realize from them — diffusion, adoption, enablement, deployment, "
    "alignment — is where Forward Deployed work creates outsized value. "
    "Capability is commoditizing; closing the realization overhang is not. "
    "This guide measures whether your week-to-week work, your skills, and the "
    "market are pulling in that direction."
)

# Proficiency → strength weight (only advanced/expert count as a standing strength).
_PROFICIENCY_RANK = {"expert": 2, "advanced": 1}

# Tags / categories that mark a media item as relevant to the FDE success thesis.
_FDE_MEDIA_TAGS = {
    "fde", "adoption", "enablement", "diffusion", "deployment",
    "forward-deployed", "solutions", "applied-ai", "alignment",
}


def _snapshot_age_days(captured_at: str | None) -> int | None:
    """Days since a snapshot's ``captured_at`` (the ``%Y-%m-%dT%H:%M:%SZ`` shape
    ``latest_snapshot`` returns). ``None`` when absent/unparseable."""
    if not captured_at:
        return None
    try:
        ts = datetime.fromisoformat(captured_at.replace("Z", ""))
    except ValueError:
        return None
    return (datetime.utcnow() - ts).days


def _parse_json_list(value) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [parsed]
    except (json.JSONDecodeError, TypeError):
        return [value]


# ---------------------------------------------------------------------------
# Strengths — what's already demonstrable
# ---------------------------------------------------------------------------


def compute_strengths(conn: sqlite3.Connection, wins: list[dict]) -> list[dict]:
    """Skills the user can already stand on, ranked by evidence depth.

    A skill counts as a strength when it's either self-rated advanced/expert OR
    backed by logged wins (the resume-ready signal — a claim with receipts).
    Win-backed skills sort first; proficiency is the tiebreaker. This is the
    deliberate mirror of the gaps section: the guide always shows both edges of
    the picture, never just the deficits.

    Win technologies and profile skill names are both run through the same
    ``_normalize_skill`` canonicalization the gap analysis uses, so a win tagged
    ``k8s`` matches a profile skill ``Kubernetes`` instead of being mis-flagged
    as an unlisted skill to add.
    """
    win_tech: Counter[str] = Counter()
    win_examples: dict[str, str] = {}
    win_display: dict[str, str] = {}
    for w in wins:
        for t in _parse_json_list(w.get("technologies")):
            canonical = _normalize_skill(str(t))
            key = canonical.lower()
            win_tech[key] += 1
            win_examples.setdefault(key, w["title"])
            win_display.setdefault(key, canonical)

    strengths: list[dict] = []
    seen: set[str] = set()

    for s in get_skills(conn):
        name = s["name"]
        key = _normalize_skill(name).lower()
        prof = s["proficiency"]
        win_count = win_tech.get(key, 0)
        if (_PROFICIENCY_RANK.get(prof, 0) == 0) and win_count == 0:
            continue
        seen.add(key)
        strengths.append({
            "skill": name,
            "category": s["category"],
            "proficiency": prof,
            "win_evidence_count": win_count,
            "example_win": win_examples.get(key),
        })

    # Win-backed skills the profile doesn't even list yet — surfaced (in their
    # canonical form) so they get added to the skills table and onto the resume.
    for key, count in win_tech.items():
        if key in seen:
            continue
        strengths.append({
            "skill": win_display.get(key, key),
            "category": None,
            "proficiency": None,
            "win_evidence_count": count,
            "example_win": win_examples.get(key),
            "unlisted": True,
        })

    strengths.sort(
        key=lambda s: (
            -s["win_evidence_count"],
            -_PROFICIENCY_RANK.get(s.get("proficiency"), 0),
            s["skill"].lower(),
        )
    )
    return strengths


# ---------------------------------------------------------------------------
# Reading / sharing queue
# ---------------------------------------------------------------------------


def high_signal_media(conn: sqlite3.Connection, since: str | None = None, limit: int = 6) -> list[dict]:
    """High-signal media rows (rating ≥4 / shareable / why_it_matters set),
    preferring those tagged to the FDE/adoption thesis.

    No hard filter on the tags — a 5-star item with no tags still belongs in the
    queue — but thesis-tagged items sort first so the reading list stays on-topic
    when there's plenty to choose from."""
    clauses = ["(rating >= 4 OR team_shareable = 1 OR (why_it_matters IS NOT NULL AND why_it_matters != ''))"]
    params: list = []
    if since:
        clauses.append("(date_consumed IS NULL OR date_consumed >= ?)")
        params.append(since)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"SELECT * FROM media_log WHERE {where} ORDER BY rating DESC, date_consumed DESC, id DESC",
        params,
    ).fetchall()

    items: list[dict] = []
    for r in rows:
        tags = {str(t).lower() for t in _parse_json_list(r["tags"])}
        category = (r["share_category"] or "").lower()
        on_thesis = bool(tags & _FDE_MEDIA_TAGS) or any(t in category for t in _FDE_MEDIA_TAGS)
        items.append({
            "id": r["id"],
            "title": r["title"],
            "source_type": r["source_type"],
            "creator": r["creator"],
            "rating": r["rating"],
            "why_it_matters": r["why_it_matters"],
            "share_note": r["share_note"],
            "url": r["url"],
            "on_thesis": on_thesis,
        })

    # Thesis-tagged first, then by rating; stable within each bucket.
    items.sort(key=lambda m: (not m["on_thesis"], -(m["rating"] or 0)))
    return items[:limit]


# ---------------------------------------------------------------------------
# Recommended focus — the heuristic synthesis of the sections above
# ---------------------------------------------------------------------------


def recommend_focus(
    win_mix: dict,
    gaps: list[dict],
    snapshot: dict | None,
    strengths: list[dict],
) -> list[str]:
    """Turn the assembled sections into 2–4 plain-language "do this next" calls.

    Pure heuristic, no LLM. Each rule fires only when its inputs exist, so an
    empty database yields the seed-the-system nudges rather than noise."""
    recs: list[str] = []

    # 1. Diffusion-vs-delivery balance — the thesis applied to the week's work.
    diffusion = win_mix.get("diffusion", 0)
    delivery = win_mix.get("delivery", 0)
    total = diffusion + delivery
    if total == 0:
        recs.append(
            "No delivery or diffusion wins logged this quarter — start the "
            "evidence base with `beacon career win add` so this guide has "
            "something to reason about."
        )
    elif diffusion < delivery:
        recs.append(
            f"Win mix skews delivery ({delivery}) over diffusion "
            f"({diffusion}). The overhang closes on the diffusion side — pick "
            "at least one adoption/enablement win to log this quarter."
        )
    else:
        recs.append(
            f"Diffusion ({diffusion}) is keeping pace with delivery "
            f"({delivery}) — the mix is pulling toward where FDE value lives. "
            "Hold the ratio."
        )

    # 2. Market-rising skills that are *also* open target gaps — the sharpest
    #    signal: the market wants it, the aspirational roles want it, you lack it.
    diff = (snapshot or {}).get("diff_vs_previous") or {}
    rising = [s["skill"] for s in diff.get("skills_rising", [])]
    rising += list(diff.get("skills_added", []))
    gap_names = {g["skill_name"].lower(): g for g in gaps}
    overlap = [r for r in rising if r.lower() in gap_names]
    for skill in overlap[:2]:
        recs.append(
            f"'{skill}' is rising in the market *and* is an open target gap — "
            "the highest-leverage thing to learn this quarter."
        )

    # 3. The single most-pressing horizon-weighted gap (if rule 2 didn't already
    #    name it).
    if gaps:
        top = gaps[0]
        if top["skill_name"].lower() not in {o.lower() for o in overlap[:2]}:
            field = " — and real FDEs report needing it" if top.get("field_observed") else ""
            recs.append(
                f"Top horizon-weighted gap: **{top['skill_name']}** "
                f"({top['demand_count']} target(s), priority {top['priority']}){field}."
            )

    # 4. Gaps you're already closing — get them onto the resume.
    evidenced = [g for g in gaps if g.get("win_evidence_count")]
    if evidenced:
        names = ", ".join(g["skill_name"] for g in evidenced[:3])
        recs.append(
            f"You have win evidence accruing against open gaps ({names}) — "
            "add these to your skills/resume; they're no longer gaps, they're "
            "under-claimed strengths."
        )
    elif not gaps and snapshot is None:
        recs.append(
            "No aspirational targets or market snapshot yet — run "
            "`beacon target seed` and `beacon career market` to point this "
            "guide at the 2–4 year vector."
        )

    return recs[:4]


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _open_target_gaps(conn: sqlite3.Connection, gaps: list[dict]) -> list[dict]:
    """Attach the tracked ``skill_gaps.status`` to each target gap and drop any
    the user has explicitly marked closed.

    Mirrors ``beacon target gaps``: ``analyze_target_gaps`` doesn't join the
    tracker, so a gap retired via ``beacon gaps update <skill> --status closed``
    would otherwise still surface as open here and could be recommended as the
    top focus even though the tracker says it's done."""
    statuses = {
        r["skill_name"].lower(): r["status"]
        for r in conn.execute("SELECT skill_name, status FROM skill_gaps").fetchall()
    }
    out: list[dict] = []
    for g in gaps:
        status = statuses.get(g["skill_name"].lower(), "open")
        if status == "closed":
            continue
        out.append({**g, "status": status})
    return out


def build_guide(
    conn: sqlite3.Connection,
    since: str = "90d",
    family_key: str | None = None,
) -> dict:
    """Assemble the success-guide payload from the four data sources.

    Deterministic and read-only — consumes the *latest persisted* market
    snapshot (run `beacon career market` to refresh it). Every section is
    populated independently so a sparse database still produces a useful guide.
    """
    family = get_family(family_key)
    since_iso = resolve_since(since)

    wins = list_wins(conn, since=since, limit=500)
    win_mix = category_mix(wins)

    analysis = analyze_target_gaps(conn)
    gaps = _open_target_gaps(conn, analysis["gaps"])

    # Any window — the guide just displays the most recent market read, so a
    # user who only keeps `--since-days N` snapshots still gets a market section
    # instead of a spurious "no snapshot yet".
    snapshot = latest_snapshot_any_window(conn, family.key)
    # Staleness must read the *selected family's* snapshot — a fresh snapshot for
    # a different family must not mask a months-old one for this family.
    market_age = _snapshot_age_days(snapshot.get("captured_at")) if snapshot else None
    market_stale = market_age is None or market_age > SNAPSHOT_STALE_DAYS

    strengths = compute_strengths(conn, wins)
    media = high_signal_media(conn, since=since_iso)

    recommendations = recommend_focus(win_mix, gaps, snapshot, strengths)

    role = current_role(conn)

    return {
        "generated_at": date.today().isoformat(),
        "since": since_iso,
        "family": family.key,
        "family_label": family.label,
        "role": {"title": role["title"], "company": role["company"]} if role else None,
        "thesis": THESIS,
        "win_mix": win_mix,
        "win_count": len(wins),
        "strengths": strengths,
        "gaps": gaps,
        "targets_analyzed": analysis["targets_analyzed"],
        "market_snapshot": snapshot,
        "market_age_days": market_age,
        "market_stale": market_stale,
        "reading_queue": media,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _fmt_band(lo, hi) -> str:
    if not lo and not hi:
        return "—"
    lo_s = f"${lo:,.0f}" if lo else "?"
    hi_s = f"${hi:,.0f}" if hi else "?"
    return f"{lo_s}–{hi_s}"


def render_guide_markdown(guide: dict) -> str:
    """Render the assembled guide into the sectioned markdown body."""
    lines: list[str] = []
    lines.append(f"# FDE Success Guide — {guide['generated_at']}\n")
    role = guide.get("role")
    if role:
        lines.append(f"**Current role:** {role['title']} at {role['company']}")
    lines.append(f"**Role family:** {guide['family_label']}")
    lines.append(f"**Window:** since {guide['since']}")
    lines.append("")

    # 1. Thesis
    lines.append("## 1. Thesis — where FDE value comes from")
    lines.append("")
    lines.append(guide["thesis"])
    lines.append("")

    # 2. This quarter's win mix
    lines.append("## 2. This quarter's win mix")
    lines.append("")
    mix = guide["win_mix"]
    if guide["win_count"] == 0:
        lines.append(
            "_No wins logged in this window. Log them as they happen with "
            "`beacon career win add` — the guide gets sharper the more evidence "
            "it has._"
        )
    else:
        for cat, count in sorted(mix["by_category"].items(), key=lambda kv: -kv[1]):
            lines.append(f"- {cat}: {count}")
        lines.append("")
        lines.append(
            f"**Diffusion vs delivery: {mix['diffusion']} vs {mix['delivery']}.** "
            "Diffusion (adoption / enablement / relationship) is the overhang-closing "
            "work — keep this ratio a choice, not an accident."
        )
    lines.append("")

    # 3. Strengths — what's already demonstrable
    lines.append("## 3. Strengths — what you can already stand on")
    lines.append("")
    strengths = guide["strengths"]
    if not strengths:
        lines.append(
            "_No advanced/expert skills or win-backed skills yet. Rate skills "
            "(`beacon profile interview`) and log wins to build this out._"
        )
    else:
        for s in strengths[:10]:
            bits = [f"**{s['skill']}**"]
            if s.get("proficiency"):
                bits.append(s["proficiency"])
            if s.get("win_evidence_count"):
                bits.append(f"{s['win_evidence_count']} win(s)")
            if s.get("unlisted"):
                bits.append("_not in skills table — add it_")
            line = f"- {' · '.join(bits)}"
            if s.get("example_win"):
                line += f" (e.g. {s['example_win']})"
            lines.append(line)
    lines.append("")

    # 4. Open target gaps — where to spend more time
    lines.append("## 4. Open target gaps — where to spend more time")
    lines.append("")
    gaps = guide["gaps"]
    if not guide["targets_analyzed"]:
        lines.append(
            "_No active aspirational targets. Seed the board with "
            "`beacon target seed` so the guide knows what you're reaching for._"
        )
    elif not gaps:
        lines.append(
            "_No open gaps against your active targets — your profile already "
            "covers their required skills. Stretch the targets or raise the bar._"
        )
    else:
        for g in gaps[:8]:
            field = " · _field-validated_" if g.get("field_observed") else ""
            evidence = (
                f" · {g['win_evidence_count']} win(s) closing it"
                if g.get("win_evidence_count") else ""
            )
            learning = " · _learning_" if g.get("status") == "learning" else ""
            lines.append(
                f"- **{g['skill_name']}** — {g['demand_count']} target(s), "
                f"priority {g['priority']}{field}{learning}{evidence}"
            )
    lines.append("")

    # 5. Market direction
    lines.append("## 5. Market direction")
    lines.append("")
    snap = guide["market_snapshot"]
    if not snap:
        lines.append(
            "_No market snapshot yet. Run `beacon career market` to capture "
            "where the FDE role family is heading (salary, skill mix, what's "
            "rising)._"
        )
    else:
        age = guide["market_age_days"]
        listings = snap.get("listings", {})
        lines.append(
            f"_Latest snapshot {snap.get('captured_at', '?')}"
            + (f" ({age}d old)" if age is not None else "")
            + f" · {listings.get('sampled', 0)} listings sampled._"
        )
        band = _fmt_band(listings.get("avg_comp_min"), listings.get("avg_comp_max"))
        lines.append(f"- **Comp band (avg):** {band}")
        if snap.get("direction"):
            lines.append(f"- **Direction:** {snap['direction']}")
        diff = snap.get("diff_vs_previous") or {}
        rising = [s["skill"] for s in diff.get("skills_rising", [])] + list(diff.get("skills_added", []))
        falling = [s["skill"] for s in diff.get("skills_falling", [])] + list(diff.get("skills_removed", []))
        if rising:
            lines.append(f"- **Rising / new skills:** {', '.join(rising[:6])}")
        if falling:
            lines.append(f"- **Falling / dropped skills:** {', '.join(falling[:6])}")
        if not diff:
            lines.append("- _First snapshot for this family — no trend to compare yet._")
        if guide["market_stale"]:
            lines.append("")
            lines.append(
                f"> ⚠️ Snapshot is older than {SNAPSHOT_STALE_DAYS} days — "
                "re-run `beacon career market` to refresh the trend."
            )
    lines.append("")

    # 6. Recommended focus — the synthesis
    lines.append("## 6. Recommended focus this quarter")
    lines.append("")
    for rec in guide["recommendations"]:
        lines.append(f"- {rec}")
    if not guide["recommendations"]:
        lines.append("- _Not enough data to synthesize a focus yet._")
    lines.append("")

    # 7. Reading / sharing queue
    lines.append("## 7. Reading & sharing queue")
    lines.append("")
    media = guide["reading_queue"]
    if not media:
        lines.append(
            "_No high-signal media logged. Capture what you read/watch with "
            "`beacon media add` (rate it ≥4 or mark it shareable to surface here)._"
        )
    else:
        for m in media:
            star = f"{m['rating']}★ " if m.get("rating") else ""
            creator = f" — {m['creator']}" if m.get("creator") else ""
            thesis = " · _on-thesis_" if m.get("on_thesis") else ""
            lines.append(f"- {star}**{m['title']}**{creator}{thesis}")
            note = m.get("why_it_matters") or m.get("share_note")
            if note:
                lines.append(f"  - {note}")
    lines.append("")

    return "\n".join(lines)
