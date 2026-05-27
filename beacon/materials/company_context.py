"""Company context builder — shared by cover_letter and interview_brief.

Pulls Phase 1 research data (companies row + leadership_signals + ai_signals +
tools_adopted) and returns either a structured dict for further composition or
a flattened string for LLM prompts.
"""

from __future__ import annotations

import sqlite3


def build_company_context_dict(conn: sqlite3.Connection, company_id: int) -> dict:
    """Return structured company context for downstream composition.

    Shape:
        {
            "company": {dict from companies row} | None,
            "leadership_signals": [{...}, ...],   # up to 5, by impact_level
            "ai_signals": [{...}, ...],           # up to 5, by signal_strength DESC
            "tools": [{...}, ...],
        }
    """
    company_row = conn.execute(
        "SELECT * FROM companies WHERE id = ?", (company_id,)
    ).fetchone()
    company = dict(company_row) if company_row else None

    leadership_rows = conn.execute(
        "SELECT * FROM leadership_signals WHERE company_id = ? ORDER BY impact_level",
        (company_id,),
    ).fetchall()
    leadership_signals = [dict(r) for r in leadership_rows[:5]]

    signal_rows = conn.execute(
        "SELECT * FROM ai_signals WHERE company_id = ? ORDER BY signal_strength DESC",
        (company_id,),
    ).fetchall()
    ai_signals = [dict(r) for r in signal_rows[:5]]

    tool_rows = conn.execute(
        "SELECT * FROM tools_adopted WHERE company_id = ?", (company_id,)
    ).fetchall()
    tools = [dict(r) for r in tool_rows]

    return {
        "company": company,
        "leadership_signals": leadership_signals,
        "ai_signals": ai_signals,
        "tools": tools,
    }


def build_company_context(conn: sqlite3.Connection, company_id: int) -> str:
    """Flatten the structured context into the LLM-prompt string format.

    Backwards-compatible with the previous `cover_letter.build_company_context`
    output — tests assert specific substrings, so the layout is preserved.
    """
    ctx = build_company_context_dict(conn, company_id)
    company = ctx["company"]
    parts: list[str] = []

    if company:
        parts.append(f"Company: {company['name']}")
        if company["description"]:
            parts.append(f"Description: {company['description']}")
        parts.append(
            f"AI-First Score: {company['ai_first_score']:.1f}/10 (Tier {company['tier']})"
        )
        if company["remote_policy"]:
            parts.append(f"Remote Policy: {company['remote_policy']}")

    if ctx["leadership_signals"]:
        parts.append("\nLeadership Signals:")
        for ls in ctx["leadership_signals"]:
            parts.append(
                f"- {ls['leader_name']} ({ls['leader_title']}): {ls['content'][:200]}"
            )

    if ctx["ai_signals"]:
        parts.append("\nAI Culture Signals:")
        for s in ctx["ai_signals"]:
            parts.append(f"- [{s['signal_type']}] {s['title']}")

    if ctx["tools"]:
        parts.append("\nAI Tools Adopted:")
        for t in ctx["tools"]:
            parts.append(f"- {t['tool_name']} ({t['adoption_level']})")

    return "\n".join(parts)
