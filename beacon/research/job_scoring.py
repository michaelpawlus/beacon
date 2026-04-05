"""Job relevance scoring engine for Beacon Phase 2.

Scores how relevant a job listing is to data/analytics/ML roles.
Score range: 0-10. Sub-scores weighted:
  - Title match (40%): Does the title match target roles?
  - Keyword match (30%): Do description keywords signal relevance?
  - Location (15%): Is the location preferred?
  - Seniority (15%): Is the seniority level right?
"""


# --- Weight configuration ---
WEIGHTS = {
    "title": 0.40,
    "keywords": 0.30,
    "location": 0.15,
    "seniority": 0.15,
}

# --- Target roles (title matching) ---
TARGET_ROLES = [
    "data engineer",
    "data scientist",
    "data analyst",
    "analytics engineer",
    "machine learning engineer",
    "ml engineer",
    "applied scientist",
    "research scientist",
    "research engineer",
    "ai engineer",
    "data platform",
    "data infrastructure",
    "business intelligence",
    "bi engineer",
    "bi developer",
    "decision scientist",
    "quantitative analyst",
    "statistical",
]

# --- Keyword signals ---
CORE_KEYWORDS = [
    "python", "sql", "dbt", "spark", "airflow", "snowflake", "bigquery",
    "databricks", "redshift", "kafka", "pandas", "scikit", "tensorflow",
    "pytorch", "machine learning", "deep learning", "nlp", "llm",
    "data pipeline", "etl", "elt", "data warehouse", "data lake",
    "statistics", "a/b test", "experimentation",
    "data model", "feature engineering", "mlops",
]

SUPPORTING_KEYWORDS = [
    "analytics", "tableau", "looker", "power bi", "metrics", "dashboard",
]

NEGATIVE_KEYWORDS = [
    "sales", "account executive", "customer success", "marketing manager",
    "recruiter", "legal counsel", "office manager", "receptionist",
    "graphic design", "content writer", "social media manager",
    "finance manager", "accountant", "payroll",
]

# --- Location preferences ---
REMOTE_LOCATIONS = ["remote", "anywhere", "united states", "usa"]

TECH_HUB_LOCATIONS = [
    "san francisco", "new york", "los angeles", "seattle",
    "austin", "denver", "chicago", "boston", "portland",
]

# --- Seniority targeting ---
SENIORITY_SCORES = {
    "senior": 10.0,
    "ii": 10.0,
    "iii": 10.0,
    "mid": 10.0,
    "staff": 7.0,
    "lead": 5.0,
    "principal": 4.0,
}
JUNIOR_SIGNALS = ["intern", "internship", "entry level", "entry-level", "new grad", "junior", "associate"]
EXEC_SIGNALS = ["vp", "vice president", "director", "chief", "head of", "c-suite", "cto", "cdo"]


def _score_title(title: str) -> tuple[float, list[str]]:
    """Score based on how well the title matches target roles. Returns (score, reasons)."""
    title_lower = title.lower()
    reasons = []

    # Direct role match
    for role in TARGET_ROLES:
        if role in title_lower:
            reasons.append(f"title_match:{role}")
            return 10.0, reasons

    # Partial matches
    data_words = ["data", "analytics", "ml", "ai", "machine learning", "intelligence"]
    eng_words = ["engineer", "scientist", "analyst", "developer", "architect"]

    has_data = any(w in title_lower for w in data_words)
    has_eng = any(w in title_lower for w in eng_words)

    if has_data and has_eng:
        reasons.append("partial_title_match:data+engineering")
        return 8.0, reasons
    elif has_data:
        reasons.append("partial_title_match:data_related")
        return 5.0, reasons
    elif has_eng:
        reasons.append("partial_title_match:engineering_role")
        return 3.0, reasons

    return 0.0, reasons


def _score_keywords(description: str) -> tuple[float, list[str]]:
    """Score based on keyword presence in job description. Returns (score, reasons)."""
    if not description:
        return 5.0, ["no_description"]  # neutral when unknown

    desc_lower = description.lower()
    reasons = []

    core_count = sum(1 for kw in CORE_KEYWORDS if kw in desc_lower)
    supporting_count = sum(1 for kw in SUPPORTING_KEYWORDS if kw in desc_lower)
    effective_count = core_count * 1.5 + supporting_count * 1.0

    negative_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in desc_lower)

    if core_count > 0 or supporting_count > 0:
        reasons.append(f"positive_keywords:{core_count}core+{supporting_count}supporting")
    if negative_count > 0:
        reasons.append(f"negative_keywords:{negative_count}")

    # Scale: 0 keywords = 2, ~8 effective = 10, with penalty for negatives
    score = min(2.0 + effective_count * 1.0, 10.0) - negative_count * 2.0
    return max(score, 0.0), reasons


def _score_location(location: str, home_location: str = "") -> tuple[float, list[str]]:
    """Score based on location preference. Returns (score, reasons)."""
    if not location:
        return 5.0, ["no_location"]  # neutral when unknown

    loc_lower = location.lower()
    reasons = []

    for pref in REMOTE_LOCATIONS:
        if pref in loc_lower:
            reasons.append(f"preferred_location:{pref}")
            return 10.0, reasons

    if home_location and home_location.lower() in loc_lower:
        reasons.append(f"home_location:{home_location}")
        return 8.0, reasons

    for hub in TECH_HUB_LOCATIONS:
        if hub in loc_lower:
            reasons.append(f"tech_hub:{hub}")
            return 6.0, reasons

    reasons.append("non_preferred_location")
    return 3.0, reasons


def _score_seniority(title: str) -> tuple[float, list[str]]:
    """Score based on seniority match. Returns (score, reasons)."""
    title_lower = title.lower()
    reasons = []

    for signal in JUNIOR_SIGNALS:
        if signal in title_lower:
            reasons.append(f"junior_role:{signal}")
            return 2.0, reasons

    for signal in EXEC_SIGNALS:
        if signal in title_lower:
            reasons.append(f"exec_role:{signal}")
            return 4.0, reasons

    for signal, score in SENIORITY_SCORES.items():
        if signal in title_lower:
            reasons.append(f"target_seniority:{signal}")
            return score, reasons

    # No seniority signal — neutral
    reasons.append("no_seniority_signal")
    return 6.0, reasons


def compute_job_relevance(job_data: dict, *, config=None, company_score: float | None = None) -> dict:
    """Compute a relevance score for a job listing.

    Args:
        job_data: Dict with keys: title, url, location, department,
                  description_text, date_posted
        config: Optional BeaconConfig for home_location scoring
        company_score: Optional company AI-first score (0-10) for tie-breaking

    Returns:
        Dict with 'score' (0-10), 'reasons' (list of strings),
        and individual sub-scores.
    """
    title = job_data.get("title", "")
    description = job_data.get("description_text", "")
    location = job_data.get("location", "")

    home_location = config.home_location if config else ""

    title_score, title_reasons = _score_title(title)
    kw_score, kw_reasons = _score_keywords(description)
    loc_score, loc_reasons = _score_location(location, home_location=home_location)
    seniority_score, seniority_reasons = _score_seniority(title)

    composite = (
        title_score * WEIGHTS["title"]
        + kw_score * WEIGHTS["keywords"]
        + loc_score * WEIGHTS["location"]
        + seniority_score * WEIGHTS["seniority"]
    )

    all_reasons = title_reasons + kw_reasons + loc_reasons + seniority_reasons

    if company_score is not None:
        multiplier = 0.9 + company_score * 0.02
        composite = composite * multiplier
        all_reasons.append(f"company_boost:{company_score:.1f}x{multiplier:.2f}")

    # Cap at 10
    composite = min(round(composite, 2), 10.0)

    return {
        "score": composite,
        "reasons": all_reasons,
        "title_score": title_score,
        "keyword_score": kw_score,
        "location_score": loc_score,
        "seniority_score": seniority_score,
    }
