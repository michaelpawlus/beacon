"""Extract structured highlights from job description text.

Parses salary/compensation, AI tools, and key requirements
so critical info is available even without reading the full description.
"""

import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_ENTITY_RE = re.compile(r"&\w+;")

_ENTITY_MAP = {
    "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&mdash;": "-", "&ndash;": "-", "&emdash;": "-",
}


def _clean_text(text: str) -> str:
    """Strip HTML tags and decode common entities for extraction."""
    cleaned = _HTML_TAG_RE.sub(" ", text)
    for entity, replacement in _ENTITY_MAP.items():
        cleaned = cleaned.replace(entity, replacement)
    cleaned = _HTML_ENTITY_RE.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()

# --- Salary patterns ---
_SALARY_PATTERN = re.compile(
    r"\$\s*([\d,]+(?:\.\d{2})?)\s*(?:[-–—to]+)\s*\$\s*([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE,
)
_SALARY_SINGLE = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)", re.IGNORECASE)

# --- AI tools list ---
AI_TOOLS = [
    "Claude", "ChatGPT", "GPT-4", "GPT-3", "OpenAI", "Anthropic",
    "Copilot", "GitHub Copilot", "Cursor", "Cody",
    "LLM", "LLMs", "large language model",
    "RAG", "retrieval augmented generation", "retrieval-augmented generation",
    "LangChain", "LlamaIndex", "Semantic Kernel",
    "Hugging Face", "HuggingFace",
    "Stable Diffusion", "Midjourney", "DALL-E",
    "vector database", "vector store", "embeddings",
    "fine-tuning", "fine tuning", "RLHF",
    "prompt engineering", "prompt design",
    "agent", "agentic", "AI agent",
    "MLflow", "Kubeflow", "SageMaker", "Vertex AI",
    "TensorFlow", "PyTorch", "JAX",
    "Gemini", "Mistral", "Llama", "Cohere",
]

# Compile patterns for case-insensitive matching, longest first to avoid partial matches
_AI_TOOL_PATTERNS = [
    (tool, re.compile(r"\b" + re.escape(tool) + r"\b", re.IGNORECASE))
    for tool in sorted(AI_TOOLS, key=len, reverse=True)
]

# --- Experience years pattern ---
_EXPERIENCE_PATTERN = re.compile(
    r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:\w+\s+)*?experience",
    re.IGNORECASE,
)


def _parse_salary(amount_str: str) -> int | None:
    """Parse a salary string like '149,000' into an integer."""
    try:
        cleaned = amount_str.replace(",", "").split(".")[0]
        value = int(cleaned)
        return value if value >= 10000 else None
    except (ValueError, IndexError):
        return None


def extract_highlights(description: str) -> dict:
    """Extract structured highlights from a job description.

    Args:
        description: Plain text job description.

    Returns:
        Dict with keys:
            salary_min, salary_max, salary_raw (int|None, int|None, str|None)
            ai_tools (list[str])
            experience_years (str|None) — e.g. "5+"
            key_requirements (list[str]) — notable tech/domain requirements
    """
    if not description:
        return {
            "salary_min": None,
            "salary_max": None,
            "salary_raw": None,
            "ai_tools": [],
            "experience_years": None,
            "key_requirements": [],
        }

    # Strip HTML tags/entities so regexes work on clean text
    description = _clean_text(description)

    highlights: dict = {}

    # --- Salary extraction ---
    range_match = _SALARY_PATTERN.search(description)
    if range_match:
        sal_min = _parse_salary(range_match.group(1))
        sal_max = _parse_salary(range_match.group(2))
        if sal_min and sal_max:
            highlights["salary_min"] = min(sal_min, sal_max)
            highlights["salary_max"] = max(sal_min, sal_max)
            highlights["salary_raw"] = range_match.group(0).strip()
        else:
            highlights["salary_min"] = None
            highlights["salary_max"] = None
            highlights["salary_raw"] = None
    else:
        highlights["salary_min"] = None
        highlights["salary_max"] = None
        highlights["salary_raw"] = None

    # --- AI tools extraction ---
    found_tools: list[str] = []
    desc_checked = description
    for canonical_name, pattern in _AI_TOOL_PATTERNS:
        if pattern.search(desc_checked):
            # Normalize similar entries
            normalized = canonical_name
            if normalized.upper() in ("LLMS",):
                normalized = "LLMs"
            elif normalized.upper() == "LLM":
                normalized = "LLMs"
            elif normalized.lower() == "large language model":
                normalized = "LLMs"
            if normalized not in found_tools:
                found_tools.append(normalized)
    highlights["ai_tools"] = found_tools

    # --- Experience years ---
    exp_matches = _EXPERIENCE_PATTERN.findall(description)
    if exp_matches:
        max_years = max(int(y) for y in exp_matches)
        highlights["experience_years"] = f"{max_years}+"
    else:
        highlights["experience_years"] = None

    # --- Key requirements (tech stack mentions) ---
    key_tech = [
        "Python", "SQL", "Spark", "Airflow", "Snowflake", "BigQuery",
        "Databricks", "dbt", "Kafka", "Flink", "Kubernetes", "Docker",
        "AWS", "GCP", "Azure", "Terraform",
        "Tableau", "Looker", "Power BI",
        "scikit-learn", "pandas", "NumPy",
    ]
    found_reqs = []
    desc_lower = description.lower()
    for tech in key_tech:
        if tech.lower() in desc_lower:
            if tech not in found_reqs:
                found_reqs.append(tech)
    highlights["key_requirements"] = found_reqs

    return highlights
