"""Profile-aware job fit ranker.

`compute_job_fit` answers "of the listings beacon knows about, which ones best
match my actual profile?" by composing five signals:

  * Skill overlap between the user's profile skills/work-tech/project-tech and
    the listing's extracted keywords.
  * Title trajectory — does the listing's seniority + role family align with
    the user's most-recent roles?
  * Domain overlap — does the listing's company industry overlap with the
    user's prior employers?
  * Outcome lift (opt-in) — empirical lift from skills that have produced
    positive application outcomes.
  * Existing `relevance_score` — preserved as a floor so the keyword/title/
    seniority/location signal is never lost.

No LLM calls in the ranking loop. Requirements extraction is deterministic
keyword matching against known tech terms and the user's own profile skills,
cached per listing in the `job_requirements` table.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from beacon.db.profile import (
    get_projects,
    get_skills,
    get_work_experiences,
)
from beacon.research.job_scoring import (
    CORE_KEYWORDS,
    EXEC_SIGNALS,
    JUNIOR_SIGNALS,
    SENIORITY_SCORES,
    SUPPORTING_KEYWORDS,
)


WEIGHTS = {
    "skill_overlap": 0.45,
    "title_trajectory": 0.20,
    "domain_overlap": 0.15,
    "outcome_lift": 0.10,
    "relevance_floor": 0.10,
}

ROLE_FAMILIES = {
    "engineer": {"engineer", "developer", "swe"},
    "scientist": {"scientist"},
    "analyst": {"analyst"},
    "manager": {"manager"},
    "architect": {"architect"},
}


@dataclass
class JobFit:
    fit_score: float
    reasons: list[str]
    missing: list[str]
    sub_scores: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "fit_score": self.fit_score,
            "reasons": self.reasons,
            "missing": self.missing,
            "sub_scores": self.sub_scores,
        }


# ---------------------------------------------------------------------------
# Requirements extraction + cache
# ---------------------------------------------------------------------------


def _heuristic_extract(description: str, profile_skills: set[str]) -> dict:
    """Deterministic keyword extraction — no LLM call.

    Pulls (a) known tech keywords from `job_scoring.CORE_KEYWORDS` /
    `SUPPORTING_KEYWORDS` and (b) any of the user's profile skill names that
    appear verbatim in the description.
    """
    if not description:
        return {"required_skills": [], "preferred_skills": [], "keywords": [], "seniority": None}

    text = description.lower()
    keywords: list[str] = []
    seen: set[str] = set()

    for term in CORE_KEYWORDS + SUPPORTING_KEYWORDS:
        if term in text and term not in seen:
            keywords.append(term)
            seen.add(term)

    for skill in profile_skills:
        skill_lc = skill.lower()
        if skill_lc and skill_lc in text and skill_lc not in seen:
            keywords.append(skill_lc)
            seen.add(skill_lc)

    seniority = None
    for signal in SENIORITY_SCORES:
        if signal in text:
            seniority = signal
            break

    return {
        "required_skills": keywords,
        "preferred_skills": [],
        "keywords": keywords,
        "seniority": seniority,
    }


def get_or_extract_requirements(
    conn: sqlite3.Connection,
    job: sqlite3.Row,
    *,
    profile_skills: set[str] | None = None,
    extract_fn=None,
) -> dict:
    """Return cached requirements, extracting + persisting on miss or stale.

    `extract_fn(description, profile_skills) -> dict` overrides the default
    heuristic extractor (e.g. for LLM-backed extraction or tests).
    """
    job_id = job["id"]
    conn.execute(
        """CREATE TABLE IF NOT EXISTS job_requirements (
            job_id INTEGER PRIMARY KEY REFERENCES job_listings(id) ON DELETE CASCADE,
            required_skills TEXT,
            preferred_skills TEXT,
            keywords TEXT,
            seniority TEXT,
            extracted_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    row = conn.execute(
        "SELECT required_skills, preferred_skills, keywords, seniority, extracted_at "
        "FROM job_requirements WHERE job_id = ?",
        (job_id,),
    ).fetchone()

    last_seen = job["date_last_seen"] if "date_last_seen" in job.keys() else None
    fresh = row is not None and (last_seen is None or row["extracted_at"] >= last_seen)
    if fresh:
        return {
            "required_skills": json.loads(row["required_skills"] or "[]"),
            "preferred_skills": json.loads(row["preferred_skills"] or "[]"),
            "keywords": json.loads(row["keywords"] or "[]"),
            "seniority": row["seniority"],
        }

    description = job["description_text"] or ""
    skills = profile_skills if profile_skills is not None else set()
    extractor = extract_fn or _heuristic_extract
    extracted = extractor(description, skills)

    conn.execute(
        """INSERT INTO job_requirements
            (job_id, required_skills, preferred_skills, keywords, seniority, extracted_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(job_id) DO UPDATE SET
             required_skills = excluded.required_skills,
             preferred_skills = excluded.preferred_skills,
             keywords = excluded.keywords,
             seniority = excluded.seniority,
             extracted_at = datetime('now')""",
        (
            job_id,
            json.dumps(extracted.get("required_skills", [])),
            json.dumps(extracted.get("preferred_skills", [])),
            json.dumps(extracted.get("keywords", [])),
            extracted.get("seniority"),
        ),
    )
    conn.commit()
    return extracted


# ---------------------------------------------------------------------------
# Profile snapshot
# ---------------------------------------------------------------------------


def load_profile_snapshot(conn: sqlite3.Connection) -> dict:
    """Pull the slices of profile data the ranker needs into a single dict."""
    skills_rows = get_skills(conn)
    work_rows = get_work_experiences(conn)
    project_rows = get_projects(conn)

    skill_names = {r["name"] for r in skills_rows}
    work_techs: set[str] = set()
    work_companies: list[str] = []
    work_titles: list[str] = []
    for r in work_rows:
        if r["technologies"]:
            try:
                for t in json.loads(r["technologies"]):
                    work_techs.add(t)
            except (json.JSONDecodeError, TypeError):
                pass
        if r["company"]:
            work_companies.append(r["company"])
        if r["title"]:
            work_titles.append(r["title"])

    project_techs: set[str] = set()
    for r in project_rows:
        if r["technologies"]:
            try:
                for t in json.loads(r["technologies"]):
                    project_techs.add(t)
            except (json.JSONDecodeError, TypeError):
                pass

    all_terms = {s.lower() for s in skill_names | work_techs | project_techs if s}

    return {
        "skill_names": skill_names,
        "work_techs": work_techs,
        "project_techs": project_techs,
        "all_terms_lc": all_terms,
        "work_companies": work_companies,
        "work_titles": work_titles,
        "counts": {
            "skills": len(skill_names),
            "work": len(work_rows),
            "projects": len(project_rows),
        },
    }


# ---------------------------------------------------------------------------
# Sub-scores
# ---------------------------------------------------------------------------


def _score_skill_overlap(profile: dict, requirements: dict) -> tuple[float, list[str], list[str]]:
    job_terms = {k.lower() for k in requirements.get("keywords", []) if k}
    if not job_terms:
        return 5.0, ["skill_overlap:no_keywords_extracted"], []

    matched = profile["all_terms_lc"] & job_terms
    missing = sorted(job_terms - profile["all_terms_lc"])

    score = 10.0 * len(matched) / max(1, len(job_terms))
    sample = ", ".join(sorted(matched)[:5])
    reason = f"skill_overlap:{len(matched)}/{len(job_terms)} ({sample})" if matched else "skill_overlap:0_matches"
    return round(score, 2), [reason], missing


def _detect_seniority(text: str) -> str | None:
    t = text.lower()
    for signal in JUNIOR_SIGNALS:
        if signal in t:
            return "junior"
    for signal in EXEC_SIGNALS:
        if signal in t:
            return "exec"
    for signal in SENIORITY_SCORES:
        if signal in t:
            return signal
    return None


def _detect_role_family(text: str) -> set[str]:
    t = text.lower()
    families: set[str] = set()
    for family, words in ROLE_FAMILIES.items():
        if any(w in t for w in words):
            families.add(family)
    return families


def _score_title_trajectory(profile: dict, job_title: str) -> tuple[float, list[str]]:
    if not profile["work_titles"]:
        return 5.0, ["title_trajectory:empty_profile"]

    recent = profile["work_titles"][:2]
    job_sen = _detect_seniority(job_title)
    job_fam = _detect_role_family(job_title)

    sen_match = False
    fam_match = False
    for t in recent:
        if job_sen and _detect_seniority(t) == job_sen:
            sen_match = True
        if job_fam and (job_fam & _detect_role_family(t)):
            fam_match = True

    reasons: list[str] = []
    if sen_match and fam_match:
        reasons.append(f"title_trajectory:{job_sen}+{','.join(sorted(job_fam))} matches recent role")
        return 10.0, reasons
    if sen_match:
        reasons.append(f"title_trajectory:seniority {job_sen} matches recent role")
        return 7.0, reasons
    if fam_match:
        reasons.append(f"title_trajectory:family {','.join(sorted(job_fam))} matches recent role")
        return 6.0, reasons
    reasons.append("title_trajectory:no_match")
    return 3.0, reasons


def _score_domain_overlap(profile: dict, job: sqlite3.Row) -> tuple[float, list[str]]:
    company_name = (job["company_name"] if "company_name" in job.keys() else None) or ""
    company_lc = company_name.lower()
    if not profile["work_companies"]:
        return 5.0, ["domain_overlap:empty_profile"]

    for wc in profile["work_companies"]:
        if wc and wc.lower() == company_lc:
            return 10.0, [f"domain_overlap:exact_employer ({company_name})"]

    # Soft signal: share a token (e.g. "data") between any work company and the
    # listing's company. Mild — capped at 5 so it can't dominate.
    job_tokens = {t for t in company_lc.split() if len(t) > 3}
    for wc in profile["work_companies"]:
        wc_tokens = {t for t in wc.lower().split() if len(t) > 3}
        if job_tokens & wc_tokens:
            return 5.0, [f"domain_overlap:partial ({company_name} ↔ {wc})"]

    return 3.0, ["domain_overlap:no_prior_employer_match"]


def _score_outcome_lift(
    conn: sqlite3.Connection,
    profile: dict,
    requirements: dict,
) -> tuple[float, list[str]]:
    """Skills the user has applied with that produced positive outcomes
    (anything past `no_response` / `rejection_*`) get a bonus.
    """
    POSITIVE = ("phone_screen", "technical", "onsite", "offer", "accepted")
    rows = conn.execute(
        "SELECT outcome FROM application_outcomes WHERE outcome IN ({})".format(
            ",".join("?" * len(POSITIVE))
        ),
        POSITIVE,
    ).fetchall()
    positive_count = len(rows)
    if positive_count == 0:
        return 5.0, ["outcome_lift:no_positive_outcomes_yet"]

    job_terms = {k.lower() for k in requirements.get("keywords", []) if k}
    matched = profile["all_terms_lc"] & job_terms
    if not matched:
        return 4.0, ["outcome_lift:no_matched_skills"]

    # Scale by positive outcome count (saturates quickly).
    lift = min(10.0, 5.0 + positive_count)
    return round(lift, 2), [f"outcome_lift:{positive_count} positive outcomes weighted matched skills"]


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def compute_job_fit(
    conn: sqlite3.Connection,
    job: sqlite3.Row,
    *,
    profile: dict | None = None,
    with_outcomes: bool = False,
    extract_fn=None,
) -> JobFit:
    """Score how well a listing matches the user's actual profile.

    Args:
        conn: Beacon DB connection.
        job: Row from `job_listings` JOIN `companies` (must include
            `company_name` + `description_text` + `date_last_seen`).
        profile: Pre-loaded profile snapshot (caller can reuse across many
            jobs in one ranking pass). When omitted, loaded from `conn`.
        with_outcomes: When True, layer outcome-weighted lift into the score.
        extract_fn: Optional override for requirements extraction (e.g.
            inject `beacon.materials.resume.extract_requirements` for the
            LLM-backed path, or a stub in tests).

    Returns:
        `JobFit` — see the dataclass.
    """
    snapshot = profile or load_profile_snapshot(conn)
    requirements = get_or_extract_requirements(
        conn, job, profile_skills=snapshot["skill_names"], extract_fn=extract_fn,
    )

    skill_score, skill_reasons, missing = _score_skill_overlap(snapshot, requirements)
    title_score, title_reasons = _score_title_trajectory(snapshot, job["title"] or "")
    domain_score, domain_reasons = _score_domain_overlap(snapshot, job)

    if with_outcomes:
        outcome_score, outcome_reasons = _score_outcome_lift(conn, snapshot, requirements)
    else:
        outcome_score, outcome_reasons = 5.0, []

    relevance = float(job["relevance_score"] or 0.0)

    composite = (
        skill_score * WEIGHTS["skill_overlap"]
        + title_score * WEIGHTS["title_trajectory"]
        + domain_score * WEIGHTS["domain_overlap"]
        + outcome_score * WEIGHTS["outcome_lift"]
        + relevance * WEIGHTS["relevance_floor"]
    )

    reasons = skill_reasons + title_reasons + domain_reasons + outcome_reasons
    if relevance > 0:
        reasons.append(f"relevance_floor:{relevance:.1f}")

    return JobFit(
        fit_score=round(min(composite, 10.0), 2),
        reasons=reasons,
        missing=missing[:10],
        sub_scores={
            "skill_overlap": skill_score,
            "title_trajectory": title_score,
            "domain_overlap": domain_score,
            "outcome_lift": outcome_score,
            "relevance_floor": relevance,
        },
    )
