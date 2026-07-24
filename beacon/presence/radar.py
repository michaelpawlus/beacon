"""Posting-strategy radar — turn recent work + live discussion into a ranked
content backlog.

Two inputs, one ranked output:

1. **Internal sweep** — recent ``sessions``, recently-touched ``projects``,
   delivered ``presentations``, and high-signal ``media_log`` rows become
   "you did X → post about it here" opportunities.
2. **External radar** — what's being discussed right now in the user's areas
   (via the LLM web-search tool) becomes timely "comment on X, you have
   credibility via Y" opportunities, and bumps the timeliness of internal ones.

Opportunities are deduped against the existing content calendar / drafts so the
radar surfaces the gap between what you *did* and what you've *posted*, then
scored and ranked.

The internal sweep is pure, deterministic SQL — no network, no LLM. Only the
external radar reaches out, and it's injectable (``search_fn``) so it can be
mocked in tests and skipped entirely with ``web=False``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date

from beacon.util.dates import format_iso, utcnow

# Source weights — how much a kind of artifact is worth posting about, all else equal.
_SOURCE_WEIGHT = {
    "trend": 2.0,
    "project": 1.5,
    "presentation": 1.5,
    "session": 1.0,
    "media": 0.5,
}

_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "into", "using", "used",
    "your", "you", "are", "was", "were", "how", "why", "what", "when", "new",
    "post", "blog", "about", "via", "more", "have", "has", "had", "our", "out",
    "built", "build", "made", "make", "add", "added", "support", "supports",
}


def _safe_json_list(value) -> list:
    """Parse a JSON-array column into a list, tolerating None / bad data."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _days_since(date_str: str | None, today: date) -> int | None:
    """Whole days between ``date_str`` (YYYY-MM-DD[...]) and ``today``."""
    if not date_str:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(date_str))
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return (today - d).days


def _norm_tokens(*texts: str | None) -> set[str]:
    """Significant lowercase word tokens (len >= 4, minus stopwords)."""
    out: set[str] = set()
    for t in texts:
        if not t:
            continue
        for w in re.findall(r"[a-zA-Z0-9+#.]+", str(t).lower()):
            w = w.strip(".")
            if len(w) >= 4 and w not in _STOPWORDS:
                out.add(w)
    return out


# --------------------------------------------------------------------------
# Internal sweep
# --------------------------------------------------------------------------

def _route_platforms(source: str, *, public: bool = False, has_recording: bool = False) -> list[str]:
    """Heuristic platform routing for an opportunity."""
    if source == "project":
        base = ["github", "blog", "linkedin"] if public else ["blog", "linkedin"]
    elif source == "presentation":
        base = ["linkedin", "blog"]
        if has_recording:
            base.append("twitter")
    elif source == "session":
        base = ["linkedin", "blog"]
    elif source == "media":
        base = ["linkedin"]
    elif source == "trend":
        base = ["linkedin", "blog"]
    else:
        base = ["linkedin"]
    return base


def sweep_sessions(conn: sqlite3.Connection, since_days: int, today: date) -> list[dict]:
    from beacon.session import list_sessions

    out: list[dict] = []
    for s in list_sessions(conn, limit=200):
        age = _days_since(s.get("session_date"), today)
        if age is None or age > since_days:
            continue
        tech = _safe_json_list(s.get("technologies"))
        evidence: list[str] = []
        if s.get("impact"):
            evidence.append(f"Impact: {s['impact']}")
        for c in _safe_json_list(s.get("challenges"))[:2]:
            evidence.append(f"Solved: {c}")
        out.append({
            "source": "session",
            "source_id": s.get("id"),
            "title": s.get("title") or "Untitled session",
            "topic": s.get("title") or "Recent work",
            "angle": s.get("summary") or "Write up what you built and what you learned.",
            "tech": tech,
            "evidence": evidence,
            "date": s.get("session_date"),
            "recency_days": age,
            "platforms": _route_platforms("session"),
        })
    return out


def sweep_projects(conn: sqlite3.Connection, since_days: int, today: date) -> list[dict]:
    from beacon.db.profile import get_projects

    out: list[dict] = []
    for p in get_projects(conn):
        age = _days_since(p["updated_at"], today)
        if age is None or age > since_days:
            continue
        outcomes = _safe_json_list(p["outcomes"])
        public = bool(p["is_public"] or p["repo_url"])
        out.append({
            "source": "project",
            "source_id": p["id"],
            "title": p["name"],
            "topic": f"How I built {p['name']}",
            "angle": p["description"] or "Tell the build story: problem, approach, outcome.",
            "tech": _safe_json_list(p["technologies"]),
            "evidence": [f"Outcome: {o}" for o in outcomes[:3]],
            "date": p["updated_at"],
            "recency_days": age,
            "platforms": _route_platforms("project", public=public),
        })
    return out


def sweep_presentations(conn: sqlite3.Connection, since_days: int, today: date) -> list[dict]:
    from beacon.db.speaker import get_presentations

    out: list[dict] = []
    for pres in get_presentations(conn):
        if pres["status"] != "delivered":
            continue
        age = _days_since(pres["date"], today)
        if age is None or age > since_days:
            continue
        has_rec = bool(pres["recording_url"])
        event = f" at {pres['event_name']}" if pres["event_name"] else ""
        out.append({
            "source": "presentation",
            "source_id": pres["id"],
            "title": pres["title"],
            "topic": f"Repurpose your talk: {pres['title']}",
            "angle": (
                f"You delivered this{event}. Spin it into a post + a thread"
                + (" + clip the recording" if has_rec else "") + "."
            ),
            "tech": _safe_json_list(pres["tags"]),
            "evidence": [e for e in [
                f"Delivered{event}" if event else "Delivered",
                f"Recording: {pres['recording_url']}" if has_rec else None,
                f"Slides: {pres['slides_url']}" if pres["slides_url"] else None,
            ] if e],
            "date": pres["date"],
            "recency_days": age,
            "platforms": _route_platforms("presentation", has_recording=has_rec),
        })
    return out


def sweep_media(conn: sqlite3.Connection, since_days: int, today: date) -> list[dict]:
    """High-signal consumed media → commentary/reaction post opportunities."""
    from beacon.media import list_media

    out: list[dict] = []
    for m in list_media(conn, since=None, limit=200):
        age = _days_since(m.get("date_consumed"), today)
        if age is None or age > since_days:
            continue
        rating = m.get("rating") or 0
        shareable = bool(m.get("team_shareable"))
        if rating < 4 and not shareable and not m.get("why_it_matters"):
            continue
        creator = f" by {m['creator']}" if m.get("creator") else ""
        evidence = [e for e in [
            f"Why it matters: {m['why_it_matters']}" if m.get("why_it_matters") else None,
            m.get("share_note"),
        ] if e]
        for q in _safe_json_list(m.get("key_quotes"))[:1]:
            evidence.append(f'Quote: "{q}"')
        out.append({
            "source": "media",
            "source_id": m.get("id"),
            "title": m.get("title"),
            "topic": f"React to: {m.get('title')}",
            "angle": (
                m.get("personal_reaction")
                or f"Share your take on this{creator} and what it means for your work."
            ),
            "tech": _safe_json_list(m.get("tags")),
            "evidence": evidence,
            "date": m.get("date_consumed"),
            "recency_days": age,
            "platforms": _route_platforms("media"),
        })
    return out


def internal_sweep(conn: sqlite3.Connection, since_days: int, today: date | None = None) -> list[dict]:
    """All internal opportunities from the last ``since_days`` days."""
    today = today or date.today()
    return (
        sweep_sessions(conn, since_days, today)
        + sweep_projects(conn, since_days, today)
        + sweep_presentations(conn, since_days, today)
        + sweep_media(conn, since_days, today)
    )


# --------------------------------------------------------------------------
# Dedupe against what's already planned / published
# --------------------------------------------------------------------------

def covered_token_sets(conn: sqlite3.Connection) -> list[set[str]]:
    """Token sets for every existing calendar entry + content draft."""
    from beacon.db.content import get_calendar_entries, get_content_drafts

    sets: list[set[str]] = []
    for e in get_calendar_entries(conn):
        toks = _norm_tokens(e["title"], e["topic"])
        if toks:
            sets.append(toks)
    for d in get_content_drafts(conn):
        toks = _norm_tokens(d["title"])
        if toks:
            sets.append(toks)
    return sets


def _is_covered(opp: dict, covered: list[set[str]]) -> bool:
    """True if a prior calendar/draft item substantially overlaps this topic."""
    toks = _norm_tokens(opp.get("topic"), opp.get("title"))
    if not toks:
        return False
    for prior in covered:
        overlap = toks & prior
        if overlap and len(overlap) / len(toks) >= 0.5:
            return True
    return False


# --------------------------------------------------------------------------
# External radar
# --------------------------------------------------------------------------

def extract_keywords(conn: sqlite3.Connection, today: date, since_days: int, limit: int = 8) -> list[str]:
    """Keywords for the trend search: recent work tech + advanced skills."""
    from beacon.db.profile import get_skills

    counts: dict[str, int] = {}

    def bump(name: str, weight: int = 1) -> None:
        key = name.strip()
        if key:
            counts[key] = counts.get(key, 0) + weight

    for opp in internal_sweep(conn, since_days, today):
        for t in opp.get("tech", []):
            bump(t, 2)

    for s in get_skills(conn):
        if s["proficiency"] in ("advanced", "expert"):
            bump(s["name"], 1)

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [name for name, _ in ranked[:limit]]


def _default_web_search(keywords: list[str], max_terms: int) -> list[dict]:
    """Real trend search via the LLM web-search tool. Returns parsed objects."""
    from beacon.llm.client import web_search
    from beacon.presence.templates import RADAR_TRENDING_PROMPT, RADAR_TRENDING_SYSTEM

    prompt = RADAR_TRENDING_PROMPT.format(keywords=", ".join(keywords), max_terms=max_terms)
    text = web_search(prompt, system=RADAR_TRENDING_SYSTEM)
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def external_radar(
    keywords: list[str],
    *,
    max_terms: int = 5,
    search_fn=None,
) -> list[dict]:
    """Trending discussion items for ``keywords``. Empty when no keywords."""
    if not keywords:
        return []
    fn = search_fn or _default_web_search
    items = fn(keywords, max_terms)
    cleaned: list[dict] = []
    for it in items or []:
        if not isinstance(it, dict) or not it.get("term"):
            continue
        cleaned.append({
            "term": it.get("term"),
            "summary": it.get("summary") or "",
            "hook": it.get("hook") or "",
            "keywords": [k.lower() for k in (it.get("keywords") or []) if k],
        })
    return cleaned[:max_terms]


def _trend_tokens(trend: dict) -> set[str]:
    return _norm_tokens(trend.get("term"), trend.get("summary")) | set(trend.get("keywords") or [])


def _best_evidence_for_trend(trend: dict, internal: list[dict]) -> dict | None:
    """Pick the internal opportunity that best grounds a trend (most tech overlap)."""
    ttoks = _trend_tokens(trend)
    best, best_overlap = None, 0
    for opp in internal:
        otoks = _norm_tokens(opp.get("topic"), opp.get("title")) | {t.lower() for t in opp.get("tech", [])}
        overlap = len(ttoks & otoks)
        if overlap > best_overlap:
            best, best_overlap = opp, overlap
    return best if best_overlap > 0 else None


# --------------------------------------------------------------------------
# Scoring + assembly
# --------------------------------------------------------------------------

def score_opportunity(opp: dict, since_days: int) -> float:
    """Score = recency + evidence + source weight + timeliness − covered penalty."""
    recency = opp.get("recency_days")
    if recency is None:
        recency_score = 0.0
    else:
        recency_score = max(0.0, (since_days - recency) / max(since_days, 1)) * 3.0

    evidence_score = min(len(opp.get("evidence", [])), 3) * 0.5
    source_score = _SOURCE_WEIGHT.get(opp.get("source"), 0.5)
    timely_score = 2.0 if opp.get("timely") else 0.0
    covered_penalty = 2.0 if opp.get("already_covered") else 0.0

    return round(recency_score + evidence_score + source_score + timely_score - covered_penalty, 2)


def build_radar(
    conn: sqlite3.Connection,
    *,
    since_days: int = 30,
    platform: str | None = None,
    limit: int = 15,
    web: bool = True,
    search_fn=None,
    today: date | None = None,
) -> dict:
    """Assemble the ranked content backlog payload."""
    today = today or date.today()
    warnings: list[str] = []

    internal = internal_sweep(conn, since_days, today)
    covered = covered_token_sets(conn)

    trending: list[dict] = []
    if web:
        try:
            keywords = extract_keywords(conn, today, since_days)
            trending = external_radar(
                keywords, search_fn=search_fn,
            )
        except RuntimeError as e:
            # Missing API key / SDK — degrade to internal-only, don't crash.
            warnings.append(f"web radar skipped: {e}")
        except Exception as e:  # network / parse — same graceful fallback
            warnings.append(f"web radar failed: {e}")

    # Mark internal opportunities that overlap a live trend as timely.
    trend_token_union: set[str] = set()
    for tr in trending:
        trend_token_union |= _trend_tokens(tr)
    for opp in internal:
        otoks = _norm_tokens(opp.get("topic"), opp.get("title")) | {t.lower() for t in opp.get("tech", [])}
        match = otoks & trend_token_union
        if match:
            opp["timely"] = True
            opp["trending_hook"] = next(
                (tr["term"] for tr in trending if _trend_tokens(tr) & otoks), None
            )

    # Turn each trend into its own opportunity, grounded in internal evidence.
    trend_opps: list[dict] = []
    for tr in trending:
        ev = _best_evidence_for_trend(tr, internal)
        evidence = [tr["summary"]] if tr["summary"] else []
        if ev:
            evidence.append(f"You can speak to this via: {ev['title']}")
        trend_opps.append({
            "source": "trend",
            "source_id": None,
            "title": tr["term"],
            "topic": tr["term"],
            "angle": tr["hook"] or tr["summary"],
            "tech": tr.get("keywords", []),
            "evidence": evidence,
            "date": today.isoformat(),
            "recency_days": 0,
            "platforms": _route_platforms("trend"),
            "timely": True,
            "trending_hook": tr["term"],
        })

    opportunities = internal + trend_opps

    # Dedupe flag + score.
    for opp in opportunities:
        opp["already_covered"] = _is_covered(opp, covered)
        opp["score"] = score_opportunity(opp, since_days)

    if platform:
        opportunities = [o for o in opportunities if platform in o["platforms"]]

    opportunities.sort(key=lambda o: o["score"], reverse=True)
    shipped_unposted = sum(
        1 for o in internal if not o["already_covered"]
    )

    payload = {
        "generated_at": format_iso(utcnow()),
        "since_days": since_days,
        "web_enabled": web,
        "trending": trending,
        "opportunities": opportunities[:limit],
        "total_opportunities": len(opportunities),
        "shipped_unposted": shipped_unposted,
        "warnings": warnings,
    }
    return payload


def seed_calendar(conn: sqlite3.Connection, opportunities: list[dict]) -> int:
    """Create one content_calendar entry per opportunity. Returns count created."""
    from beacon.db.content import add_calendar_entry

    count = 0
    for opp in opportunities:
        platform = opp["platforms"][0] if opp.get("platforms") else "linkedin"
        content_type = "post" if platform in ("linkedin", "twitter") else "post"
        notes = opp.get("angle") or ""
        if opp.get("trending_hook"):
            notes = f"[trending: {opp['trending_hook']}] {notes}"
        add_calendar_entry(
            conn,
            title=opp["topic"][:100],
            platform=platform,
            content_type=content_type,
            topic=(opp.get("title") or opp["topic"])[:100],
            notes=notes,
        )
        count += 1
    return count


# --------------------------------------------------------------------------
# Markdown rendering (for the vault brief)
# --------------------------------------------------------------------------

_SOURCE_LABEL = {
    "session": "🛠 Recent work",
    "project": "📦 Project",
    "presentation": "🎤 Talk",
    "media": "📺 Consumed",
    "trend": "🔥 Trending",
}


def render_radar_markdown(payload: dict) -> str:
    """Render the radar payload into a vault-ready markdown brief."""
    lines: list[str] = ["# Posting Strategy Radar\n"]
    lines.append(
        f"_Window: last {payload['since_days']} days · "
        f"{payload['total_opportunities']} opportunities · "
        f"{payload['shipped_unposted']} shipped-but-unposted_\n"
    )

    if payload.get("warnings"):
        for w in payload["warnings"]:
            lines.append(f"> ⚠️ {w}")
        lines.append("")

    if payload.get("trending"):
        lines.append("## What's being discussed now")
        for tr in payload["trending"]:
            lines.append(f"- **{tr['term']}** — {tr['summary']}")
            if tr.get("hook"):
                lines.append(f"  - Angle: {tr['hook']}")
        lines.append("")

    lines.append("## Ranked posting backlog")
    if not payload["opportunities"]:
        lines.append("- _Nothing surfaced. Log sessions/projects/media or widen `--since`._")
    for i, o in enumerate(payload["opportunities"], 1):
        label = _SOURCE_LABEL.get(o["source"], o["source"])
        platforms = ", ".join(o["platforms"])
        flags = []
        if o.get("timely"):
            flags.append("⏱ timely")
        if o.get("already_covered"):
            flags.append("✓ already planned")
        flag_str = f" ({', '.join(flags)})" if flags else ""
        lines.append(f"### {i}. {o['topic']}  · score {o['score']}{flag_str}")
        lines.append(f"- **Source:** {label}" + (f" — {o['title']}" if o["title"] != o["topic"] else ""))
        lines.append(f"- **Post to:** {platforms}")
        if o.get("angle"):
            lines.append(f"- **Angle:** {o['angle']}")
        for e in o.get("evidence", []):
            lines.append(f"- {e}")
        lines.append("")

    return "\n".join(lines)
