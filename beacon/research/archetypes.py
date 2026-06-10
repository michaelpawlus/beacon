"""Role archetype classification for job listings (issue #29).

Beacon already scores *how relevant* and *how well a listing fits the user's
profile*. The archetype is the missing axis: *what kind of role is this?* —
which then tells downstream commands (resume / cover-letter tailoring,
interview prep, filtering) **how** to frame the candidate.

Classification is deterministic: title-pattern + keyword heuristics over the
title and description. No LLM call. Definitions live in-module (like the
scoring constants in ``job_scoring.py``) so the classifier is fully testable
without file IO; ``classify_job`` accepts an ``archetypes=`` override for
callers that want a custom taxonomy.

Scoring per archetype::

    score = title_hits * TITLE_WEIGHT + min(keyword_hits, KEYWORD_CAP) * KEYWORD_WEIGHT

The highest-scoring archetype wins (ties broken by definition order). A listing
with no signal at all classifies as ``None`` (unclassified) with confidence 0.
"""

from __future__ import annotations

from dataclasses import dataclass

TITLE_WEIGHT = 3.0
KEYWORD_WEIGHT = 1.0
# Keyword hits past this point don't add score — keeps a keyword-stuffed
# description from outranking a clean title match.
KEYWORD_CAP = 4


@dataclass(frozen=True)
class Archetype:
    """A role archetype definition.

    ``title_patterns`` are substrings matched against the (lowercased) job
    title — the strongest signal. ``keywords`` are substrings matched against
    the description. ``framing`` is the one-line positioning guidance surfaced
    to downstream commands.
    """

    key: str
    label: str
    title_patterns: tuple[str, ...]
    keywords: tuple[str, ...]
    framing: str


# Order matters: it's the tie-breaker when two archetypes score equally, so the
# more specialized archetypes come first.
ARCHETYPES: tuple[Archetype, ...] = (
    Archetype(
        key="agentic",
        label="Agentic / Applied AI",
        title_patterns=(
            "agent engineer", "ai agent", "agentic", "applied ai",
            "applied scientist", "ai application",
        ),
        keywords=(
            "agent", "multi-agent", "agentic", "orchestrat", "human-in-the-loop",
            "hitl", "tool use", "tool-use", "langchain", "langgraph", "autonomous",
            "copilot", "assistant", "workflow automation",
        ),
        framing="Lead with multi-agent orchestration, human-in-the-loop design, and tool-use systems you've shipped.",
    ),
    Archetype(
        key="ai_engineer_llmops",
        label="AI Engineer / LLMOps",
        title_patterns=(
            "llmops", "mlops", "ml platform", "ai platform", "ml infrastructure",
            "ai engineer", "llm engineer", "inference engineer", "ml ops",
        ),
        keywords=(
            "evals", "evaluation", "observability", "fine-tun", "rag",
            "vector", "llm", "inference", "prompt", "model serving", "mlflow",
            "production", "latency", "gpu", "deployment pipeline", "monitoring",
        ),
        framing="Foreground eval/observability rigor and production-hardening of LLM/ML systems.",
    ),
    Archetype(
        key="data_platform",
        label="Data Platform / Analytics Engineer",
        title_patterns=(
            "data engineer", "analytics engineer", "data platform",
            "data infrastructure", "bi engineer", "bi developer",
            "data warehouse", "etl developer",
        ),
        keywords=(
            "dbt", "airflow", "spark", "snowflake", "bigquery", "redshift",
            "databricks", "etl", "elt", "data pipeline", "data warehouse",
            "data lake", "kafka", "ingestion", "tableau", "looker", "power bi",
        ),
        framing="Center pipeline reliability, warehouse modeling, and BI enablement.",
    ),
    Archetype(
        key="ml_ds",
        label="ML / Data Science",
        title_patterns=(
            "data scientist", "machine learning engineer", "ml engineer",
            "research scientist", "research engineer", "decision scientist",
            "quantitative", "statistician", "modeler",
        ),
        keywords=(
            "modeling", "experimentation", "a/b test", "statistics",
            "statistical", "regression", "forecasting", "scikit", "pytorch",
            "tensorflow", "feature engineering", "hypothesis", "causal",
            "deep learning", "nlp",
        ),
        framing="Center modeling depth, experimentation discipline, and statistical rigor.",
    ),
    Archetype(
        key="solutions_fde",
        label="Solutions Architect / FDE",
        title_patterns=(
            "solutions architect", "solutions engineer", "forward deployed",
            "forward-deployed", "fde", "sales engineer", "implementation",
            "customer engineer", "delivery engineer",
        ),
        keywords=(
            "client", "customer", "stakeholder", "integration", "deployment",
            "onboarding", "presales", "pre-sales", "demo", "proof of concept",
            "poc", "delivery", "consult",
        ),
        framing="Lead with client-facing delivery speed, integrations, and customer outcomes.",
    ),
    Archetype(
        key="eng_leadership",
        label="Engineering Leadership",
        title_patterns=(
            "engineering manager", "engineering director", "director of engineering",
            "head of engineering", "head of data", "head of ai", "vp engineering",
            "vp of engineering", "director of data",
        ),
        keywords=(
            "hiring", "roadmap", "mentor", "people management", "org design",
            "direct reports", "team of", "cross-functional", "budget",
            "performance review", "headcount",
        ),
        framing="Highlight hiring, roadmap ownership, and org design.",
    ),
    Archetype(
        key="product_pm",
        label="Product / PM (technical)",
        title_patterns=(
            "product manager", "product owner", "technical product",
            "program manager", "group product",
        ),
        keywords=(
            "roadmap", "discovery", "prioritization", "metrics", "kpi",
            "user research", "trade-off", "tradeoff", "requirements", "backlog",
            "go-to-market", "stakeholder",
        ),
        framing="Frame product discovery, metrics-driven prioritization, and trade-off decisions.",
    ),
)

_BY_KEY = {a.key: a for a in ARCHETYPES}


def list_archetypes() -> list[dict]:
    """Return the taxonomy as plain dicts (for ``--json`` / ``--list``)."""
    return [
        {"key": a.key, "label": a.label, "framing": a.framing}
        for a in ARCHETYPES
    ]


def archetype_label(key: str | None) -> str | None:
    """Human-readable label for an archetype key (``None`` passes through)."""
    if not key:
        return None
    a = _BY_KEY.get(key)
    return a.label if a else key


def framing_for(key: str | None) -> str | None:
    """One-line positioning guidance for an archetype key."""
    if not key:
        return None
    a = _BY_KEY.get(key)
    return a.framing if a else None


def is_valid_archetype(key: str) -> bool:
    """True if ``key`` is a known archetype."""
    return key in _BY_KEY


def _score_archetype(arch: Archetype, title_lc: str, desc_lc: str) -> tuple[float, int, list[str]]:
    """Return (score, title_hits, reasons) for one archetype."""
    title_hits = 0
    reasons: list[str] = []
    for pat in arch.title_patterns:
        if pat in title_lc:
            title_hits += 1
            reasons.append(f"title:{pat}")

    kw_hits = 0
    for kw in arch.keywords:
        if kw in desc_lc:
            kw_hits += 1
            if kw_hits <= KEYWORD_CAP:
                reasons.append(f"keyword:{kw}")

    score = title_hits * TITLE_WEIGHT + min(kw_hits, KEYWORD_CAP) * KEYWORD_WEIGHT
    return score, title_hits, reasons


def classify_job(
    title: str | None,
    description: str | None = "",
    *,
    archetypes: tuple[Archetype, ...] | None = None,
) -> dict:
    """Classify a listing into a role archetype.

    Returns a dict::

        {
          "archetype": "data_platform" | None,
          "label": "Data Platform / Analytics Engineer" | None,
          "confidence": 0.0-1.0,
          "framing": "Center pipeline reliability...",
          "scores": {"data_platform": 7.0, ...},   # non-zero archetypes
          "reasons": ["title:data engineer", "keyword:dbt", ...],
        }

    ``confidence`` blends absolute signal strength with how far the winner
    separates from the runner-up. A keyword-only match (no title hit) is capped
    at 0.5 since the title is the load-bearing signal.
    """
    defs = archetypes or ARCHETYPES
    title_lc = (title or "").lower()
    desc_lc = (description or "").lower()

    scored: list[tuple[float, int, Archetype, list[str]]] = []
    for arch in defs:
        score, title_hits, reasons = _score_archetype(arch, title_lc, desc_lc)
        scored.append((score, title_hits, arch, reasons))

    # Stable sort: highest score first; definition order breaks ties because
    # Python's sort is stable and ``defs`` is already in priority order.
    ranked = sorted(scored, key=lambda s: s[0], reverse=True)
    top_score, top_title_hits, top_arch, top_reasons = ranked[0]

    if top_score <= 0:
        return {
            "archetype": None,
            "label": None,
            "confidence": 0.0,
            "framing": None,
            "scores": {},
            "reasons": [],
        }

    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    strength = min(1.0, top_score / 6.0)
    separation = (top_score - second_score) / top_score if top_score else 0.0
    confidence = 0.6 * strength + 0.4 * separation
    if top_title_hits == 0:
        confidence = min(confidence, 0.5)
    confidence = round(min(1.0, confidence), 2)

    scores = {arch.key: score for score, _, arch, _ in scored if score > 0}

    return {
        "archetype": top_arch.key,
        "label": top_arch.label,
        "confidence": confidence,
        "framing": top_arch.framing,
        "scores": scores,
        "reasons": top_reasons,
    }


def positioning_block(key: str | None) -> str:
    """Prompt-ready positioning section for an archetype key ('' when unknown)."""
    framing = framing_for(key)
    if not framing:
        return ""
    return (
        f"Role Positioning ({archetype_label(key)}):\n"
        f"{framing}\n"
        "Frame the summary line and choose proof points to match this positioning."
    )


def positioning_for_job(job_row, description: str | None = None) -> str:
    """Prompt-ready positioning block for a job row.

    Prefers the archetype stored on the row; rows that predate the classifier
    fall back to on-the-fly classification (deterministic, nothing persisted).
    Returns '' when the role can't be classified.
    """
    keys = job_row.keys() if hasattr(job_row, "keys") else []
    key = job_row["archetype"] if "archetype" in keys else None
    if not key:
        key = classify_job(job_row["title"], description or "")["archetype"]
    return positioning_block(key)
